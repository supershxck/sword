# Glamdring — Sword of Command

Local ops dashboard: telemetry, neglect radar, forge orientation, docker fleet, markdown signal log. A Textual TUI and a browser companion on the same collectors.

| | |
|---|---|
| **Status** | instrument |
| **House** | Workbench |
| **Stack** | Python, Textual, psutil |

The sprint board stays private. This repo is the sword, not the ledger.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python glamdring.py          # terminal dashboard
python server.py             # http://127.0.0.1:8787
```

| Flag | What it scans |
|---|---|
| `--projects-root` | git repos for neglect radar (default `~/Projects`) |
| `--watch-dir` | recent markdown for the signal log |
| `--pipeline-dir` | optional folder of sprint cards (`01_scoping`, `02_building`, …) |

If `--pipeline-dir` is missing, forge status simply says the pipeline was not found.

## Layout

```
collectors.py     system, docker, markdown, neglect, forge — no UI
widgets.py        TUI panels and ring gauges
glamdring.py      Textual app
sword.tcss        used-future terminal theme
server.py         local API + companion
companion/        holographic browser dashboard
```

## Keys

| Key | Action |
|---|---|
| `q` | Quit |
| `r` | Refresh all |
| `f` | Refresh forge |
| `n` | Refresh neglect radar |
