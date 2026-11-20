"""The gate decides, and fails open when it cannot."""

from __future__ import annotations

from scripted import script, text

from byo.memory.retrieval_gate import decide


def yes() -> dict:
    return {
        "text": '{"needs_memory": true, "reason": "about a person"}',
        "usage": {"in": 5, "out": 5},
    }


def no() -> dict:
    return {
        "text": '{"needs_memory": false, "reason": "plain arithmetic"}',
        "usage": {"in": 5, "out": 5},
    }


def test_gate_yes():
    decision = decide(script(yes()), "m", "when does alex prefer to meet?")
    assert decision["decision"] == "retrieve"
    assert decision["reason"] == "about a person"


def test_gate_no():
    decision = decide(script(no()), "m", "what is 2+2?")
    assert decision["decision"] == "skip"


def test_gate_fails_open_when_the_model_is_unavailable():
    decision = decide(script(), "m", "anything")
    assert decision["decision"] == "retrieve"
    assert "failed open" in decision["reason"]


def test_gate_fails_open_on_malformed_json():
    decision = decide(script(text("{not json}")), "m", "anything")
    assert decision["decision"] == "retrieve"
    assert "unclearly" in decision["reason"]


def test_gate_fails_open_on_unparseable_text():
    decision = decide(script(text("I think maybe?")), "m", "anything")
    assert decision["decision"] == "retrieve"
    assert "unclearly" in decision["reason"]
