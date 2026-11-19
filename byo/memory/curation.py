"""Curation: validated human writes to facts.

Mechanism: one pure rule module for the Memory view. It cleans the two fields, bounds their
length, detects a normalized duplicate, compares an edit baseline and writes through FactStore.
It raises one typed refusal (code, message, field, existing id) that the dashboard maps to HTTP,
so the rules are testable without a server and live in the module that owns memory, not next to
response formatting.

Rejected alternative: validating inside the dashboard handler. The rules would only be reachable
over HTTP, would be hard to unit test, and would drift from any future surface that reuses them.

Length is measured with len() over the cleaned text: Unicode code points, a deterministic proxy
for display characters that needs no new dependency.
"""

from __future__ import annotations

import re
from typing import Any

SUBJECT_LIMIT = 120
CONTENT_LIMIT = 2000

_SPACE_RUN = re.compile(r"\s+")
_NEWLINE = re.compile(r"\s*\n\s*")


class Refused(Exception):
    """One explicit refusal: a stable code, a person-readable message and its field."""

    def __init__(
        self,
        code: str,
        message: str,
        field: str | None = None,
        existing_id: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.field = field
        self.existing_id = existing_id


def clean_subject(text: Any) -> str:
    """Trim, and turn any internal line break into one space."""
    return _NEWLINE.sub(" ", str(text or "")).strip()


def clean_content(text: Any) -> str:
    """Trim only: content keeps its internal line breaks and spacing."""
    return str(text or "").strip()


def duplicate_key(subject: str, content: str) -> tuple[str, str]:
    """The normalized pair two facts must share to count as the same statement."""
    return (
        _SPACE_RUN.sub(" ", subject).strip().casefold(),
        _SPACE_RUN.sub(" ", content).strip().casefold(),
    )


def _prepare(subject: Any, content: Any) -> tuple[str, str]:
    subject = clean_subject(subject)
    content = clean_content(content)
    if not subject:
        raise Refused("fact_validation", "subject is required", field="subject")
    if not content:
        raise Refused("fact_validation", "content is required", field="content")
    if len(subject) > SUBJECT_LIMIT:
        raise Refused(
            "fact_validation",
            f"subject is longer than {SUBJECT_LIMIT} characters",
            field="subject",
        )
    if len(content) > CONTENT_LIMIT:
        raise Refused(
            "fact_validation",
            f"content is longer than {CONTENT_LIMIT} characters",
            field="content",
        )
    return subject, content


def duplicate_of(
    store, subject: str, content: str, exclude_id: int | None = None
) -> dict[str, Any] | None:
    """Return a different stored fact with the same normalized pair, if any."""
    wanted = duplicate_key(subject, content)
    for row in store.all():
        if exclude_id is not None and int(row["id"]) == int(exclude_id):
            continue
        if duplicate_key(str(row["subject"]), str(row["content"])) == wanted:
            return dict(row)
    return None


def _duplicate_refusal(found: dict[str, Any]) -> Refused:
    return Refused(
        "fact_duplicate",
        f"Fact {found['id']} already says this — edit it instead.",
        existing_id=int(found["id"]),
    )


def add(store, subject: Any, content: Any, source: str = "user") -> dict[str, Any]:
    """Validate and store a new fact; return the stored row."""
    subject, content = _prepare(subject, content)
    found = duplicate_of(store, subject, content)
    if found is not None:
        raise _duplicate_refusal(found)
    fact_id = store.add(subject, content, source=source)
    row = store.get(fact_id)
    if row is None:  # pragma: no cover - the insert and this read share one connection
        raise Refused("fact_failed", "The fact could not be saved.")
    return dict(row)


def edit(
    store,
    fact_id: int,
    subject: Any,
    content: Any,
    baseline_subject: str | None = None,
    baseline_content: str | None = None,
) -> dict[str, Any]:
    """Validate and update one fact; preserve identity, source and creation time.

    When both baselines are supplied, the write is a compare-and-swap: a fact that changed
    since edit mode opened is refused as a conflict and never overwritten by an older value.
    """
    current = store.get(int(fact_id))
    if current is None:
        raise Refused("fact_not_found", f"No fact with id {fact_id}.")
    subject, content = _prepare(subject, content)
    found = duplicate_of(store, subject, content, exclude_id=int(current["id"]))
    if found is not None:
        raise _duplicate_refusal(found)
    conflict = Refused(
        "fact_conflict",
        "This fact changed while you were editing it. The list now shows the current values.",
    )
    if baseline_subject is not None and baseline_content is not None:
        if current["subject"] != baseline_subject or current["content"] != baseline_content:
            raise conflict
        if not store.update_if_unchanged(
            int(fact_id), subject, content, baseline_subject, baseline_content
        ):
            raise conflict
    else:
        store.update(int(fact_id), subject, content)
    row = store.get(int(fact_id))
    if row is None:  # pragma: no cover - the update and this read share one connection
        raise Refused("fact_not_found", f"No fact with id {fact_id}.")
    return dict(row)
