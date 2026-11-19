# Quickstart Validation: Facts Add/Edit

**Date**: 2026-11-19 | **Feature**: specs/007-memory-facts-editing

A runnable guide for proving the feature end to end. Shapes and guarantees are in
[data-model.md](data-model.md) and [contracts/memory-facts-api.md](contracts/memory-facts-api.md);
this file only lists commands and expected outcomes.

## Prerequisites

- A Python virtual environment with the project installed: .venv/bin/python exists.
- No network access and no real model credential are needed: every Memory operation touches
  only SQLite, the local mirror and the trajectory.

## 1. The offline suite

~~~bash
make eval
make lint
~~~

Expected: the deterministic suite passes. Baseline before this feature was 234 tests; the
post-change run includes the new curation, dashboard and static-view cases and reports a higher
count. Lint is clean.

## 2. Run the dashboard against a scratch home

Start the server in one terminal (a dummy key is enough because Memory operations never call a
model; do not use this instance for chat):

~~~bash
SCRATCH_HOME=$(mktemp -d)
BYO_HOME="$SCRATCH_HOME" BYO_API_KEY=test BYO_PORT=7788 .venv/bin/python -m byo dashboard
~~~

Open http://127.0.0.1:7788, choose **Memory**, and keep a second terminal for the checks below.
The scratch home path is printed at startup and in the sidebar.

## 3. Add and edit by hand

| Scenario | Steps | Expected |
|----------|-------|----------|
| Add a multi-line fact | Subject "tea", content two paragraphs separated by a blank line; press remember | Confirmation appears; the fact is first; count increments; MEMORY.md and memory/<id>.md contain the text with the line break preserved |
| Empty submission | Clear the subject (or content) and press remember | A message names the field and says it is required; nothing is stored; the typed value remains; the trajectory gains one memory_change record with outcome refused |
| Over the limit | Subject of 121 characters, or content of 2001 characters; press remember | A message states 120 or 2000; nothing is trimmed or stored; the form keeps the text |
| Duplicate | Add "tea" / "green over black" twice | The second is refused, names the existing fact, and offers its edit control; count stays at one |
| Edit subject only | Use edit on the row, change "tea" to "Tea (morning)", save | Subject updates; content, source and created_at are unchanged; row and MEMORY.md agree |
| Edit content only, multi-line | Use edit, replace content with two lines, save | Both lines render literally; MEMORY.md keeps the line break |
| Cancel | Change both fields, press cancel | Nothing is written; the read row shows the original values; no confirmation |
| Conflict | Open Memory in two tabs; change a fact in tab A; in tab B, open the old row, edit, save | Tab B shows a conflict notice, closes edit mode, reloads the list, and does not overwrite tab A |
| Literal text | Add content <img src=x onerror=alert(1)> | It is displayed as text; no dialog and no image request |
| Keyboard only | Tab to the add form, type, submit; then edit, save, cancel | Every control is reachable; save is operable from the keyboard; after a refusal focus lands on the first invalid field |
| Mirror degradation | chmod 444 on the scratch MEMORY.md, add a fact, then chmod 644 and refresh Memory | The add still succeeds with a warning that the mirror is stale; after restoring permissions and refreshing, the warning is gone and MEMORY.md contains the new fact |

## 4. API checks

The same scratch home, server running. Replace SUBJECT/CONTENT as needed.

~~~bash
curl -s http://127.0.0.1:7788/api/memory
curl -s -i -X POST http://127.0.0.1:7788/api/memory \
  -H 'Content-Type: application/json' \
  -d '{"action":"add","subject":"tea","content":"green over black"}'
curl -s -i -X POST http://127.0.0.1:7788/api/memory \
  -H 'Content-Type: application/json' \
  -d '{"action":"add","subject":"tea","content":"green over black"}'
~~~

Expected:

- The first POST is 200 with ok true, the new fact, a memory payload and warnings [].
- The second is 400 with error.code fact_duplicate and existing_id equal to the first fact's id.
- GET /api/memory lists the fact once and counts.facts is 1.

Edit with a stale baseline (use the id from the first response and its current values):

~~~bash
curl -s -i -X POST http://127.0.0.1:7788/api/memory \
  -H 'Content-Type: application/json' \
  -d '{"action":"edit","id":1,"subject":"tea","content":"black",
       "baseline_subject":"wrong","baseline_content":"green over black"}'
~~~

Expected: 409 with error.code fact_conflict; GET /api/memory still shows the original fact.

## 5. Activity record

~~~bash
grep memory_change "$SCRATCH_HOME"/trajectories/*.jsonl
~~~

Expected: exactly one line per add/edit attempt, including refusals and the conflict, with
action, outcome, fact_id where applicable, code, field and warning. No subject or content text
appears; a secret pasted as fact content is not present in the record.

## 6. Volume at the agreed scale

Seed 500 facts into the running scratch home (stop the server first if your SQLite build
complains, then start it again):

~~~bash
BYO_HOME="$SCRATCH_HOME" .venv/bin/python - <<'PY'
from byo.config import load_settings
from byo.db import connect

settings = load_settings()
conn = connect(settings.home)
for index in range(500):
    conn.execute(
        "INSERT INTO facts (subject, content, source) VALUES (?, ?, 'user')",
        (f"subject {index}", f"content number {index}"),
    )
conn.commit()
PY
~~~

Reload Memory. Expected: every fact is listed (at most 500), counts.facts is 500, and an add or
edit completes within about 2 seconds (SC-010).

## 7. Regression checks

~~~bash
grep -c memory_change "$SCRATCH_HOME"/trajectories/*.jsonl
curl -s http://127.0.0.1:7788/api/data | head -c 400
~~~

- /api/data is unchanged in shape; its memory slice is still the 100-row overview payload.
- No save_note or manage_memory behavior changed: their existing tests (test_memory_admin.py,
  test_memory.py) still pass under make eval.
- The Memory view keeps its existing labels: facts, episodes, mirror, subject, source, when,
  what, forget, nothing remembered yet.

## Related artifacts

- [spec.md](spec.md) — acceptance scenarios and measurable outcomes.
- [plan.md](plan.md) — technical context, constitution check and source layout.
- [research.md](research.md) — decisions and rejected alternatives.
- [data-model.md](data-model.md) — entities, refusals, payloads, activity record, view state.
- [contracts/memory-facts-api.md](contracts/memory-facts-api.md) — HTTP and UI contract.
