"""Messages: a draft that never leaves the machine — the outbox is a file.

Mechanism: send_message writes one markdown file with front matter. There is no
transport, and the returned sentence says so.

Rejected alternative: quietly integrating a mail or chat API. It would make the
agent claim a delivery it cannot verify, which the tool contract forbids.
"""

from __future__ import annotations

import re
from datetime import datetime

from byo.tools.registry import Tool

SEND_SCHEMA = {
    "type": "object",
    "properties": {
        "to": {"type": "string", "description": "who the message is for"},
        "body": {"type": "string", "description": "the message text"},
    },
    "required": ["to", "body"],
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:40] or "message"


def make_tools(conn, settings) -> list[Tool]:
    def send_message(to: str, body: str) -> str:
        to, body = to.strip(), body.strip()
        if not to or not body:
            raise ValueError("to and body are both required")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = settings.outbox_dir / f"{stamp}-{slugify(to)}.md"
        settings.outbox_dir.mkdir(parents=True, exist_ok=True)
        stamp_text = datetime.now().isoformat(timespec="seconds")
        path.write_text(
            f"---\nto: {to}\ncreated_at: {stamp_text}\n---\n\n{body}\n",
            encoding="utf-8",
        )
        return f"Drafted to {path} — not sent anywhere."

    return [
        Tool(
            "send_message",
            "Draft a message to a person; it is written to the local outbox.",
            SEND_SCHEMA,
            send_message,
        )
    ]
