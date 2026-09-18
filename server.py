#!/usr/bin/env python3
"""Glamdring browser companion — local API + static file server."""

from __future__ import annotations

import argparse
import json
import mimetypes
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from collectors import (
    get_docker_containers,
    get_forge_status,
    get_neglected_items,
    get_recent_markdown_files,
    get_system_stats,
)

COMPANION_DIR = Path(__file__).resolve().parent / "companion"
DEFAULT_WATCH_DIR = Path.home() / "Projects"
DEFAULT_PROJECTS_ROOT = Path.home() / "Projects"
DEFAULT_PIPELINE_DIR = Path(__file__).resolve().parent / "pipeline"
DEFAULT_PORT = 8787


def collect_status(
    watch_dir: Path,
    projects_root: Path,
    pipeline_dir: Path,
) -> dict[str, Any]:
    return {
        "system": get_system_stats(),
        "docker": get_docker_containers(),
        "signals": get_recent_markdown_files(watch_dir),
        "neglect": get_neglected_items(projects_root, pipeline_dir),
        "forge": get_forge_status(pipeline_dir),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class CompanionHandler(BaseHTTPRequestHandler):
    watch_dir: Path = DEFAULT_WATCH_DIR
    projects_root: Path = DEFAULT_PROJECTS_ROOT
    pipeline_dir: Path = DEFAULT_PIPELINE_DIR

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(404)
            return
        content_type, _ = mimetypes.guess_type(str(path))
        content_type = content_type or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        route = parsed.path

        if route == "/api/status":
            self._send_json(
                collect_status(self.watch_dir, self.projects_root, self.pipeline_dir)
            )
            return

        if route in ("/", ""):
            self._send_file(COMPANION_DIR / "index.html")
            return

        candidate = (COMPANION_DIR / route.lstrip("/")).resolve()
        if candidate.is_file() and str(candidate).startswith(str(COMPANION_DIR.resolve())):
            self._send_file(candidate)
            return

        self.send_error(404)


def make_handler(
    watch_dir: Path,
    projects_root: Path,
    pipeline_dir: Path,
) -> type[CompanionHandler]:
    class ConfiguredHandler(CompanionHandler):
        pass

    ConfiguredHandler.watch_dir = watch_dir.resolve()
    ConfiguredHandler.projects_root = projects_root.resolve()
    ConfiguredHandler.pipeline_dir = pipeline_dir.resolve()
    return ConfiguredHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Glamdring browser companion server.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--watch-dir", type=Path, default=DEFAULT_WATCH_DIR)
    parser.add_argument("--projects-root", type=Path, default=DEFAULT_PROJECTS_ROOT)
    parser.add_argument("--pipeline-dir", type=Path, default=DEFAULT_PIPELINE_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    handler = make_handler(args.watch_dir, args.projects_root, args.pipeline_dir)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Glamdring companion live at {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.server_close()


if __name__ == "__main__":
    main()
