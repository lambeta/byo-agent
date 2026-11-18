"""The correspondence eval: before and after, measured on the same fixtures.

Runs every fixture twice. The baseline reproduces today's playback rules (a light at the
completion of a step, no start alignment, the pre-change component map). The candidate is
the highlight projection. The printed table is the constitutional evidence that the map
now matches the run; the assertions are the regression gate.
"""

from __future__ import annotations

from byo.ops import highlight
from byo.ops.map import NODES

OLD_COMPONENTS = {
    "turn_start": ["surfaces"],
    "gate": ["gate"],
    "llm": ["context", "model"],
    "tool": ["tools"],
    "consolidation": ["consolidation", "facts"],
    "receipt": ["cost", "record"],
    "error": [],
    "turn_end": ["reply", "record"],
}

# The component each step is allowed to light. Anything else is a phantom light.
EXPECTED = {
    "llm_start": {"model"},
    "tool_start": {"tools"},
    "gate_start": {"gate"},
    "consolidation_start": {"consolidation"},
    "context": {"context"},
    "receipt": {"cost"},
    "turn_start": {"surfaces", "record"},
    "turn_end": {"reply", "record"},
    "llm": {"model"},
    "tool": {"tools"},
    "gate": {"gate"},
}


def ev(type_, ts, turn="t_eval", **fields):
    return {"type": type_, "turn_id": turn, "ts": ts, **fields}


def start(turn="t_eval", pid=111, source="cli"):
    return ev("turn_start", "2026-11-19T10:00:00.000+08:00", turn=turn,
              source=source, user_message="hi", pid=pid)


def skip_turn():
    return [
        start(),
        ev("gate_start", "2026-11-19T10:00:00.100+08:00", model="small"),
        ev(
            "gate",
            "2026-11-19T10:00:01.200+08:00",
            decision="skip",
            reason="plain",
            degraded=False,
        ),
        ev(
            "context",
            "2026-11-19T10:00:01.210+08:00",
            recalled=False,
            recalled_chars=0,
            duration_ms=2,
        ),
        ev("llm_start", "2026-11-19T10:00:01.220+08:00", iteration=1, model="big"),
        ev("llm", "2026-11-19T10:00:03.700+08:00", iteration=1, kind="loop", model="big",
           stop_reason="end_turn", usage={"in": 1, "out": 1}, duration_ms=2480),
        ev("receipt", "2026-11-19T10:00:03.710+08:00", total_usd=0.001, iterations=1,
           tool_calls=0, tokens_in=1, tokens_out=1, estimate=False),
        ev("turn_end", "2026-11-19T10:00:03.720+08:00", reply="ok", iterations=1, state="complete"),
    ]


def tool_turn():
    return [
        start(),
        ev("gate_start", "2026-11-19T10:00:00.100+08:00", model="small"),
        ev(
            "gate",
            "2026-11-19T10:00:00.500+08:00",
            decision="retrieve",
            reason="alex",
            degraded=False,
        ),
        ev(
            "context",
            "2026-11-19T10:00:00.510+08:00",
            recalled=True,
            recalled_chars=20,
            duration_ms=2,
        ),
        ev("llm_start", "2026-11-19T10:00:00.520+08:00", iteration=1, model="big"),
        ev("llm", "2026-11-19T10:00:02.000+08:00", iteration=1, kind="loop", model="big",
           stop_reason="tool_use", usage={"in": 1, "out": 1}, duration_ms=1480),
        ev("tool_start", "2026-11-19T10:00:02.010+08:00", tool="list_events", call_id="c1"),
        ev("tool", "2026-11-19T10:00:02.020+08:00", tool="list_events", ok=False,
           args={}, output="Error", call_id="c1", duration_ms=10),
        ev("llm_start", "2026-11-19T10:00:02.030+08:00", iteration=2, model="big"),
        ev("llm", "2026-11-19T10:00:03.500+08:00", iteration=2, kind="loop", model="big",
           stop_reason="end_turn", usage={"in": 1, "out": 1}, duration_ms=1470),
        ev("receipt", "2026-11-19T10:00:03.510+08:00", total_usd=0.002, iterations=2,
           tool_calls=1, tokens_in=2, tokens_out=2, estimate=False),
        ev(
            "turn_end",
            "2026-11-19T10:00:03.520+08:00",
            reply="none",
            iterations=2,
            state="complete",
        ),
    ]


def failed_turn():
    return [
        start(pid=222),
        ev("gate_start", "2026-11-19T10:00:00.100+08:00", model="small"),
        ev("gate", "2026-11-19T10:00:00.300+08:00", decision="skip", reason="x", degraded=False),
        ev(
            "context",
            "2026-11-19T10:00:00.310+08:00",
            recalled=False,
            recalled_chars=0,
            duration_ms=1,
        ),
        ev("llm_start", "2026-11-19T10:00:00.320+08:00", iteration=1, model="big"),
        ev(
            "error",
            "2026-11-19T10:00:01.000+08:00",
            stage="llm",
            error_kind="Timeout",
            message="slow",
        ),
        ev("turn_end", "2026-11-19T10:00:01.010+08:00", reply="", iterations=1, state="failed"),
    ]


FIXTURES = {
    "skip": (skip_turn, {"gate": "skipped", "facts": "skipped", "reply": "done", "tools": "idle"}),
    "tool": (tool_turn, {"gate": "done", "facts": "done", "tools": "failed", "reply": "done"}),
    "failed": (failed_turn, {"model": "failed", "tools": "not-reached", "reply": "not-reached",
                             "observability": "idle"}),
}


def baseline_cues(events):
    """Today's playback: a light at completion, the pre-change component map."""
    out = []
    for event in events:
        nodes = OLD_COMPONENTS.get(event.get("type"))
        if not nodes:
            continue
        out.append({
            "seq": len(out),
            "at": event.get("ts", ""),
            "step": event.get("type"),
            "states": {node: "live" for node in nodes},
            "edges": [],
            "label": "",
            "role": "step",
        })
    return out


def measure(units, events):
    """(start aligned %, phantom lights, silent omissions) for one cue list."""
    starts = [
        event
        for event in events
        if str(event.get("type", "")).endswith("_start")
        and event.get("type") != "turn_start"
    ]
    aligned = 0
    omissions = 0
    for event in starts:
        node = highlight.STAGE_NODES[event["type"][: -len("_start")]]
        found = any(
            cue["at"] == event["ts"] and cue["states"].get(node) == "live" for cue in units
        )
        aligned += 1 if found else 0
        omissions += 0 if found else 1
    phantom = 0
    for cue in units:
        allowed = EXPECTED.get(cue["step"], set())
        if cue["step"] == "gate" and "facts" in cue["states"]:
            allowed = allowed | {"facts", "episodes", "persona"}
        if cue["step"] == "error":
            allowed = set(cue["states"])
        for node in cue["states"]:
            if node not in allowed:
                phantom += 1
    total = len(starts) or 1
    return round(100 * aligned / total), phantom, omissions


def final_score(states, expected):
    checked = 0
    right = 0
    for node, want in expected.items():
        checked += 1
        right += 1 if states.get(node) == want else 0
    return round(100 * right / (checked or 1))


def run():
    rows = []
    for name, (builder, expected) in FIXTURES.items():
        events = builder()
        aligned, phantom, omissions = measure(baseline_cues(events), events)
        old_states = {node["id"]: "idle" for node in NODES}
        rows.append(("baseline", name, aligned, phantom, omissions,
                     final_score(old_states, expected)))
        units = highlight.cues(events, memory_enabled=True)
        aligned, phantom, omissions = measure(units, events)
        rows.append(("candidate", name, aligned, phantom, omissions,
                     final_score(highlight.final_states(events, memory_enabled=True), expected)))
    return rows


def summary(rows):
    def avg(which, index):
        values = [row[index] for row in rows if row[0] == which]
        return round(sum(values) / (len(values) or 1))

    return {
        "baseline": {
            "start_aligned": avg("baseline", 2),
            "phantom": sum(row[3] for row in rows if row[0] == "baseline"),
            "omissions": sum(row[4] for row in rows if row[0] == "baseline"),
            "final_state_ok": avg("baseline", 5),
        },
        "candidate": {
            "start_aligned": avg("candidate", 2),
            "phantom": sum(row[3] for row in rows if row[0] == "candidate"),
            "omissions": sum(row[4] for row in rows if row[0] == "candidate"),
            "final_state_ok": avg("candidate", 5),
        },
    }


def test_correspondence_improves_and_reaches_the_bar(capsys):
    rows = run()
    scores = summary(rows)
    before, after = scores["baseline"], scores["candidate"]
    print("correspondence   baseline   post-change")
    print(f"start aligned    {before['start_aligned']}%        {after['start_aligned']}%")
    print(f"phantom lights   {before['phantom']}          {after['phantom']}")
    print(f"silent omissions {before['omissions']}          {after['omissions']}")
    print(f"final state ok   {before['final_state_ok']}%        {after['final_state_ok']}%")
    assert scores["candidate"]["start_aligned"] == 100
    assert scores["candidate"]["phantom"] == 0
    assert scores["candidate"]["omissions"] == 0
    assert scores["candidate"]["final_state_ok"] == 100
    assert scores["baseline"]["start_aligned"] < 100
