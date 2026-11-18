"""The vocabulary the loop speaks. Vendor SDK types stop at the adapter.

Mechanism: plain frozen dataclasses for requests, messages, tool calls and usage,
plus four typed errors. The loop branches on these and on Capabilities, never on a
provider name.

Rejected alternative: reusing the Anthropic SDK's response objects end to end (what
the reference does). It couples every module to one vendor and makes the offline
test double impersonate a third-party type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TextBlock:
    text: str


@dataclass(frozen=True)
class ToolCallBlock:
    id: str
    name: str
    args: dict[str, Any]


@dataclass(frozen=True)
class ToolResultBlock:
    tool_call_id: str
    content: str


ContentBlock = TextBlock | ToolCallBlock | ToolResultBlock


@dataclass(frozen=True)
class Message:
    role: str
    blocks: tuple[ContentBlock, ...]

    @staticmethod
    def user(text: str) -> Message:
        return Message("user", (TextBlock(text),))

    def text(self) -> str:
        return "".join(b.text for b in self.blocks if isinstance(b, TextBlock))


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class Request:
    model: str
    system: str
    messages: tuple[Message, ...]
    tools: tuple[ToolSpec, ...] = ()
    max_tokens: int = 4096
    tool_choice: str = "auto"


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class Response:
    blocks: tuple[TextBlock | ToolCallBlock, ...]
    stop_reason: str
    usage: Usage
    model: str

    def text(self) -> str:
        return "".join(b.text for b in self.blocks if isinstance(b, TextBlock))

    def tool_calls(self) -> list[ToolCallBlock]:
        return [b for b in self.blocks if isinstance(b, ToolCallBlock)]


@dataclass(frozen=True)
class Capabilities:
    streaming: bool = False
    tool_calls: bool = True
    usage: bool = True
    tool_choice_none: bool = True


class ModelError(Exception):
    """Base for everything an adapter raises. The loop records these as text."""

    kind = "ModelError"


class Refused(ModelError):
    """The provider looked at the request and said no. Never retried."""

    kind = "Refused"

    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


class RateLimited(ModelError):
    kind = "RateLimited"

    def __init__(self, message: str = "rate limited", status: int = 429):
        super().__init__(message)
        self.status = status


class Transport(ModelError):
    """Network, timeout, truncated stream. Retried once."""

    kind = "Transport"


class BadResponse(ModelError):
    """The provider answered, but not in a shape we can map."""

    kind = "BadResponse"
