"""Money: the table, the estimate flag, and the sum."""

from __future__ import annotations

from byo.ops.pricing import cost
from byo.ops.receipt import build


def test_known_model_cost():
    usd, estimate = cost("anthropic", "claude-sonnet-4-5", {"in": 1000, "out": 1000})
    assert estimate is False
    assert usd == 0.018


def test_unknown_model_is_an_estimate_not_a_zero_surprise():
    usd, estimate = cost("mystery", "some-new-model", {"in": 1000, "out": 1000})
    assert usd == 0.0
    assert estimate is True


def test_receipt_sums_the_calls():
    calls = [
        {"model": "claude-sonnet-4-5", "usage": {"in": 1000, "out": 500}},
        {"model": "claude-sonnet-4-5", "usage": {"in": 200, "out": 100}},
    ]
    receipt = build(calls, tool_calls=1)
    assert receipt["iterations"] == 2
    assert receipt["tool_calls"] == 1
    assert receipt["tokens_in"] == 1200
    assert receipt["tokens_out"] == 600
    assert receipt["usd"] == round((1200 * 3.0 + 600 * 15.0) / 1000000, 6)
    assert receipt["estimate"] is False


def test_one_unknown_call_marks_the_whole_receipt():
    calls = [
        {"model": "claude-sonnet-4-5", "usage": {"in": 1, "out": 1}},
        {"model": "unlisted", "usage": {"in": 1, "out": 1}},
    ]
    assert build(calls)["estimate"] is True
