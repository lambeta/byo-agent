# Tasks: Fact Capture and Correction in Memory

**Input**: Design documents from specs/007-memory-facts-editing/

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/memory-facts-api.md,
quickstart.md, .specify/memory/constitution.md

**Tests**: Required. FR-025 and SC-009 require every acceptance scenario to have an automated
offline check, so test tasks are part of each story and are written before the code they pin.

**Organization**: Tasks are grouped by user story so each increment is independently testable.
The shared rules and append helper are foundational; the view is shared by US1 and US2, so the
two UI phases touch dock.js sequentially.

## Format: [ID] [P?] [Story] Description

- [P]: can run in parallel (different files, no dependency on an incomplete task)
- [Story]: US1, US2 or US3 on user-story phase tasks only
- Every task names the exact file path

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the baseline and that the repository is ready for the change.

- [x] T001 Confirm baseline: run make eval (234 tests) and make lint from the repo root; record both results in the implementation report.
- [x] T002 [P] Verify .gitignore already covers .venv/, __pycache__/, *.pyc, .pytest_cache/, .ruff_cache/, build artifacts and .env; add nothing unless a pattern is missing.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared rules and record helper every story uses. No user story work starts until this phase passes.

**CHECKPOINT**: curation tests pass; store and trajectory helpers are in place.

- [x] T003 [P] Write failing curation rule tests in evals/deterministic/test_curation.py: add trims and records source 'user'; subject line breaks become one space while content line breaks are preserved; empty/whitespace-only subject or content is fact_validation with field subject/content; 120/2000 code points are accepted and 121/2001 are fact_validation with the limit named; normalized duplicates (trim, casefold, collapsed whitespace) are fact_duplicate with existing_id; edit subject-only/content-only/both preserves id, source and created_at; edit of a missing id is fact_not_found; a mismatched edit baseline is fact_conflict with the store unchanged; a matching baseline succeeds; an omitted baseline edits unconditionally; an edit onto another fact's normalized key is fact_duplicate while keeping its own key is allowed; an over-limit legacy fact can be saved only after shortening.
- [x] T004 [P] Add FactStore.all() returning every fact ordered by id descending and FactStore.update_if_unchanged(fact_id, subject, content, baseline_subject, baseline_content) returning whether one row matched, in byo/memory/semantic/store.py.
- [x] T005 Implement byo/memory/curation.py: SUBJECT_LIMIT = 120, CONTENT_LIMIT = 2000, one Refused exception carrying code/message/field/existing_id, clean_subject (trim; internal line breaks to one space), clean_content (trim only), normalized duplicate detection over store.all() excluding the edited id, add() recording source 'user', and edit() enforcing existence, validation, duplicates, the optional edit baseline and the conditional update. Include the module design note and rejected alternative.
- [x] T006 [P] Write failing activity-record tests in evals/deterministic/test_trajectory_contract.py: Trajectory.record_activity writes a memory_change envelope with turn_id "", source dashboard, ts and the supplied action/outcome/fact_id/code/field/warning; it creates the trajectory directory on a fresh home; it does not disturb self.turn_id; redaction still removes a key-shaped value; and group_turns ignores the record outside a turn.
- [x] T007 Implement Trajectory.record_activity and factor the existing append into one private writer in byo/ops/trajectory.py, keeping record() behavior and redaction unchanged and documenting the rejected alternative (reusing the last turn id).

---

## Phase 3: User Story 1 - Correct a fact in place (Priority: P1) MVP

**Goal**: A stored fact opens in its row with both fields prefilled; subject-only, content-only or both can be saved; identity/origin/creation time survive; cancel is a no-op; stale saves conflict; refusals keep the typed values.

**Independent Test**: Edit only the subject, then only the content, then both, then cancel; verify the row, store, count and mirror agree and id/source/created_at are unchanged. Force a baseline mismatch and verify 409 with the store unchanged.

### Tests for User Story 1

- [x] T008 [P] [US1] Add failing edit-path HTTP tests to evals/deterministic/test_dashboard.py: edit subject-only and content-only via POST /api/memory preserves id/source/created_at and updates memory/mirror; matching baseline succeeds; mismatched baseline returns 409 fact_conflict and leaves the store unchanged; a missing id returns 404 fact_not_found and creates nothing; a duplicate normalized key on another fact returns 400 fact_duplicate with existing_id; a mirror rewrite failure returns 200 with a mirror_write_failed warning while the store keeps the change; one success and one refused edit each append exactly one memory_change event with no subject/content.
- [x] T009 [P] [US1] Implement the edit action in byo/ops/dashboard.py: memory lock, id parsing, curation.edit call, typed-refusal to HTTP mapping (fact_validation/fact_duplicate 400, fact_not_found 404, fact_conflict 409, fact_failed 500), mirror rewrite with durable marker and warning, and one activity record per attempt.
- [x] T010 [P] [US1] Add failing static edit-view tests to evals/deterministic/test_views_static.py: dock.js defines the one-at-a-time edit state, prefilled subject and content controls, save and cancel, aria-invalid/aria-describedby/role=alert wiring, esc() around baseline and draft values, and a cancel path that writes nothing.
- [x] T011 [P] [US1] Implement in-place editing in byo/ops/static/js/dock.js: MEMORY_UI (editingId, editDraft, editBaseline, errors, general, notice, saving), memoryView edit rows, startEditFact/saveEditFact/cancelEditFact, baseline capture, focus of the first invalid field, disabled controls while saving, and a postMemory helper that applies the returned memory payload.
- [x] T012 [US1] Add edit-mode, field-error, disabled-control and pre-wrap fact styles using only existing --byo-* tokens in byo/ops/static/style.css.

**Checkpoint**: User Story 1 is functional and independently testable; adding facts still uses the existing form and API path.

---

## Phase 4: User Story 2 - Capture a fact with proof it was kept (Priority: P2)

**Goal**: Add accepts multi-line content, shows field-level validation, blocks normalized duplicates with a pointer to the existing fact, preserves typed values on failure, clears on success, and shows a confirmation.

**Independent Test**: Add a multi-line fact and verify confirmation, first position, count, origin, creation time and mirror. Add empty, whitespace-only, over-limit and duplicate values and verify each refusal names the rule and writes nothing.

### Tests for User Story 2

- [x] T013 [P] [US2] Add failing add-path HTTP tests to evals/deterministic/test_dashboard.py: multi-line content round-trips; empty and whitespace-only subject/content return 400 fact_validation with the field; 120/2000 boundaries are accepted and 121/2001 refused with the limit in the message and nothing stored; a normalized duplicate returns 400 fact_duplicate with existing_id and stores nothing; every add outcome appends exactly one memory_change; a mirror failure degrades to a warning; GET /api/memory counts.facts increments.
- [x] T014 [P] [US2] Implement the add action in byo/ops/dashboard.py using curation.add, the same status mapping, the durable mirror marker and activity record used by edit; keep the action-dispatcher error for unknown actions.
- [x] T015 [P] [US2] Add failing static add-form tests to evals/deterministic/test_views_static.py: novalidate form with labeled subject input and content textarea, no required or maxlength attribute, remember submit, field error elements, retained draft state, and addFact posting even when fields are empty.
- [x] T016 [P] [US2] Implement the add form and add action in byo/ops/static/js/dock.js: draft retention, general duplicate message with an edit-existing control, success notice and form clear, subject focus after success, and disabled controls while saving.
- [x] T017 [US2] Add add-form, notice, warning and error styles using only existing --byo-* tokens in byo/ops/static/style.css.

**Checkpoint**: User Stories 1 and 2 both work through the same view; the shared payload shape is stable.

---

## Phase 5: User Story 3 - Every change is reflected everywhere (Priority: P3)

**Goal**: The Memory view receives a full payload (up to 500 facts) with counts and warnings; a stale mirror repairs on the next read; every acceptance scenario has an offline check; escaping and accessibility are pinned.

**Independent Test**: With 500 facts, GET /api/memory returns 500 and counts.facts is 500 within 2 seconds; force a mirror failure, add a fact, verify warning, then refresh and verify repair; inspect the JS for escaping, pre-wrap, ARIA and the absence of prompt/required/maxlength.

### Tests for User Story 3

- [x] T018 [P] [US3] Add failing payload, scale, repair and compatibility tests to evals/deterministic/test_dashboard.py: GET /api/memory returns created_at, counts and warnings; 500 seeded facts are all returned within 2 seconds; a failed mirror sets the marker and a later GET repairs it and clears the warning; /api/data keeps its existing shape and 100-row memory slice; /api/events exposes the memory_change records.
- [x] T019 [P] [US3] Implement the GET /api/memory payload in byo/ops/dashboard.py: 500-row cap, counts, created_at, warnings, durable marker check and one repair attempt; keep /api/data unchanged; ensure a memory=None dashboard still serves the payload without a mirror.
- [x] T020 [US3] Switch byo/ops/static/js/main.js to fetch /api/memory for the #memory route, pass the payload to memoryView, and reset MEMORY_UI plus the cached memory payload on navigation.
- [x] T021 [P] [US3] Add failing static rendering tests to evals/deterministic/test_views_static.py: every fact field is escaped in text and attributes, content uses a pre-wrap class, no window.prompt/alert/contenteditable, no client-side cap, main.js loads /api/memory, and the existing Memory labels remain.
- [x] T022 [US3] Finish the Memory view rendering in byo/ops/static/js/dock.js: counts from the payload, warning and notice banners, conflict/not-found reload, duplicate pointer, empty states, and keyboard focus behavior.

**Checkpoint**: All three stories are independently functional and covered by offline tests.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T023 Run make eval and make lint; fix every failure. Report the post-change test count against the 234 baseline and list the new cases (the constitution's eval delta).
- [x] T024 Run the quickstart API scenarios against a scratch home: add success, duplicate refusal, over-limit refusal, stale-baseline conflict, one activity record per attempt, mirror failure and repair, and 500-fact payload; record the observed results.
- [x] T025 Verify scope boundaries: no change to byo/tools/*, retrieval_gate.py, consolidation.py, mirror.py, byo/db.py or the schema; confirm save_note/manage_memory tests still pass; scan the diff for secrets and unescaped fact rendering.
- [x] T026 [P] Re-check the spec's acceptance scenarios against the implemented tests and mark this tasks file complete; note any scenario that remains manual (SC-003, SC-006, SC-008 walkthroughs) in the implementation report.

---

## Dependencies & Execution Order

### Phase Dependencies

- Setup (Phase 1) has no dependencies and starts immediately.
- Foundational (Phase 2) depends on Setup and blocks all user stories.
- User stories (Phases 3-5) depend on Foundational. US1 is the MVP and lands first; US2 extends
  the shared view; US3 hardens payload, repair and rendering. They are delivered sequentially.
- Polish (Phase 6) depends on all three stories.

### User Story Dependencies

- US1 (P1): depends only on Phase 2. Delivers row editing end to end.
- US2 (P2): depends only on Phase 2 in principle; in this repository it shares dock.js,
  dashboard.py and style.css with US1, so those files are edited in US1 then US2 order.
- US3 (P3): depends on Phase 2 and on the payload returned by US1/US2; it adds the full list,
  counts, repair and rendering guarantees.

### Within Each User Story

- Tests are written first and must fail for the intended reason before the implementation task.
- Store helpers precede curation; curation precedes the dashboard mapping.
- Dashboard mapping precedes the view actions; the view precedes its styles.
- Each story ends at a checkpoint verified independently.

### Parallel Opportunities

- T002, T003, T004 and T006 are different files and can run together.
- T008 and T010 are different test files; T009 and T011 touch different implementation files.
- T013 and T015 are different test files; T014 and T016 touch different implementation files.
- T018 and T021 are different test files.
- T026 is documentation only and can run beside T024/T025.

---

## Parallel Example: User Story 1

~~~text
After Phase 2 passes:
  Task T008: edit-path HTTP tests in evals/deterministic/test_dashboard.py
  Task T010: edit-view static tests in evals/deterministic/test_views_static.py
Then, in parallel because they touch different files:
  Task T009: dashboard edit mapping in byo/ops/dashboard.py
  Task T011: edit state and rows in byo/ops/static/js/dock.js
Then sequentially:
  Task T012: styles in byo/ops/static/style.css
~~~

---

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Setup and Foundational.
2. Complete US1: edit in place, conflict, refusals, mirror warning, activity record.
3. Stop and validate US1 with its HTTP and static tests.
4. Continue with US2 and US3.

### Incremental Delivery

1. Foundational: rules + append helper, proven by unit tests.
2. US1: corrections are safe and complete.
3. US2: capture is fast, validated and duplicate-aware.
4. US3: every change is visible in the payload, mirror and record at the agreed scale.
5. Polish: full suite, lint, quickstart, scope and eval delta.

### Notes

- [P] tasks are different files with no incomplete dependency.
- Tests must fail before the related implementation lands.
- Commit after each logical group if committing; this run leaves the working tree for review.
- The dashboard is static JS; there is no build step and no Node toolchain in the default test path.
