# Implementation Plan: Fact Capture and Correction in Memory

**Branch**: `007-memory-facts-editing` | **Date**: 2026-11-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from specs/007-memory-facts-editing/spec.md

## Summary

The Facts section of the dashboard Memory view gets a complete add/edit experience. A correction
opens in the row with both subject and content prefilled, so only the wrong field changes and
the fact keeps its identity, origin and creation time. Adding accepts multi-line content and
proves it was kept. Both actions share one server-side rule set: trimming, 120/2000-code-point
limits, normalized duplicate blocking, field-level refusals, baseline conflict detection, and an
explicit outcome for every attempt. Successful changes keep the store, view and readable mirror
in agreement; a mirror failure degrades to a warning that repairs on the next Memory read. Every
add/edit attempt appends one turn-less memory_change event to the trajectory, and the Memory view
receives a full payload capped at the agreed 500 facts.

No schema change, no new dependency, no build step, no new tool. The agent-facing tools
(save_note, manage_memory) are untouched, as clarified.

## Technical Context

**Language/Version**: Python 3.11+ (runtime in this checkout is 3.14); dependency-free vanilla
JavaScript for the static dashboard.

**Primary Dependencies**: None added. Backend stays stdlib (http.server, sqlite3); frontend stays
build-free classic scripts; dev tooling stays pytest + ruff.

**Storage**: Existing SQLite facts table (no migration); existing MEMORY.md and memory/<id>.md
mirror; existing JSON Lines trajectory, now carrying memory_change records.

**Testing**: Offline deterministic pytest suite (make eval / make gate). Baseline: 234 tests,
all passing. New: curation unit tests, dashboard HTTP contract/activity/mirror/scale tests, and
static source-contract tests for the JS view. No network, no credentials.

**Target Platform**: macOS/Linux local machine; dashboard on 127.0.0.1 loopback.

**Project Type**: local-first agent (CLI + local web dashboard), single repository.

**Performance Goals**: With 500 stored facts, opening the Facts section and completing an add or
edit shows the result within 2 seconds (SC-010). Duplicate detection scans the stored facts
(about 500 at the agreed scale). No new network calls.

**Constraints**: Offline-first test path; no new runtime dependencies; secrets redacted at the
trace sink; one source of truth for facts; view-only scope (tools, gate, retrieval and
consolidation unchanged); 120/2000 limits enforced on every save, including legacy over-limit
facts; no history/undo, no paging, search or filtering.

**Scale/Scope**: One person locally; up to roughly 500 facts displayed in one list; one extended
API endpoint, one new rules module, one new trajectory helper, one view and its styles, plus
tests and design artifacts.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Evidence |
|-----------|---------|--------|
| I. Build From Primitives | PASS | Validation, conflict detection, activity recording and the view are all source here. No framework, no schema generator, no front-end build; the server stays stdlib http.server and the view stays hand-written JS. |
| II. Provider-Agnostic Model Boundary | PASS | No model adapter, prompt or tool-description change. The feature runs entirely against SQLite and files; the offline suite uses the existing scripted adapters only. |
| III. Small Modules With Narrow Contracts | PASS | One new memory module (curation) owns the rules; FactStore gains two narrow methods; Trajectory gains one append method; the dashboard maps outcomes to HTTP; the view owns presentation state. Each new seam carries a design note with a rejected alternative (research.md, Decisions 1, 2, 6, 8), and each is testable in isolation. |
| IV. Observable by Default | PASS | Every add/edit attempt appends one structured memory_change event through the redacting sink; conflicts, refusals and mirror warnings are recorded. The view remains a projection of the store and the record; no second data source is introduced. |
| V. Eval-Driven Behavior Change | PASS | This changes memory write policy and dashboard behavior, so it ships with an eval delta: baseline 234 passing; the added cases cover validation boundaries, duplicate normalization, conflict, activity records, mirror degradation, escaping and the 500-fact budget. The implementation report records the post-change count and the cases that moved. No prompt, loop, context or tool-description change is involved. |

**Post-design re-check**: PASS. Phase 1 adds no dependency, schema change, second writer or
model-facing behavior. The only new persistent artifact is the durable mirror-pending marker,
which carries no fact text and is removed on repair. No Complexity Tracking entries are needed.

## Project Structure

### Documentation (this feature)

~~~text
specs/007-memory-facts-editing/
├── plan.md              # this file
├── research.md          # Phase 0 — decisions and rejected alternatives
├── data-model.md        # Phase 1 — entities, refusals, payloads, activity, view state
├── quickstart.md        # Phase 1 — runnable validation scenarios
├── contracts/
│   └── memory-facts-api.md   # HTTP + UI contract
└── tasks.md             # Phase 2 output (/speckit-tasks; not created here)
~~~

### Source Code (repository root)

~~~text
byo/
├── memory/
│   ├── curation.py             # NEW — clean, limit, duplicate, add/edit, conflict refusal
│   └── semantic/store.py       # + all() and update_if_unchanged() (narrow helpers)
├── ops/
│   ├── dashboard.py            # memory payload + add/edit mapping, statuses, lock, mirror repair
│   ├── trajectory.py           # + record_activity() (turn-less, redacted append)
│   └── static/
│       ├── style.css           # + textarea/form/error/notice/disabled/fact-body styles (tokens only)
│       └── js/
│           ├── dock.js         # memory view rebuilt: add form, in-place edit, state, actions
│           └── main.js         # load /api/memory for #memory; pass payload to the view
evals/
└── deterministic/
    ├── test_curation.py        # NEW — rules in isolation
    ├── test_dashboard.py       # + add/edit contracts, activity, mirror, 500-fact budget
    └── test_views_static.py    # + view wiring, escaping, ARIA, no prompt/required/maxlength
~~~

Unchanged: byo/tools/*, byo/memory/retrieval_gate.py, consolidation.py, mirror.py, episodic/*,
byo/loop/*, byo/config.py, byo/db.py, index.html, api.js, map.js, live.js, observe.js, tools.js.

**Structure Decision**: Keep the existing single-project layout and the existing seams. The
feature adds one memory module for policy, two small FactStore helpers, one Trajectory append
helper, and modifies the dashboard handler, the Memory view and its styles. No package, no build
step, no schema migration.

### Implementation sequence (for /speckit-tasks)

1. Curation and store helpers with their unit tests (red then green).
2. Trajectory activity append with a redaction test.
3. Dashboard payload, mutation mapping, statuses, lock, mirror repair; HTTP tests.
4. Memory view state, add form, in-place edit, focus and error rendering; static tests.
5. Styles within the existing token system; style checks stay green.
6. Full suite, lint, eval delta and quickstart pass.

## Complexity Tracking

No constitution violations; nothing to justify.
