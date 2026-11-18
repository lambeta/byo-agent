"""Render one recorded trajectory as a terminal timeline.

Mechanism: stream the file line by line, print one readable line per record, indent
events inside their turn. A malformed line is reported and skipped; the rest render.

Rejected alternative: loading and sorting the whole file. Streaming keeps a long day
off the heap and matches the append-only file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TextIO

from rich.console import Console
from rich.markup import escape

from byo.config import load_settings


def newest_trajectory(home: Path) -> Path | None:
    directory = Path(home) / "trajectories"
    if not directory.is_dir():
        return None
    files = sorted(directory.glob("*.jsonl"))
    return files[-1] if files else None


def _short(value, limit: int = 100) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def summary(event: dict) -> str:
    kind = event.get("type", "event")
    if kind == "turn_start":
        return f"turn start · {_short(event.get('user_message', ''))}"
    if kind == "turn_end":
        iterations = event.get("iterations", 0)
        return f"turn end · {_short(event.get('reply', ''))} · {iterations} iteration(s)"
    if kind == "llm":
        usage = event.get("usage") or {}
        label = "final" if event.get("kind") == "final" else "loop"
        return (
            f"llm · {label} · iteration {event.get('iteration', '?')} · "
            f"{usage.get('in', 0)} in / {usage.get('out', 0)} out · "
            f"{event.get('duration_ms', 0)} ms"
        )
    if kind == "tool":
        status = "" if event.get("ok", True) else " [failed]"
        return (
            f"tool · {event.get('tool', '?')}({_short(event.get('args', {}))}) → "
            f"{_short(event.get('output', ''))}{status}"
        )
    if kind == "gate":
        reason = event.get("reason")
        return f"gate · {event.get('decision', '?')}" + (f" — {_short(reason)}" if reason else "")
    if kind == "consolidation":
        return f"memory · consolidated {event.get('new_facts', 0)} fact(s)"
    if kind == "receipt":
        usd = event.get("total_usd", 0)
        return (
            f"receipt · USD {usd} · {event.get('tokens_in', 0)} in / "
            f"{event.get('tokens_out', 0)} out"
        )
    if kind == "error":
        return f"error · {event.get('stage')} · {_short(event.get('message', ''))}"
    fields = {k: v for k, v in event.items() if k not in {"type", "ts"}}
    return str(kind) + (f" · {_short(fields)}" if fields else "")


def render(path: Path, console: Console | None = None) -> int:
    console = console or Console()
    console.print(f"[bold]Trajectory[/bold] {path}")
    count = 0
    try:
        handle: TextIO = path.open(encoding="utf-8")
    except FileNotFoundError:
        console.print(f"[dim]No trajectory at {path}[/dim]")
        return 0
    with handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                console.print(f"[yellow]Skipping invalid JSON on line {number}.[/yellow]")
                continue
            if not isinstance(event, dict):
                console.print(f"[yellow]Skipping non-object JSON on line {number}.[/yellow]")
                continue
            kind = event.get("type", "event")
            indent = "" if kind in ("turn_start", "turn_end") else "  "
            stamp = str(event.get("ts", ""))[11:23]
            console.print(f"{indent}[dim]{stamp}[/dim] {escape(summary(event))}")
            count += 1
    return count


def main(argv: list[str] | None = None) -> int:
    args = list(argv or [])
    settings = load_settings()
    path = Path(args[0]).expanduser() if args else newest_trajectory(settings.home)
    if path is None or not path.exists():
        Console().print("[yellow]No trajectory recorded yet.[/yellow]")
        return 1
    render(path)
    return 0
