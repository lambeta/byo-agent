"""Calendar tools: the flagship task that proves the loop can act."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from byo.tools.registry import Tool

CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "short title of the event"},
        "start": {"type": "string", "description": "ISO 8601 start with offset"},
        "end": {"type": "string", "description": "ISO 8601 end (optional)"},
        "attendees": {"type": "string", "description": "comma-separated names (optional)"},
        "notes": {"type": "string", "description": "free text (optional)"},
    },
    "required": ["title", "start"],
}

LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "start": {"type": "string", "description": "ISO date to start from (default today)"},
        "end": {"type": "string", "description": "ISO date to end at (default start)"},
    },
}


def _parse(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO 8601, got {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must carry an offset, got {value!r}")
    return parsed


def _iso_date(value: str | None, field: str) -> str:
    if not value:
        return date.today().isoformat()
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date, got {value!r}") from exc


def make_tools(conn, settings) -> list[Tool]:
    db: Path = settings.db_path

    def create_event(
        title: str,
        start: str,
        end: str | None = None,
        attendees: str = "",
        notes: str = "",
    ) -> str:
        _parse(start, "start")
        if end:
            _parse(end, "end")
        if not title.strip():
            raise ValueError("title cannot be empty")
        cursor = conn.execute(
            'INSERT INTO calendar_events (title, start, "end", attendees, notes) '
            "VALUES (?, ?, ?, ?, ?)",
            (title.strip(), start, end, attendees, notes),
        )
        conn.commit()
        return f"Created event {cursor.lastrowid}: {title.strip()} at {start} (saved in {db})."

    def list_events(start: str | None = None, end: str | None = None) -> str:
        first = _iso_date(start, "start")
        last = _iso_date(end or start, "end")
        rows = conn.execute(
            "SELECT id, title, start, attendees FROM calendar_events "
            "WHERE date(start) >= ? AND date(start) <= ? ORDER BY start LIMIT 20",
            (first, last),
        ).fetchall()
        if not rows:
            return f"No events between {first} and {last}."
        lines = [
            f"{row['id']} · {row['start']} · {row['title']}"
            + (f" ({row['attendees']})" if row["attendees"] else "")
            for row in rows
        ]
        return f"{len(rows)} event(s) between {first} and {last} (from {db}):\n" + "\n".join(lines)

    return [
        Tool(
            "create_event",
            "Create a calendar event and save it locally.",
            CREATE_SCHEMA,
            create_event,
        ),
        Tool("list_events", "List calendar events in a date range.", LIST_SCHEMA, list_events),
    ]
