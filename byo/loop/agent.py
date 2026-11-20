"""The loop — reason, act, observe, repeat, and the two ways to stop.

Mechanism: one while-loop over model calls. A response with no tool call ends the
turn; a response at the step limit gets one final call with tools disabled so the
person still gets an answer from what was gathered. A Transport failure before any
text was emitted is retried once, so one network blip does not end the turn.

Rejected alternative: raising the step limit until it never trips. It turns a
bounded turn into unbounded spend, and it hides the one failure a person can fix
by asking a smaller question.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from byo.loop.types import (
    Message,
    ModelError,
    Request,
    ToolResultBlock,
    ToolSpec,
    Transport,
)
from byo.tools.registry import ToolRegistry

Observer = Callable[[str, dict[str, Any]], None]

LIMIT_NOTE = (
    "You have reached the step limit for this turn and cannot call any more tools. "
    "Answer now from what you already gathered; say plainly what is missing."
)
LIMIT_REPLY = "(Reached the step limit before finishing — try a smaller request.)"
EMPTY_REPLY = "(The model returned no text and no tool call.)"


@dataclass
class LoopResult:
    reply: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    iterations: int = 0
    limit_reached: bool = False
    llm_calls: list[dict[str, Any]] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    error: str = ""


def error_text(exc: BaseException) -> str:
    message = getattr(exc, "message", "")
    if message and getattr(exc, "status", 0):
        return str(message)
    return f"{type(exc).__name__}: {exc}"


def _complete(
    adapter,
    request: Request,
    notify: Observer,
    stream: bool,
    on_delta: Callable[[str], None],
):
    """One model call, retried once on a Transport error before anything was emitted.

    Mechanism: a network blip gets a single second attempt, so a flaky connection
    does not end the turn. A stream that already delivered text is not retried: the
    person would see the opening twice. Refused and RateLimited are decisions, not
    faults, and are never retried.
    """
    retried = False
    delivered = False

    def guarded(delta: str) -> None:
        nonlocal delivered
        delivered = True
        on_delta(delta)

    while True:
        try:
            if stream and adapter.capabilities.streaming:
                return adapter.stream(request, on_delta=guarded)
            return adapter.complete(request)
        except Transport:
            if retried or delivered:
                raise
            retried = True
            notify("retry", {"stage": "llm", "model": request.model})


def run_loop(
    adapter,
    model: str,
    system: str,
    messages: list[Message],
    tools: ToolRegistry,
    max_iterations: int = 10,
    max_tokens: int = 2048,
    observer: Observer | None = None,
    stream: bool = False,
    trim: Callable[[list[Message]], None] | None = None,
) -> LoopResult:
    """Run one turn. The messages list is mutated in place and ends up holding the
    full working memory of the turn, which is what the trajectory records."""
    notify = observer or (lambda kind, event: None)
    result = LoopResult(messages=messages)
    specs = tuple(
        ToolSpec(item["name"], item["description"], item["input_schema"])
        for item in tools.schemas()
    )

    for iteration in range(1, max_iterations + 1):
        result.iterations = iteration
        if trim is not None and iteration > 1:
            trim(messages)

        request = Request(
            model=model,
            system=system,
            messages=tuple(messages),
            tools=specs,
            max_tokens=max_tokens,
        )
        started = time.perf_counter()
        notify("llm_start", {"iteration": iteration, "model": model})
        try:
            response = _complete(
                adapter,
                request,
                notify,
                stream,
                on_delta=lambda delta: notify("text", {"delta": delta}),
            )
        except ModelError as exc:
            result.error = exc.kind
            notify("error", {"stage": "llm", "error_kind": exc.kind, "message": error_text(exc)})
            result.reply = error_text(exc)
            return result
        duration_ms = int((time.perf_counter() - started) * 1000)

        call = {
            "iteration": iteration,
            "kind": "loop",
            "model": response.model,
            "stop_reason": response.stop_reason,
            "usage": {
                "in": response.usage.input_tokens,
                "out": response.usage.output_tokens,
            },
            "duration_ms": duration_ms,
            # The model's own words for this call. Persisted so the chat can keep the
            # thinking after the turn ends, bounded so a long answer stays cheap.
            "text": response.text()[:4000],
        }
        result.llm_calls.append(call)
        notify("llm", call)

        messages.append(Message("assistant", response.blocks))

        calls = response.tool_calls()
        if not calls:
            result.reply = response.text() or EMPTY_REPLY
            return result

        results: list[ToolResultBlock] = []
        for call_block in calls:
            started = time.perf_counter()
            notify("tool_start", {"tool": call_block.name, "call_id": call_block.id})
            output = tools.execute(call_block.name, call_block.args)
            event = {
                "tool": call_block.name,
                "args": call_block.args,
                "output": output,
                "ok": not output.startswith("Error:"),
                "call_id": call_block.id,
                "duration_ms": int((time.perf_counter() - started) * 1000),
            }
            result.tool_calls.append(event)
            notify("tool", event)
            results.append(ToolResultBlock(call_block.id, output))
        messages.append(Message("user", tuple(results)))

    result.limit_reached = True
    reply = _final_answer(adapter, model, system, messages, specs, max_tokens, notify, result, trim)
    result.reply = reply or LIMIT_REPLY
    return result


def _final_answer(
    adapter,
    model: str,
    system: str,
    messages: list[Message],
    specs: tuple[ToolSpec, ...],
    max_tokens: int,
    notify: Observer,
    result: LoopResult,
    trim,
) -> str:
    """The one tools-off call after the limit: its text, or a failed result.

    A failed final answer sets result.error: the turn ends on the canned
    LIMIT_REPLY, not on anything the model said, so the record must say failed
    and agree with the projections that treat a stage=llm error as fatal.
    """
    if trim is not None:
        trim(messages)
    request = Request(
        model=model,
        system=f"{system}\n\n{LIMIT_NOTE}",
        messages=tuple(messages),
        tools=specs,
        max_tokens=max_tokens,
        tool_choice="none",
    )
    started = time.perf_counter()
    notify("llm_start", {"iteration": result.iterations + 1, "model": model, "kind": "final"})
    try:
        response = _complete(adapter, request, notify, False, lambda delta: None)
    except ModelError as exc:
        result.error = exc.kind
        notify("error", {"stage": "llm", "error_kind": exc.kind, "message": error_text(exc)})
        return ""
    call = {
        "iteration": result.iterations + 1,
        "kind": "final",
        "model": response.model,
        "stop_reason": response.stop_reason,
        "usage": {
            "in": response.usage.input_tokens,
            "out": response.usage.output_tokens,
        },
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "text": response.text()[:4000],
    }
    result.llm_calls.append(call)
    notify("llm", call)
    messages.append(Message("assistant", response.blocks))
    return response.text()
