"""Memory self-management: a person can correct or forget, and retune the persona."""

from __future__ import annotations

from byo.tools.registry import Tool

MANAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["list", "edit", "forget"]},
        "id": {"type": "integer", "description": "the fact id (edit and forget)"},
        "subject": {"type": "string"},
        "content": {"type": "string"},
    },
    "required": ["action"],
}

PERSONA_SCHEMA = {
    "type": "object",
    "properties": {"content": {"type": "string", "description": "the complete new persona text"}},
    "required": ["content"],
}


def make_tools(conn, settings, memory) -> list[Tool]:
    def manage_memory(
        action: str, id: int | None = None, subject: str = "", content: str = ""
    ) -> str:
        if action == "list":
            rows = memory.facts.list(20)
            if not rows:
                return "No facts yet."
            return "\n".join(f"{row['id']} · [{row['subject']}] {row['content']}" for row in rows)
        if action == "edit":
            subject, content = subject.strip(), content.strip()
            if id is None or not subject or not content:
                raise ValueError("edit needs id, subject and content")
            if not memory.facts.update(int(id), subject, content):
                return f"No fact with id {id}."
            memory.rewrite_mirror()
            return f"Updated fact {id}: [{subject}] {content} (and {settings.mirror_path})."
        if action == "forget":
            if id is None:
                raise ValueError("forget needs id")
            if not memory.facts.delete(int(id)):
                return f"No fact with id {id}."
            memory.rewrite_mirror()
            return f"Forgot fact {id}; its file and the mirror entry are gone."
        raise ValueError(f"unknown action {action!r}")

    def update_persona(content: str) -> str:
        text = content.strip()
        if not text:
            raise ValueError("content cannot be empty")
        path = settings.persona_path
        if path.exists():
            path.with_suffix(".md.bak").write_text(
                path.read_text(encoding="utf-8"), encoding="utf-8"
            )
        path.write_text(text + "\n", encoding="utf-8")
        return f"Persona saved to {path} ({len(text)} bytes). The next turn uses it."

    return [
        Tool(
            "manage_memory", "List, correct or forget a stored fact.", MANAGE_SCHEMA, manage_memory
        ),
        Tool(
            "update_persona",
            "Replace the persona file with new standing instructions.",
            PERSONA_SCHEMA,
            update_persona,
        ),
    ]
