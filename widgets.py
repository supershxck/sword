"""Glamdring UI widgets — holographic panels and ring gauges."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widgets import DataTable, Static

from collectors import (
    get_docker_containers,
    get_forge_status,
    get_neglected_items,
    get_recent_markdown_files,
    get_system_stats,
)

RING_ARCS = "\u25d4\u25d5\u25d6\u25d7\u25de\u25df\u25de\u25d7"


def _ring_arc(percent: float) -> str:
    idx = int((percent / 100) * len(RING_ARCS)) % len(RING_ARCS)
    return RING_ARCS[idx]


def _tier_style(tier: str) -> str:
    return {
        "critical": "bold #fbbf24",
        "warm": "#22d3ee",
        "cool": "dim #64748b",
    }.get(tier, "dim")


class RingGauge(Static):
    percent: reactive[float] = reactive(0.0)
    label: reactive[str] = reactive("SYS")
    sublabel: reactive[str] = reactive("")

    def __init__(self, label: str = "SYS", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.label = label

    def watch_percent(self, percent: float) -> None:
        self._render_gauge()

    def watch_label(self, label: str) -> None:
        self._render_gauge()

    def watch_sublabel(self, sublabel: str) -> None:
        self._render_gauge()

    def on_mount(self) -> None:
        self._render_gauge()

    def _render_gauge(self) -> None:
        arc = _ring_arc(self.percent)
        pct_text = Text(f"{self.percent:>3.0f}%", style="bold #4ade80")
        arc_text = Text(f" {arc} ", style="bold #22d3ee")
        label_text = Text(f"\n{self.label}", style="bold #22d3ee")
        sub_text = Text(f"\n{self.sublabel}", style="dim #64748b") if self.sublabel else Text("")
        body = Text.assemble(arc_text, pct_text, label_text, sub_text)
        self.update(Panel(body, border_style="#0891b2", padding=(0, 1), title_align="center"))


class TelemetryRow(Static):
    stats: reactive[dict[str, Any]] = reactive({})

    def compose(self) -> ComposeResult:
        yield RingGauge("CPU", id="cpu-ring", classes="gauge")
        yield RingGauge("RAM", id="ram-ring", classes="gauge")
        yield RingGauge("DISK", id="disk-ring", classes="gauge")
        yield Static(id="gpu-readout", classes="gpu-panel")

    def watch_stats(self, stats: dict[str, Any]) -> None:
        if not stats:
            return
        self.query_one("#cpu-ring", RingGauge).percent = stats["cpu_percent"]
        self.query_one("#cpu-ring", RingGauge).sublabel = "compute"
        self.query_one("#ram-ring", RingGauge).percent = stats["mem_percent"]
        self.query_one("#ram-ring", RingGauge).sublabel = f"{stats['mem_used_gb']}/{stats['mem_total_gb']}G"
        self.query_one("#disk-ring", RingGauge).percent = stats["disk_percent"]
        self.query_one("#disk-ring", RingGauge).sublabel = f"{stats['disk_used_gb']}/{stats['disk_total_gb']}G"
        gpu = Text()
        gpu.append("GPU TELEMETRY\n", style="bold #22d3ee")
        gpu.append(stats["gpu_info"], style="#4ade80")
        gpu.append(f"\n\nSYNC {stats['timestamp']}", style="dim #64748b")
        self.query_one("#gpu-readout", Static).update(
            Panel(gpu, border_style="#0891b2", title="SUBSYSTEMS", padding=(1, 2))
        )

    def refresh_stats(self) -> None:
        self.stats = get_system_stats()


class NeglectRadarPanel(Static):
    items: reactive[list[dict[str, Any]]] = reactive([])

    def __init__(self, projects_root: Path, pipeline_dir: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.projects_root = projects_root
        self.pipeline_dir = pipeline_dir
        self.border_title = "NEGLECT RADAR"

    def compose(self) -> ComposeResult:
        yield Static(id="neglect-content")

    def watch_items(self, items: list[dict[str, Any]]) -> None:
        if not items:
            body = Text("No neglected targets in scan range.\nAll systems attended.", style="#4ade80")
            self.query_one("#neglect-content", Static).update(
                Panel(body, border_style="#0891b2", padding=(1, 2))
            )
            return
        table = Table(show_header=True, header_style="bold #22d3ee", expand=True, pad_edge=False)
        table.add_column("TARGET", ratio=2)
        table.add_column("TYPE", ratio=1)
        table.add_column("DRIFT", justify="right", ratio=1)
        for item in items:
            drift = Text(f"{item['days']}d", style=_tier_style(item["tier"]))
            kind = "SPRINT" if item["kind"] == "sprint" else "REPO"
            name = Text(item["name"], style=_tier_style(item["tier"]))
            table.add_row(name, kind, drift)
        footer = Text(f"\n{items[0]['detail']}", style="dim #64748b")
        self.query_one("#neglect-content", Static).update(
            Panel(Group(table, footer), border_style="#0891b2", padding=(0, 1))
        )

    def refresh_items(self) -> None:
        self.items = get_neglected_items(self.projects_root, self.pipeline_dir)


class ForgePanel(Static):
    status: reactive[dict[str, Any]] = reactive({})

    def __init__(self, pipeline_dir: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.pipeline_dir = pipeline_dir
        self.border_title = "FORGE STATUS"

    def compose(self) -> ComposeResult:
        yield Static(id="forge-content")

    def watch_status(self, status: dict[str, Any]) -> None:
        if not status:
            return
        lines = Text()
        slots = status["slots_used"]
        max_slots = status["slots_max"]
        load_pct = int((slots / max_slots) * 100) if max_slots else 0
        lines.append(f"SPRINT LOAD  {slots}/{max_slots}  ", style="bold #22d3ee")
        lines.append(f"[{load_pct}%]\n\n", style="#4ade80")
        for digest_line in status.get("digest_lines", []):
            style = "#4ade80" if digest_line.startswith("ORIENTATION") else "#94a3b8"
            lines.append(digest_line + "\n", style=style)
        if status.get("active_cards"):
            lines.append("\n", style="")
            for card in status["active_cards"][:5]:
                stage_style = {
                    "Building": "bold #4ade80",
                    "Scoping": "#22d3ee",
                    "Review": "#fbbf24",
                }.get(card["stage"], "#94a3b8")
                lines.append(f"\u25b8 {card['name']}", style=stage_style)
                lines.append(f"  {card['stage']}", style="dim")
                lines.append(f"  {card['goal'][:50]}\n", style="dim #64748b")
        self.query_one("#forge-content", Static).update(
            Panel(lines, border_style="#0891b2", padding=(1, 2))
        )

    def refresh_status(self) -> None:
        self.status = get_forge_status(self.pipeline_dir)


class DockerFleetPanel(Static):
    containers: reactive[list[dict[str, str]]] = reactive([])

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.border_title = "DOCKER FLEET"

    def compose(self) -> ComposeResult:
        table = DataTable(id="docker-table", show_header=True, zebra_stripes=False)
        table.add_columns("UNIT", "IMAGE", "STATE")
        yield table

    def watch_containers(self, containers: list[dict[str, str]]) -> None:
        table = self.query_one("#docker-table", DataTable)
        table.clear()
        if not containers:
            table.add_row("\u2014", "no active containers", "idle")
            return
        for c in containers:
            table.add_row(c["name"][:18], c["image"][:22], c["status"][:16])

    def refresh_containers(self) -> None:
        self.containers = get_docker_containers()


class SignalLogPanel(Static):
    files: reactive[list[dict[str, Any]]] = reactive([])

    def __init__(self, watch_dir: Path, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.watch_dir = watch_dir
        display = str(watch_dir).replace(str(Path.home()), "~", 1)
        self.border_title = f"SIGNAL LOG \u00b7 {display}"

    def compose(self) -> ComposeResult:
        table = DataTable(id="signal-table", show_header=True, zebra_stripes=False)
        table.add_columns("TIME", "SIGNAL", "PATH")
        yield table

    def watch_files(self, files: list[dict[str, Any]]) -> None:
        table = self.query_one("#signal-table", DataTable)
        table.clear()
        if not files:
            table.add_row("\u2014", "no markdown signals", str(self.watch_dir))
            return
        for f in files:
            table.add_row(f["modified"], f["name"][:24], str(f["path"])[:30])

    def refresh_files(self) -> None:
        self.files = get_recent_markdown_files(self.watch_dir)
