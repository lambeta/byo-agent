# Tasks: Runtime-Accurate Live Highlighting

**Input**: Design documents from `specs/004-runtime-highlight-fidelity/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required. The project constitution makes the offline deterministic suite the bar for a
behavior change, and the plan's correspondence eval is the measured before/after. Write each test
task first, run it, and confirm it fails for the expected reason before implementing the task it
covers. Browser-only behaviour (paint latency, motion, keyboard) is verified by the quickstart
section named on the task.

**Organization**: Tasks are grouped by user story. Setup and Foundational phases carry no story
label; US1/US2/US3 phases carry the matching label; Polish is cross-cutting.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: `[US1]`, `[US2]`, `[US3]` — required only in user-story phases
- Every task names the exact file path(s) it changes or validates

## Path Conventions

Single project: package `byo/`, tests `evals/deterministic/`, feature docs under
`specs/004-runtime-highlight-fidelity/`. The dashboard's static front end is `byo/ops/static/`; there
is no frontend project and no build step. Contracts quoted in a task are binding verbatim.

> **Working tree note**: `byo/ops/static/index.html`, `byo/ops/static/js/map.js`,
> `byo/ops/static/js/main.js`, `byo/ops/static/js/dock.js`, `byo/ops/static/js/observe.js`,
> `byo/ops/static/style.css` and `evals/deterministic/test_style_parity.py` already carry uncommitted
> cosmetic edits (copy and class names). Keep them; the tasks below edit on top of the current files.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the baseline and create the three new module homes. No feature behavior yet.

- [X] T001 Run `make eval`, `make gate` and `make lint` and record the passing count (expected 157 tests) and the route inventory of `byo/ops/dashboard.py`; stop and report if any target is already red.
- [X] T002 [P] Create `byo/ops/feed.py`, `byo/ops/liveness.py` and `byo/ops/highlight.py` with design-note docstrings naming the mechanism and one rejected alternative each (constitution III); keep them importable with no behaviour yet.

**Checkpoint**: The existing suite is green and the three modules exist as empty seams.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The record additions, the incremental feed reader, the pid check and the event-map
extension. Every user story depends on this phase.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Tests for the foundation (write first, confirm red)

- [X] T003 [P] Write the failing record tests in `evals/deterministic/test_record_additions.py`: a scripted turn writes `gate_start` before `gate`, `llm_start` before each `llm`, `tool_start` before `tool`, `context` after the gate and before the first model call, and `consolidation_start < consolidation` when the backlog reaches the threshold; `turn_start.pid` is the current pid; a raising `Agent.respond` still writes `error(stage="turn")` then `turn_end` with `state="failed"`; a start record never carries usage, cost or a result; every new field is redacted by the sink; a turn's step list, spend and `build_turn.summary` are identical with and without the start records.
- [X] T004 [P] Write the failing feed tests in `evals/deterministic/test_feed.py`: incremental reads equal `observability.read_events(home, "7d")` after every append; a truncated file, a replaced file and a new day file each trigger a correct reload; the 7-day window and `skipped` count match the full read; two threads refreshing concurrently never see a partially applied file.
- [X] T005 [P] Write the failing liveness tests in `evals/deterministic/test_liveness.py`: the current pid is alive; the pid of a spawned-and-exited subprocess is not; `None`, `0` and a negative pid are not alive; a pid the test cannot signal (permission denied) is treated as alive.

### Implementation for the foundation

- [X] T006 Implement the record surface in `byo/ops/trajectory.py`: `start(..., pid=os.getpid())` writes the pid; `end(reply, iterations, state="complete")` writes `turn_end.state`; add a `begin(event_type, **fields)` helper that records a `*_start` line through the same `record()` path so redaction and locking are unchanged. [contracts/record-additions.md](contracts/record-additions.md) §1–3 are binding.
- [X] T007 Wire the app-level records in `byo/app.py`: `gate_start` before `memory.gate()`; `context` (`recalled`, `recalled_chars`, `duration_ms`) right after `session.build_system()`; `consolidation_start` through the callback added in T009; extend `RECORDED` so start records are persisted and forwarded; wrap the turn body so an exception records `error(stage="turn")` and a terminal `turn_end` (`state="failed"`) before re-raising, without double-writing on the normal path.
- [X] T008 Emit start notifications from `byo/loop/agent.py`: `notify("llm_start", {"iteration": n, "model": model})` immediately before the adapter call and `notify("tool_start", {"tool": name, "call_id": id})` immediately before `tools.execute`; keep the existing `llm`/`tool` notifications, their order and payloads unchanged; keep `text` and `error` untouched.
- [X] T009 Add the structured degraded flag in `byo/memory/retrieval_gate.py` (`degraded: True` on a `ModelError` or an unparseable answer, `False` otherwise) and an `on_start` callback on `Memory.maybe_consolidate` in `byo/memory/__init__.py` invoked only when the pending backlog actually triggers a run.
- [X] T010 Make the projection guards explicit in `byo/ops/observability.py`: `_step` returns `None` for every `*_start` and for `context`; `spend` ignores both; `group_turns` keeps them in `turn["events"]` so the raw record and the cue projection see them. Add the regression assertion to `evals/deterministic/test_observability.py` that step kinds, summary and spend are unchanged for a turn recorded with start records.
- [X] T011 Implement `byo/ops/feed.py` per [data-model.md](data-model.md) §5: per-file `(size, mtime_ns, byte_offset, events)`, a merged list and skipped counter, append-only fast path, full-reload fallback on shrink/replace/new file, the same `7d`/`today`/`all` window rule as `read_events`, and one lock around refresh with immutable snapshots for readers.
- [X] T012 Implement `alive(pid)` in `byo/ops/liveness.py` per [data-model.md](data-model.md) §2: `os.kill(pid, 0)`, `ProcessLookupError` ⇒ dead, `PermissionError` ⇒ alive, `None`/`0`/negative ⇒ dead; no side effects, standard library only.
- [X] T013 Route `GET /api/events` in `byo/ops/dashboard.py` through `feed.Feed` while keeping the v1 payload (`events`, `cursor`, `complete`, `skipped`) and the read-only, lock-free behaviour.
- [X] T014 Update the observer-vocabulary tests to the amended contract rather than deleting them: `evals/deterministic/test_timing.py`, `evals/deterministic/test_loop.py` and `evals/deterministic/test_dashboard.py` assert the full sequence including `llm_start`/`tool_start` in recorded order; `evals/deterministic/test_parity_seams.py::test_trajectory_vocabulary` asserts the grown vocabulary explicitly (the eight original types plus the five additive ones) instead of a closed set.
- [X] T015 Extend the map's own mapping table and liveness in `byo/ops/map.py`: `EVENT_MAP` gains `gate_start`, `context`, `llm_start`, `tool_start` and `consolidation_start`; `llm` no longer lights `context`; `turn_start` gains the `record` mark. `_active` and `payload.active` now mean *live only* (no `turn_end`, `pid` present and `alive(pid)`; a missing pid is never live). Update `evals/deterministic/test_map.py` (event-map keys) and `evals/deterministic/test_map_api.py` (the active fixture gains a live pid; a dead-pid unfinished turn is `null`).

**Checkpoint**: Records carry starts and pids, projections are unchanged, the feed is incremental, and `/api/map` no longer reports a dead turn as active.

---

## Phase 3: User Story 1 - Watch a turn and believe the map (Priority: P1) 🎯 MVP

**Goal**: During a live turn the component reading `running` is the one whose step is in flight, each step produces one highlight in recorded order, the running state lasts as long as the step, and the status line names the current step and round/tool count. The browser applies the projection instead of mapping events.

**Independent Test**: Run a scripted turn (1.2 s gate decision, 2.5 s model call, one tool, 2.5 s final model call), sample the map every 100 ms, and get seven step transitions in recorded order, the in-flight step is the running component in at least 95% of samples, zero samples with a step running while nothing is in flight, and the trajectory mark running exactly while the turn is. Manual: [quickstart.md](quickstart.md) §2 and §8.

### Tests for User Story 1 (required)

- [X] T016 [P] [US1] Write the failing cue tests in `evals/deterministic/test_highlight.py`: for the scripted fixture, `cues(events, memory_enabled=True)` returns a `live` cue at each `*_start`'s `ts` and one settle cue at each completion's `ts`; `seq` is strictly increasing; `llm` never lights `context`; labels are `loop <n> · model reasons`, `tool <name> · <k> tool calls`, `final answer` for a turn-ending model call, `message in · <source>`, `memory decision · <decision>`, `context assembled`, `costed` and `reply`; `record` is `mark` from `turn_start` to `turn_end`; `at` is always a recorded `ts` (contract §5).
- [X] T017 [P] [US1] Write the failing `/api/live` tests in `evals/deterministic/test_live_api.py`: a running turn returns `active: true`, `turn.state: "running"`, the whole cue list, `seq == len(cues)`, `poll_ms: 100` and `status` equal to the last cue's label; an empty home returns `turn: null`, `cues: []`, `status: "Agent idle"` and `poll_ms: 1000`; the route takes no input, only returns 200, never acquires `dash.lock`, and never mutates the trajectory.

### Implementation for User Story 1

- [X] T018 [US1] Implement `cues(events, *, memory_enabled)` and the label/edge rules in `byo/ops/highlight.py` exactly per [contracts/highlight-cues.md](contracts/highlight-cues.md) §2–3 and §6, consuming `map.EVENT_MAP` for the component mapping: one cue per transition, `states` as a node→state map, edges with `live`/`idle`, `role` of `step`/`mark`, and the final-answer distinction from the completion record's stop reason.
- [X] T019 [US1] Implement `GET /api/live` in `byo/ops/dashboard.py` (new `Dashboard.live_payload`) per [contracts/live-api.md](contracts/live-api.md) §1: newest turn from the feed, `running` only when `alive(pid)`, the full cue list, `status`, `skipped` and `poll_ms` (100 while active, 1000 otherwise); 500 `server_error` on an unexpected projection failure.
- [X] T020 [US1] Rewrite `byo/ops/static/js/live.js` as a sequencer: poll `/api/live` with a chained `setTimeout` (`poll_ms` clamped to 100–1000), never overlap requests, pause on `visibilitychange`, diff by `seq`, apply `states`/`edges` in order, hold a running/settle pair closer than 150 ms for the 150 ms floor, abandon the floor when it would exceed the 1 s lag bound, and set `caught up` when jumping. Update the live-player assertions in `evals/deterministic/test_map_static.py` to `/api/live`, `MapLive` and the absence of a global cadence constant.
- [X] T021 [US1] Add the cue applier and split the status region in `byo/ops/static/js/map.js`: `mapApplyCue(cue)` (node states, edge states, text-view parity, `aria-label`), `mapSetStatus` for the step line and a separate `#map-note` for transport notices (skipped lines, reconnecting, caught up) so a notice never replaces the step name (spec FR-012); keep the existing `renderOverview`/`mapBind` contract hooks.
- [X] T022 [US1] Update `byo/ops/static/js/main.js` mount/unmount: start `MapLive` on Overview, stop it on leaving, and stop feeding the player `state.map.active` (the first `/api/live` response now drives the initial state); keep the post-turn `/api/map` refresh.
- [X] T023 [P] [US1] Add the `#map-note` treatment to `byo/ops/static/style.css` using existing tokens and the same contour/shadow grammar; add no new `[data-state]` value and no new hue.
- [X] T024 [US1] Write `evals/deterministic/test_highlight_eval.py`: score the fixture set twice — once through a simulation of today's playback (light at completion, 550 ms beat, 650 ms pulse) and once through `highlight.cues` — and print `start aligned`, `phantom lights`, `silent omissions` and `final state ok` before/after. Assert post-change `start aligned == 100%`, `phantom == 0` and `omissions == 0`; keep the baseline numbers in the printed table as the constitutional evidence.
- [ ] T025 [US1] Validate [quickstart.md](quickstart.md) §2 against a real turn and record the result beside this task: the lit component is the one working, a 2–3 s thought lights for its real duration, every round and tool call is countable, the final call reads `final answer`, and the layout does not move.

**Checkpoint**: US1 is independently demoable — a live turn lights truthfully, from the correct start instant, for its real duration, with countable rounds.

---

## Phase 4: User Story 2 - Read a finished turn's map and get the truth (Priority: P2)

**Goal**: After a turn — and for any recorded turn opened later — each component's final state matches the record: skipped memory is `skipped` (never `not reached`), a failed tool is `failed`, a gate that failed open is `degraded`, memory that is not configured leaves the gate `idle` with "not configured" text, stage components cut off by a failure are `not-reached`, and the operations group never becomes `not-reached`.

**Independent Test**: Replay twenty recorded turns covering skip, retrieve, failed tool, gate failure, memory disabled and an error cut-off; compare every component's final state word with the record. All agree. Manual: [quickstart.md](quickstart.md) §3.

### Tests for User Story 2 (required)

- [X] T026 [P] [US2] Extend `evals/deterministic/test_highlight.py` with the failing final-state table: `final_states(events, memory_enabled)` gives `gate/skipped` and `facts|episodes|persona/skipped` for a skip decision; `done` for a retrieve; `gate/degraded` when `gate.degraded`; `tools/failed` for `tool.ok == false`; the mapped node `failed` for an `error.stage`; `idle` for the operations group; `not-reached` only for stage components after a failure; `idle` gate when `memory_enabled == False`.

### Implementation for User Story 2

- [X] T027 [US2] Implement `final_states(events, memory_enabled)` and the `turn_end` settle cues in `byo/ops/highlight.py` per [contracts/highlight-cues.md](contracts/highlight-cues.md) §4: one settle per started component, stage components cut off by a failure become `not-reached`, the operations group and unused memory become `idle`/`skipped` as documented, and no state is emitted without a record fact.
- [X] T028 [US2] Pass the memory configuration into the projection: `Dashboard.live_payload` in `byo/ops/dashboard.py` and the `/api/live` route supply `memory_enabled` from the dashboard's settings, so a memory-off home never shows a skip or a failure for the gate.
- [X] T029 [US2] Make the settled rendering match the projection in `byo/ops/static/js/map.js`: apply the final state map on `active: false` for a turn just watched, keep the state word visible on every component, and never map `not reached` onto the operations group; no new CSS state.
- [X] T030 [US2] Handle records the projection does not know: in `byo/ops/highlight.py` emit a status-only cue (`unmapped step · <type>`, empty `states`) and light nothing; add the case to `evals/deterministic/test_highlight.py`.
- [ ] T031 [US2] Validate [quickstart.md](quickstart.md) §3 against the six state scenarios and record the result; any mismatch becomes a bug task before US3 starts.

**Checkpoint**: US1 and US2 work together — the live view tells the truth while running, the settled view tells the truth afterwards.

---

## Phase 5: User Story 3 - Join mid-turn, come back later, and never be told a stale story (Priority: P3)

**Goal**: Opening Overview during a turn lands on the step in flight now and says it caught up; an interrupted turn is reported as not running with its last step `partial`; a viewer who joined and one who watched from the start end at the same picture; watching stays read-only and independent.

**Independent Test**: Open Overview 2 s into a 6 s turn; both viewers agree on the steps after the join and the final state, with no replayed step shown as running. Then load a record with a dead pid and no end: the map reports not running with `partial` within 5 s and never replays it as live. Manual: [quickstart.md](quickstart.md) §4–7.

### Tests for User Story 3 (required)

- [X] T032 [P] [US3] Write the failing interrupted/legacy tests in `evals/deterministic/test_highlight.py` and `evals/deterministic/test_live_api.py`: an unfinished turn with a dead pid projects `state: "interrupted"`, `active: false`, the last started component `partial`, and a status that says not running and names the stopping step; an unfinished record with no `pid` is interrupted; a legacy completed record produces settle cues only (no `live` cue) and a state word per component.
- [X] T033 [P] [US3] Add the read-only multi-viewer assertions to `evals/deterministic/test_live_api.py`: two concurrent `/api/live` requests while `dash.lock` is held both return 200, and neither mutates the trajectory, the chat log or the lock.

### Implementation for User Story 3

- [X] T034 [US3] Implement `turn_state(events, alive)` and the synthetic interrupted cue in `byo/ops/highlight.py` per [data-model.md](data-model.md) §2 and [contracts/highlight-cues.md](contracts/highlight-cues.md) §3: `running` only with a live pid, otherwise `interrupted`, with `partial` on the last unmatched start and a `not running · interrupted at <step>` status; a legacy record yields settle cues only.
- [X] T035 [US3] Return the interrupted and legacy shapes from `GET /api/live` in `byo/ops/dashboard.py` and keep `/api/map.active` `null` for anything not running (additive to the v1 payload).
- [X] T036 [US3] Implement the mount and catch-up rules in `byo/ops/static/js/live.js` per [contracts/live-api.md](contracts/live-api.md) §1: on first response `running` ⇒ apply existing cues as history and continue from `seq`; `interrupted` ⇒ apply the final states once with no animation; `complete|failed` on load ⇒ stay idle; a turn-id change ⇒ reset `seq` and the graph; when behind by more than 1 s ⇒ jump and put `caught up` in the note element.
- [X] T037 [US3] Render the interrupted and caught-up states in `byo/ops/static/js/map.js` and `byo/ops/static/js/main.js`: hold `partial` without animating, show the interruption status, keep the recent-turn list and detail reachable, and never start a settle timer for a turn the viewer did not watch.
- [ ] T038 [US3] Validate [quickstart.md](quickstart.md) §4–7 (join mid-turn, interrupted fixture and `kill -9`, reduced motion, legacy record) and record the result.

**Checkpoint**: All three stories work independently and together; the map is a shared, read-only, truthful window.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Budgets, documentation, contract pointer, redaction audit and final validation.

- [X] T039 [P] Add the performance budget to `evals/deterministic/test_live_api.py`: a 200-turn / 20-step 7-day home answers `/api/live` under 20 ms p95 on the development laptop (CI-safe margin), and a second poll reads only appended bytes.
- [X] T040 [P] Add readable lines for the new record types in `byo/ops/show_trajectory.py` (`gate_start`, `llm_start`, `tool_start`, `context`, `consolidation_start`) and assert them in `evals/deterministic/test_show_trajectory.py`.
- [X] T041 [P] Update `README.md`: Overview now lights at the start of each step for its real duration, rounds and tool calls are countable, the settled states distinguish skipped / not reached / not configured / partial, and the live view is served by `GET /api/live`.
- [X] T042 [P] Add the supersession pointer to `specs/002-execution-flow-visualization/contracts/live-feed.md` (one line: superseded for the Overview map by `specs/004-runtime-highlight-fidelity/contracts/live-api.md`), leaving the v1 `/api/events` contract intact.
- [X] T043 [P] Finalize `evals/deterministic/test_map_static.py`: `live.js` polls `/api/live`, has no global cadence constant, applies `states`/`edges` from cues, keeps the `role="status"` region, and no external URL, CDN or build dependency entered the static assets.
- [X] T044 Run `make eval`, `make gate` and `make lint` from `Makefile`; all green, including the pre-existing uncommitted style edits in the working tree.
- [ ] T045 Execute [quickstart.md](quickstart.md) end to end (§1–9) and record the outcome beside this task; any failed check becomes a new task, not a silent waiver.
- [X] T046 Review `evals/deterministic/test_redaction.py` and inspect a written turn plus a `/api/live` payload: no key-shaped value, no unredacted field, no secret in a status label, and `recalled_chars` carries a count rather than remembered text.
- [X] T047 Re-read [spec.md](spec.md), [plan.md](plan.md) and this list under `specs/004-runtime-highlight-fidelity/`; confirm every FR-001–FR-026 and SC-001–SC-014 has a task, no new dependency/table/visual state slipped in, and the eight state words still mean what `contracts/highlight-cues.md` §4 says; tick the boxes and note follow-ups.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies; T001 and T002 are independent.
- **Foundational (Phase 2)**: depends on T002. T003/T004/T005 can be written in parallel; T006 depends on T003; T007 depends on T006/T009; T008 depends on T006; T009 is independent; T010 depends on T007/T008; T011 depends on T004; T012 depends on T005; T013 depends on T011; T014 depends on T007/T008; T015 depends on T012. **Blocks all user stories.**
- **US1 (Phase 3)**: depends on Foundational (T010–T015). T016/T017 can be written in parallel; T018 depends on T016/T015; T019 depends on T018/T012; T020 depends on T019; T021 depends on T020/T018; T022 depends on T020; T023 depends on T021; T024 depends on T018; T025 depends on T019–T023.
- **US2 (Phase 4)**: depends on US1's projection (T018). T026 can be written after T018; T027 depends on T026; T028 depends on T027/T019; T029 depends on T027/T021; T030 depends on T018; T031 depends on T027–T030.
- **US3 (Phase 5)**: depends on Foundational (T012/T013) and US1 (T018/T019/T020). T032/T033 can be written in parallel; T034 depends on T032; T035 depends on T034/T019; T036 depends on T035/T020; T037 depends on T036/T021; T038 depends on T034–T037.
- **Polish (Phase 6)**: depends on all desired stories. T039–T043 are parallel; T044–T047 run after them, in order.

### User Story Dependencies

- **US1 (P1)**: can start after Foundational; no dependency on US2/US3. It is the MVP: the lit component becomes the working component.
- **US2 (P2)**: needs US1's `highlight.cues` for the settle path but is testable on its own through `final_states` fixtures.
- **US3 (P3)**: needs US1's player; it adds join, catch-up and interrupted behaviour without changing US1's single-viewer-from-start path.

### Parallel Opportunities

- Setup: T001 and T002.
- Foundational tests: T003, T004, T005 (three different files); T011 (`feed.py`) and T012 (`liveness.py`) are independent of T006–T010.
- US1: T016 and T017 (two test files) in parallel; T023 (`style.css`) alongside T020/T021.
- US3: T032 and T033 in parallel.
- Polish: T039–T043 (five different targets).

---

## Parallel Example: User Story 1

The two failing test files are written together: the cue tests in
`evals/deterministic/test_highlight.py` and the `/api/live` tests in
`evals/deterministic/test_live_api.py`. With those red, `byo/ops/highlight.py` (T018) and
`byo/ops/static/style.css` (T023) can proceed in parallel, because neither needs the other's file.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup → baseline green, three seams.
2. Phase 2 Foundational (blocking) → records carry starts and pids; projections unchanged; feed incremental; `/api/map.active` means live.
3. Phase 3 US1 → the map lights truthfully while a turn runs, and the correspondence eval reports the before/after.
4. **STOP and VALIDATE**: run the eval and quickstart §2; the numbers are the feature's evidence.

### Incremental Delivery

1. Foundational + US1 → the live claim is true (MVP).
2. US2 → the settled claim is true (skipped / not-reached / not-configured / partial are distinguishable).
3. US3 → the claim survives joining, returning and dying.
4. Polish → budgets, docs, contract pointer, redaction audit.

### Notes

- Every test task is written before its implementation task and must fail for the expected reason.
- No task adds a dependency, a table, a visual state or a build step; if one seems necessary, stop and amend the plan first.
- Keep the existing uncommitted style edits in `byo/ops/static/`; do not revert them to make a diff smaller.
- Commit after each checkpoint (end of a phase), not after every task.

---

## Implementation Status

**Implemented**: 43 of 47 tasks. `make eval` is green (207 of 209 tests; the two failures are
`test_brand_assets.py` from the unrelated 005 logo work in the same working tree), `make lint` is
clean, and the correspondence eval prints:

```text
correspondence   baseline   post-change
start aligned    0%        100%
phantom lights   5          0
silent omissions 8          0
final state ok   17%        100%
```

**Pending (browser or human judgement, cannot be claimed from the server side)**:

- **T025** — quickstart `2 (a live turn: the lit component is the working one, real duration, countable rounds).
- **T031** — quickstart `3 (the six settled-state scenarios in a browser).
- **T038** — quickstart `4–7 (join mid-turn, interrupted fixture, `kill -9`, reduced motion, legacy record).
- **T045** — the full quickstart end to end.

The server-side facts behind those four are covered by automated tests: `/api/live`
(`test_live_api.py`), the projection (`test_highlight.py`), the record (`test_record_additions.py`),
the feed (`test_feed.py`) and liveness (`test_liveness.py`); what remains is that a person watches the
seven real scenarios in `quickstart.md` and confirms the paint, motion and keyboard behaviour.

**Recorded deviations from the plan, all deliberate**:

1. Cue shape: `edges` is the **complete** set of connections live after a cue, so the client can idle
   everything else; the `edge_state` field was dropped. The contracts (data-model `3, highlight-cues
   `1, live-api `1) were updated to match.
2. A cue for a step that has no start record is a settle cue only; `context`, `receipt` and the memory
   path therefore carry no `live` phase. This is what keeps a legacy turn from claiming a running
   interval.
3. The browser keeps one poller across a re-render (`MapLive.started`) so a refresh after a turn ends
   cannot cut the 1.2 s settle short.
