"""Tool registry — a tool is a declaration plus a function that returns text.

Mechanism: ToolRegistry.execute() looks a tool up, calls it, and converts every
failure into a string the model can read; the turn never dies on a tool.

Rejected alternative: decorators that reflect on a function signature to build the
schema. The schema would become implicit, which is the opposite of this project's
purpose: the model's contract should be readable where it is written.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    fn: Callable[..., str]

    def to_api(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def schemas(self) -> list[dict[str, Any]]:
        return [tool.to_api() for tool in self._tools.values()]

    def execute(self, name: str, args: dict[str, Any] | None = None) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"Error: unknown tool '{name}'"
        try:
            return tool.fn(**(args or {}))
        except TypeError as exc:
            return f"Error: {name} needs different arguments ({exc})"
        except Exception as exc:  # noqa: BLE001 - the model reads it and retries
            return f"Error: {type(exc).__name__}: {exc}"
