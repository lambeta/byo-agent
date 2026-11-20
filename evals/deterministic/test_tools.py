"""Tool contracts: dispatch rules, and each tool's write-through and honest output."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from byo.tools import build_registry
from byo.tools.registry import Tool, ToolRegistry


def dummy_registry() -> ToolRegistry:
    reg = ToolRegistry()

    def ok(value: str) -> str:
        return f"ran:{value}"

    def boom(value: str) -> str:
        raise RuntimeError("kaboom")

    reg.register(Tool("ok", "works", {"type": "object"}, ok))
    reg.register(Tool("boom", "fails", {"type": "object"}, boom))
    return reg


def test_unknown_tool_is_text():
    assert dummy_registry().execute("nope", {}) == "Error: unknown tool 'nope'"


def test_bad_arguments_are_text():
    output = dummy_registry().execute("ok", {"wrong": "x"})
    assert output.startswith("Error: ok needs different arguments")


def test_raising_tool_is_text():
    assert dummy_registry().execute("boom", {"value": "x"}) == "Error: RuntimeError: kaboom"


def test_registry_exposes_model_schemas(settings, conn):
    registry = build_registry(conn, settings)
    names = set(registry.names())
    assert names == {
        "create_event",
        "list_events",
        "save_note",
        "send_message",
        "query_weather",
    }
    for schema in registry.schemas():
        assert schema["input_schema"]["type"] == "object"


def test_create_and_list_events(settings, conn):
    registry = build_registry(conn, settings)
    out = registry.execute(
        "create_event",
        {"title": "Catch-up", "start": "2026-11-20T09:00:00+08:00", "attendees": "alex"},
    )
    assert "Created event" in out
    assert str(settings.db_path) in out
    row = conn.execute("SELECT * FROM calendar_events").fetchone()
    assert row["title"] == "Catch-up"
    assert row["attendees"] == "alex"

    listed = registry.execute("list_events", {"start": "2026-11-20"})
    assert "Catch-up" in listed


def test_create_event_rejects_a_bad_start(settings, conn):
    registry = build_registry(conn, settings)
    out = registry.execute("create_event", {"title": "x", "start": "friday"})
    assert out.startswith("Error:")
    assert "ISO 8601" in out
    assert conn.execute("SELECT COUNT(*) FROM calendar_events").fetchone()[0] == 0


def test_create_event_rejects_a_start_without_offset(settings, conn):
    registry = build_registry(conn, settings)
    out = registry.execute(
        "create_event", {"title": "x", "start": "2026-11-20T09:00:00"}
    )
    assert out.startswith("Error:")
    assert "offset" in out
    assert conn.execute("SELECT COUNT(*) FROM calendar_events").fetchone()[0] == 0


def test_create_event_names_end_when_the_end_is_bad(settings, conn):
    registry = build_registry(conn, settings)
    out = registry.execute(
        "create_event",
        {"title": "x", "start": "2026-11-20T09:00:00+08:00", "end": "soon"},
    )
    assert out.startswith("Error:")
    assert "end must be" in out
    assert "start must be" not in out
    assert conn.execute("SELECT COUNT(*) FROM calendar_events").fetchone()[0] == 0


def test_create_event_rejects_an_empty_title(settings, conn):
    registry = build_registry(conn, settings)
    out = registry.execute(
        "create_event", {"title": "   ", "start": "2026-11-20T09:00:00+08:00"}
    )
    assert out.startswith("Error:")
    assert "title" in out
    assert conn.execute("SELECT COUNT(*) FROM calendar_events").fetchone()[0] == 0


def test_list_events_defaults_to_today(settings, conn):
    registry = build_registry(conn, settings)
    out = registry.execute("list_events", {})
    today = date.today().isoformat()
    assert out == f"No events between {today} and {today}."


def test_list_events_names_the_bad_field(settings, conn):
    registry = build_registry(conn, settings)
    out = registry.execute("list_events", {"start": "friday"})
    assert "start must be an ISO date" in out
    out = registry.execute("list_events", {"start": "2026-11-20", "end": "later"})
    assert "end must be an ISO date" in out


def test_list_events_covers_a_range(settings, conn):
    registry = build_registry(conn, settings)
    registry.execute(
        "create_event", {"title": "Solo", "start": "2026-11-21T09:00:00+08:00"}
    )
    out = registry.execute(
        "list_events", {"start": "2026-11-20", "end": "2026-11-22"}
    )
    assert "1 event(s) between 2026-11-20 and 2026-11-22" in out
    assert "Solo" in out


def test_save_note_writes_a_fact(settings, conn):
    registry = build_registry(conn, settings)
    out = registry.execute("save_note", {"subject": "alex", "content": "prefers morning meetings"})
    assert str(settings.db_path) in out
    row = conn.execute("SELECT subject, content, source FROM facts").fetchone()
    assert (row["subject"], row["source"]) == ("alex", "tool")


def test_send_message_writes_the_outbox_and_says_so(settings, conn):
    registry = build_registry(conn, settings)
    out = registry.execute("send_message", {"to": "Alex Chen", "body": "running late"})
    assert "not sent anywhere" in out
    files = list(Path(settings.outbox_dir).glob("*.md"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert "to: Alex Chen" in text
    assert "running late" in text
