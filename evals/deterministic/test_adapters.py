"""Adapter conformance: the protocol, the mappings, and the vendor boundary."""

from __future__ import annotations

import pathlib

import pytest
from scripted import script, text, tool_call

from byo.loop.adapters import AnthropicAdapter, OpenAIAdapter, _normalize
from byo.loop.types import (
    BadResponse,
    Message,
    RateLimited,
    Refused,
    Request,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
)


def request(messages=None, tools=()) -> Request:
    return Request(
        model="m",
        system="sys",
        messages=tuple(messages or (Message.user("hi"),)),
        tools=tuple(tools),
    )


def test_scripted_text_turn():
    response = script(text("hello", {"in": 3, "out": 4})).complete(request())
    assert response.text() == "hello"
    assert response.stop_reason == "end_turn"
    assert (response.usage.input_tokens, response.usage.output_tokens) == (3, 4)


def test_scripted_tool_call_turn():
    response = script(tool_call("echo", {"value": "x"})).complete(request())
    calls = response.tool_calls()
    assert len(calls) == 1
    assert calls[0].name == "echo"
    assert calls[0].args == {"value": "x"}
    assert response.stop_reason == "tool_use"


def test_scripted_stream_yields_deltas_and_returns_response():
    adapter = script(text("one two"))
    seen: list[str] = []
    response = adapter.stream(request(), on_delta=seen.append)
    assert response.text() == "one two"
    assert "".join(seen).split() == ["one", "two"]


def test_scripted_exhaustion_is_a_typed_error():
    adapter = script(text("only once"))
    adapter.complete(request())
    with pytest.raises(BadResponse):
        adapter.complete(request())


def test_anthropic_message_mapping():
    messages = (
        Message.user("hi"),
        Message("assistant", (TextBlock("hello"), ToolCallBlock("t1", "echo", {"value": "x"}))),
        Message("user", (ToolResultBlock("t1", "echo:x"),)),
    )
    mapped = AnthropicAdapter._messages(messages)
    assert mapped[0] == {"role": "user", "content": [{"type": "text", "text": "hi"}]}
    assert mapped[1]["content"][1] == {
        "type": "tool_use",
        "id": "t1",
        "name": "echo",
        "input": {"value": "x"},
    }
    assert mapped[2]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "t1",
        "content": "echo:x",
    }


def test_openai_message_mapping():
    messages = (
        Message.user("hi"),
        Message("assistant", (TextBlock("hello"), ToolCallBlock("t1", "echo", {"value": "x"}))),
        Message("user", (ToolResultBlock("t1", "echo:x"),)),
    )
    mapped = OpenAIAdapter._messages(request(messages))
    assert mapped[0]["role"] == "system"
    assert mapped[1] == {"role": "user", "content": "hi"}
    assert mapped[2]["tool_calls"][0]["function"]["name"] == "echo"
    assert mapped[3] == {"role": "tool", "tool_call_id": "t1", "content": "echo:x"}


def test_error_taxonomy():
    class Boom(Exception):
        status_code = 400

    class Slow(Exception):
        status_code = 429

    assert isinstance(_normalize(Boom("no")), Refused)
    assert isinstance(_normalize(Slow("wait")), RateLimited)
    assert isinstance(_normalize(ValueError("weird")), BadResponse)


def test_loop_module_imports_no_vendor_sdk():
    source = pathlib.Path("byo/loop/agent.py").read_text(encoding="utf-8")
    assert "anthropic" not in source
    assert "openai" not in source
