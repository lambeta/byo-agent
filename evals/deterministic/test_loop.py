"""The loop: guardrails, tool dispatch and what the observer sees."""

from __future__ import annotations

from scripted import script, text, tool_call

from byo.loop.agent import run_loop
from byo.loop.types import Message
from byo.tools.registry import Tool, ToolRegistry

ECHO_SCHEMA = {"type": "object", "properties": {"value": {"type": "string"}}}


def registry(calls: list[str], explode: bool = False) -> ToolRegistry:
    reg = ToolRegistry()

    def echo(value: str) -> str:
        calls.append(value)
        if explode:
            raise RuntimeError("tool broke")
        return f"echo:{value}"

    reg.register(Tool("echo", "echo it", ECHO_SCHEMA, echo))
    return reg


def collect():
    events: list[tuple[str, dict]] = []
    return events, (lambda kind, event: events.append((kind, event)))


def test_text_only_turn():
    adapter = script(text("hello"))
    result = run_loop(adapter, "m", "sys", [Message.user("hi")], ToolRegistry())
    assert result.reply == "hello"
    assert result.iterations == 1
    assert result.limit_reached is False
    assert result.tool_calls == []


def test_tool_turn_feeds_the_result_back():
    calls: list[str] = []
    adapter = script(tool_call("echo", {"value": "x"}), text("done"))
    events, observer = collect()
    result = run_loop(adapter, "m", "sys", [Message.user("hi")], registry(calls), observer=observer)
    assert result.reply == "done"
    assert calls == ["x"]
    assert result.tool_calls[0]["output"] == "echo:x"
    assert [kind for kind, _ in events] == [
        "llm_start",
        "llm",
        "tool_start",
        "tool",
        "llm_start",
        "llm",
    ]
    second = adapter.calls[1]
    last = second.messages[-1]
    assert last.blocks[0].content == "echo:x"


def test_two_tool_calls_in_one_response():
    calls: list[str] = []
    adapter = script(
        {
            "tool_calls": [
                {"id": "a", "name": "echo", "args": {"value": "1"}},
                {"id": "b", "name": "echo", "args": {"value": "2"}},
            ],
            "stop_reason": "tool_use",
            "usage": {"in": 5, "out": 5},
        },
        text("done"),
    )
    result = run_loop(adapter, "m", "sys", [Message.user("hi")], registry(calls))
    assert calls == ["1", "2"]
    assert len(result.tool_calls) == 2


def test_tool_failure_is_text_not_a_crash():
    adapter = script(tool_call("echo", {"value": "x"}), text("explained"))
    result = run_loop(adapter, "m", "sys", [Message.user("hi")], registry([], explode=True))
    assert result.reply == "explained"
    assert result.tool_calls[0]["output"].startswith("Error:")
    assert result.tool_calls[0]["ok"] is False


def test_unknown_tool_is_an_error_text():
    adapter = script(tool_call("nope", {}), text("ok"))
    result = run_loop(adapter, "m", "sys", [Message.user("hi")], registry([]))
    assert "unknown tool 'nope'" in result.tool_calls[0]["output"]


def test_step_limit_makes_one_tools_off_call():
    calls: list[str] = []
    adapter = script(tool_call("echo", {"value": "x"}), text("final answer"))
    events, observer = collect()
    result = run_loop(
        adapter,
        "m",
        "sys",
        [Message.user("hi")],
        registry(calls),
        max_iterations=1,
        observer=observer,
    )
    assert result.limit_reached is True
    assert result.reply == "final answer"
    final = adapter.calls[-1]
    assert final.tool_choice == "none"
    llm_kinds = [event.get("kind") for kind, event in events if kind == "llm"]
    assert llm_kinds == ["loop", "final"]


def test_a_model_script_fixture_replays():
    from scripted import ScriptedAdapter, load_script

    script_data = load_script("two-step")
    adapter = ScriptedAdapter(script_data)
    calls: list[str] = []
    result = run_loop(adapter, "m", "sys", [Message.user("hi")], registry(calls))
    assert result.reply == "done"
    assert calls == ["x"]


def test_trim_runs_before_second_iteration_only():
    calls: list[str] = []
    seen: list[int] = []
    adapter = script(tool_call("echo", {"value": "x"}), text("done"))

    def trim(messages):
        seen.append(len(messages))

    run_loop(adapter, "m", "sys", [Message.user("hi")], registry(calls), trim=trim)
    assert len(seen) == 1
