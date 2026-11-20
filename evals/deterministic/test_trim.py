"""The trim: old tool results are cut, the fresh one goes out in full once."""

from __future__ import annotations

from scripted import script, text, tool_call

from byo.loop.agent import run_loop
from byo.loop.trim import CAP, MARKER, shrink
from byo.loop.types import Message, TextBlock, ToolResultBlock
from byo.tools.registry import Tool, ToolRegistry

BIG = "x" * (CAP + 1000)


def big_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(
        Tool("big", "big output", {"type": "object", "properties": {}}, lambda: BIG)
    )
    return reg


def result_message(call_id: str, content: str) -> Message:
    return Message("user", (ToolResultBlock(call_id, content),))


def test_shrink_cuts_only_results_the_model_already_read():
    messages = [
        Message.user("hi"),
        result_message("old", BIG),
        result_message("fresh", BIG),
    ]
    shrink(messages)
    old, fresh = messages[1].blocks[0], messages[2].blocks[0]
    assert old.content == BIG[:CAP] + MARKER
    assert fresh.content == BIG  # appended after the last model call: unread, sent in full


def test_shrink_leaves_short_results_and_other_blocks_alone():
    message = Message(
        "user", (TextBlock("note"), ToolResultBlock("c1", "short"), ToolResultBlock("c2", BIG))
    )
    messages = [message, Message.user("tail")]
    shrink(messages)
    text_block, short, cut = messages[0].blocks
    assert text_block is message.blocks[0]
    assert short.content == "short"
    assert cut.tool_call_id == "c2"
    assert cut.content == BIG[:CAP] + MARKER


def test_shrink_is_idempotent():
    messages = [result_message("old", BIG), Message.user("tail")]
    shrink(messages)
    once = messages[0].blocks[0].content
    shrink(messages)
    assert messages[0].blocks[0].content == once


def test_loop_sends_a_large_result_in_full_once_then_cut():
    adapter = script(tool_call("big", {}), tool_call("big", {}, call_id="call_2"), text("done"))
    result = run_loop(
        adapter, "m", "sys", [Message.user("hi")], big_registry(), trim=shrink
    )
    assert result.reply == "done"

    def results_of(call):
        return [
            b.content
            for m in call.messages
            for b in m.blocks
            if isinstance(b, ToolResultBlock)
        ]

    # Iteration 2: the first big result is sent in full - the model has not read it yet.
    assert results_of(adapter.calls[1]) == [BIG]
    # Iteration 3: the read result is cut, the fresh one still goes out in full.
    assert results_of(adapter.calls[2]) == [BIG[:CAP] + MARKER, BIG]
