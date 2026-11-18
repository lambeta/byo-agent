# Tasks: Agent Execution Visualization

**Input**: Design documents from `specs/002-execution-flow-visualization/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required. The plan and the project constitution make the deterministic offline suite the
bar for behavior changes. Write each test task first, run it, and confirm it fails for the expected
reason before implementing the task it covers. Browser-only behavior has no JS test runner; it is
verified by the quickstart sections named below.

**Organization**: Tasks are grouped by user story. Setup and Foundational phases have no story
label; US1/US2/US3 phases carry the matching label; Polish is cross-cutting.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: `[US1]`, `[US2]`, `[US3]` — required only in user-story phases
- Every task names the exact file path(s) it changes or validates

## Path Conventions

Single project: package `byo/`, tests `evals/deterministic/`, feature docs under
`specs/002-execution-flow-visualization/`. The dashboard's static front end is
`byo/ops/static/`; there is no frontend project and no build step.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm the baseline and create the two new module homes. No feature behavior yet.

- [X] T001 Run the baseline `make eval` and `make lint` and record the current dashboard route/static inventory from `Makefile`, `byo/ops/dashboard.py` and `byo/ops/static/index.html`; stop if either check is already red.
- [X] T002 [P] Create `byo/ops/map.py` and `byo/ops/turn_detail.py` with design-note docstrings naming the mechanism and one rejected alternative (per constitution III); keep them importable with no behavior yet.

**Checkpoint**: The existing suite is green and the new modules exist.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The server-owned map graph, its summaries and the `/api/map` route that US1 and US3
depend on. No user story UI can start until this phase is complete.

**⚠️ CRITICAL**: US1, US2 and US3 depend on this phase.

### Tests for the foundation (write first, confirm red)

- [X] T003 [P] Write the failing graph/summary tests in `evals/deterministic/test_map.py`: 4 groups, 13 unique node ids, 15 unique edge ids, every edge endpoint exists, every destination is `chat|session|memory|turn|observability`, every box inside 1040 × 680, no retired/eval/release id, event-map keys exactly `turn_start, gate, llm, tool, consolidation, receipt, error, turn_end`, every event-map node/edge exists, and every node has a non-empty summary on an empty home.
- [X] T004 [P] Write the failing `/api/map` contract tests in `evals/deterministic/test_map_api.py`: 200 with `window`, `map`, `turns`, `active`, `cursor`, `skipped_lines`; graph is a deep copy; turns are newest first and carry `turn_id, started_at, ended_at, source, state, iterations, tool_calls, usd, estimate`; empty home still returns the full map; `window=bogus` is `400 bad_request`; no route acquires the turn lock.

### Implementation for the foundation

- [X] T005 Implement `GROUPS`, `NODES`, `EDGES` and `graph()` in `byo/ops/map.py` exactly per [contracts/map-graph.md](contracts/map-graph.md): Surfaces; Harness (gate/context/model/tools/reply); Memory (facts/episodes/persona/consolidation); Operations (record/observability/cost); 13 nodes, 15 edges, deep-copy on return, no retired or eval/release node.
- [X] T006 Implement `EVENT_MAP`, `event_map()` and the reference/range validators in `byo/ops/map.py`: the eight keys, `gate.retrieve` adds facts/episodes/persona and the three `e-gate-*` edges, `tool.ok == false` marks failed, `error.stage` maps to gate/model/tools/consolidation, `llm.kind == final` carries the final label, and the map contains no command-line eval/release node.
- [X] T007 Implement `summaries(conn, settings, turns, spend, memory_enabled, tool_count, session_id)` in `byo/ops/map.py`: one short line per node; gate `N skip · M retrieve` / `not configured` / `no turns yet`; facts/episodes counts; context `<session_id> · N messages`; active model; registry tool count; reply `idle` or last `HH:MM`; persona present/missing; consolidation pending/every; record turn count; observability tool-call count; cost `USD X` or `no spend`; never a number the stores did not produce.
- [X] T008 Implement `GET /api/map?window=` and `Dashboard.map_payload` in `byo/ops/dashboard.py`: validate `today|7d|all`, deep-copy the graph, fill summaries, return newest-first turn summaries from the window, the 7-day `active` unfinished turn plus its already-recorded events, the 7-day `cursor`, and `skipped_lines`; keep the route read-only and loopback-only.

**Checkpoint**: `test_map.py` and the `/api/map` tests pass; `GET /api/map` returns the full map on an empty home.

---

## Phase 3: User Story 1 - The runtime agent at a glance, live (Priority: P1) 🎯 MVP

**Goal**: The dashboard lands on a data-driven runtime map; a turn started in the dashboard lights
the correct nodes and edges in order; the status line names each step; every node is navigable and
has a text alternative. The full per-turn timeline is US2; in this phase a `turn` node opens the
existing Chat card as a temporary destination.

**Independent Test**: Open `http://127.0.0.1:7777`, land on Overview, see 13 nodes with summaries,
send a tool-using message from the dock, and watch Surfaces → gate → context → model → tools → reply
→ record light in order without leaving Overview; the status line, node state words, text list and
node destinations all work. Manual: [quickstart.md](quickstart.md) §2–3.

### Tests for User Story 1 (required)

- [X] T009 [P] [US1] Write the failing static-shell test in `evals/deterministic/test_map_static.py`: `index.html` has Overview first in the nav and loads `api.js`, `render.js`, `map.js`, `live.js`, `observe.js`, `dock.js`, `main.js` in that order; no external URL/CDN/build tool; `map.js` and `live.js` are served; no retired/eval/release string appears in the map assets; the text-view and status hooks exist.

### Implementation for User Story 1

- [X] T010 [P] [US1] Add the `Overview` nav entry (first, active by default) and the `map.js`/`live.js` script tags in `byo/ops/static/index.html`.
- [X] T011 [P] [US1] Add the map shell to `byo/ops/static/style.css`: four group panels, node boxes/diamond, state colours **and** state words, edges and labels, status line, recent-turn strip, text view, focus-visible ring, horizontal-scroll map container, and `prefers-reduced-motion` rules.
- [X] T012 [US1] Implement `overviewView()`, the SVG graph renderer, node state machine (`idle|live|done|skipped|degraded|failed|not-reached|partial`), summaries, text alternative and node navigation in `byo/ops/static/js/map.js`; route `turn` nodes to the selected-turn panel. Start the file with a design-note header (data-driven SVG + focusable nodes; rejected: canvas/graph library).
- [X] T013 [US1] Implement `byo/ops/static/js/live.js`: poll `/api/events?cursor=` every 500 ms, apply `map.event_map`, play one 450–650 ms highlight, reset on `turn_start`, keep a 1 s lag bound, hold the final state 0.5–2 s, mark untouched nodes `not-reached` at `turn_end`, and report an unknown type as `unmapped step: <type>` without lighting a node. Start the file with a design-note header (cursor polling + queued highlights; rejected: SSE-only broadcast).
- [X] T014 [US1] Modify `byo/ops/static/js/main.js`: default `#overview`, fetch `/api/map` for the overview, mount/unmount the live player on view change, refresh the map after a turn, and keep a dock send from Overview on Overview (do not replace the map with the chat card).
- [X] T015 [US1] Add the accessible status live region, keyboard Enter/Space activation, node `aria-label` state words and text-view state sync in `byo/ops/static/js/map.js` and `byo/ops/static/style.css`; align `render.js`'s stage chips to the canonical `gate/loop/tool/reply` vocabulary.
- [X] T016 [US1] Refresh the map payload after `turn_end`/consolidation (debounced) so node summaries and the recent-turn strip reflect the new turn, in `byo/ops/static/js/main.js` and `byo/ops/static/js/live.js`.
- [X] T017 [US1] Wire all destinations in `byo/ops/static/js/map.js`: Surfaces → Chat, Working context → current session/history, gate/memory/consolidation → Memory, record/observability/cost → Observability, and loop/tool/reply → the selected turn's detail panel (implemented by T023).

**Checkpoint**: US1 is independently demoable: the map is the landing view, lights for dashboard turns, and opens the selected-turn detail. US2 validates/deepens that detail with the fixture, failure and unfinished cases.

---

## Phase 4: User Story 2 - Drill from the map into one turn (Priority: P2)

**Goal**: The selected turn opens a secondary detail with one-line summary, slowest/most-expensive
hotspots, a one-axis timeline (one row per loop, nested tools), step details, failure/unfinished
states and the raw record. A turn list and the Today/7 days/All window make any recorded turn
reachable.

**Independent Test**: With a recorded fixture (two loops, two tools, one receipt), open the detail
from the map or turn list; the summary, row order, bar geometry, hotspots and raw record match the
trajectory; a failed and an unfinished turn show the documented states; a restart still renders the
detail. Manual: [quickstart.md](quickstart.md) §5–6.

### Tests for User Story 2 (required)

- [X] T018 [P] [US2] Write the failing `evals/deterministic/test_turn_detail.py`: exact summary strings (skipped/retrieved, singular/plural, seconds, cost, estimate, failed/unfinished), hotspot indexes (ties to the earlier step, null cases), raw record includes unknown/text records in order, no receipt => `cost not recorded`, zero-duration axis => `not timed`, and a truncated value stays marked. Include the pre-feature `golden-cli.jsonl` fixture.
- [X] T019 [P] [US2] Add the failing `/api/turn` tests to `evals/deterministic/test_map_api.py`: 200 with `turn`, `summary`, `hotspots`, `raw`, `window`, `skipped_lines`; missing/bad window `400`; unknown/out-of-window id `404`; raw is redacted and read-only; no turn lock. Also add a 50-turn fixture asserting `/api/data`, `/api/map` and `/api/turn` agree.

### Implementation for User Story 2

- [X] T020 [US2] Implement `summary()`, `hotspots()` and `detail(home, turn_id, window)` in `byo/ops/turn_detail.py` per [contracts/turn-detail.md](contracts/turn-detail.md); derive everything from `observability.read_events/group_turns/build_turn` and the raw records; add no table and no event.
- [X] T021 [US2] Implement `GET /api/turn?turn_id=&window=` and `Dashboard.turn_payload` in `byo/ops/dashboard.py`: `400` for a missing id or bad window, `404 not_found` for an id outside the window, and the documented payload otherwise.
- [X] T022 [US2] Add the turn list and selection to `byo/ops/static/js/map.js`: newest first, time/source/state/iterations/tool calls/cost, empty state, click opens the detail, and the selected id survives a map refresh.
- [X] T023 [US2] Implement the detail panel in `byo/ops/static/js/map.js`: header (time/source/state), summary, hotspot badges, loop rows with nested tools, reply/consolidation/receipt rows, per-step `<details>`, raw `<details>`, close returns to the same map; keep the map visible (non-modal).
- [X] T024 [P] [US2] Add the detail/timeline styles to `byo/ops/static/style.css`: one shared axis, proportional model/tool bars, minimum instant markers, nested loop rows, failure/partial states, detail table, raw block, stacked layout at narrow widths.
- [X] T025 [US2] Implement timeline geometry in `byo/ops/static/js/map.js`: axis from `started_at` to `ended_at` (or last record when unfinished); `llm`/`tool` start at `ts - duration_ms`; gate/memory/error markers at `ts`, receipt at its raw `ts` or `ended_at`; zero axis falls back to record order with minimum markers and `not timed`.
- [X] T026 [US2] Add the Today / 7 days / All control in `byo/ops/static/js/main.js` and `byo/ops/static/js/map.js`: refresh `/api/map?window=`, keep the selected turn when it is still in range, otherwise close the detail and say so.
- [X] T027 [US2] Wire the final detail panel in `byo/ops/static/js/map.js` and `byo/ops/static/js/main.js`; every loop/tool/reply node opens the selected turn's detail and no temporary Chat destination remains.
- [X] T028 [US2] Render the raw record in `byo/ops/static/js/map.js`: read-only `<details>`, one JSON object per line, escaped text, no unredaction, truncation marker preserved, no auto-scroll.
- [X] T029 [US2] Add the `slowest` and `most $` text badges plus the `no timed steps` / `no costed steps` legends to `byo/ops/static/js/map.js` and `byo/ops/static/style.css`; the values must come from `hotspots`, never be recomputed differently.
- [X] T030 [US2] Implement failure, unfinished, partial, not-reached, empty, and detail-fetch-error states in `byo/ops/static/js/map.js` and `byo/ops/static/style.css`; no invented reply, cost or completion.
- [X] T031 [US2] Validate the detail in a browser against `specs/002-execution-flow-visualization/quickstart.md` §5–6, including a recorded fixture, a failed/unfinished fixture and a restart; record any mismatch as a bug task before moving on.

**Checkpoint**: US1 and US2 work together: the map lights, and every recorded turn opens a faithful detail.

---

## Phase 5: User Story 3 - Watch turns from anywhere, without disturbing them (Priority: P3)

**Goal**: A terminal turn lights an open map, labels its source, supports multiple independent
viewers, catches up after a gap or a burst without dropping steps or claiming stale state, and does
not steal a detail someone is reading.

**Independent Test**: With the map open, run a turn in the terminal; the map lights, labels `cli`,
and needs no refresh. Two tabs watch the same sequence; closing one does not cancel the turn; a
forced disconnect says `reconnecting`, then catches up with each recorded step exactly once. Manual:
[quickstart.md](quickstart.md) §4 and §8.

### Tests for User Story 3 (required)

- [X] T032 [P] [US3] Add the failing feed tests to `evals/deterministic/test_map_api.py`: `/api/events` returns a `skipped` count and only records after the cursor; a CLI-written trajectory becomes visible without the server starting a turn; the route is GET-only and does not acquire `dash.lock`.
- [X] T033 [US3] Add the `skipped` count to the `/api/events` response in `byo/ops/dashboard.py` (additive field; preserve `events`, `cursor`, `complete`), and keep the route read-only.

### Implementation for User Story 3

- [X] T034 [US3] Implement the initial active-turn replay and cursor handoff in `byo/ops/static/js/live.js`: replay `/api/map.active.events` in order, then poll from `cursor`; never duplicate the active turn's events.
- [X] T035 [US3] Implement source labelling and status transitions in `byo/ops/static/js/live.js` and `byo/ops/static/js/map.js`: `cli`/`dashboard` from `turn_start`, `reconnecting` on a failed poll, `caught up` after coalescing, `skipped N bad line(s)` when the feed reports it, and a visible stale mark until recovery.
- [X] T036 [US3] Implement the backlog policy in `byo/ops/static/js/live.js`: if the queue exceeds 8 events or the oldest is older than 2 s, drop intermediate highlights, apply the latest complete state, keep the displayed state within 1 s of the record, and say `caught up`.
- [X] T037 [US3] Implement visibility and navigation lifecycle in `byo/ops/static/js/live.js` and `byo/ops/static/js/main.js`: pause polling on `visibilitychange`, resume from the last cursor, stop on leaving Overview, and never cancel or block the turn.
- [X] T038 [US3] Implement the "new turn while a detail is open" behaviour in `byo/ops/static/js/map.js` and `byo/ops/static/js/main.js`: the detail and selection stay put; a visible indicator offers the live turn; choosing it returns to the map.
- [X] T039 [US3] Add read-only/multi-viewer assertions to `evals/deterministic/test_map_api.py`: two simultaneous `/api/events` polls succeed while the turn lock is held, and neither route mutates the trajectory or the lock.
- [X] T040 [US3] Validate the cross-surface journey in `specs/002-execution-flow-visualization/quickstart.md` §4 and §8 with two tabs and a terminal turn; record any mismatch as a bug task.

**Checkpoint**: All three stories work independently and together; the map is a shared, read-only window on the agent.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Scale, documentation, accessibility sweep, security and final validation.

- [X] T041 [P] Add `evals/deterministic/test_map_scale.py`: build a 200-turn / 20-step fixture and assert `/api/map` and `/api/turn` stay within the documented budget (1 s on the development laptop; use a CI-safe margin), with exact summary/hotspot values.
- [X] T042 [P] Update `README.md` for the Overview landing view, the map's runtime scope, the detail, and the fact that evals/release stay command-line.
- [X] T043 [P] Add the final assertions to `evals/deterministic/test_map_static.py` and `evals/deterministic/test_map.py`: no external URL/build tool, script order, text view, reduced-motion CSS, no reference brand asset, no retired/eval/release node, and every node destination has a handler.
- [X] T044 Run `make eval`, `make gate` and `make lint` from `Makefile`; all must be green before the feature is called ready.
- [X] T045 Execute `specs/002-execution-flow-visualization/quickstart.md` §2–10 (map, live from both surfaces, detail, failure/unfinished, accessibility, restart, scale, secrets) and record the result beside the task.
- [X] T046 Measure the 200-turn budget from `evals/deterministic/test_map_scale.py` and the quickstart §9 browser check; if the map or detail exceeds 1 s, add a tail-read cache in `byo/ops/observability.py` without changing the API, then re-run.
- [X] T047 Run `evals/deterministic/test_redaction.py` and inspect `/api/turn` raw output; confirm no key-shaped value, no unredaction, and no secret in the map/detail.
- [X] T048 Re-read `specs/002-execution-flow-visualization/spec.md`, `specs/002-execution-flow-visualization/plan.md` and `specs/002-execution-flow-visualization/tasks.md`; confirm every FR/SC is covered, no new dependency/schema/event type was added, and the map contains no eval/release node; update this task list's checkboxes and note any follow-up.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies; T001 and T002 can run in parallel.
- **Foundational (Phase 2)**: depends on T002; T003/T004 can be written in parallel; T005 depends on T003/T004; T006/T007 depend on T005; T008 depends on T005–T007. **Blocks all user stories.**
- **US1 (Phase 3)**: depends on Foundational (T008) and T009; T010/T011 depend on T009; T012 depends on T010/T011/T008; T013 depends on T012/T008; T014 depends on T012/T013; T015 depends on T012; T016 depends on T014; T017 depends on T012.
- **US2 (Phase 4)**: server work (T018–T021) depends on Foundational; UI work (T022–T030) depends on US1's shell (T012/T014); T018/T019 can be written in parallel; T020/T021 depend on them; T022/T023 depend on T021 and T012; T024 depends on T023; T025–T030 depend on T023; T027 depends on T017/T023.
- **US3 (Phase 5)**: depends on US1's live player (T013) and T008; T032/T033 can be written in parallel; T034–T037 depend on T032/T033; T038 depends on T023/T014; T039 depends on T032; T040 depends on T034–T039.
- **Polish (Phase 6)**: depends on all desired stories; T041/T042/T043 can be parallel; T044–T048 after them.

### User Story Dependencies

- **US1 (P1)**: can start after Foundational; no dependency on US2/US3. It is the MVP.
- **US2 (P2)**: server detail can start after Foundational; the full UI needs US1's map shell. It is independently testable against a fixture before US3.
- **US3 (P3)**: depends on US1's live player; it adds cross-surface/reconnect behavior without changing US1's single-viewer path.
- US1 wires loop/tool/reply to the selected-turn detail; US2 fills that panel with the full timeline/summary/raw. No temporary Chat destination remains.

### Within Each User Story

- Tests first; confirm the expected failure before implementation.
- Data/model before endpoint; endpoint before UI; UI before integration.
- US1: T009 → T010/T011 → T012 → T013 → T014 → T015/T016/T017.
- US2: T018/T019 → T020 → T021 → T022/T023 → T024/T025 → T026–T030 → T031.
- US3: T032/T033 → T034 → T035/T036/T037 → T038/T039 → T040.

### Parallel Opportunities

- Setup: T001 and T002 (different files/commands).
- Foundation: T003 and T004 (different test files); T006 and T007 both touch `map.py`, so they are sequential.
- US1: T010 (HTML) and T011 (CSS) are different files; T009 is the test that must precede them. Do not parallelize T012/T013 (live.js calls map functions).
- US2: T018 (turn detail tests) and T019 (API tests) are different files; T024 (CSS) can run alongside T023 (map.js) if the class names in the plan are respected.
- US3: T032 (feed tests) and T033 (dashboard.py) are different files.
- Polish: T041, T042 and T043 are different files and can run in parallel.

---

## Parallel Example: User Story 1

```bash
# After T009 is written and red:
Task: "T010 Add Overview nav and script tags in byo/ops/static/index.html"
Task: "T011 Add the map shell and state styles in byo/ops/static/style.css"
```

## Parallel Example: User Story 2

```bash
# After T009/T010/T011 and the US2 tests are red:
Task: "T018 Write evals/deterministic/test_turn_detail.py"
Task: "T019 Add /api/turn tests to evals/deterministic/test_map_api.py"

# Later, once T023's detail markup exists:
Task: "T024 Add detail/timeline styles to byo/ops/static/style.css"
```

## Parallel Example: User Story 3

```bash
# After T013 and T032/T033:
Task: "T034 Implement active replay in byo/ops/static/js/live.js"
Task: "T035 Implement source/reconnect/caught-up status in live.js and map.js"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1 and Phase 2 (the map data, summaries and `/api/map`).
2. Complete Phase 3 (the landing map, live lighting, status, text alternative, navigation).
3. **STOP and VALIDATE** with [quickstart.md](quickstart.md) §2–3.
4. Demo the map lighting for a browser turn; the full detail and terminal observation follow.

### Incremental Delivery

1. Setup + Foundational → map data/API ready.
2. US1 → map landing + live lighting (MVP), independently testable.
3. US2 → detail/timeline/summary/hotspots/raw, independently testable against fixtures; the selected-turn panel is filled out by the full detail.
4. US3 → terminal turns, multiple viewers, reconnect/catch-up, detail-safe live updates.
5. Polish → scale, accessibility, docs, final suite and quickstart.

### Parallel Team Strategy

- One developer on the map foundation (T003–T008), one on the detail read model (T018–T021) after the foundation.
- Once US1's shell exists, one developer can do US2 UI while another does US3 live hardening, because they touch different concerns (detail vs feed) even though both use `map.js`.
- Keep a single owner for `byo/ops/map.py`, `byo/ops/static/js/map.js` and `byo/ops/static/style.css` at a time; these files have the most merge risk.

---

## Notes

- Every task has a checkbox, a T-id, an optional `[P]`, a story label only in Phases 3–5, and an exact file path.
- Tests are required by the plan and constitution; the browser-only visual/live checks are manual by design (no JS test runner, no new dependency).
- No task adds a database table, a trajectory event type, a runtime dependency or a build step.
- The map stays runtime-only: evals and release are never nodes, placeholders or edge labels.
- Update the checkbox as each task lands; do not mark a task done while its test or quickstart check is red.
