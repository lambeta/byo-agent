"""Per-turn accounting, built only from the turn's model calls."""

from __future__ import annotations

from typing import Any

from byo.ops.pricing import cost


def build(llm_calls: list[dict[str, Any]], tool_calls: int = 0) -> dict[str, Any]:
    tokens_in = 0
    tokens_out = 0
    total = 0.0
    estimate = False
    iterations = 0
    for call in llm_calls:
        usage = call.get("usage") or {}
        tokens_in += int(usage.get("in", 0) or 0)
        tokens_out += int(usage.get("out", 0) or 0)
        usd, guessed = cost(call.get("provider", ""), call.get("model", ""), usage)
        total += usd
        estimate = estimate or guessed
        iterations += 1
    return {
        "iterations": iterations,
        "tool_calls": tool_calls,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "usd": round(total, 6),
        "estimate": estimate,
    }
