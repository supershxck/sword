#!/usr/bin/env python3
"""
Glamdring — Sword of Command

Unified local command dashboard: system telemetry, neglect radar, forge orientation,
docker fleet, and signal log. Used-future retro sci-fi TUI.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Static

from widgets import (
    DockerFleetPanel,
    ForgePanel,
    NeglectRadarPanel,
    SignalLogPanel,
    TelemetryRow,
)

DEFAULT_WATCH_DIR = Path.home() / "Projects"
DEFAULT_PROJECTS_ROOT = Path.home() / "Projects"
DEFAULT_PIPELINE_DIR = Path(__file__).resolve().parent / "pipeline"

REFRESH_SYSTEM_SECS = 1.0
REFRESH_DOCKER_SECS = 3.0
REFRESH_FILES_SECS = 5.0
REFRESH_NEGLECT_SECS = 30.0
REFRESH_FORGE_SECS = 15.0


class TextureOverlay(Static):
    """Subtle scanline texture behind panels."""

    def render(self) -> str:
        return "· " * 4000


class SwordOfCommand(App):
    """Glamdring command dashboard."""

    TITLE = "Glamdring"
    CSS_PATH = "sword.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh_all", "Refresh"),
        ("f", "refresh_forge", "Forge"),
        ("n", "refresh_neglect", "Radar"),
    ]

    def __init__(
        self,
        watch_dir: Path,
        projects_root: Path,
        pipeline_dir: Path,
    ) -> None:
        super().__init__()
        self.watch_dir = watch_dir.resolve()
        self.projects_root = projects_root.resolve()
        self.pipeline_dir = pipeline_dir.resolve()

    def compose(self) -> ComposeResult:
        yield TextureOverlay(id="texture")
        yield Header(show_clock=True)
        yield Static("◆ GLAMDRING // SWORD OF COMMAND", id="title-bar")
        yield Static(
            "local telemetry · neglect radar · forge orientation",
            id="subtitle-bar",
        )

        yield TelemetryRow(id="telemetry")

        with Horizontal(id="command-deck"):
            yield NeglectRadarPanel(
                projects_root=self.projects_root,
                pipeline_dir=self.pipeline_dir,
                id="neglect",
            )
            yield ForgePanel(pipeline_dir=self.pipeline_dir, id="forge")

        with Horizontal(id="ops-deck"):
            yield DockerFleetPanel(id="docker")
            yield SignalLogPanel(watch_dir=self.watch_dir, id="signals")

        yield Footer()

    def on_mount(self) -> None:
        self._refresh_all()
        self.set_interval(REFRESH_SYSTEM_SECS, self._refresh_telemetry)
        self.set_interval(REFRESH_DOCKER_SECS, self._refresh_docker)
        self.set_interval(REFRESH_FILES_SECS, self._refresh_signals)
        self.set_interval(REFRESH_NEGLECT_SECS, self._refresh_neglect)
        self.set_interval(REFRESH_FORGE_SECS, self._refresh_forge)

    def _refresh_telemetry(self) -> None:
        self.query_one("#telemetry", TelemetryRow).refresh_stats()

    def _refresh_docker(self) -> None:
        self.query_one("#docker", DockerFleetPanel).refresh_containers()

    def _refresh_signals(self) -> None:
        self.query_one("#signals", SignalLogPanel).refresh_files()

    def _refresh_neglect(self) -> None:
        self.query_one("#neglect", NeglectRadarPanel).refresh_items()

    def _refresh_forge(self) -> None:
        self.query_one("#forge", ForgePanel).refresh_status()

    def _refresh_all(self) -> None:
        self._refresh_telemetry()
        self._refresh_docker()
        self._refresh_signals()
        self._refresh_neglect()
        self._refresh_forge()

    def action_refresh_all(self) -> None:
        self._refresh_all()

    def action_refresh_forge(self) -> None:
        self._refresh_forge()

    def action_refresh_neglect(self) -> None:
        self._refresh_neglect()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Glamdring — Sword of Command. Sci-fi local ops dashboard.",
    )
    parser.add_argument(
        "--watch-dir",
        type=Path,
        default=DEFAULT_WATCH_DIR,
        help="Directory to scan for recent markdown signals",
    )
    parser.add_argument(
        "--projects-root",
        type=Path,
        default=DEFAULT_PROJECTS_ROOT,
        help="Root directory for neglect radar git scan",
    )
    parser.add_argument(
        "--pipeline-dir",
        type=Path,
        default=DEFAULT_PIPELINE_DIR,
        help="Pipeline folder for forge orientation",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = SwordOfCommand(
        watch_dir=args.watch_dir,
        projects_root=args.projects_root,
        pipeline_dir=args.pipeline_dir,
    )
    app.run()


if __name__ == "__main__":
    main()
