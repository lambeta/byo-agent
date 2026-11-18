"""The runtime map: the graph of parts, its event mapping and its summaries.

Mechanism: one in-repo Python data structure (groups, nodes, edges, EVENT_MAP) plus a
read-model summariser. The dashboard serialises it; the browser renders it. Tests can
assert destinations and event coverage without a browser.

Rejected alternative: a hand-authored SVG. It would look the same at first, then drift
from the routes and the trajectory vocabulary with no test able to notice.
"""

from __future__ import annotations

import copy
from datetime import datetime
from pathlib import Path
from typing import Any

from byo.config import Settings
from byo.ops.observability import build_turn, group_turns, read_events, spend

WINDOWS = ("today", "7d", "all")
VERSION = 1

GROUPS: list[dict[str, Any]] = [
    {"id": "surfaces", "label": "SURFACES", "x": 20, "y": 64, "w": 152, "h": 180},
    {"id": "harness", "label": "HARNESS", "x": 184, "y": 64, "w": 600, "h": 250},
    {"id": "memory", "label": "MEMORY", "x": 24, "y": 340, "w": 560, "h": 300},
    {"id": "operations", "label": "OPERATIONS", "x": 620, "y": 340, "w": 396, "h": 300},
]

# The stage field is the shared vocabulary FR-021 asks for. A node that is not one of
# the four turn stages carries its group name instead; the compact card and the detail
# use the same four stage terms.
NODES: list[dict[str, Any]] = [
    {
        "id": "surfaces", "label": "Surfaces", "group": "surfaces", "stage": "input",
        "shape": "box", "x": 32, "y": 110, "w": 128, "h": 56, "destination": "chat",
    },
    {
        "id": "gate", "label": "Memory gate", "group": "harness", "stage": "gate",
        "shape": "diamond", "x": 208, "y": 100, "w": 120, "h": 80, "destination": "memory",
    },
    {
        "id": "context", "label": "Working context", "group": "harness", "stage": "context",
        "shape": "box", "x": 360, "y": 110, "w": 140, "h": 56, "destination": "session",
    },
    {
        "id": "model", "label": "Model", "group": "harness", "stage": "loop",
        "shape": "box", "x": 520, "y": 110, "w": 140, "h": 56, "destination": "turn",
    },
    {
        "id": "tools", "label": "Tools", "group": "harness", "stage": "tool",
        "shape": "box", "x": 520, "y": 190, "w": 140, "h": 56, "destination": "turn",
    },
    {
        "id": "reply", "label": "Reply", "group": "harness", "stage": "reply",
        "shape": "box", "x": 680, "y": 110, "w": 100, "h": 56, "destination": "turn",
    },
    {
        "id": "facts", "label": "Fact memory", "group": "memory", "stage": "memory",
        "shape": "box", "x": 44, "y": 390, "w": 150, "h": 60, "destination": "memory",
    },
    {
        "id": "episodes", "label": "Episodes", "group": "memory", "stage": "memory",
        "shape": "box", "x": 214, "y": 390, "w": 150, "h": 60, "destination": "memory",
    },
    {
        "id": "persona", "label": "Persona", "group": "memory", "stage": "memory",
        "shape": "box", "x": 384, "y": 390, "w": 150, "h": 60, "destination": "memory",
    },
    {
        "id": "consolidation", "label": "Consolidation", "group": "memory", "stage": "memory",
        "shape": "box", "x": 44, "y": 510, "w": 240, "h": 60, "destination": "memory",
    },
    {
        "id": "record", "label": "Trajectory", "group": "operations", "stage": "operations",
        "shape": "box", "x": 640, "y": 390, "w": 160, "h": 60, "destination": "observability",
    },
    {
        "id": "observability", "label": "Observability", "group": "operations",
        "stage": "operations", "shape": "box", "x": 820, "y": 390, "w": 176, "h": 60,
        "destination": "observability",
    },
    {
        "id": "cost", "label": "Spend", "group": "operations", "stage": "operations",
        "shape": "box", "x": 820, "y": 480, "w": 176, "h": 60,
        "destination": "observability",
    },
]

EDGES: list[dict[str, Any]] = [
    {
        "id": "e-surfaces-gate", "source": "surfaces", "target": "gate",
        "label": "message in", "dashed": False,
    },
    {
        "id": "e-gate-context", "source": "gate", "target": "context",
        "label": "assemble", "dashed": False,
    },
    {
        "id": "e-gate-facts", "source": "gate", "target": "facts",
        "label": "only if needed", "dashed": True,
    },
    {
        "id": "e-gate-episodes", "source": "gate", "target": "episodes",
        "label": "only if needed", "dashed": True,
    },
    {
        "id": "e-gate-persona", "source": "gate", "target": "persona",
        "label": "only if needed", "dashed": True,
    },
    {
        "id": "e-context-model", "source": "context", "target": "model",
        "label": "prompt", "dashed": False,
    },
    {
        "id": "e-model-tools", "source": "model", "target": "tools",
        "label": "act", "dashed": False,
    },
    {
        "id": "e-tools-model", "source": "tools", "target": "model",
        "label": "observe", "dashed": False,
    },
    {
        "id": "e-model-reply", "source": "model", "target": "reply",
        "label": "answer", "dashed": False,
    },
    {
        "id": "e-reply-surfaces", "source": "reply", "target": "surfaces",
        "label": "reply out", "dashed": False,
    },
    {
        "id": "e-reply-record", "source": "reply", "target": "record",
        "label": "save", "dashed": False,
    },
    {
        "id": "e-reply-consolidation", "source": "reply", "target": "consolidation",
        "label": "saved chats", "dashed": True,
    },
    {
        "id": "e-consolidation-facts", "source": "consolidation", "target": "facts",
        "label": "distill", "dashed": False,
    },
    {
        "id": "e-record-observability", "source": "record", "target": "observability",
        "label": "read", "dashed": False,
    },
    {
        "id": "e-record-cost", "source": "record", "target": "cost",
        "label": "price", "dashed": False,
    },
]

EVENT_MAP: dict[str, dict[str, Any]] = {
    "turn_start": {
        "nodes": ["surfaces"], "edges": ["e-surfaces-gate"], "label": "message in",
    },
    "gate": {
        "nodes": ["gate"], "edges": ["e-gate-context"], "label": "memory decision",
        "retrieve": {
            "nodes": ["facts", "episodes", "persona"],
            "edges": ["e-gate-facts", "e-gate-episodes", "e-gate-persona"],
        },
    },
    "llm": {
        "nodes": ["context", "model"], "edges": ["e-context-model"],
        "label": "model reasons", "final_label": "final answer",
    },
    "tool": {
        "nodes": ["tools"], "edges": ["e-model-tools", "e-tools-model"], "label": "tool runs",
    },
    "consolidation": {
        "nodes": ["consolidation", "facts"], "edges": ["e-consolidation-facts"],
        "label": "memory written",
    },
    "receipt": {
        "nodes": ["cost", "record"], "edges": ["e-record-cost"], "label": "costed",
    },
    "error": {
        "nodes": [], "edges": [], "label": "failed",
        "stage_nodes": {
            "gate": "gate", "llm": "model", "tool": "tools", "consolidation": "consolidation",
        },
    },
    "turn_end": {
        "nodes": ["reply", "record"],
        "edges": ["e-model-reply", "e-reply-surfaces", "e-reply-record"],
        "label": "reply",
    },
}


def graph() -> dict[str, Any]:
    """A deep copy so a caller can annotate nodes without mutating module state."""
    return {
        "version": VERSION,
        "groups": copy.deepcopy(GROUPS),
        "nodes": copy.deepcopy(NODES),
        "edges": copy.deepcopy(EDGES),
        "event_map": copy.deepcopy(EVENT_MAP),
    }


def _count(conn, sql: str, params: tuple[Any, ...] = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row[0] or 0) if row else 0


def _plural(value: int, word: str) -> str:
    return f"{value} {word}{'' if value == 1 else 's'}"


def _money(value: float) -> str:
    text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return text or "0"


def _last_time(turns: list[dict[str, Any]]) -> str:
    if not turns:
        return "idle"
    started = str(turns[-1].get("started_at") or "")
    return f"last {started[11:16]}" if len(started) >= 16 else "idle"


def summaries(
    conn,
    settings: Settings,
    turns: list[dict[str, Any]],
    spend_data: dict[str, Any],
    memory_enabled: bool,
    tool_count: int,
    session_id: str,
) -> dict[str, str]:
    """One measured line per node. No value here is invented."""
    facts = _count(conn, "SELECT COUNT(*) FROM facts")
    episodes = _count(conn, "SELECT COUNT(*) FROM episodes")
    context_rows = _count(conn, "SELECT COUNT(*) FROM chat_log WHERE session_id = ?", (session_id,))
    pending = _count(conn, "SELECT COUNT(*) FROM chat_log WHERE consolidated = 0")
    tool_calls = sum(
        1 for turn in turns for step in turn.get("steps", []) if step.get("kind") == "tool"
    )
    gates = [turn.get("gate") for turn in turns if turn.get("gate")]
    if not memory_enabled:
        gate = "not configured"
    elif not turns:
        gate = "no turns yet"
    elif not gates:
        gate = "no memory decisions"
    else:
        skip = sum(1 for item in gates if item.get("decision") == "skip")
        retrieve = sum(1 for item in gates if item.get("decision") == "retrieve")
        gate = f"{skip} skip · {retrieve} retrieve"
    context = (
        f"{session_id} · empty"
        if context_rows == 0
        else f"{session_id} · {_plural(context_rows, 'message')}"
    )
    persona = "PERSONA.md" if settings.persona_path.exists() else "not created yet"
    total = float(spend_data.get("total_usd") or 0)
    return {
        "surfaces": "terminal · dashboard",
        "gate": gate,
        "context": context,
        "model": settings.effective_model(),
        "tools": _plural(tool_count, "tool"),
        "reply": _last_time(turns),
        "facts": _plural(facts, "fact"),
        "episodes": _plural(episodes, "episode"),
        "persona": persona,
        "consolidation": f"{pending} pending · every {settings.consolidate_every}",
        "record": _plural(len(turns), "turn"),
        "observability": _plural(tool_calls, "tool call"),
        "cost": "no spend" if total <= 0 else f"USD {_money(total)}",
    }


def turn_summaries(turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Newest-first lightweight entries for the turn list."""
    result: list[dict[str, Any]] = []
    for turn in reversed(turns):
        receipt = turn.get("receipt") or {}
        result.append(
            {
                "turn_id": turn.get("turn_id"),
                "started_at": turn.get("started_at"),
                "ended_at": turn.get("ended_at"),
                "source": turn.get("source"),
                "state": turn.get("state"),
                "iterations": turn.get("iterations") or receipt.get("iterations") or 0,
                "tool_calls": receipt.get(
                    "tool_calls",
                    sum(1 for step in turn.get("steps", []) if step.get("kind") == "tool"),
                ),
                "usd": receipt.get("usd"),
                "estimate": bool(receipt.get("estimate", False)),
            }
        )
    return result


def _active(events: list[dict[str, Any]], turns: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not turns or turns[-1].get("state") != "unfinished":
        return None
    turn = turns[-1]
    turn_id = turn.get("turn_id")
    return {
        "turn": {
            "turn_id": turn_id,
            "source": turn.get("source"),
            "started_at": turn.get("started_at"),
            "state": "unfinished",
        },
        "events": [event for event in events if event.get("turn_id") == turn_id],
    }


def payload(
    home: Path,
    conn,
    settings: Settings,
    window: str = "7d",
    memory_enabled: bool = True,
    tool_count: int = 6,
    session_id: str = "default",
) -> dict[str, Any]:
    """The landing payload: graph + summaries + turn list + live cursor."""
    if window not in WINDOWS:
        raise ValueError("window must be today, 7d or all")
    events, skipped = read_events(home, window)
    turns = [
        build_turn(raw, settings.provider, settings.effective_model())
        for raw in group_turns(events)
    ]
    spend_data = spend(events)
    nodes = summaries(conn, settings, turns, spend_data, memory_enabled, tool_count, session_id)
    data = graph()
    for node in data["nodes"]:
        node["summary"] = nodes.get(node["id"], "—")

    feed_events, _ = read_events(home, "7d")
    feed_turns = [
        build_turn(raw, settings.provider, settings.effective_model())
        for raw in group_turns(feed_events)
    ]
    active = _active(feed_events, feed_turns)
    return {
        "window": window,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "map": data,
        "turns": turn_summaries(turns),
        "active": active,
        "cursor": len(feed_events),
        "skipped_lines": skipped,
    }
