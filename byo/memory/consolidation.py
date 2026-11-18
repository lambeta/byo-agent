"""Consolidation: turn raw chat into facts and one episode, every N exchanges.

Mechanism: when the unconsolidated backlog reaches the configured size, ask the small
model for candidate facts and one episode, keep every fact except one that only
repeats text this turn already recalled, mark the consumed rows, and rewrite the
mirror. Any failure leaves the rows pending for the next attempt.

Rejected alternative: storing every message as a memory. It makes retrieval noise, and
the person would have to curate rather than correct.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from byo.loop.types import Message, Request

SYSTEM = (
    "You distill a conversation into durable memory. Keep only facts worth having next "
    "week: preferences, people, ongoing projects, decisions. Do not keep small talk. "
    'Reply with JSON only: {"facts": [{"subject": "...", "content": "..."}], '
    '"episode": "one sentence about what happened"}'
)

PROMPT = """Conversation since the last consolidation:

{transcript}

What happened this turn that the assistant already recalled (do not keep a fact that
only repeats this):
{recalled}
"""


def pending_rows(conn) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in conn.execute(
            "SELECT id, role, content, created_at FROM chat_log WHERE consolidated = 0 ORDER BY id"
        )
    ]


def transcript(rows: list[dict[str, Any]]) -> str:
    return "\n".join(f"{row['role']}: {row['content']}" for row in rows)


def normalize(content: str) -> str:
    return " ".join(str(content).lower().split())


def is_repeat(content: str, recalled: str) -> bool:
    """A fact that only restates what the turn already read is not new."""
    fact = normalize(content)
    if not fact or not recalled:
        return False
    return fact in normalize(recalled)


def consolidate(
    conn,
    adapter,
    model: str,
    facts,
    episodes,
    recalled: str = "",
    max_tokens: int = 512,
) -> dict[str, Any] | None:
    rows = pending_rows(conn)
    if not rows:
        return None
    request = Request(
        model=model,
        system=SYSTEM,
        messages=(
            Message.user(
                PROMPT.format(transcript=transcript(rows), recalled=recalled or "(nothing)")
            ),
        ),
        max_tokens=max_tokens,
    )
    try:
        response = adapter.complete(request)
    except Exception:  # noqa: BLE001 - consolidation never fails the turn
        return None
    start, end = response.text().find("{"), response.text().rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(response.text()[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    kept: list[dict[str, Any]] = []
    for candidate in data.get("facts") or []:
        if not isinstance(candidate, dict):
            continue
        subject = str(candidate.get("subject") or "").strip()
        content = str(candidate.get("content") or "").strip()
        if not subject or not content or is_repeat(content, recalled):
            continue
        facts.add(subject, content, source="consolidation")
        kept.append({"subject": subject, "content": content})

    episode_text = str(data.get("episode") or "").strip()
    if episode_text:
        last = rows[-1]["created_at"] or date.today().isoformat()
        episodes.add(str(last)[:10], episode_text)

    conn.executemany(
        "UPDATE chat_log SET consolidated = 1 WHERE id = ?", [(row["id"],) for row in rows]
    )
    conn.commit()

    return {
        "new_facts": len(kept),
        "kept": kept,
        "episode": episode_text or None,
        "messages": len(rows),
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
