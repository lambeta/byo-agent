"""Trajectory v1: envelope, ordering, version and the unfinished turn."""

from __future__ import annotations

import json

from scripted import script, text, tool_call

from byo.app import Agent
from byo.ops.observability import build_turn, group_turns, read_events
from byo.ops.trajectory import Trajectory


def run_one(settings, *responses):
    agent = Agent(settings, adapter=script(*responses), memory=None)
    result = agent.respond("what is on friday", source="cli")
    agent.close()
    return result


def test_a_turn_writes_the_documented_events(settings):
    run_one(settings, tool_call("list_events", {"start": "2026-11-20"}), text("Nothing booked."))
    events, skipped = read_events(settings.home, "all")
    kinds = [event["type"] for event in events]
    assert skipped == 0
    assert kinds[0] == "turn_start"
    assert kinds[-1] == "turn_end"
    assert kinds.count("turn_start") == 1
    assert kinds[-2] == "receipt"
    assert {"llm", "tool"} <= set(kinds)
    start = events[0]
    assert start["trajectory_version"] == 1
    assert start["turn_id"].startswith("t_")
    assert len(start["turn_id"]) == 18
    for event in events:
        assert event["turn_id"] == start["turn_id"]
        assert "T" in event["ts"]


def test_tool_record_carries_args_output_and_duration(settings):
    run_one(settings, tool_call("list_events", {"start": "2026-11-20"}), text("ok"))
    events, _ = read_events(settings.home, "all")
    tool = next(event for event in events if event["type"] == "tool")
    assert tool["tool"] == "list_events"
    assert tool["args"] == {"start": "2026-11-20"}
    assert tool["ok"] is True
    assert isinstance(tool["duration_ms"], int)


def test_activity_record_is_turn_less_redacted_and_ignored_as_a_step(settings):
    sink = Trajectory(settings)
    sink.start("a turn", source="cli")
    turn_id = sink.turn_id
    sink.end("ok", 1)

    event = sink.record_activity(
        "memory_change",
        action="add",
        outcome="ok",
        fact_id=3,
        code=None,
        field=None,
        warning=None,
        detail="sk-ant-abcdefgh12345678",
    )

    assert event["turn_id"] == ""
    assert event["source"] == "dashboard"
    assert sink.turn_id == turn_id
    assert "sk-ant-" not in event["detail"]
    assert "[redacted]" in event["detail"]

    events, skipped = read_events(settings.home, "all")
    assert skipped == 0
    changes = [record for record in events if record["type"] == "memory_change"]
    assert len(changes) == 1
    turns = group_turns(events)
    assert len(turns) == 1
    assert all(step["kind"] != "memory_change" for step in build_turn(turns[0])["steps"])


def test_activity_record_before_any_turn_does_not_mint_a_turn(settings):
    sink = Trajectory(settings)
    sink.record_activity("memory_change", action="edit", outcome="refused", code="fact_conflict")
    events, _ = read_events(settings.home, "all")
    assert [record["type"] for record in events] == ["memory_change"]
    assert group_turns(events) == []


def test_unfinished_turn_does_not_swallow_the_next_one(settings):
    path = settings.trajectories_dir
    path.mkdir(parents=True, exist_ok=True)
    (path / "2026-11-18.jsonl").write_text(
        json.dumps(
            {
                "type": "turn_start",
                "turn_id": "t_1",
                "user_message": "old",
                "ts": "2026-11-18T10:00:00.000+08:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    run_one(settings, text("fresh"))
    events, _ = read_events(settings.home, "all")
    turns = group_turns(events)
    assert len(turns) == 2
    assert turns[0]["unfinished"] is True
    assert turns[1]["user_message"] == "what is on friday"
    assert build_turn(turns[0])["state"] == "unfinished"
    assert build_turn(turns[1])["state"] == "complete"
