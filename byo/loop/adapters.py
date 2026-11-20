"""Model adapters — the only place a vendor SDK is imported.

Mechanism: two thin adapters map the normalized Request/Response types onto the
Anthropic and OpenAI wire formats, normalize errors into four kinds, and expose
streaming as a capability. The SDKs are imported lazily, inside __init__, so the
package imports and the offline suite runs with neither installed.

Rejected alternative: raw httpx. It would mean re-implementing retries and stream
frame parsing that the SDKs already ship, and httpx would become a fifth dependency.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from byo.loop.types import (
    BadResponse,
    Capabilities,
    Message,
    ModelError,
    RateLimited,
    Refused,
    Request,
    Response,
    TextBlock,
    ToolCallBlock,
    ToolResultBlock,
    Transport,
    Usage,
)

Handler = Callable[[str], None]


def _normalize(exc: Exception) -> ModelError:
    """One vendor-agnostic error taxonomy. 4xx is a decision, not a fault."""
    status = int(getattr(exc, "status_code", 0) or getattr(exc, "status", 0) or 0)
    if status == 429:
        return RateLimited(str(exc), 429)
    if 400 <= status < 500:
        return Refused(str(exc), status)
    name = type(exc).__name__.lower()
    if status >= 500 or "timeout" in name or "connect" in name:
        return Transport(f"{type(exc).__name__}: {exc}")
    return BadResponse(f"{type(exc).__name__}: {exc}")


class AnthropicAdapter:
    capabilities = Capabilities(streaming=True, tool_calls=True, usage=True, tool_choice_none=True)

    def __init__(
        self, api_key: str = "", base_url: str | None = None, client: Any = None
    ) -> None:
        if client is None:
            import anthropic

            kwargs: dict[str, Any] = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            client = anthropic.Anthropic(**kwargs)
        self._client = client

    @staticmethod
    def _messages(messages: tuple[Message, ...]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for message in messages:
            blocks: list[dict[str, Any]] = []
            for block in message.blocks:
                if isinstance(block, TextBlock):
                    blocks.append({"type": "text", "text": block.text})
                elif isinstance(block, ToolCallBlock):
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.args,
                        }
                    )
                elif isinstance(block, ToolResultBlock):
                    blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.tool_call_id,
                            "content": block.content,
                        }
                    )
            out.append({"role": message.role, "content": blocks})
        return out

    def _params(self, request: Request) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": request.model,
            "system": request.system,
            "messages": self._messages(request.messages),
            "max_tokens": request.max_tokens,
        }
        if request.tools:
            params["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in request.tools
            ]
            if request.tool_choice == "none":
                params["tool_choice"] = {"type": "none"}
        return params

    @staticmethod
    def _response(message: Any, model: str) -> Response:
        blocks: list[TextBlock | ToolCallBlock] = []
        for block in message.content:
            if getattr(block, "type", "") == "text":
                blocks.append(TextBlock(block.text))
            elif getattr(block, "type", "") == "tool_use":
                blocks.append(ToolCallBlock(block.id, block.name, dict(block.input or {})))
        usage = Usage(
            int(getattr(message.usage, "input_tokens", 0) or 0),
            int(getattr(message.usage, "output_tokens", 0) or 0),
        )
        return Response(tuple(blocks), str(message.stop_reason or "end_turn"), usage, model)

    def complete(self, request: Request) -> Response:
        try:
            message = self._client.messages.create(**self._params(request))
        except Exception as exc:
            raise _normalize(exc) from exc
        return self._response(message, request.model)

    def stream(self, request: Request, on_delta: Handler | None = None) -> Response:
        try:
            with self._client.messages.stream(**self._params(request)) as stream:
                for delta in stream.text_stream:
                    if on_delta:
                        on_delta(delta)
                message = stream.get_final_message()
        except Exception as exc:
            raise _normalize(exc) from exc
        return self._response(message, request.model)


class OpenAIAdapter:
    capabilities = Capabilities(streaming=True, tool_calls=True, usage=True, tool_choice_none=True)

    def __init__(
        self, api_key: str = "", base_url: str | None = None, client: Any = None
    ) -> None:
        if client is None:
            import openai

            kwargs: dict[str, Any] = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            client = openai.OpenAI(**kwargs)
        self._client = client

    @staticmethod
    def _messages(request: Request) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = [{"role": "system", "content": request.system}]
        for message in request.messages:
            texts = [b.text for b in message.blocks if isinstance(b, TextBlock)]
            calls = [b for b in message.blocks if isinstance(b, ToolCallBlock)]
            results = [b for b in message.blocks if isinstance(b, ToolResultBlock)]
            for result in results:
                out.append(
                    {"role": "tool", "tool_call_id": result.tool_call_id, "content": result.content}
                )
            if calls:
                out.append(
                    {
                        "role": "assistant",
                        "content": "".join(texts) or None,
                        "tool_calls": [
                            {
                                "id": call.id,
                                "type": "function",
                                "function": {"name": call.name, "arguments": json.dumps(call.args)},
                            }
                            for call in calls
                        ],
                    }
                )
            elif texts:
                out.append({"role": message.role, "content": "".join(texts)})
        return out

    def _params(self, request: Request) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": request.model,
            "messages": self._messages(request),
            "max_tokens": request.max_tokens,
        }
        if request.tools:
            params["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in request.tools
            ]
            if request.tool_choice == "none":
                params["tool_choice"] = "none"
        return params

    @staticmethod
    def _response(message: Any, usage: Any, model: str) -> Response:
        blocks: list[TextBlock | ToolCallBlock] = []
        if getattr(message, "content", None):
            blocks.append(TextBlock(str(message.content)))
        for call in getattr(message, "tool_calls", None) or []:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError as exc:
                raise BadResponse(f"tool arguments were not JSON: {exc}") from exc
            blocks.append(ToolCallBlock(call.id, call.function.name, args))
        stop = (
            "tool_use"
            if blocks and any(isinstance(b, ToolCallBlock) for b in blocks)
            else "end_turn"
        )
        return Response(
            tuple(blocks),
            stop,
            Usage(
                int(getattr(usage, "prompt_tokens", 0) or 0),
                int(getattr(usage, "completion_tokens", 0) or 0),
            ),
            model,
        )

    def complete(self, request: Request) -> Response:
        try:
            completion = self._client.chat.completions.create(**self._params(request))
        except Exception as exc:
            raise _normalize(exc) from exc
        choice = completion.choices[0]
        return self._response(choice.message, getattr(completion, "usage", None), request.model)

    def stream(self, request: Request, on_delta: Handler | None = None) -> Response:
        text: list[str] = []
        calls: dict[int, dict[str, str]] = {}
        usage = None
        try:
            chunks = self._client.chat.completions.create(stream=True, **self._params(request))
            for chunk in chunks:
                # Usage arrives on one chunk only; later chunks carry None again.
                usage = getattr(chunk, "usage", None) or usage
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if getattr(delta, "content", None):
                    text.append(delta.content)
                    if on_delta:
                        on_delta(delta.content)
                for call in getattr(delta, "tool_calls", None) or []:
                    slot = calls.setdefault(call.index, {"id": "", "name": "", "arguments": ""})
                    if call.id:
                        slot["id"] = call.id
                    if call.function and call.function.name:
                        slot["name"] = call.function.name
                    if call.function and call.function.arguments:
                        slot["arguments"] += call.function.arguments
        except Exception as exc:
            raise _normalize(exc) from exc

        blocks: list[TextBlock | ToolCallBlock] = []
        if text:
            blocks.append(TextBlock("".join(text)))
        for index in sorted(calls):
            slot = calls[index]
            try:
                args = json.loads(slot["arguments"] or "{}")
            except json.JSONDecodeError as exc:
                raise BadResponse(f"tool arguments were not JSON: {exc}") from exc
            blocks.append(ToolCallBlock(slot["id"] or f"call_{index}", slot["name"], args))
        return Response(
            tuple(blocks),
            "tool_use" if calls else "end_turn",
            Usage(
                int(getattr(usage, "prompt_tokens", 0) or 0),
                int(getattr(usage, "completion_tokens", 0) or 0),
            ),
            request.model,
        )


def build_adapter(settings) -> Any:
    """Pick the adapter for the configured provider. The loop never asks which."""
    if settings.provider == "anthropic":
        return AnthropicAdapter(settings.api_key, settings.base_url)
    if settings.provider == "openai":
        return OpenAIAdapter(settings.api_key, settings.base_url)
    raise ValueError(f"unknown provider {settings.provider!r}")
