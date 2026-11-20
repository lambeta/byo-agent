"""The correspondence between a turn's records and the map's lights.

Mechanism: a pure projection. Given one turn's records and the memory configuration it
returns the ordered list of component-state cues the map plays and the settled state of
every component. Records in, cues out: no I/O, no clock, no second store.

Rejected alternative: mapping events in the browser. That is the arrangement this
feature replaces: the page cannot be tested offline and the mapping drifts from the
record it claims to depict.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from byo.ops.liveness import alive as process_alive
from byo.ops.map import NODES
from byo.ops.observability import FATAL_STAGES

STAGE_NODES = {
    "gate": "gate",
    "llm": "model",
    "tool": "tools",
    "consolidation": "consolidation",
}
MEMORY_NODES = ("facts", "episodes", "persona")
STAGE_COMPONENTS = ("gate", "context", "model", "tools", "reply", "consolidation")
COMPLETIONS = ("gate", "llm", "tool", "consolidation")
PREVIEW = 60


def _short(value: Any) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= PREVIEW else text[: PREVIEW - 1] + "…"


def _calls(count: int) -> str:
    return f"{count} tool call" + ("" if count == 1 else "s")


def cues(
    events: list[dict[str, Any]],
    *,
    memory_enabled: bool = True,
) -> list[dict[str, Any]]:
    """Ordered component-state transitions for one turn's records.

    Cue.edges is the complete set of connections live after the cue; the client idles
    every other edge. Cue.states maps node id to the state applied by this cue.
    """
    records = [event for event in events if isinstance(event, dict)]
    out: list[dict[str, Any]] = []

    def add(at: str, step: str, states: dict[str, str], edges: list[str], label: str,
            role: str = "step") -> None:
        out.append(
            {
                "seq": len(out),
                "at": at,
                "step": step,
                "states": dict(states),
                "edges": list(edges),
                "label": label,
                "role": role,
            }
        )

    llm_indexes = [index for index, event in enumerate(records) if event.get("type") == "llm"]
    last_llm = llm_indexes[-1] if llm_indexes else -1
    tool_starts = any(event.get("type") == "tool_start" for event in records)
    tools = 0
    round_no = 0

    for index, event in enumerate(records):
        kind = event.get("type")
        at = str(event.get("ts") or "")
        if kind == "turn_start":
            source = event.get("source") or "cli"
            add(at, kind, {"surfaces": "live", "record": "live"},
                ["e-surfaces-gate"], f"message in · {source}")
            add(at, kind, {"surfaces": "done"}, [], f"message in · {source}")
        elif kind == "gate_start":
            add(at, kind, {"gate": "live"}, [], "memory decision")
        elif kind == "gate":
            decision = event.get("decision") or "unknown"
            degraded = bool(event.get("degraded"))
            state = "skipped" if decision == "skip" else ("degraded" if degraded else "done")
            label = f"memory decision · {decision}"
            if decision == "skip":
                label = f"memory skipped · {_short(event.get('reason'))}"
            add(at, kind, {"gate": state}, [], label)
            if memory_enabled and decision == "retrieve":
                add(at, kind, {node: "done" for node in MEMORY_NODES},
                    ["e-gate-facts", "e-gate-episodes", "e-gate-persona"],
                    f"memory retrieved · {_short(event.get('reason'))}")
            elif memory_enabled and decision == "skip":
                add(at, kind, {node: "skipped" for node in MEMORY_NODES}, [], label)
        elif kind == "context":
            add(at, kind, {"context": "done"}, ["e-gate-context"], "context assembled")
        elif kind == "llm_start":
            round_no = int(event.get("iteration") or (round_no + 1))
            add(at, kind, {"model": "live"}, ["e-context-model"],
                f"loop {round_no} · model reasons")
        elif kind == "llm":
            number = event.get("iteration") or round_no
            label = "final answer" if index == last_llm else f"loop {number} · model answered"
            add(at, kind, {"model": "done"}, [], label)
        elif kind == "tool_start":
            if not tool_starts:
                tools += 1
            else:
                tools += 1
            add(at, kind, {"tools": "live"}, ["e-model-tools"],
                f"tool {event.get('tool') or 'tool'} · {_calls(tools)}")
        elif kind == "tool":
            if not tool_starts:
                tools += 1
            outcome = "done" if event.get("ok") is not False else "failed"
            add(
                at,
                kind,
                {"tools": outcome},
                ["e-tools-model"],
                f"tool {event.get('tool') or 'tool'} · {outcome} · {_calls(tools)}",
            )
        elif kind == "consolidation_start":
            add(at, kind, {"consolidation": "live"}, [], "memory write")
        elif kind == "consolidation":
            add(at, kind, {"consolidation": "done", "facts": "done"},
                ["e-consolidation-facts"],
                f"memory written · {int(event.get('new_facts') or 0)} facts")
        elif kind == "retry":
            add(at, kind, {"model": "live"}, [], "model retry · transport hiccup")
        elif kind == "receipt":
            add(at, kind, {"cost": "done"}, ["e-record-cost"], "costed")
        elif kind == "error":
            stage = event.get("stage") or "turn"
            node = STAGE_NODES.get(stage)
            add(at, kind, {node: "failed"} if node else [], [],
                f"failed: {stage}")
        elif kind == "turn_end":
            failed = event.get("state") == "failed" or any(
                item.get("type") == "error" for item in records
            )
            label = "reply · failed" if failed else "reply"
            add(at, kind, {"reply": "live"},
                ["e-model-reply", "e-reply-surfaces", "e-reply-record"], label)
            add(at, kind, {"reply": "done", "record": "done"}, [], label)
        else:
            add(at, kind, {}, [], f"unmapped step · {kind or 'unknown'}")
    return out


def interrupted_cue(events: list[dict[str, Any]]) -> dict[str, Any]:
    """The one synthetic cue: an unfinished turn is not running any more."""
    records = [event for event in events if isinstance(event, dict)]
    open_nodes: list[str] = []
    at = ""
    for event in records:
        kind = str(event.get("type") or "")
        if kind.endswith("_start"):
            node = STAGE_NODES.get(kind[:-6])
            if node:
                open_nodes.append(node)
            at = str(event.get("ts") or at)
        elif kind in COMPLETIONS and open_nodes:
            open_nodes.pop()
    where = open_nodes[-1] if open_nodes else "unknown"
    return {
        "seq": 0,
        "at": at,
        "step": "synthetic",
        "states": {open_nodes[-1]: "partial"} if open_nodes else {},
        "edges": [],
        "label": f"not running · interrupted at {where}",
        "role": "step",
    }


def final_states(
    events: list[dict[str, Any]],
    *,
    memory_enabled: bool = True,
) -> dict[str, str]:
    """The settled state of every component, derived only from the record."""
    records = [event for event in events if isinstance(event, dict)]
    states = {node["id"]: "idle" for node in NODES}
    touched: set[str] = set()
    gate: dict[str, Any] | None = None
    ended = False
    tool_failed = False
    error_stages: set[str] = set()

    for event in records:
        kind = event.get("type")
        if kind == "turn_start":
            touched.add("surfaces")
        elif kind == "gate":
            gate = event
            touched.add("gate")
        elif kind == "context":
            touched.add("context")
        elif kind in ("llm_start", "llm"):
            touched.add("model")
        elif kind in ("tool_start", "tool"):
            touched.add("tools")
            if kind == "tool" and event.get("ok") is False:
                tool_failed = True
        elif kind in ("consolidation_start", "consolidation"):
            touched.add("consolidation")
            if kind == "consolidation":
                touched.add("facts")
        elif kind == "receipt":
            touched.add("cost")
        elif kind == "error":
            error_stages.add(str(event.get("stage") or ""))
            node = STAGE_NODES.get(str(event.get("stage") or ""))
            if node:
                touched.add(node)
        elif kind == "turn_end":
            ended = True

    if gate is not None:
        if gate.get("degraded"):
            states["gate"] = "degraded"
        elif gate.get("decision") == "skip":
            states["gate"] = "skipped"
        elif gate.get("decision") == "retrieve":
            states["gate"] = "done"
    if memory_enabled and gate is not None:
        decision = gate.get("decision")
        if decision == "retrieve":
            for node in MEMORY_NODES:
                states[node] = "done"
        elif decision == "skip":
            for node in MEMORY_NODES:
                states[node] = "skipped"
    if "context" in touched:
        states["context"] = "done"
    if "model" in touched:
        states["model"] = "failed" if "llm" in error_stages else "done"
    if "tools" in touched:
        states["tools"] = "failed" if tool_failed or "tool" in error_stages else "done"
    if "consolidation" in touched:
        states["consolidation"] = "done"
    if "facts" in touched:
        states["facts"] = "done"
    if "cost" in touched:
        states["cost"] = "done"
    if ended:
        states["record"] = "done"
        if not (error_stages & FATAL_STAGES):
            states["reply"] = "done"

    cut = bool(error_stages) or not ended
    if cut:
        for node in STAGE_COMPONENTS:
            if node not in touched:
                states[node] = "not-reached"
        if not ended:
            open_nodes: list[str] = []
            for event in records:
                kind = str(event.get("type") or "")
                if kind.endswith("_start"):
                    node = STAGE_NODES.get(kind[:-6])
                    if node:
                        open_nodes.append(node)
                elif kind in COMPLETIONS and open_nodes:
                    open_nodes.pop()
            if open_nodes:
                states[open_nodes[-1]] = "partial"
    return states


def turn_state(
    events: list[dict[str, Any]],
    is_alive: Callable[[Any], bool] = process_alive,
) -> str:
    """running | interrupted | complete | failed, from the record plus the pid."""
    records = [event for event in events if isinstance(event, dict)]
    start = next((event for event in records if event.get("type") == "turn_start"), None)
    end = next(
        (event for event in reversed(records) if event.get("type") == "turn_end"), None
    )
    errors = [
        event
        for event in records
        if event.get("type") == "error" and str(event.get("stage") or "") in FATAL_STAGES
    ]
    if end is not None:
        if end.get("state") == "failed" or errors:
            return "failed"
        return "complete"
    if start is None:
        return "interrupted"
    pid = start.get("pid")
    if pid is None:
        return "interrupted"
    return "running" if is_alive(pid) else "interrupted"
