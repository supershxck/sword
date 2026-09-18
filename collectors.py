"""Data collectors for Glamdring — pure functions, no UI dependencies."""

from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

DEFAULT_PROJECTS_ROOT = Path.home() / "Projects"
DEFAULT_PIPELINE_DIR = Path(__file__).resolve().parent / "pipeline"
MAX_MD_FILES = 10
MAX_DOCKER_ROWS = 12
MAX_NEGLECT_ITEMS = 10
MAX_FORGE_CARDS = 8
NEGLECT_DAYS_THRESHOLD = 14
SPRINT_SLOT_MAX = 10

SKIP_DIRS = {
    ".git", ".hg", ".svn",
    "node_modules", "bower_components",
    ".venv", "venv", "env",
    "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache",
    "build", "dist", ".next", ".nuxt", "target", "out",
    "site-packages", ".tox", ".nox",
    ".idea", ".vscode",
}

SKIP_REPO_NAMES = {".git", "node_modules", "venv", ".venv"}

STAGE_ORDER = ("01_scoping", "02_building", "03_review")
STAGE_LABELS = {
    "00_backlog": "Backlog",
    "01_scoping": "Scoping",
    "02_building": "Building",
    "03_review": "Review",
    "04_shipped": "Shipped",
}


def get_system_stats() -> dict[str, Any]:
    cpu_percent = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "cpu_percent": round(cpu_percent, 1),
        "mem_used_gb": round(mem.used / (1024**3), 1),
        "mem_total_gb": round(mem.total / (1024**3), 1),
        "mem_percent": round(mem.percent, 1),
        "disk_used_gb": round(disk.used / (1024**3), 1),
        "disk_total_gb": round(disk.total / (1024**3), 1),
        "disk_percent": round(disk.percent, 1),
        "gpu_info": _get_gpu_info(),
        "timestamp": datetime.now().strftime("%H:%M:%S"),
    }


def _get_gpu_info() -> str:
    try:
        if psutil.MACOS:
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                gpus: list[str] = []
                for line in result.stdout.splitlines():
                    if "Chipset Model:" in line:
                        name = line.split(":", 1)[1].strip()
                        if name:
                            gpus.append(name)
                if gpus:
                    return ", ".join(gpus[:2])
            return "Apple GPU"
        if psutil.LINUX:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                first = result.stdout.strip().split("\n")[0]
                parts = [p.strip() for p in first.split(",")]
                if len(parts) >= 2:
                    return f"{parts[0]} ({parts[1]}%)"
                return parts[0]
            return "No NVIDIA GPU"
        return "GPU N/A"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "GPU unavailable"


def get_docker_containers() -> list[dict[str, str]]:
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True, text=True, timeout=4,
        )
        if result.returncode != 0:
            return []
        lines = result.stdout.strip().splitlines()
        if len(lines) <= 1:
            return []
        containers: list[dict[str, str]] = []
        for line in lines[1:][:MAX_DOCKER_ROWS]:
            parts = [p.strip() for p in line.split("\t")]
            if len(parts) >= 4:
                containers.append({
                    "id": parts[0][:12],
                    "name": parts[1],
                    "image": parts[2],
                    "status": parts[3],
                    "ports": parts[4] if len(parts) > 4 else "",
                })
        return containers
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def get_recent_markdown_files(watch_dir: Path, limit: int = MAX_MD_FILES) -> list[dict[str, Any]]:
    if not watch_dir.exists() or not watch_dir.is_dir():
        return []
    md_files: list[tuple[datetime, Path]] = []
    try:
        for root, dirs, files in os.walk(watch_dir, topdown=True):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            root_path = Path(root)
            for name in files:
                if name.lower().endswith(".md"):
                    try:
                        full_path = root_path / name
                        mtime = datetime.fromtimestamp(full_path.stat().st_mtime)
                        md_files.append((mtime, full_path))
                    except (OSError, PermissionError):
                        continue
    except OSError:
        return []
    md_files.sort(reverse=True, key=lambda x: x[0])
    results: list[dict[str, Any]] = []
    now = datetime.now()
    for mtime, path in md_files[:limit]:
        try:
            rel_path = path.relative_to(watch_dir)
        except ValueError:
            rel_path = path
        results.append({
            "modified": mtime.strftime("%m-%d %H:%M"),
            "name": path.name,
            "path": str(rel_path),
            "days_ago": (now - mtime).days,
        })
    return results


def _days_since(dt: datetime | None) -> int | None:
    if dt is None:
        return None
    if dt.tzinfo:
        now = datetime.now(timezone.utc)
        delta = now - dt.astimezone(timezone.utc)
    else:
        delta = datetime.now() - dt
    return max(0, delta.days)


def _git_last_commit(repo: Path) -> datetime | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "log", "-1", "--format=%cI"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        raw = result.stdout.strip()
        if raw.endswith("Z"):
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return datetime.fromisoformat(raw)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, ValueError):
        return None


def discover_git_repos(root: Path, max_depth: int = 4) -> list[Path]:
    repos: list[Path] = []
    def walk(path: Path, depth: int) -> None:
        if depth > max_depth:
            return
        if (path / ".git").is_dir():
            repos.append(path)
            return
        try:
            for child in sorted(path.iterdir()):
                if not child.is_dir():
                    continue
                if child.name in SKIP_REPO_NAMES or child.name.startswith("."):
                    continue
                walk(child, depth + 1)
        except (OSError, PermissionError):
            return
    if root.exists():
        walk(root, 0)
    return repos


def _parse_card_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for key in ("Stage", "Sprint Goal", "Opened", "Repo"):
        match = re.search(rf"\*\*{re.escape(key)}:\*\*\s*(.+)", text)
        if match:
            fields[key] = match.group(1).strip()
    return fields


def _parse_last_log_date(text: str) -> datetime | None:
    dates = re.findall(r"^### (\d{4}-\d{2}-\d{2})", text, re.MULTILINE)
    if not dates:
        return None
    try:
        return datetime.strptime(dates[-1], "%Y-%m-%d")
    except ValueError:
        return None


def _staleness_tier(days: int) -> str:
    if days >= 30:
        return "critical"
    if days >= 14:
        return "warm"
    return "cool"


def get_neglected_items(
    projects_root: Path,
    pipeline_dir: Path,
    threshold_days: int = NEGLECT_DAYS_THRESHOLD,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for repo in discover_git_repos(projects_root):
        last = _git_last_commit(repo)
        days = _days_since(last)
        if days is None or days < threshold_days:
            continue
        name = repo.name
        if name in seen_names:
            continue
        seen_names.add(name)
        items.append({
            "name": name,
            "kind": "repo",
            "days": days,
            "detail": str(repo).replace(str(Path.home()), "~", 1),
            "tier": _staleness_tier(days),
        })
    if pipeline_dir.exists():
        for stage in STAGE_ORDER:
            stage_path = pipeline_dir / stage
            if not stage_path.is_dir():
                continue
            for card_path in sorted(stage_path.glob("*.md")):
                try:
                    text = card_path.read_text(encoding="utf-8")
                except OSError:
                    continue
                fields = _parse_card_fields(text)
                last_log = _parse_last_log_date(text)
                opened_raw = fields.get("Opened", "")
                opened_dt = None
                if opened_raw:
                    try:
                        opened_dt = datetime.strptime(opened_raw, "%Y-%m-%d")
                    except ValueError:
                        pass
                reference = last_log or opened_dt
                days = _days_since(reference)
                if days is None or days < threshold_days:
                    continue
                name = card_path.stem
                if name in seen_names:
                    continue
                seen_names.add(name)
                items.append({
                    "name": name,
                    "kind": "sprint",
                    "days": days,
                    "detail": fields.get("Sprint Goal", STAGE_LABELS.get(stage, stage))[:60],
                    "tier": _staleness_tier(days),
                    "stage": STAGE_LABELS.get(stage, stage),
                })
    items.sort(key=lambda x: x["days"], reverse=True)
    return items[:MAX_NEGLECT_ITEMS]


def get_forge_status(pipeline_dir: Path) -> dict[str, Any]:
    active_cards: list[dict[str, Any]] = []
    if not pipeline_dir.exists():
        return {
            "active_cards": [],
            "slots_used": 0,
            "slots_max": SPRINT_SLOT_MAX,
            "digest_lines": ["Pipeline directory not found."],
        }
    for stage in STAGE_ORDER:
        stage_path = pipeline_dir / stage
        if not stage_path.is_dir():
            continue
        for card_path in sorted(stage_path.glob("*.md")):
            try:
                text = card_path.read_text(encoding="utf-8")
            except OSError:
                continue
            fields = _parse_card_fields(text)
            last_log = _parse_last_log_date(text)
            active_cards.append({
                "name": card_path.stem,
                "stage": STAGE_LABELS.get(stage, stage),
                "stage_key": stage,
                "goal": fields.get("Sprint Goal", "\u2014")[:70],
                "opened": fields.get("Opened", "\u2014"),
                "last_log": last_log.strftime("%Y-%m-%d") if last_log else "no log",
                "days_since_log": _days_since(last_log),
            })
    slots_used = len(active_cards)
    digest_lines = _build_forge_digest(active_cards, slots_used)
    return {
        "active_cards": active_cards[:MAX_FORGE_CARDS],
        "slots_used": slots_used,
        "slots_max": SPRINT_SLOT_MAX,
        "digest_lines": digest_lines,
    }


def _build_forge_digest(cards: list[dict[str, Any]], slots_used: int) -> list[str]:
    lines: list[str] = []
    today = datetime.now().strftime("%Y-%m-%d")
    lines.append(f"ORIENTATION // {today}")
    lines.append(f"Sprint load {slots_used}/{SPRINT_SLOT_MAX}")
    if not cards:
        lines.append("No active pipeline cards \u2014 pull from backlog.")
        return lines
    building = [c for c in cards if c["stage_key"] == "02_building"]
    scoping = [c for c in cards if c["stage_key"] == "01_scoping"]
    review = [c for c in cards if c["stage_key"] == "03_review"]
    if building:
        lines.append(f"BUILD: {', '.join(c['name'] for c in building)}")
    if scoping:
        lines.append(f"SCOPE: {', '.join(c['name'] for c in scoping)}")
    if review:
        lines.append(f"REVIEW: {', '.join(c['name'] for c in review)}")
    stale = [c for c in cards if c.get("days_since_log") is not None and c["days_since_log"] >= 3]
    if stale:
        lines.append(f"STALE LOG: {', '.join(c['name'] for c in stale[:3])}")
    return lines
