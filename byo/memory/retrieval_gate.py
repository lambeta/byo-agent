"""The retrieval gate: does answering this turn need what we remember?

Mechanism: one small-model call that returns JSON ({needs_memory, reason}). Any
failure — a refusal, a timeout, unparseable output — fails open and retrieves, with
the failure recorded as the reason, so a slow judge never costs a memory.

Rejected alternative: always retrieve. It spends money and attention on every turn
and removes the mechanism this project exists to show.
"""

from __future__ import annotations

import json
from typing import Any

from byo.loop.types import Message, ModelError, Request

SYSTEM = (
    "You decide whether answering a message needs the assistant's long-term memory "
    "(facts about the person, their people, projects or preferences). "
    'Reply with JSON only: {"needs_memory": true|false, "reason": "short sentence"}.'
)

PROMPT = "Message: {message}\n\nDoes answering it need long-term memory?"


def first_json(text: str) -> dict[str, Any] | None:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    # A valid JSON slice from "{" to "}" can only be an object.
    return data


def decide(adapter, model: str, message: str, max_tokens: int = 256) -> dict[str, Any]:
    request = Request(
        model=model,
        system=SYSTEM,
        messages=(Message.user(PROMPT.format(message=message)),),
        max_tokens=max_tokens,
    )
    try:
        response = adapter.complete(request)
    except ModelError as exc:
        return {
            "decision": "retrieve",
            "reason": f"gate failed open ({exc.kind})",
            "degraded": True,
        }
    data = first_json(response.text())
    if not data or "needs_memory" not in data:
        return {
            "decision": "retrieve",
            "reason": "gate answered unclearly; retrieved anyway",
            "degraded": True,
        }
    decision = "retrieve" if data.get("needs_memory") else "skip"
    return {
        "decision": decision,
        "reason": str(data.get("reason") or ""),
        "degraded": False,
    }
