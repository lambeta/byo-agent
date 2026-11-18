"""The tool set is closed: calendar, notes and messages, and later memory admin."""

from __future__ import annotations

from byo.tools import calendar, memory_admin, messages, notes
from byo.tools.registry import ToolRegistry


def build_registry(conn, settings, memory=None) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in calendar.make_tools(conn, settings):
        registry.register(tool)
    for tool in notes.make_tools(conn, settings, memory=memory):
        registry.register(tool)
    for tool in messages.make_tools(conn, settings):
        registry.register(tool)
    if memory is not None:
        for tool in memory_admin.make_tools(conn, settings, memory):
            registry.register(tool)
    return registry
