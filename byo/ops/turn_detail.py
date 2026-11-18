"""One turn, projected for the map's secondary detail.

Mechanism: find the turn in the recorded trajectory, project it with the existing
observability read model, then build the summary, hotspot indexes and raw record from
that same projection. Nothing is cached and nothing is written.

Rejected alternative: a detail table or a client-side interpretation of raw events.
Either would become a second source of truth and could disagree with the turn card.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from byo.ops.observability import build_turn, group_turns, read_events

WINDOWS = ("today", "7d", "all")


def _moment(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _duration(turn: dict[str, Any]) -> float | None:
    start = _moment(turn.get("started_at"))
    end = _moment(turn.get("ended_at"))
    if end is None:
        stamps = [_moment(step.get("ts")) for step in turn.get("steps", [])]
        stamps = [stamp for stamp in stamps if stamp is not None]
        end = max(stamps) if stamps else None
    if start is None or end is None:
        return None
    seconds = (end - start).total_seconds()
    return max(0.0, seconds)


def _money(value: Any, estimate: bool = False) -> str:
    try:
        text = f"{float(value):.4f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return "cost not recorded"
    return ("~" if estimate else "") + "$" + (text or "0")


def summary(turn: dict[str, Any]) -> str:
    """The one-line story, in the order the turn actually happened."""
    steps = turn.get("steps", [])
    gate = turn.get("gate")
    head = ["question"]
    if gate:
        decision = gate.get("decision")
        if decision == "retrieve":
            head.append("memory retrieved")
        elif decision == "skip":
            head.append("memory skipped")
        else:
            head.append("memory decision")
    calls = sum(1 for step in steps if step.get("kind") == "llm")
    tools = sum(1 for step in steps if step.get("kind") == "tool")
    seconds = _duration(turn)
    duration = f"{seconds:.1f} s" if seconds is not None else "not timed"
    receipt = turn.get("receipt")
    cost = (
        _money(receipt.get("usd"), bool(receipt.get("estimate")))
        if receipt
        else "cost not recorded"
    )
    tail = [
        f"{calls} model call{'s' if calls != 1 else ''}",
        f"{tools} tool{'s' if tools != 1 else ''}",
        duration,
        cost,
    ]
    if turn.get("state") == "failed":
        stage = next(
            (step.get("stage") for step in steps if step.get("kind") == "error"),
            "unknown",
        )
        tail.append(f"failed at {stage}")
    elif turn.get("state") == "unfinished":
        tail.append("unfinished")
    return " → ".join(head) + " → " + " · ".join(tail)


def hotspots(turn: dict[str, Any]) -> dict[str, int | None]:
    """Indexes into turn['steps'] for the slowest and most expensive leaf step."""
    slowest: int | None = None
    most_usd: int | None = None
    for index, step in enumerate(turn.get("steps", [])):
        duration = step.get("duration_ms")
        if isinstance(duration, (int, float)) and (
            slowest is None
            or duration > turn["steps"][slowest].get("duration_ms", -1)
        ):
            slowest = index
        usd = step.get("usd")
        if isinstance(usd, (int, float)) and (
            most_usd is None or usd > turn["steps"][most_usd].get("usd", -1)
        ):
            most_usd = index
    return {"slowest": slowest, "most_usd": most_usd}


def detail(
    home: Path,
    turn_id: str,
    window: str = "7d",
    provider: str = "",
    model: str = "",
) -> dict[str, Any] | None:
    """The turn detail payload, or None when the id is outside the window."""
    if window not in WINDOWS:
        raise ValueError("window must be today, 7d or all")
    events, skipped = read_events(home, window)
    raw_turns = group_turns(events)
    target = next((turn for turn in raw_turns if turn.get("turn_id") == turn_id), None)
    if target is None:
        return None
    turn = build_turn(target, provider, model)
    raw = [event for event in events if event.get("turn_id") == turn_id]
    return {
        "window": window,
        "turn": turn,
        "summary": summary(turn),
        "hotspots": hotspots(turn),
        "raw": raw,
        "skipped_lines": skipped,
    }
