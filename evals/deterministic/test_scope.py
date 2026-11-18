"""The retired surface is absent, not stubbed (FR-002, FR-003)."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RETIRED = ("graph", "plugins", "voice", "telegram", "discord", "whatsapp", "hosted", "arena")


def test_no_retired_module_exists():
    for name in RETIRED:
        assert not (ROOT / "byo" / name).exists(), name


def test_gateway_has_only_the_terminal_surface():
    assert sorted(path.name for path in (ROOT / "byo" / "gateway").glob("*.py")) == [
        "__init__.py",
        "cli.py",
    ]


def test_help_lists_only_retained_commands():
    from byo.__main__ import USAGE

    for name in RETIRED:
        assert name not in USAGE


def test_dependency_budget_is_four_and_framework_free():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = data["project"]["dependencies"]
    assert len(dependencies) == 4
    for forbidden in ("langchain", "langgraph", "llama-index", "crewai", "fastapi"):
        assert not any(forbidden in dep for dep in dependencies)


def test_tool_set_is_closed(settings, conn):
    from scripted import script

    from byo.memory import Memory
    from byo.tools import build_registry

    with_memory = build_registry(conn, settings, memory=Memory(conn, settings, script()))
    assert set(with_memory.names()) == {
        "create_event",
        "list_events",
        "save_note",
        "send_message",
        "manage_memory",
        "update_persona",
    }
