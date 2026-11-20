"""A scripted model adapter — the offline test double.

Mechanism: a JSON script lists the responses a turn should see, in order, with text,
tool calls, stop reason, usage and an optional delay. The adapter implements the
same protocol as the real ones, so tests exercise the real loop, the real registry
and the real trajectory writer with no network and no credentials.

Rejected alternative: unittest.mock around the SDK clients. A script is a readable
record of the expected conversation, and the same file doubles as a defect replay.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from byo.loop.types import (
    BadResponse,
    Capabilities,
    RateLimited,
    Refused,
    Request,
    Response,
    TextBlock,
    ToolCallBlock,
    Transport,
    Usage,
)

ERROR_KINDS = {
    "Transport": Transport,
    "Refused": Refused,
    "RateLimited": RateLimited,
    "BadResponse": BadResponse,
}

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "models"


def load_script(name: str) -> dict[str, Any]:
    """Load fixtures/models/<name>.json (the .json suffix is optional)."""
    path = FIXTURES / (name if name.endswith(".json") else f"{name}.json")
    return json.loads(path.read_text(encoding="utf-8"))


class ScriptedAdapter:
    capabilities = Capabilities(streaming=True, tool_calls=True, usage=True, tool_choice_none=True)

    def __init__(self, script: dict[str, Any]):
        self.responses: list[dict[str, Any]] = list(script.get("responses") or [])
        self.calls: list[Request] = []
        self.deltas: list[str] = []

    def _next(self, request: Request) -> tuple[Response, dict[str, Any]]:
        self.calls.append(request)
        if not self.responses:
            raise BadResponse("script exhausted: the model was called more times than scripted")
        spec = self.responses.pop(0)
        if spec.get("error"):
            kind = ERROR_KINDS.get(str(spec["error"]))
            if kind is None:
                raise BadResponse(f"unknown scripted error kind {spec['error']!r}")
            raise kind(str(spec.get("message") or spec["error"]))
        blocks: list[TextBlock | ToolCallBlock] = []
        if spec.get("text"):
            blocks.append(TextBlock(str(spec["text"])))
        for index, call in enumerate(spec.get("tool_calls") or []):
            blocks.append(
                ToolCallBlock(
                    call.get("id") or f"call_{index}", call["name"], call.get("args") or {}
                )
            )
        usage = spec.get("usage") or {}
        stop = spec.get("stop_reason") or ("tool_use" if spec.get("tool_calls") else "end_turn")
        response = Response(
            tuple(blocks),
            stop,
            Usage(int(usage.get("in", 0)), int(usage.get("out", 0))),
            request.model,
        )
        return response, spec

    def _pause(self, spec: dict[str, Any]) -> None:
        delay = spec.get("delay_ms") or 0
        if delay:
            time.sleep(delay / 1000)

    def complete(self, request: Request) -> Response:
        response, spec = self._next(request)
        self._pause(spec)
        return response

    def stream(self, request: Request, on_delta=None) -> Response:
        response, spec = self._next(request)
        self._pause(spec)
        if on_delta:
            for word in response.text().split(" "):
                on_delta(word + " ")
                self.deltas.append(word)
        return response


def script(*responses: dict[str, Any]) -> ScriptedAdapter:
    return ScriptedAdapter({"responses": list(responses)})


def text(text: str, usage: dict[str, int] | None = None) -> dict[str, Any]:
    return {"text": text, "stop_reason": "end_turn", "usage": usage or {"in": 10, "out": 5}}


def error(kind: str, message: str = "") -> dict[str, Any]:
    """Script one failing model call: error('Transport') or error('Refused')."""
    return {"error": kind, "message": message or kind}


def tool_call(
    name: str, args: dict[str, Any], call_id: str = "call_1", text: str = ""
) -> dict[str, Any]:
    return {
        "text": text,
        "tool_calls": [{"id": call_id, "name": name, "args": args}],
        "stop_reason": "tool_use",
        "usage": {"in": 20, "out": 8},
    }
