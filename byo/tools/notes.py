"""Notes: the one tool that writes a durable fact on purpose."""

from __future__ import annotations

from byo.tools.registry import Tool

SAVE_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string", "description": "who or what the note is about"},
        "content": {"type": "string", "description": "the durable statement"},
    },
    "required": ["subject", "content"],
}


def make_tools(conn, settings, memory=None) -> list[Tool]:
    def save_note(subject: str, content: str) -> str:
        subject, content = subject.strip(), content.strip()
        if not subject or not content:
            raise ValueError("subject and content are both required")
        cursor = conn.execute(
            "INSERT INTO facts (subject, content, source) VALUES (?, ?, 'tool')",
            (subject, content),
        )
        conn.commit()
        where = str(settings.db_path)
        if memory is not None:
            memory.rewrite_mirror()
            where += f" and {settings.memory_dir / (str(cursor.lastrowid) + '.md')}"
        return f"Saved: [{subject}] {content} (in {where})."

    return [
        Tool(
            "save_note",
            "Save a durable fact about the person or their world.",
            SAVE_SCHEMA,
            save_note,
        )
    ]
