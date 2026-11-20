"""Adapter conformance: the protocol, the mappings, and the vendor boundary."""

from __future__ import annotations

import pathlib
from types import SimpleNamespace

import pytest
from scripted import script, text, tool_call

from byo.config import Settings
from byo.loop.adapters import AnthropicAdapter, OpenAIAdapter, _normalize, build_adapter
from byo.loop.types import (
    BadResponse,
    Message,
    RateLimited,
    Refused,
    Request,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
    ToolSpec,
    Transport,
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


# --- Vendor adapters, driven through injected fake clients (no SDK, no network) ---


def anthropic_message(text_value="hi", tool=None, stop="end_turn", usage=(3, 4)):
    blocks = []
    if text_value:
        blocks.append(SimpleNamespace(type="text", text=text_value))
    if tool:
        blocks.append(
            SimpleNamespace(type="tool_use", id=tool[0], name=tool[1], input=tool[2])
        )
    return SimpleNamespace(
        content=blocks,
        stop_reason=stop,
        usage=SimpleNamespace(input_tokens=usage[0], output_tokens=usage[1]),
    )


class FakeAnthropicClient:
    def __init__(self, message=None, exc=None, deltas=()):
        self.message = message
        self.exc = exc
        self.deltas = list(deltas)
        self.params: dict = {}
        self.messages = self

    def create(self, **params):
        self.params = params
        if self.exc:
            raise self.exc
        return self.message

    def stream(self, **params):
        self.params = params
        if self.exc:
            raise self.exc
        client = self

        class FakeStream:
            text_stream = client.deltas

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def get_final_message(self):
                return client.message

        return FakeStream()


def openai_chunk(content=None, calls=(), usage=None):
    delta = SimpleNamespace(
        content=content,
        tool_calls=[
            SimpleNamespace(
                index=call.get("index", 0),
                id=call.get("id"),
                function=SimpleNamespace(
                    name=call.get("name"), arguments=call.get("arguments")
                ),
            )
            for call in calls
        ],
    )
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)], usage=usage)


def openai_completion(content=None, calls=(), usage=(5, 7)):
    message = SimpleNamespace(
        content=content,
        tool_calls=[
            SimpleNamespace(
                id=call[0],
                function=SimpleNamespace(name=call[1], arguments=call[2]),
            )
            for call in calls
        ],
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(prompt_tokens=usage[0], completion_tokens=usage[1]),
    )


class FakeOpenAIClient:
    def __init__(self, completion=None, chunks=(), exc=None):
        self.completion = completion
        self.chunks = list(chunks)
        self.exc = exc
        self.params: dict = {}
        self.chat = SimpleNamespace(completions=self)

    def create(self, **params):
        self.params = params
        if self.exc:
            raise self.exc
        if params.get("stream"):
            return iter(self.chunks)
        return self.completion


def test_anthropic_params_include_tools_and_tool_choice_none():
    adapter = AnthropicAdapter(client=FakeAnthropicClient())
    spec = ToolSpec("echo", "say it back", {"type": "object"})
    params = adapter._params(request(tools=[spec]))
    assert params["tools"] == [
        {"name": "echo", "description": "say it back", "input_schema": {"type": "object"}}
    ]
    none = Request(
        model="m", system="sys", messages=(Message.user("hi"),),
        tools=(spec,), tool_choice="none",
    )
    assert adapter._params(none)["tool_choice"] == {"type": "none"}


def test_anthropic_complete_maps_blocks_usage_and_stop():
    client = FakeAnthropicClient(
        message=anthropic_message("working", tool=("t1", "echo", {"value": "x"}), stop="tool_use")
    )
    response = AnthropicAdapter(client=client).complete(request())
    assert response.text() == "working"
    assert response.stop_reason == "tool_use"
    calls = response.tool_calls()
    assert len(calls) == 1 and calls[0].name == "echo" and calls[0].args == {"value": "x"}
    assert (response.usage.input_tokens, response.usage.output_tokens) == (3, 4)


def test_anthropic_complete_normalizes_sdk_errors():
    class Down(Exception):
        status_code = 503

    with pytest.raises(Transport):
        AnthropicAdapter(client=FakeAnthropicClient(exc=Down("down"))).complete(request())


def test_anthropic_stream_normalizes_sdk_errors():
    class Down(Exception):
        status_code = 503

    with pytest.raises(Transport):
        AnthropicAdapter(client=FakeAnthropicClient(exc=Down("down"))).stream(request())


def test_anthropic_stream_yields_deltas_and_returns_final_message():
    client = FakeAnthropicClient(
        message=anthropic_message("one two"), deltas=["one ", "two"]
    )
    seen: list[str] = []
    response = AnthropicAdapter(client=client).stream(request(), on_delta=seen.append)
    assert "".join(seen) == "one two"
    assert response.text() == "one two"


def test_openai_params_map_tools_and_tool_choice_none():
    adapter = OpenAIAdapter(client=FakeOpenAIClient())
    spec = ToolSpec("echo", "say it back", {"type": "object"})
    params = adapter._params(request(tools=[spec]))
    assert params["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "echo",
                "description": "say it back",
                "parameters": {"type": "object"},
            },
        }
    ]
    none = Request(
        model="m", system="sys", messages=(Message.user("hi"),),
        tools=(spec,), tool_choice="none",
    )
    assert adapter._params(none)["tool_choice"] == "none"


def test_openai_complete_maps_tool_calls():
    client = FakeOpenAIClient(
        completion=openai_completion(calls=[("c1", "echo", '{"value": "x"}')])
    )
    response = OpenAIAdapter(client=client).complete(request())
    assert response.stop_reason == "tool_use"
    calls = response.tool_calls()
    assert len(calls) == 1 and calls[0].id == "c1" and calls[0].args == {"value": "x"}
    assert (response.usage.input_tokens, response.usage.output_tokens) == (5, 7)


def test_openai_complete_rejects_non_json_tool_arguments():
    client = FakeOpenAIClient(
        completion=openai_completion(calls=[("c1", "echo", "{not json")])
    )
    with pytest.raises(BadResponse):
        OpenAIAdapter(client=client).complete(request())


def test_openai_stream_reassembles_text_calls_and_keeps_usage():
    usage = SimpleNamespace(prompt_tokens=5, completion_tokens=7)
    chunks = [
        openai_chunk(content="he", usage=usage),
        openai_chunk(calls=[{"id": "c1", "name": "ec", "arguments": '{"val'}]),
        openai_chunk(calls=[{"arguments": 'ue": 1}'}]),
        openai_chunk(content="llo"),  # usage None here must not clobber the earlier one
    ]
    client = FakeOpenAIClient(chunks=chunks)
    seen: list[str] = []
    response = OpenAIAdapter(client=client).stream(request(), on_delta=seen.append)
    assert "".join(seen) == "hello"
    assert response.stop_reason == "tool_use"
    calls = response.tool_calls()
    assert len(calls) == 1
    assert calls[0].id == "c1" and calls[0].name == "ec" and calls[0].args == {"value": 1}
    assert (response.usage.input_tokens, response.usage.output_tokens) == (5, 7)


def test_openai_stream_rejects_non_json_tool_arguments():
    chunks = [openai_chunk(calls=[{"id": "c1", "name": "echo", "arguments": "{oops"}])]
    with pytest.raises(BadResponse):
        OpenAIAdapter(client=FakeOpenAIClient(chunks=chunks)).stream(request())


def test_openai_complete_maps_text_content():
    client = FakeOpenAIClient(completion=openai_completion(content="plain text"))
    response = OpenAIAdapter(client=client).complete(request())
    assert response.text() == "plain text"
    assert response.stop_reason == "end_turn"


def test_openai_complete_normalizes_sdk_errors():
    class Nope(Exception):
        status_code = 400

    with pytest.raises(Refused):
        OpenAIAdapter(client=FakeOpenAIClient(exc=Nope("no"))).complete(request())


def test_openai_stream_skips_choiceless_chunks():
    chunks = [
        openai_chunk(content="a"),
        SimpleNamespace(choices=[], usage=None),  # keep-alive chunk carries no choices
        openai_chunk(content="b"),
    ]
    response = OpenAIAdapter(client=FakeOpenAIClient(chunks=chunks)).stream(request())
    assert response.text() == "ab"


def test_openai_stream_normalizes_sdk_errors():
    class Down(Exception):
        status_code = 503

    with pytest.raises(Transport):
        OpenAIAdapter(client=FakeOpenAIClient(exc=Down("down"))).stream(request())


def test_build_adapter_picks_provider_and_rejects_unknown():
    settings = Settings(
        provider="anthropic", api_key="", base_url="https://anthropic.test"
    )
    assert type(build_adapter(settings)).__name__ == "AnthropicAdapter"
    settings = Settings(provider="openai", api_key="sk-test", base_url="https://openai.test")
    assert type(build_adapter(settings)).__name__ == "OpenAIAdapter"
    with pytest.raises(ValueError, match="unknown provider"):
        build_adapter(Settings(provider="bogus", api_key="", base_url=None))
