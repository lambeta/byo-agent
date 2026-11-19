---
description: "Task list for Working Tools & Memory in the Dashboard"
---

# Tasks: Working Tools & Memory in the Dashboard

**Input**: Design documents from `/specs/006-tools-memory-support/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/dashboard-api.md

**Tests**: Included — the spec requires offline coverage (FR-010, FR-011, SC-001..SC-007) and the
constitution mandates test-first for logic and a regression case per fixed bug. Tests come first
within each story (red → green).

**Organization**: Tasks are grouped by user story (US1 P1, US2 P2, US3 P3 from spec.md) so each
story can be implemented, tested and delivered independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Every task names its exact file path(s)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Baseline and regression-net scaffolding for this feature

- [ ] T001 Run `make gate` on the untouched tree and record the baseline (223 tests passing as of 2026-11-19); this baseline is the "before" score the constitution requires reported alongside behavior-touching diffs

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared test scaffolding both story phases build on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T002 [P] Add a shared helper that builds a dashboard server whose agent has **memory enabled** (scripted adapter, temp BYO_HOME, real `Memory` instance — fixing the RC-3 gap where every dashboard test passes `memory=None`) in evals/deterministic/test_dashboard.py
- [ ] T003 [P] Create evals/deterministic/test_views_static.py with the view-contract checks: every view function referenced by byo/ops/static/js/main.js (`overviewView`, `observeView`, `memoryView`, `settingsView`, `toolsView`) is defined in a loaded script, and no view builder in byo/ops/static/js/ contains a bare `return` immediately followed by a newline (the RC-1 "Undefined" pattern). This test is expected to FAIL until T023 lands (`memoryView`, `toolsView`); that red is the regression pin.

---

## Phase 3: User Story 1 — Tools work in the dashboard chat (Priority: P1) 🎯 MVP

**Goal**: The six existing tools execute from the dashboard chat with live visibility, and the
Overview map's Tools node opens a dedicated Tools view (Available catalog + Results).

**Independent Test**: With a scripted model, drive a tool-calling turn through `/api/chat/stream`;
the tool executes, its frames arrive in order, and `GET /api/tools` lists the six tools plus the
recorded call. Clicking the Tools node navigates to `#tools`.

### Tests for User Story 1

- [ ] T010 [P] [US1] Write failing contract test for `GET /api/tools`: response is `{tools, results}`; `tools` equals the live registry's six entries with name, description and input_schema verbatim (FR-003b validation rule from data-model.md) in evals/deterministic/test_dashboard.py
- [ ] T011 [P] [US1] Write failing test that `GET /api/tools` `results` are read from the recorded trajectory: newest-first, bounded at 50, each entry carries tool/args/output-preview/ok/duration_ms/turn_id, and `results: []` is a normal empty state (data-model.md payload rules) in evals/deterministic/test_dashboard.py
- [ ] T012 [US1] Write failing test that a dashboard `/api/chat/stream` tool turn emits `tool_start` before `tool` before the reply/done frames (SC-002 ordering) in evals/deterministic/test_dashboard.py

### Implementation for User Story 1

- [ ] T013 [US1] Implement `GET /api/tools` in byo/ops/dashboard.py: catalog from the live registry (never a duplicated static list — D-3), results from the trajectory tail via the existing feed/observability readers, redacted like every trajectory read (FR-012)
- [ ] T014 [P] [US1] Create byo/ops/static/js/tools.js with `toolsView(data)`: **Available** section (one card per tool: name, description, input schema) and **Results** section (recent calls with outcome and duration; explicit "no tool calls recorded yet" empty state); register the script and the `#tools` nav link in byo/ops/static/index.html
- [ ] T015 [US1] Route `#tools` in byo/ops/static/js/main.js: `VIEW_HEADS` entry and a `render()` branch calling `toolsView`, fetching `/api/tools` (unknown hashes keep the `#overview` fallback)
- [ ] T016 [US1] Change the `tools` node destination from `"turn"` to `"tools"` in byo/ops/map.py and handle `destination === 'tools'` → `location.hash = '#tools'` in `mapNodeClick` in byo/ops/static/js/map.js
- [ ] T017 [US1] Extend evals/deterministic/test_views_static.py with the destination/route consistency rule (contracts/dashboard-api.md): every `destination` value in byo/ops/map.py is handled by `mapNodeClick` in map.js, and every navigated hash is a route main.js renders; the nav contains `#tools`
- [ ] T018 [US1] Run `make gate`: T010–T012 and T017 green; walk quickstart.md scenario 3 offline portions

**Checkpoint**: US1 is fully functional and testable independently — MVP deliverable

---

## Phase 4: User Story 2 — Memory works end to end in the dashboard (Priority: P2)

**Goal**: Gate, retrieval, Memory view (waku-style sections) and consolidation all work from the
dashboard; the "Undefined" defect is fixed and pinned.

**Independent Test**: Offline, a memory-enabled dashboard turn with a scripted "retrieve" gate
decision injects the recalled block; Memory add/edit/forget leaves store, payload and mirror
consistent; the Memory view source passes the RC-1 static check.

### Tests for User Story 2

- [ ] T020 [P] [US2] Write failing test using the T002 helper: a dashboard chat turn with memory enabled runs the gate, and with a scripted `retrieve` decision the recalled block reaches the system prompt (FR-004, FR-005) in evals/deterministic/test_dashboard.py
- [ ] T021 [P] [US2] Write failing test that `GET /api/memory` gains additive `gate` (retrieve/skip counts from trajectory events, `last_*` null when none) and `consolidation` (`pending` from the same `pending_rows` source the runtime uses, `threshold`, `last_run_at`) fields, with no existing key renamed or re-typed (contracts/dashboard-api.md) in evals/deterministic/test_dashboard.py
- [ ] T022 [US2] Write failing test that `POST /api/memory` add/edit/forget leaves the `facts` table, the `GET /api/memory` payload and the `MEMORY.md` mirror consistent (FR-006; extend the coverage in evals/deterministic/test_dashboard.py, complementing evals/deterministic/test_memory_admin.py)

### Implementation for User Story 2

- [ ] T023 [US2] Fix the RC-1 ASI defect and rebuild `memoryView()` in byo/ops/static/js/dock.js as waku-style sections (D-1): gate overview, facts (with add/edit/forget wired to `POST /api/memory`), episodes, consolidation status — each with its explicit empty state per data-model.md's rendering contract; the view never renders blank or "Undefined" on valid or empty data
- [ ] T024 [US2] Extend `GET /api/memory` in byo/ops/dashboard.py with the `gate` and `consolidation` fields (additive only), sourced from trajectory events and `consolidation_mod.pending_rows`
- [ ] T025 [US2] Verify every memory-group node in byo/ops/map.py (`gate`, memory stores, consolidation) carries `destination: "memory"` routing to `#memory`; the T017 consistency test pins this
- [ ] T026 [US2] Run `make gate`: T003, T020–T022 green; walk quickstart.md scenario 2 offline portions

**Checkpoint**: US2 independently delivers a working Memory view and memory-visible turns

---

## Phase 5: User Story 3 — CLI and dashboard tell the same story (Priority: P3)

**Goal**: One scripted scenario produces equivalent trajectories through the terminal path and the
dashboard path, and the suite fails on any future divergence.

**Independent Test**: The parity test compares event-kind sequences from both surfaces for the same
scripted tool-and-memory turn (SC-005).

### Tests for User Story 3

- [ ] T030 [US3] Write failing parity test in evals/deterministic/test_dashboard.py: one scripted scenario (gate retrieve → tool call → reply → receipt) runs once via `Agent.respond` (CLI path) and once via `/api/chat/stream` (dashboard path); both trajectories record the same event-kind sequence (FR-009, SC-005)

### Implementation for User Story 3

- [ ] T031 [US3] Make T030 green by removing any divergence in the dashboard path (per FR-009 the server must not grow parallel dispatch/memory logic — fix wiring, not duplicate code); record the eval delta (baseline from T001 vs. now) in the change notes as constitution V requires

**Checkpoint**: All three stories independently functional; parity pinned

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, full verification, release readiness

- [ ] T040 [P] Update README.md ("Use" / dashboard description) to mention the Tools view and the sectioned Memory view; keep the "read in an afternoon" tone
- [ ] T041 Run `make gate` and `make lint`; confirm the suite grew by the new regression cases and nothing regressed; walk quickstart.md scenarios 1–4 (scenario 5 is live-model, optional)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: none — start immediately
- **Phase 2 (Foundational)**: depends on Phase 1 — BLOCKS all user stories
- **Phase 3 (US1)**: depends on Phase 2; independent of US2/US3
- **Phase 4 (US2)**: depends on Phase 2; independent of US1/US3 (T003 red-state resolves here)
- **Phase 5 (US3)**: depends on Phase 2; lands most cleanly after US1+US2 (it pins their combined behavior) but its test can be written any time
- **Phase 6 (Polish)**: depends on US1–US3

### Within Each User Story

- Tests (T010–T012 / T020–T022 / T030) MUST be written and failing before implementation tasks
- Implementation tasks in story order: API → view/route → map wiring → static contract → gate run

### Parallel Opportunities

- T002 and T003 (different files) can run in parallel
- Within US1: T010, T011 in parallel; T014 parallel with T013/T015 once contracts are fixed
- Within US2: T020, T021 in parallel
- US1 and US2 are independently deliverable after Phase 2 — different files except the shared evals/deterministic/test_dashboard.py (coordinate edits there)

## Parallel Example: User Story 1

```text
# After Phase 2 completes:
Task: "T010 [US1] /api/tools catalog contract test"        ┐ parallel (same file: coordinate
Task: "T011 [US1] /api/tools results-from-trajectory test" ┘ hunks, or one author)
Task: "T014 [US1] tools.js + index.html wiring"            — parallel with T013 (different files)
```

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 + Phase 2 (baseline + test scaffolding)
2. Complete Phase 3 (US1): tools work in dashboard chat + Tools view
3. **STOP and VALIDATE**: `make gate` green, quickstart scenario 3 passes
4. Demo-ready increment: the Tools node defect is gone and tools are visibly working

### Incremental Delivery

1. Setup + Foundational → scaffolding ready
2. US1 → validate → **MVP**
3. US2 → validate → Memory defect fixed and pinned
4. US3 → validate → parity pinned
5. Polish → release-ready

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [USn] labels map tasks to spec.md user stories for traceability
- Every fixed defect adds its regression case to the deterministic suite (constitution V): RC-1 → T003 static check, RC-2 → T017 consistency check, RC-3 → T002 memory-enabled dashboard tests
- Commit after each task or logical group; run `make gate` at every checkpoint
- Total: 20 tasks (Setup 1, Foundational 2, US1 9, US2 7, US3 2, Polish 2 — T-numbers: T001–T041 sparse)
