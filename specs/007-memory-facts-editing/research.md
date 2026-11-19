# Phase 0 Research: Fact Capture and Correction in Memory

**Date**: 2026-11-19 | **Feature**: specs/007-memory-facts-editing

This feature changes how a person adds and edits facts from the dashboard Memory view. The
store schema stays as it is; the new work is a validation seam, a conflict rule, a turn-less
activity record, a mirror repair path, and an in-place editing surface that is honest about
every outcome.

Baseline before implementation: the offline deterministic suite passes, 234 tests collected
and green. No live-model call is involved anywhere in this feature.

## Decision 1: Fact-writing rules live in a memory-module curation seam

**Decision**: Add byo/memory/curation.py. It owns cleaning (trim; subject newlines become
spaces; content line breaks survive), the 120/2000 display-length limits, normalized duplicate
detection, the not-found/conflict refusals, and the add/edit calls into FactStore. It raises
one typed refusal (code, field, message, existing id) and never formats HTTP or HTML.

**Rationale**: The rules are memory policy, not surface policy. A pure seam is testable
without a server, gives the dashboard one place to call, and keeps FactStore a store rather
than a policy object. This follows constitution III (small modules, narrow contracts). The
module carries a design note naming what it implements and the rejected alternative.

**Alternatives considered**:
- Validate in the dashboard handler: rejected. The rules would only be reachable over HTTP,
  would sit next to response formatting, and would be hard to test in isolation.
- Put validation on FactStore: rejected. FactStore is used by manage_memory and save_note,
  which are deliberately unchanged this iteration; adding product rules there would change
  their behavior by accident.
- Add a schema library: rejected. A new runtime dependency for two integer limits and an
  exception is not justified.

**Length unit**: Python len() over the cleaned string measures Unicode code points. That is the
deterministic, dependency-free proxy for display characters. Tests use ASCII, CJK and
single-code-point emoji; a multi-code-point emoji grapheme may count more than one unit, and
that trade-off is recorded rather than hidden behind a new dependency.

## Decision 2: Conflict detection is compare-and-swap on the edit baseline

**Decision**: The edit request carries the subject and content shown when edit mode opened
(baseline_subject, baseline_content). curation loads the fact (missing -> not found), compares
the stored subject/content with the baseline (different -> conflict), then writes with one
conditional statement: UPDATE facts SET subject = ?, content = ? WHERE id = ? AND subject = ?
AND content = ?. A rowcount of zero after a matching read is also a conflict. The baseline
fields are optional at the HTTP level: when absent, the edit is unconditional, which keeps
the 006-era API contract and its existing test working. The Memory view always sends them.

**Rationale**: The clarification chose the edit baseline over a revision column. A conditional
update makes the check atomic against save_note or another process writing the same fact
between the read and the write. It needs no schema change and no migration, so no fact gains a
last-edited field or a UI timestamp.

**Alternatives considered**:
- Read then unconditional update: rejected. Two writers can interleave and the older value
  wins silently, which is exactly the defect the spec names.
- A revision or updated_at column: rejected by the clarification; it adds a migration and an
  obligation to show an edit time.
- Last-write-wins: rejected; it drops the conflict requirement and its acceptance scenario.

**Concurrency note**: the dashboard also takes a process lock around its own mutations so two
browser requests cannot both pass the duplicate check and insert. The conditional update still
covers writers outside that lock.

## Decision 3: Duplicates are compared on a normalized projection, scanned in Python

**Decision**: The duplicate key is the pair (subject, content) after trimming, case-folding and
collapsing every internal whitespace run to one space. The check scans every stored fact's id,
subject and content (store helper returns all rows) and excludes the fact being edited.

**Rationale**: The rule is deterministic and testable, and it deliberately treats "Tea" plus
"green   over black" as the same fact as "tea" plus "green over black". At the agreed scale
(a few hundred facts) a Python scan under the dashboard lock costs microseconds. It needs no
schema change and cannot drift from the displayed rules.

**Alternatives considered**:
- An SQL lower(trim(subject)) comparison: rejected. It leaves internal whitespace differences
  and would make the rule depend on SQLite string functions.
- A generated normalized column with a unique index: rejected. It is a migration, changes
  insert failure modes for every writer including the unchanged tools, and is not needed at
  this scale.
- Reusing the agent tool's duplicate behavior: rejected. The tools have no duplicate rule and
  are explicitly untouched this iteration.

## Decision 4: Validation is server-authoritative; the form submits even when empty

**Decision**: The add form is submitted with novalidate, and no required or maxlength attribute
blocks submission. The client always posts the typed values; the server cleans and validates,
returns a field-level refusal, and records the attempt. The UI maps the refusal to the field,
keeps the typed values, and focuses the first offending field.

**Rationale**: FR-026 requires one activity record for every accepted or refused attempt. A
browser-native required or maxlength check would block the request, so the refusal would be
invisible to the record and untestable through the API. Server authority also makes the
limits provable with the offline suite.

**Alternatives considered**:
- required and maxlength attributes: rejected. Silent client refusal, no activity record, and
  the server would never see the over-limit value.
- Client-side validation followed by a synthetic activity call: rejected. It would record an
  event for a change that never reached the store and could drift from the server rule.
- Both client and server validation, with the client only for speed: allowed as a rendering
  convenience, but the server remains authoritative and every refusal still comes from it.

## Decision 5: The Memory view has its own full payload, capped at 500 facts

**Decision**: GET /api/memory returns every fact up to a 500-row cap, plus counts, warnings,
mirror path, gate and consolidation status. The Memory view fetches this payload when it is
entered and after a mutation; it no longer reads the 100-row slice embedded in /api/data.
/api/data keeps its existing 100-row memory slice for other surfaces.

**Rationale**: The scale clarification promises every fact in one list at up to roughly 500
facts, but the current Memory view is fed by a 100-row query. Giving the view its own payload
satisfies the promise without inflating the payload every overview render carries. The same
payload already exists for the API and its tests; only the cap and the counts are new.

**Alternatives considered**:
- Raise the /api/data slice to 500: rejected. Every overview refresh would carry the full fact
  list even though only the Memory view needs it.
- Keep 100 and document a smaller scale: rejected; it contradicts the clarified assumption.
- Pagination or search: rejected by the clarification and kept out of scope.

## Decision 6: Activity records are turn-less trajectory events, redacted at the sink

**Decision**: Add Trajectory.record_activity(event_type, **fields). It writes the normal
envelope (type, ts) with turn_id "" through the same redact-then-append path as any other
record. The dashboard writes one memory_change event per add or edit attempt with action,
outcome, fact id where it applies, refusal code and field, and a mirror warning flag. It never
records the subject or content.

**Rationale**: The trajectory is the project's only append-only record, and its sink is the
only place redaction can be guaranteed. A turn-less record keeps admin changes from being
misattributed to a turn, while group_turns ignores events outside a turn and _step ignores
unknown types, so no existing projection changes. The event stays readable through
/api/events, the daily JSONL file, and any trajectory reader. Recording only identity and
outcome means a fact containing a secret cannot leak through the activity record.

**Alternatives considered**:
- Reuse the last turn id: rejected. An admin change after a turn would appear to belong to
  that turn and would pollute parity comparisons between CLI and dashboard turns.
- A separate activity.jsonl file: rejected. It is a second record with its own reader, and the
  feed would need to know about it.
- A database table: rejected. It is a second source that can disagree with the file a person
  opens, which the project explicitly avoids.

**Failure note**: if the trajectory append itself fails, the fact change stays successful and
the response carries a trace_write_failed warning; this is an I/O failure path, not a silent
drop, and it never loses the stored fact.

## Decision 7: A mirror failure degrades to a warning and repairs on the next memory read

**Decision**: The store write is the truth. After a successful add or edit, the dashboard tries
to rewrite the readable mirror. On failure it writes a small marker file (home/.mirror-pending),
keeps the stored change, and returns 200 with a warnings entry. GET /api/memory checks the
marker; when present it retries the rewrite once, removes the marker on success, and omits the
warning; on failure it keeps the marker and reports the warning. The marker is durable, so a
restart does not lose the repair obligation.

**Rationale**: FR-019 asks for a warning plus convergence on the next successful change or view
refresh. The marker makes convergence real without rewriting every fact file on every read and
without a background worker. A hidden marker in the home directory is not part of the mirror
glob and carries no fact text.

**Alternatives considered**:
- Fail the mutation when the mirror fails: rejected. The store already changed; failing would
  either lie or force a rollback across two media.
- Rewrite the mirror on every GET: rejected. With 500 facts that is 501 file writes per view
  load.
- A background repair thread or queue: rejected. New moving parts and lifecycle for a rare
  local failure.
- An in-process dirty flag only: rejected. A restart would silently leave the mirror stale.

## Decision 8: In-place editing is state plus a pure renderer, with server outcomes driving it

**Decision**: dock.js gains a small MEMORY_UI state object (editing id, add draft, edit draft,
field errors, general error, notice, warning, saving). memoryView renders from the payload and
that state. Opening edit captures the baseline and prefills both fields; save posts the draft;
cancel restores the read row; a refusal re-renders with typed values and field messages; a
conflict closes the edit and reloads the payload. Only one row is editable at a time, and the
add form and other edit controls are disabled while it is open.

**Rationale**: This keeps the dashboard's existing string-rendering architecture and its
no-build constraint. It preserves typed values across failures (a fresh render would otherwise
empty the fields), gives deterministic focus targets, and avoids contenteditable's keyboard and
IME problems. Server refusals, not client guesses, decide what the person sees.

**Alternatives considered**:
- contenteditable cells: rejected. Rich text, IME, selection and accessibility complexity for
  a two-field edit; also easy to submit HTML that the renderer must then untangle.
- A modal or the existing window.prompt: rejected. The spec explicitly requires the row itself
  with both fields visible and no retyping; a prompt cannot show both values.
- A new front-end framework or build step: rejected. The constitution's dependency budget and
  the existing no-build dashboard.

## Decision 9: Escaping and line breaks are explicit rendering rules

**Decision**: Every fact value is passed through esc() in text and in attribute values, and the
read row wraps content in a .fact-body element with white-space: pre-wrap. The server returns
raw text, never HTML, so escaping happens exactly once at the rendering boundary.

**Rationale**: FR-020 requires literal rendering. The existing esc() helper is the project's
boundary; reusing it keeps the rule reviewable. pre-wrap is what preserves the multi-line
content the add form now accepts without inserting markup.

**Alternatives considered**:
- Server-side HTML escaping: rejected. It would double-escape and put presentation in the API.
- Rendering fact text as Markdown: rejected. Memory content is literal text; Markdown would
  create links and emphasis the person did not write.

## Decision 10: Testing stays offline, HTTP-level and source-contract level

**Decision**: Add evals/deterministic/test_curation.py for the rules; extend test_dashboard.py
for add/edit contracts, statuses, mirror warning and repair, activity records and the 500-fact
budget; extend test_views_static.py for the rendered controls, escaping calls, ARIA wiring and
the absence of prompt/required/maxlength blocks. No Node, browser or network enters the
default path.

**Rationale**: Constitution II and V require an offline, credential-free suite; 006 already
rejected a Node renderer as a second toolchain. HTTP tests exercise the real handler and the
real store; source contracts pin the JS wiring that a Python test cannot execute.

**Alternatives considered**:
- Node-based render tests: rejected for the same reason as 006 (second toolchain).
- Playwright or a browser driver: rejected. A new dependency and a display requirement for a
  local single-user page.
- Manual clicking only: rejected. It leaves the new rules without a regression net.

**Eval delta**: baseline 234 tests pass. The feature adds the curation, dashboard and static
cases listed above; the post-change suite must pass with no network and no credentials, and the
completion report records the new count and the added cases. No prompt, tool description, loop
or context behavior changes.
