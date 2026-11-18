"""A defect is reproducible from its trajectory alone (FR-037)."""

from __future__ import annotations

import io

from rich.console import Console
from scripted import script, text, tool_call

from byo.app import Agent
from byo.ops.show_trajectory import render


def failing_turn(settings):
    return script(
        tool_call("create_event", {"title": "Catch-up", "start": "friday"}),
        text("I could not book it: start must be ISO 8601."),
    )


def test_the_trace_names_the_failing_step_and_replays(settings):
    first = Agent(settings, adapter=failing_turn(settings), memory=None)
    result = first.respond("book a catch-up on friday")
    assert result.tool_calls[0]["ok"] is False

    events = list(first.trajectory.events)
    start = next(event for event in events if event["type"] == "turn_start")
    failed_tool = next(event for event in events if event["type"] == "tool")
    assert failed_tool["ok"] is False
    assert "ISO 8601" in failed_tool["output"]

    buffer = io.StringIO()
    render(
        first.trajectory.path_for(
            start["ts"] and __import__("datetime").datetime.fromisoformat(start["ts"])
        ),
        Console(file=buffer, width=200),
    )
    assert "[failed]" in buffer.getvalue()

    second = Agent(settings, adapter=failing_turn(settings), memory=None)
    again = second.respond(start["user_message"])
    assert again.reply == result.reply
    assert again.tool_calls[0]["ok"] is False
