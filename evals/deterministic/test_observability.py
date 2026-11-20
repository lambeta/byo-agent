"""Projections over the trajectory: turns, steps, spend."""

from __future__ import annotations

import json

from byo.ops import observability
from byo.ops.observability import build_turn, group_turns, read_events, spend


def write(settings, events):
    settings.trajectories_dir.mkdir(parents=True, exist_ok=True)
    path = settings.trajectories_dir / "2026-11-18.jsonl"
    path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")


def sample(turn_id="t_abc"):
    return [
        {
            "type": "turn_start",
            "turn_id": turn_id,
            "user_message": "hi",
            "source": "dashboard",
            "session_id": "default",
            "ts": "2026-11-18T10:00:00.000+08:00",
        },
        {
            "type": "gate",
            "turn_id": turn_id,
            "decision": "retrieve",
            "reason": "about a person",
            "ts": "2026-11-18T10:00:00.100+08:00",
        },
        {
            "type": "llm",
            "turn_id": turn_id,
            "iteration": 1,
            "kind": "loop",
            "model": "claude-sonnet-4-5",
            "usage": {"in": 100, "out": 20},
            "duration_ms": 900,
            "ts": "2026-11-18T10:00:01.000+08:00",
        },
        {
            "type": "tool",
            "turn_id": turn_id,
            "tool": "list_events",
            "args": {"start": "x"},
            "output": "none",
            "ok": True,
            "duration_ms": 4,
            "ts": "2026-11-18T10:00:01.100+08:00",
        },
        {
            "type": "receipt",
            "turn_id": turn_id,
            "total_usd": 0.0006,
            "tokens_in": 100,
            "tokens_out": 20,
            "iterations": 1,
            "tool_calls": 1,
            "estimate": False,
            "ts": "2026-11-18T10:00:01.200+08:00",
        },
        {
            "type": "turn_end",
            "turn_id": turn_id,
            "reply": "done",
            "iterations": 1,
            "ts": "2026-11-18T10:00:01.300+08:00",
        },
    ]


def test_steps_and_state(settings):
    write(settings, sample())
    events, skipped = read_events(settings.home, "all")
    assert skipped == 0
    turns = group_turns(events)
    assert len(turns) == 1
    payload = build_turn(turns[0])
    assert payload["state"] == "complete"
    assert payload["gate"]["decision"] == "retrieve"
    assert [step["kind"] for step in payload["steps"]] == ["gate", "llm", "tool"]
    assert payload["steps"][2]["tool"] == "list_events"
    assert payload["receipt"]["usd"] == 0.0006


def test_a_retry_marker_is_not_a_step(settings):
    events = sample()
    events.insert(
        2,
        {
            "type": "retry",
            "turn_id": "t_abc",
            "stage": "llm",
            "model": "claude-sonnet-4-5",
            "ts": "2026-11-18T10:00:00.900+08:00",
        },
    )
    write(settings, events)
    payload = build_turn(group_turns(read_events(settings.home, "all")[0])[0])
    assert payload["state"] == "complete"
    assert [step["kind"] for step in payload["steps"]] == ["gate", "llm", "tool"]


def test_failure_state(settings):
    events = sample()
    events.insert(
        3,
        {
            "type": "error",
            "turn_id": "t_abc",
            "stage": "llm",
            "error_kind": "Refused",
            "message": "no",
            "ts": "2026-11-18T10:00:00.900+08:00",
        },
    )
    write(settings, events)
    payload = build_turn(group_turns(read_events(settings.home, "all")[0])[0])
    assert payload["state"] == "failed"
    assert any(step["kind"] == "error" for step in payload["steps"])


def test_a_consolidation_error_does_not_fail_the_turn(settings):
    events = sample()
    events.insert(
        3,
        {
            "type": "error",
            "turn_id": "t_abc",
            "stage": "consolidation",
            "error_kind": "Internal",
            "message": "disk on fire",
            "ts": "2026-11-18T10:00:00.900+08:00",
        },
    )
    write(settings, events)
    payload = build_turn(group_turns(read_events(settings.home, "all")[0])[0])
    assert payload["state"] == "complete"
    assert any(step["kind"] == "error" for step in payload["steps"])


def test_spend_totals(settings):
    write(settings, sample())
    events, _ = read_events(settings.home, "all")
    totals = spend(events)
    assert totals["total_usd"] == 0.0006
    assert totals["by_day"] == [{"day": "2026-11-18", "usd": 0.0006}]


def test_llm_steps_keep_the_model_text(settings):
    from scripted import script, text

    from byo.app import Agent

    agent = Agent(settings, adapter=script(text("hello there")), memory=None)
    agent.respond("hi")
    payload = observability.payload(settings.home, "all")
    llm = [step for step in payload["turns"][0]["steps"] if step["kind"] == "llm"][0]
    assert llm["text"] == "hello there"
    agent.close()


def test_read_events_counts_bad_lines_and_skips_blank_ones(settings):
    settings.trajectories_dir.mkdir(parents=True, exist_ok=True)
    path = settings.trajectories_dir / "2026-11-18.jsonl"
    path.write_text(
        "\n"
        "not json\n"
        '["not", "an", "object"]\n'
        '{"type": "turn_start", "turn_id": "t_ok", "ts": "2026-11-18T10:00:00.000+08:00"}\n',
        encoding="utf-8",
    )
    events, skipped = read_events(settings.home, "all")
    assert [event["turn_id"] for event in events] == ["t_ok"]
    assert skipped == 2


def test_read_events_survives_an_unreadable_file(settings):
    settings.trajectories_dir.mkdir(parents=True, exist_ok=True)
    # A directory named like a day file makes read_text raise IsADirectoryError,
    # an OSError the reader must skip over instead of dying.
    (settings.trajectories_dir / "2026-11-17.jsonl").mkdir()
    write(settings, sample())
    events, skipped = read_events(settings.home, "all")
    assert [event["turn_id"] for event in events] == ["t_abc"] * len(sample())
    assert skipped == 0


def test_a_consolidation_event_projects_as_a_memory_write_step(settings):
    events = sample()
    events.insert(
        3,
        {
            "type": "consolidation",
            "turn_id": "t_abc",
            "new_facts": 2,
            "kept": [{"subject": "alex", "content": "prefers mornings"}],
            "ts": "2026-11-18T10:00:00.900+08:00",
        },
    )
    write(settings, events)
    payload = build_turn(group_turns(read_events(settings.home, "all")[0])[0])
    step = next(item for item in payload["steps"] if item["kind"] == "memory_write")
    assert step["new_facts"] == 2
    assert step["kept"] == [{"subject": "alex", "content": "prefers mornings"}]
