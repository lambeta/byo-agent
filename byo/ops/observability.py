"""Turn projections — the trajectory is the only source for every screen.

Mechanism: read the day files, group records between turn_start and turn_end, and
project each turn into the payload the dashboard and the timeline render.

Rejected alternative: a turns table. It would be a second source of truth that can
disagree with the file a person can open.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from byo.ops.pricing import cost

PREVIEW = 2000


def _bounded(value: Any, limit: int = PREVIEW) -> str:
    """A truncated value that keeps its line breaks (thinking, replies)."""
    text = "" if value is None else str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _preview(value: Any, limit: int = PREVIEW) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def read_events(home: Path, window: str = "all") -> tuple[list[dict[str, Any]], int]:
    """(events, skipped_lines). A bad line is counted, never fatal."""
    directory = Path(home) / "trajectories"
    if not directory.is_dir():
        return [], 0
    files = sorted(directory.glob("*.jsonl"))
    if window == "today":
        files = files[-1:]
    elif window == "7d":
        floor = (date.today() - timedelta(days=6)).isoformat()
        files = [path for path in files if path.stem >= floor]
    events: list[dict[str, Any]] = []
    skipped = 0
    for path in files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if isinstance(event, dict):
                events.append(event)
            else:
                skipped += 1
    return events, skipped


def group_turns(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for event in events:
        kind = event.get("type")
        if kind == "turn_start":
            if current is not None:
                current["unfinished"] = True
                turns.append(current)
            current = {
                "turn_id": event.get("turn_id") or "",
                "user_message": event.get("user_message") or "",
                "source": event.get("source") or "cli",
                "session_id": event.get("session_id") or "default",
                "started_at": event.get("ts"),
                "events": [],
            }
        elif current is not None:
            if kind == "turn_end":
                current["ended_at"] = event.get("ts")
                current["reply"] = event.get("reply") or ""
                current["iterations"] = event.get("iterations")
                turns.append(current)
                current = None
            elif kind != "text":
                current["events"].append(event)
    if current is not None:
        current["unfinished"] = True
        turns.append(current)
    return turns


# Start markers and the context mark describe when a step ran, not a step of its own:
# they must never appear as a turn step or add to spend.
NOT_STEPS = frozenset(
    {"gate_start", "llm_start", "tool_start", "consolidation_start", "context"}
)


def _step(event: dict[str, Any], provider: str, model: str) -> dict[str, Any] | None:
    kind = event.get("type")
    if kind in NOT_STEPS:
        return None
    base = {"kind": kind, "ts": event.get("ts")}
    if kind == "gate":
        return {
            **base,
            "decision": event.get("decision"),
            "reason": _preview(event.get("reason", "")),
        }
    if kind == "llm":
        usage = event.get("usage") or {}
        usd, _ = cost(event.get("provider", provider), event.get("model") or model, usage)
        return {
            **base,
            "kind": "llm",
            "call": event.get("kind") or "loop",
            "iteration": event.get("iteration"),
            "model": event.get("model") or model,
            "in": int(usage.get("in", 0) or 0),
            "out": int(usage.get("out", 0) or 0),
            "usd": round(float(usd), 6),
            "duration_ms": event.get("duration_ms"),
            "text": _bounded(event.get("text")),
            "ok": True,
        }
    if kind == "tool":
        return {
            **base,
            "kind": "tool",
            "tool": event.get("tool"),
            "args": _preview(event.get("args", {})),
            "output": _preview(event.get("output", "")),
            "duration_ms": event.get("duration_ms"),
            "ok": event.get("ok") is not False,
        }
    if kind == "consolidation":
        return {
            **base,
            "kind": "memory_write",
            "new_facts": event.get("new_facts", 0),
            "kept": event.get("kept") or [],
        }
    if kind == "error":
        return {
            **base,
            "kind": "error",
            "stage": event.get("stage"),
            "error_kind": event.get("error_kind"),
            "message": _preview(event.get("message", "")),
            "ok": False,
        }
    return None


def build_turn(turn: dict[str, Any], provider: str = "", model: str = "") -> dict[str, Any]:
    steps = [step for step in (_step(e, provider, model) for e in turn["events"]) if step]
    raw_receipt = next((e for e in turn["events"] if e.get("type") == "receipt"), None)
    receipt = (
        {
            "iterations": raw_receipt.get("iterations"),
            "tool_calls": raw_receipt.get("tool_calls"),
            "tokens_in": raw_receipt.get("tokens_in"),
            "tokens_out": raw_receipt.get("tokens_out"),
            "usd": raw_receipt.get("total_usd"),
            "estimate": raw_receipt.get("estimate"),
        }
        if raw_receipt
        else None
    )
    gate = next((e for e in turn["events"] if e.get("type") == "gate"), None)
    failed = any(step["kind"] == "error" for step in steps)
    state = "unfinished" if turn.get("unfinished") else ("failed" if failed else "complete")
    return {
        "turn_id": turn["turn_id"],
        "source": turn["source"],
        "session_id": turn["session_id"],
        "user_message": turn["user_message"],
        "started_at": turn["started_at"],
        "ended_at": turn.get("ended_at"),
        "state": state,
        "iterations": turn.get("iterations") or 0,
        "reply": turn.get("reply", ""),
        "gate": {"decision": gate.get("decision"), "reason": gate.get("reason")} if gate else None,
        "steps": steps,
        "receipt": receipt,
    }


def spend(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_day: dict[str, float] = {}
    by_model: dict[str, float] = {}
    total = 0.0
    for event in events:
        if event.get("type") in NOT_STEPS:
            continue
        if event.get("type") == "receipt":
            usd = float(event.get("total_usd", 0) or 0)
            day = str(event.get("ts", ""))[:10]
            by_day[day] = round(by_day.get(day, 0.0) + usd, 6)
            total += usd
        elif event.get("type") == "llm":
            name = event.get("model") or "unknown"
            usd, _ = cost(event.get("provider", ""), name, event.get("usage") or {})
            by_model[name] = round(by_model.get(name, 0.0) + usd, 6)
    return {
        "total_usd": round(total, 6),
        "by_day": [{"day": day, "usd": usd} for day, usd in sorted(by_day.items())],
        "by_model": [{"model": name, "usd": usd} for name, usd in sorted(by_model.items())],
    }


def payload(home: Path, window: str = "7d", provider: str = "", model: str = "") -> dict[str, Any]:
    events, skipped = read_events(home, window)
    turns = [build_turn(turn, provider, model) for turn in group_turns(events)]
    tools = [step for turn in turns for step in turn["steps"] if step["kind"] in ("tool", "llm")]
    return {
        "window": window,
        "turns": turns,
        "tools": tools,
        "spend": spend(events),
        "skipped_lines": skipped,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
