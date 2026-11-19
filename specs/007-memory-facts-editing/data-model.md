# Phase 1 Data Model: Facts, Refusals and Activity Records

**Date**: 2026-11-19 | **Feature**: specs/007-memory-facts-editing

## Storage decision

No database migration. The existing facts table already holds every field this feature needs:
id, subject, content, source, created_at (see byo/db.py). The new constraints are enforced in
the curation seam, not as schema constraints, because the agent-facing tools keep their
current behavior and must still be able to write what they write today.

## Fact

A durable remembered statement, owned by the semantic store.

| Field | Type | Source | Rules |
|-------|------|--------|-------|
| id | integer, primary key | database | Never changes during an edit; it is the fact's identity. |
| subject | text, not null | person or agent | Cleaned: trimmed; each internal line break becomes one space. 1 to 120 Unicode code points after cleaning. |
| content | text, not null | person or agent | Cleaned: trimmed only; internal line breaks and spacing are preserved. 1 to 2000 Unicode code points after cleaning. |
| source | text, default 'user' | writer | A view add records 'user'. An edit preserves whatever source the fact already had ('user', 'tool', or 'consolidation'). Never rewritten by this feature. |
| created_at | text, default now | database | Preserved across edits. Returned by the API; any display keeps its existing timestamp presentation. |

**Duplicate key (derived, not stored)**: the pair (subject, content) after trimming,
case-folding and collapsing every whitespace run to one space. Two facts with the same key are
duplicates, regardless of source. The key is computed per request over all stored facts.

**Ordering**: newest first (id descending), as today. The Memory payload is capped at 500 rows;
that cap is the agreed scale, not a paging mechanism.

**Lifecycle**:
- Created: by the view (source 'user') or existing writers (save_note, consolidation).
- Updated: by the view, subject and/or content; identity, source and created_at survive.
- Deleted: existing Forget action (unchanged); out of this feature's validation scope except
  that a change aimed at a deleted fact must fail as not found.

## Fact draft

Not persisted. The values currently typed in the add form or in a row's edit mode.

| Field | Rules |
|-------|-------|
| subject | Trimmed for storage; whitespace-only is a refusal with field 'subject'. |
| content | Trimmed for storage; whitespace-only is a refusal with field 'content'. |
| origin form | 'add' reads the add form; 'edit' reads the row and carries the edit baseline. |
| preservation | A refused or failed save keeps the typed values in the form or row; they are never silently discarded. |

## Edit baseline

The subject and content the person saw when edit mode opened. It is carried in the edit request
as baseline_subject and baseline_content; it is not stored.

- Stored values equal the baseline: the edit may proceed.
- Stored values differ: refusal code fact_conflict; nothing is written; the list refreshes.
- Fact is gone: refusal code fact_not_found; nothing is recreated.
- Baseline fields omitted by a direct API caller: the edit is unconditional (compatibility with
  the 006 contract). The Memory view always supplies them.

## Refusals

One typed refusal from curation; the dashboard maps it to an HTTP status and an error object.

| Code | Meaning | Field | Extra | HTTP |
|------|---------|-------|-------|------|
| fact_validation | Empty/whitespace value, or over a length limit | 'subject' or 'content' | none | 400 |
| fact_duplicate | A different fact already has this normalized key | none | existing_id | 400 |
| fact_conflict | The stored fact changed since edit mode opened | none | none | 409 |
| fact_not_found | The edited fact no longer exists | none | none | 404 |
| fact_failed | Unexpected storage failure (message is generic, never echoes content) | none | none | 500 |
| bad_request | Action is missing or is not add/edit/forget | none | none | 400 |

Every refusal message names the field and the rule (for example: "content is longer than 2000
characters"), and every add/edit refusal produces exactly one activity record.

## API payloads

### GET /api/memory

~~~json
{
  "facts": [
    {"id": 12, "subject": "tea", "content": "green over black", "source": "user",
     "created_at": "2026-11-19 10:00:00"}
  ],
  "episodes": [{"id": 1, "happened_at": "2026-11-18", "summary": "booked a catch-up"}],
  "counts": {"facts": 1, "episodes": 1},
  "mirror_path": "/Users/me/.byo/MEMORY.md",
  "gate": {"retrieve": 2, "skip": 1, "last_decision": "retrieve", "last_reason": "..."},
  "consolidation": {"pending": 4, "threshold": 12, "last_run_at": "2026-11-19T10:00:00+08:00"},
  "warnings": []
}
~~~

- facts is newest first, capped at 500.
- counts reflect the returned list (the view's promise is every fact up to the cap).
- warnings is present and empty on health, or contains {code: "mirror_write_failed", message: ...}
  when a repair attempt failed. Mutation responses use the same shape and may also carry
  {code: "trace_write_failed", message: ...} if the activity append itself failed.
- gate and consolidation keep their existing shapes and sources.

### POST /api/memory (add)

Request:

~~~json
{"action": "add", "subject": "tea", "content": "green over black"}
~~~

Success 200:

~~~json
{"ok": true, "fact": {"id": 13, "subject": "tea", "content": "green over black",
 "source": "user", "created_at": "2026-11-19 10:05:00"},
 "memory": {"...": "same shape as GET /api/memory"},
 "warnings": []}
~~~

Refusal 400 (validation) or 400 (duplicate):

~~~json
{"error": {"code": "fact_duplicate", "message": "Fact 12 already says this — edit it instead.",
 "existing_id": 12}}
~~~

### POST /api/memory (edit)

Request:

~~~json
{"action": "edit", "id": 13, "subject": "tea", "content": "black over green",
 "baseline_subject": "tea", "baseline_content": "green over black"}
~~~

- Success shape is the same as add, with fact carrying the updated row.
- fact_conflict returns 409, fact_not_found returns 404; neither carries a memory payload, so
  the client reloads GET /api/memory to show the current truth.
- Duplicate check excludes the fact being edited.

### POST /api/memory (forget)

Unchanged: {action: "forget", id}. No new validation, no baseline, no activity requirement
beyond the existing behavior. Kept working so the existing view and tests do not regress.

## Activity record

One JSON Lines record per add or edit attempt, appended by Trajectory.record_activity through
the redacting sink. It has no turn attribution.

| Field | Value |
|-------|-------|
| type | "memory_change" |
| ts | ISO-8601 local timestamp with milliseconds, as every record |
| turn_id | "" (empty: this change is not part of a turn) |
| source | "dashboard" |
| action | "add" or "edit" |
| outcome | "ok", "refused" or "failed" |
| fact_id | integer for a successful add/edit or an edit refusal that knew the id; null otherwise |
| code | refusal code for refused/failed outcomes; null on success |
| field | "subject" or "content" when the refusal names a field; null otherwise |
| warning | "mirror_write_failed" or "trace_write_failed" when applicable; null otherwise |

The event never contains subject, content, a message that echoes either, or a secret. Redaction
still runs at the sink. Existing projections ignore the type: group_turns only builds turns
around turn_start/turn_end, _step returns None for unknown types, and the live map filters by
turn id, so a memory_change record cannot become a visible step or a spend line.

**Exactly one rule**: the dashboard records once after the attempt settles (store outcome and
mirror attempt), including validation refusals, duplicates, conflicts, not-found and unexpected
failures. A malformed request that never names add or edit is not an add/edit attempt and is not
recorded. If the append fails, the change result is unchanged and the response carries the
trace_write_failed warning.

## View state (client-side, not persisted)

MEMORY_UI in dock.js:

| Field | Meaning |
|-------|---------|
| editingId | The one fact id in edit mode, or null. |
| addDraft | {subject, content} retained across a refusal so typed text survives the re-render. |
| editDraft | {subject, content} for the open edit; initialized from the baseline. |
| errors | Field errors ({subject?: message, content?: message}) from the last refusal. |
| general | A duplicate/conflict/not-found/server message, plus existing_id for duplicates. |
| notice | The success confirmation or a conflict notice, announced with role=status. |
| warning | A mirror or trace warning from the last payload. |
| saving | True while a request is in flight; save controls are disabled. |

**State transitions**:

- Read -> edit: capture baseline, prefill both fields, disable the add form and other edit controls.
- Edit -> saving: disable save and cancel; keep values.
- Saving -> saved: close edit, replace the payload, show a confirmation, focus the row's edit control.
- Saving -> refused: stay in edit, keep values, show field or general message, focus the first field.
- Saving -> conflict: close edit, reload the payload, show the conflict notice, focus the list.
- Saving -> not found: close edit, reload, show the message.
- Add -> saved: clear the draft and form, show a confirmation, keep the fact first, focus subject.
- Add -> refused: keep the draft, show the message, focus the offending field.

## Scale and budgets

- Facts: up to roughly 500 shown; GET /api/memory returns at most 500.
- Add/edit validation: one scan of at most 500 rows for duplicates; no network.
- View mutation: store write, one mirror rewrite (up to 501 small files), one activity append.
- Response time target: the result is visible within 2 seconds of the action at 500 facts (SC-010).
- No new runtime dependency, no build step, no schema change, no new memory type.
