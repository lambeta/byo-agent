"""The record gains start markers without changing any projection."""

from __future__ import annotations

import json
import os

import pytest
from scripted import script, text, tool_call

from byo.app import Agent
from byo.ops import observability
from byo.ops.trajectory import Trajectory

GATE_SKIP = {
    "text": '{"needs_memory": false, "reason": "no memory needed"}',
    "usage": {"in": 5, "out": 2},
}


def turn_events(settings):
    path = sorted(settings.trajectories_dir.glob("*.jsonl"))[-1]
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def kinds(events):
    return [event["type"] for event in events]


def test_start_records_bracket_each_step(settings):
    agent = Agent(
        settings,
        adapter=script(tool_call("list_events", {"start": "2026-11-20"}), text("nothing")),
        memory=None,
    )
    agent.respond("what is on friday")
    order = kinds(turn_events(settings))
    assert order[0] == "turn_start" and order[-1] == "turn_end"
    assert order.index("context") < order.index("llm_start")
    assert order.index("llm_start") < order.index("llm")
    assert order.index("tool_start") < order.index("tool")
    assert order.count("llm_start") == order.count("llm") == 2
    assert order.count("tool_start") == order.count("tool") == 1
    agent.close()


def test_gate_start_precedes_the_decision(settings):
    agent = Agent(settings, adapter=script(GATE_SKIP, text("hello")))
    agent.respond("hi")
    events = turn_events(settings)
    order = kinds(events)
    assert order.index("gate_start") < order.index("gate")
    gate = next(event for event in events if event["type"] == "gate")
    assert gate["degraded"] is False
    agent.close()


def test_turn_start_records_the_writer_pid(settings):
    agent = Agent(settings, adapter=script(text("hello")), memory=None)
    agent.respond("hi")
    start = turn_events(settings)[0]
    assert start["type"] == "turn_start"
    assert start["pid"] == os.getpid()
    agent.close()


def test_a_raising_turn_still_ends(settings):
    class Exploding:
        def complete(self, request):
            raise RuntimeError("boom")

    agent = Agent(settings, adapter=Exploding(), memory=None)
    with pytest.raises(RuntimeError):
        agent.respond("hi")
    events = turn_events(settings)
    assert kinds(events)[-2:] == ["error", "turn_end"]
    assert events[-2]["stage"] == "turn"
    assert events[-1]["state"] == "failed"
    agent.close()


def test_start_records_carry_no_results(settings):
    agent = Agent(
        settings,
        adapter=script(tool_call("list_events", {"start": "2026-11-20"}), text("nothing")),
        memory=None,
    )
    agent.respond("what is on friday")
    for event in turn_events(settings):
        if event["type"].endswith("_start") or event["type"] == "context":
            assert "usage" not in event
            assert "total_usd" not in event
            assert "output" not in event
            assert "args" not in event
    agent.close()


def test_the_model_text_is_recorded_so_history_can_keep_it(settings):
    agent = Agent(settings, adapter=script(text("the answer")), memory=None)
    agent.respond("hi")
    llm = next(event for event in turn_events(settings) if event["type"] == "llm")
    assert llm["text"] == "the answer"
    agent.close()


def test_start_records_are_redacted(settings):
    settings.ensure_home()
    sink = Trajectory(settings)
    sink.start("hi", source="test")
    sink.begin("llm_start", model="sk-ant-abcdefgh12345678", note="token=abc")
    path = sorted(settings.trajectories_dir.glob("*.jsonl"))[-1]
    line = path.read_text(encoding="utf-8").splitlines()[-1]
    assert "sk-ant-" not in line
    assert "[redacted]" in line


def test_projections_ignore_start_records(settings):
    agent = Agent(
        settings,
        adapter=script(
            GATE_SKIP,
            tool_call("list_events", {"start": "2026-11-20"}),
            text("nothing"),
        ),
    )
    agent.respond("what is on friday")
    events, skipped = observability.read_events(settings.home, "all")
    turn = observability.build_turn(observability.group_turns(events)[0])
    assert [step["kind"] for step in turn["steps"]] == ["gate", "llm", "tool", "llm"]
    assert turn["receipt"]["iterations"] == 2
    assert observability.spend(events)["total_usd"] == turn["receipt"]["usd"]
    assert skipped == 0
    agent.close()


def test_consolidation_start_precedes_the_note(settings):
    settings.consolidate_every = 1
    agent = Agent(
        settings,
        adapter=script(
            GATE_SKIP,
            text("noted"),
            {
                "text": (
                    '{"facts": [{"subject": "alex", "content": "likes fridays"}], '
                    '"episode": "planned friday"}'
                ),
                "usage": {"in": 10, "out": 10},
            },
        ),
    )
    agent.respond("alex likes fridays")
    order = kinds(turn_events(settings))
    assert "consolidation_start" in order
    assert order.index("consolidation_start") < order.index("consolidation")
    agent.close()
