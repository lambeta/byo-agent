# Contracts: Memory Facts Add/Edit

**Date**: 2026-11-19 | **Feature**: specs/007-memory-facts-editing

The dashboard's external surface is its loopback HTTP API plus the hash-routed Memory view. This
contract covers the facts add/edit path only. It is additive to the 006 dashboard contract:
forget, chat, tools, settings and navigation keep their existing behavior.

## GET /api/memory

Read-only. Returns the full Memory payload for the view and for tests.

- **Response 200**: facts (newest first, at most 500), episodes, counts {facts, episodes},
  mirror_path, gate, consolidation, warnings. Shapes are in [data-model.md](../data-model.md).
- **Facts**: every field needed to render and edit a row: id, subject, content, source,
  created_at. Values are raw text, never HTML.
- **Counts**: facts equals the number of facts in this response; episodes equals the number of
  episodes in this response.
- **Warnings**: an empty list on a healthy mirror; otherwise one entry per problem, each with a
  code and a person-readable message. Never includes fact text or a secret.
- **Repair**: when the durable mirror-pending marker is present, the handler retries the mirror
  rewrite once before building the response. A successful retry removes the marker and the
  warning; a failed retry keeps both.
- **Errors**: a server failure follows the existing 500 {"error": {code, message}} envelope.

## POST /api/memory — add

Request: {action: "add", subject, content}. Both values are strings; missing values are treated
as empty strings.

**Guarantees**:
- Values are trimmed; the subject's internal line breaks become single spaces; content line
  breaks are preserved.
- Empty/whitespace-only values are refused with fact_validation and a field.
- Values over 120 (subject) or 2000 (content) code points are refused with fact_validation and
  a message stating the limit; nothing is stored or truncated.
- A normalized duplicate of any stored fact is refused with fact_duplicate and existing_id;
  nothing is stored.
- Success stores source 'user' and the current creation time, commits the store, attempts the
  mirror, and returns the fact plus the refreshed payload.
- If the mirror rewrite fails, the response is still 200; warnings carries
  mirror_write_failed, and the change is kept.

**Success 200**:

~~~json
{"ok": true,
 "fact": {"id": 13, "subject": "tea", "content": "green over black",
          "source": "user", "created_at": "2026-11-19 10:05:00"},
 "memory": {"...": "shape of GET /api/memory"},
 "warnings": []}
~~~

**Refusals**:

| Case | Status | Body |
|------|--------|------|
| empty/whitespace or over limit | 400 | {"error": {"code": "fact_validation", "message": "...", "field": "subject" or "content"}} |
| normalized duplicate | 400 | {"error": {"code": "fact_duplicate", "message": "...", "existing_id": 12}} |
| unexpected storage failure | 500 | {"error": {"code": "fact_failed", "message": "The fact could not be saved."}} |
| action missing/unknown | 400 | {"error": {"code": "bad_request", "message": "..."}} |

## POST /api/memory — edit

Request: {action: "edit", id, subject, content, baseline_subject?, baseline_content?}.

**Guarantees**:
- The fact must exist; otherwise 404 fact_not_found and nothing is created.
- Subject/content are cleaned, validated and duplicate-checked exactly as for add, excluding the
  fact itself.
- When both baseline fields are present, they are compared with the stored values. A difference
  is 409 fact_conflict; the store is unchanged. The write itself is a conditional update on
  id + baseline, so a writer that slips between the read and the write is also a conflict.
- When baseline fields are absent, the edit is unconditional after validation; this preserves
  the 006 API contract for direct callers. The Memory view always sends both baseline fields.
- Success preserves id, source and created_at, updates subject and/or content, attempts the
  mirror, and returns the updated fact plus the refreshed payload.
- A mirror failure degrades to 200 with warnings, exactly as for add.

**Success 200**: same shape as add, with the updated fact.
**Refusals**: 400 fact_validation / fact_duplicate, 404 fact_not_found, 409 fact_conflict,
500 fact_failed.

## POST /api/memory — forget

Unchanged. {action: "forget", id} keeps its current response and error behavior. This feature
does not add validation, confirmation or activity records to forget.

## Activity record

- Event type: memory_change, appended to the current day's JSONL trajectory through the
  redacting sink.
- Envelope: type, ts, turn_id "" (empty), source "dashboard"; fields action, outcome, fact_id,
  code, field, warning. No subject or content.
- Exactly one record per add/edit attempt, including every refusal and unexpected failure.
- Readable through GET /api/events, the daily file, and any trajectory reader. Existing
  projections ignore it as a step or a spend line; it never belongs to a turn.
- If the append fails, the change result is unchanged and the response warning is
  trace_write_failed.

## UI contract — Memory view, Facts section

**Add form**
- Separate labeled subject input and content textarea; content accepts multiple lines.
- The form has novalidate; no required or maxlength attribute may block a submission, so every
  attempt reaches the server and is recorded.
- Submit posts even when either field is empty. A refusal names the field, shows the message
  next to it (role=alert), keeps the typed values, sets aria-invalid, and moves focus to the
  first offending field.
- Success shows a role=status confirmation, clears the form and draft, puts the new fact first,
  updates the fact count from the returned payload, and focuses the subject field.
- A duplicate refusal shows the message and a control that starts editing the existing fact;
  the typed values stay.

**Edit mode**
- Every row has an edit control. Activating it replaces that row's read cells with prefilled
  subject and content fields plus save and cancel; no separate dialog and no retyping of the
  unchanged field.
- Save posts the draft and the captured baseline. Success updates the row in place, preserves
  identity/origin/creation time, shows a confirmation and focuses the row's edit control.
- Cancel writes nothing and restores the read row exactly.
- A validation refusal keeps edit mode and the typed values, shows field messages, and focuses
  the first offending field.
- A conflict or not-found closes edit mode, reloads the payload so the list shows the current
  truth, and shows an explicit notice; no older value overwrites a newer one.
- While one row is in edit mode, the add form and the other rows' edit controls are disabled;
  save and cancel are disabled while a request is in flight. Repeated activation cannot write
  twice.

**Rendering and accessibility**
- Every fact value is escaped with esc() in text and in attribute values; the server never sends
  HTML. Fact content uses white-space: pre-wrap so line breaks are preserved literally.
- Labels are associated with their controls; field messages are connected with
  aria-describedby; confirmations and warnings use role=status; field refusals use role=alert.
- All controls are native buttons/inputs/textarea and operable with a keyboard alone; focus is
  visible through the existing focus-visible tokens.
- No window.prompt, no alert, no contenteditable, and no client-side length cap may stand in
  for the server rule.

## Compatibility and non-goals

- No new tools or actions; save_note and manage_memory schemas, validation and result text are
  unchanged.
- No change to retrieval, the gate, consolidation, episodes or the mirror format.
- No new dependencies, no build step, no schema migration.
- /api/data keeps its existing memory slice for other surfaces; only /api/memory and the
  Memory view gain the 500-row full payload.
- Hash route #memory and the rest of the navigation are unchanged.
