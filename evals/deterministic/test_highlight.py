"""The correspondence: records in, ordered cues and settled states out."""

from __future__ import annotations

from byo.ops.highlight import cues, final_states, turn_state


def base(turn="t_hl", source="cli", pid=111):
    return {
        "type": "turn_start",
        "turn_id": turn,
        "ts": "2026-11-19T10:00:00.000+08:00",
        "source": source,
        "user_message": "hi",
        "pid": pid,
    }


def ev(type_, ts, turn="t_hl", **fields):
    return {"type": type_, "turn_id": turn, "ts": ts, **fields}


def skipped_turn():
    return [
        base(),
        ev("gate_start", "2026-11-19T10:00:00.100+08:00", model="small"),
        ev(
            "gate",
            "2026-11-19T10:00:01.200+08:00",
            decision="skip",
            reason="no memory needed",
            degraded=False,
        ),
        ev(
            "context",
            "2026-11-19T10:00:01.210+08:00",
            recalled=False,
            recalled_chars=0,
            duration_ms=3,
        ),
        ev("llm_start", "2026-11-19T10:00:01.220+08:00", iteration=1, model="big"),
        ev("llm", "2026-11-19T10:00:03.700+08:00", iteration=1, kind="loop", model="big",
           stop_reason="end_turn", usage={"in": 10, "out": 5}, duration_ms=2480),
        ev(
            "receipt",
            "2026-11-19T10:00:03.710+08:00",
            total_usd=0.001,
            tokens_in=10,
            tokens_out=5,
            iterations=1,
            tool_calls=0,
            estimate=False,
        ),
        ev("turn_end", "2026-11-19T10:00:03.720+08:00", reply="hi", iterations=1, state="complete"),
    ]


def tool_turn():
    return [
        base(),
        ev("gate_start", "2026-11-19T10:00:00.100+08:00", model="small"),
        ev(
            "gate",
            "2026-11-19T10:00:00.900+08:00",
            decision="retrieve",
            reason="about alex",
            degraded=False,
        ),
        ev(
            "context",
            "2026-11-19T10:00:00.910+08:00",
            recalled=True,
            recalled_chars=40,
            duration_ms=2,
        ),
        ev("llm_start", "2026-11-19T10:00:00.920+08:00", iteration=1, model="big"),
        ev("llm", "2026-11-19T10:00:02.500+08:00", iteration=1, kind="loop", model="big",
           stop_reason="tool_use", usage={"in": 10, "out": 5}, duration_ms=1580),
        ev("tool_start", "2026-11-19T10:00:02.510+08:00", tool="list_events", call_id="c1"),
        ev("tool", "2026-11-19T10:00:02.520+08:00", tool="list_events", ok=False,
           args={}, output="Error: boom", call_id="c1", duration_ms=10),
        ev("llm_start", "2026-11-19T10:00:02.530+08:00", iteration=2, model="big"),
        ev("llm", "2026-11-19T10:00:04.000+08:00", iteration=2, kind="loop", model="big",
           stop_reason="end_turn", usage={"in": 20, "out": 8}, duration_ms=1470),
        ev(
            "receipt",
            "2026-11-19T10:00:04.010+08:00",
            total_usd=0.002,
            tokens_in=30,
            tokens_out=13,
            iterations=2,
            tool_calls=1,
            estimate=False,
        ),
        ev(
            "turn_end",
            "2026-11-19T10:00:04.020+08:00",
            reply="nothing",
            iterations=2,
            state="complete",
        ),
    ]


def test_a_step_lights_at_its_start_and_settles_at_its_end():
    units = cues(tool_turn(), memory_enabled=True)
    starts = [cue for cue in units if cue["step"] == "llm_start"]
    assert [cue["at"] for cue in starts] == [
        "2026-11-19T10:00:00.920+08:00",
        "2026-11-19T10:00:02.530+08:00",
    ]
    assert all(cue["states"] == {"model": "live"} for cue in starts)
    settles = [cue for cue in units if cue["step"] == "llm"]
    assert [cue["at"] for cue in settles] == [
        "2026-11-19T10:00:02.500+08:00",
        "2026-11-19T10:00:04.000+08:00",
    ]
    assert [cue["states"]["model"] for cue in settles] == ["done", "done"]


def test_the_last_model_call_is_labelled_final_answer():
    units = cues(tool_turn(), memory_enabled=True)
    settles = [cue for cue in units if cue["step"] == "llm"]
    assert settles[0]["label"] == "loop 1 · model answered"
    assert settles[1]["label"] == "final answer"


def test_sequence_numbers_are_strictly_increasing():
    units = cues(tool_turn(), memory_enabled=True)
    assert [cue["seq"] for cue in units] == list(range(len(units)))


def test_the_context_lights_once_and_never_on_a_model_call():
    units = cues(tool_turn(), memory_enabled=True)
    context = [cue for cue in units if "context" in cue["states"]]
    assert [cue["states"]["context"] for cue in context] == ["done"]
    for cue in units:
        if cue["step"] == "llm_start":
            assert "context" not in cue["states"]


def test_edges_are_the_full_live_set_for_each_cue():
    units = cues(tool_turn(), memory_enabled=True)
    model = next(cue for cue in units if cue["step"] == "llm_start")
    assert model["edges"] == ["e-context-model"]
    tool = next(cue for cue in units if cue["step"] == "tool_start")
    assert tool["edges"] == ["e-model-tools"]
    tool_end = next(cue for cue in units if cue["step"] == "tool")
    assert tool_end["edges"] == ["e-tools-model"]
    assert all("edge_state" not in cue for cue in units)


def test_a_skipped_decision_marks_the_memory_path_skipped():
    states = [cue for cue in cues(skipped_turn(), memory_enabled=True) if cue["step"] == "gate"]
    flat = {}
    for cue in states:
        flat.update(cue["states"])
    assert flat["gate"] == "skipped"
    assert flat["facts"] == flat["episodes"] == flat["persona"] == "skipped"
    assert any("memory skipped" in cue["label"] for cue in states)


def test_a_retrieval_lights_the_memory_path():
    units = cues(tool_turn(), memory_enabled=True)
    memory = [cue for cue in units if "facts" in cue["states"]]
    assert [cue["states"]["facts"] for cue in memory] == ["done"]
    assert memory[0]["edges"] == ["e-gate-facts", "e-gate-episodes", "e-gate-persona"]


def test_tool_labels_carry_the_running_count():
    units = cues(tool_turn(), memory_enabled=True)
    start = next(cue for cue in units if cue["step"] == "tool_start")
    assert start["label"] == "tool list_events · 1 tool call"
    failed = next(cue for cue in units if cue["step"] == "tool")
    assert failed["states"]["tools"] == "failed"
    assert "failed" in failed["label"]


def test_the_trajectory_mark_spans_the_turn():
    units = cues(skipped_turn(), memory_enabled=True)
    record_live = [cue for cue in units if cue["states"].get("record") == "live"]
    record_done = [cue for cue in units if cue["states"].get("record") == "done"]
    assert len(record_live) == 1 and record_live[0]["role"] == "step"
    assert len(record_done) == 1


def test_an_unknown_record_is_named_not_lit():
    events = skipped_turn()
    events.insert(-1, ev("future_thing", "2026-11-19T10:00:03.715+08:00", payload=1))
    units = cues(events, memory_enabled=True)
    unknown = [cue for cue in units if cue["step"] == "future_thing"]
    assert unknown and unknown[0]["states"] == {}
    assert "unmapped step" in unknown[0]["label"]


def test_every_cue_names_a_real_node_and_edge():
    from byo.ops.map import graph

    data = graph()
    nodes = {node["id"] for node in data["nodes"]}
    edges = {edge["id"] for edge in data["edges"]}
    for units in (cues(skipped_turn()), cues(tool_turn())):
        for cue in units:
            assert set(cue["states"]) <= nodes
            assert set(cue["edges"]) <= edges


def test_final_states_distinguish_skipped_not_reached_and_idle():
    states = final_states(skipped_turn(), memory_enabled=True)
    assert states["gate"] == "skipped"
    assert states["facts"] == states["episodes"] == states["persona"] == "skipped"
    assert states["record"] == "done"
    assert states["observability"] == "idle"
    assert states["tools"] == "idle"
    assert states["reply"] == "done"


def test_final_states_after_a_failed_tool():
    states = final_states(tool_turn(), memory_enabled=True)
    assert states["tools"] == "failed"
    assert states["model"] == "done"
    assert states["reply"] == "done"


def test_final_states_after_a_failure_cut_the_path():
    events = [
        base(),
        ev("gate_start", "2026-11-19T10:00:00.100+08:00", model="small"),
        ev("gate", "2026-11-19T10:00:00.200+08:00", decision="skip", reason="x", degraded=False),
        ev(
            "context",
            "2026-11-19T10:00:00.210+08:00",
            recalled=False,
            recalled_chars=0,
            duration_ms=1,
        ),
        ev("llm_start", "2026-11-19T10:00:00.220+08:00", iteration=1, model="big"),
        ev(
            "error",
            "2026-11-19T10:00:01.000+08:00",
            stage="llm",
            error_kind="Timeout",
            message="slow",
        ),
        ev("turn_end", "2026-11-19T10:00:01.010+08:00", reply="", iterations=1, state="failed"),
    ]
    states = final_states(events, memory_enabled=True)
    assert states["model"] == "failed"
    assert states["tools"] == "not-reached"
    assert states["reply"] == "not-reached"
    assert states["observability"] == "idle"


def test_memory_disabled_leaves_the_gate_idle():
    events = [e for e in skipped_turn() if e["type"] not in ("gate_start", "gate")]
    states = final_states(events, memory_enabled=False)
    assert states["gate"] == "idle"
    assert states["facts"] == "idle"


def test_turn_state_running_interrupted_complete():
    assert turn_state(skipped_turn(), is_alive=lambda pid: True) == "complete"
    open_turn = skipped_turn()[:-1]
    assert turn_state(open_turn, is_alive=lambda pid: True) == "running"
    assert turn_state(open_turn, is_alive=lambda pid: False) == "interrupted"
    legacy = [e for e in open_turn if e["type"] != "turn_start"] + [base(pid=None)]
    assert turn_state(legacy, is_alive=lambda pid: True) == "interrupted"


def test_turn_state_survives_a_consolidation_error():
    events = skipped_turn()
    events.insert(
        -1,
        ev(
            "error",
            "2026-11-19T10:00:03.715+08:00",
            stage="consolidation",
            error_kind="Internal",
            message="disk on fire",
        ),
    )
    assert turn_state(events, is_alive=lambda pid: True) == "complete"
    fatal = [
        {**e, "stage": "llm"} if e["type"] == "error" else e for e in events
    ]
    assert turn_state(fatal, is_alive=lambda pid: True) == "failed"


def test_a_legacy_turn_invents_no_running_stage():
    events = [e for e in skipped_turn() if not e["type"].endswith("_start")]
    units = cues(events, memory_enabled=True)
    stages = {"gate", "context", "model", "tools", "consolidation", "facts"}
    for cue in units:
        for node, state in cue["states"].items():
            if node in stages:
                assert state != "live", (node, cue["step"])
