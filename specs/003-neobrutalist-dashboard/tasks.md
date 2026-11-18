---

description: "Task list for feature implementation"
---

# Tasks: Neobrutalist Dashboard Refresh

**Input**: Design documents from `/specs/003-neobrutalist-dashboard/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Included. The plan mandates deterministic static-asset tests (research R8; constitution V) — they are written FIRST and must FAIL before the stylesheet work that satisfies them.

**Organization**: Tasks are grouped by user story. The feature is one shared stylesheet, so story phases sequence the *rules* added to `byo/ops/static/style.css`; test files and markup hooks are parallelizable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- File paths are repository-relative

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Baseline capture so parity and sizing claims are checkable, not aspirational

- [X] T001 Extract the pre-change label/action inventory from `byo/ops/static/index.html` and `byo/ops/static/js/*.js` into the pinned parity list used by the parity test, matching [contracts/surface-parity.md](contracts/surface-parity.md) exactly (nav labels, view heads, button copy, table heads, empty-state strings, timeline labels)
- [X] T002 [P] Record pre-change body text sizes (14 px body, 12.5 px dense data) and the eight `data-state` values emitted by `byo/ops/static/js/map.js`, `live.js`, `render.js` as test constants for the size-floor and state-selector assertions

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The token seam and its tests — every story's rules consume these tokens, and no component rule may introduce raw values

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests first — write, watch FAIL, then implement

- [X] T003 [P] Create `evals/deterministic/test_style_tokens.py`: assert every token in [contracts/design-tokens.md](contracts/design-tokens.md) is defined in the `:root` (dark) block AND re-valued in the `prefers-color-scheme: light` block of `byo/ops/static/style.css`; compute each enumerated contrast pair from hex values with the WCAG relative-luminance formula and assert >= 4.5:1 (text) / >= 3:1 (large text and interactive boundaries) in both schemes
- [X] T004 [P] Create `evals/deterministic/test_style_states.py`: assert `byo/ops/static/style.css` contains `[data-state]` selectors for all eight states (idle, running, done, skipped, degraded, failed, not-reached, partial) with contour weight/dash declarations per [contracts/state-cues.md](contracts/state-cues.md); assert `:focus-visible` rules exist for links, buttons, inputs and `.map-node`; assert the three media queries exist (`prefers-color-scheme`, `prefers-reduced-motion`, `forced-colors`); assert no `@keyframes` and no `infinite` animation
- [X] T005 [P] Create `evals/deterministic/test_style_offline.py`: scan every file under `byo/ops/static/` and assert no `@import`, no `http://`/`https://` reference, and no `url()` pointing outside the local server (spec FR-014)
- [X] T006 [P] Create `evals/deterministic/test_style_parity.py`: diff the pinned label list from T001 against the strings present in `byo/ops/static/index.html` and `byo/ops/static/js/*.js`; any missing label fails (spec FR-015)
- [X] T007 [P] Extend `evals/deterministic/test_map_static.py`: assert the shell still loads the same seven scripts in order and the static server still serves them (guard against accidental script changes)

### Implementation — tokens and base grammar

- [X] T008 Implement the full token block in `byo/ops/static/style.css` per [contracts/design-tokens.md](contracts/design-tokens.md): `:root` dark defaults and the `prefers-color-scheme: light` re-valuation for every field, ink, accent, contour, shadow, type, space, radius and motion token (until T014 enables it, the strict no-raw-hex scan is out of scope)
- [X] T009 Rewrite the base element rules in `byo/ops/static/style.css`: body grid unchanged in structure but token-driven, the four typographic levels (`--byo-font-display` for brand/titles/figures at weight 700–900, body never below 14 px, dense never below 12.5 px, micro-labels uppercase with `--byo-track-wide`), global `:focus-visible` double-ring (3.5 px `--byo-accent-live` outline, 2 px offset, on top of the element's own contour), and the `prefers-reduced-motion` + `forced-colors` blocks per [contracts/state-cues.md](contracts/state-cues.md)

**Checkpoint**: `pytest evals/deterministic/test_style_tokens.py evals/deterministic/test_style_states.py evals/deterministic/test_style_offline.py` passes; the page renders token-driven base typography in both schemes

---

## Phase 3: User Story 1 — Land on a dashboard that looks built, not skinned (Priority: P1) 🎯 MVP

**Goal**: The shell (sidebar, brand, navigation, home path) and the entire Overview — status pill, window controls, runtime map, text view, recent turns — carry the Neobrutalist language in both schemes, with the eight runtime states distinguishable without hue and live lighting perceivable on the new flat fills.

**Independent Test**: Open `byo dashboard` on Overview with a recorded sample: every surface-parity row for surfaces 1, 3, 9, 11 shows the new vocabulary; a scripted turn lights nodes/edges in order; the quickstart scenarios 2, 3, 5 and 7 pass for Overview.

### Implementation for User Story 1

- [X] T010 [P] [US1] Add the `.brand-sticker` wrapper hook around the brand word in `byo/ops/static/index.html` (allowlisted markup hook; rotated brand-accent sticker behind "byo")
- [X] T011 [P] [US1] Add the `.live-sticker` span hook inside the live indicator in `byo/ops/static/js/map.js` `overviewView` (allowlisted hook; rotated "LIVE" tag, carries no data)
- [X] T012 [US1] Restyle the sidebar in `byo/ops/static/style.css`: brand in display face with the sticker accent (VD-006, at most one per region), nav links with contour + accent-fill active marking (two cues, FR-003), home path in mono with wrap; sidebar keeps its grid row and width
- [X] T013 [US1] Restyle the Overview chrome in `byo/ops/static/style.css`: status pill (contour, `data-kind="bad"` and `data-stale` treatments), window buttons with two-cue active state, live indicator with brand-accent fill and sticker, section heads and map toolbar
- [X] T014 [US1] Restyle the runtime map in `byo/ops/static/style.css`: `.map-wrap` (contour + resting shadow, scroll region preserved), group rects and labels, node boxes with the eight-state cue matrix from [contracts/state-cues.md](contracts/state-cues.md) (running = 3.5 px contour + flat live-accent fill + resting shadow; failed = strong contour + double bad shadow; skipped/degraded/partial = dashed `4 3`; not-reached = dashed + opacity 0.45), edges (1.4 px idle / 2.4 px live-accent running, no glow), arrowheads, node/summary/state labels, hover/focus per interaction contract, transitions <= `--byo-motion-fast` and removed under reduced motion
- [X] T015 [US1] Restyle the map text view and recent turns in `byo/ops/static/style.css`: `<details>` container, `.state-dot` cues matching the matrix, `.linkish` buttons, `.recent-row` with compact row shadow and `.recent-state` word+cue treatment
- [ ] T016 [US1] Verify US1 in the browser — **MANUAL**: headless screenshot blocked by sandbox, see validation.md per [quickstart.md](quickstart.md) scenarios 2, 3, 5, 7 limited to Overview and the sidebar: token-driven rendering in both schemes, keyboard focus ring unclipped on map nodes, grayscale state naming 8/8, live lighting perceivable without translucency

**Checkpoint**: User Story 1 stands alone — Overview and the shell are fully restyled, state cues are grayscale-safe, and the map's live lighting works on flat fills

---

## Phase 4: User Story 2 — Send a message and watch a turn without the style getting in the way (Priority: P2)

**Goal**: The composer and the Chat view (turn cards, stage chips, step rows, replies, receipts, live card) speak the same language; streaming never moves the shell; failures read as failures by label and cue; long content wraps.

**Independent Test**: Send a scripted turn with a tool call and a failure from the composer: composer focus/press states are unmistakable, the live card updates in place without dock movement, the failed step is recognisable without a legend, and an overlong message wraps within its card (quickstart scenarios 4 and 8, chat portions).

### Implementation for User Story 2

- [X] T017 [P] [US2] Add the `primary` class hook to the send button in `byo/ops/static/index.html` (allowlisted hook)
- [X] T018 [US2] Restyle the composer in `byo/ops/static/style.css`: input with contour and unclipped focus ring, send button as the primary action (live-accent fill, `--byo-contour-w-strong`, resting shadow, `--byo-shadow-press` + `translate(3px,3px)` on active, removed under reduced motion); dock keeps its grid placement and never shifts during streaming (FR-009)
- [X] T019 [US2] Restyle turn cards in `byo/ops/static/style.css`: `.card` with contour + resting shadow, `.card.user` accent contour (replaces the 3 px left border with the cue-kit equivalent), meta row in mono, `.stages` chips (pill exception to the radius rule), `.chip.ok`/`.chip.bad` flat fills with `--byo-ink-on-accent` text
- [X] T020 [US2] Restyle step rows, replies and receipts in `byo/ops/static/style.css`: `.step` grid preserved, `.step.bad` with bad-accent contour + label cue (not hue alone, US2 scenario 3), `.reply` dashed separators re-drawn as contour-dashed, receipt line in mono; long messages, args, model names and errors wrap via `overflow-wrap:anywhere` without page-level scroll (US2 scenario 4)

**Checkpoint**: User Stories 1 AND 2 both work — the full send-and-watch loop is restyled and stream-stable

---

## Phase 5: User Story 3 — Read the record: turn detail, memory, spend and settings (Priority: P3)

**Goal**: The dense surfaces — turn-detail overlay with timeline and raw record, Observability stats/tracks/table, Memory tables and forget actions, Settings form — are restyled yet remain aligned, scannable and operable down to 375 px and up to 200% zoom.

**Independent Test**: Open a recorded turn's detail, expand its raw record, then visit Observability, Memory and Settings at 1280/900/375 and 200% zoom: rows align, figures line up, the forget and save actions are unambiguous, empty states explain themselves (quickstart scenarios 6, 8 and 9).

### Implementation for User Story 3

- [X] T021 [P] [US3] Add the `primary` class hook to the save button in `byo/ops/static/js/dock.js` `settingsView` (allowlisted hook)
- [X] T022 [US3] Restyle the turn-detail overlay in `byo/ops/static/style.css`: `.turn-detail` as a raised panel (panel-raised fill, strong contour, resting shadow, visually distinct from the map behind it), detail head/meta/summary/legend, `.tl-axis`, `.tl-row` grid, `.tl-track`/ `.tl-bar` (flat fills, instant bars in warn-accent), loop disclosures and carets, `.tl-step pre` and `.raw pre` mono blocks with `overflow-wrap:anywhere`, `.hot` badges, `.bad-row` treatment, close control focus
- [X] T023 [US3] Restyle Observability and Memory in `byo/ops/static/style.css`: stat cards with display-face figures (`--byo-text-4`), `.turnbar`/`.track` bars distinguishable from their tracks, tables with contour-bounded container, aligned rows and consistent figures, `forget` buttons with bad-accent contour, empty states in the new language (FR-013)
- [X] T024 [US3] Restyle the Settings form in `byo/ops/static/style.css`: labels as micro-labels, inputs with contour + focus ring, key-set indicator text preserved, save as primary action; focus order follows the DOM through provider → model → key → save
- [X] T025 [US3] Implement the responsive rules in `byo/ops/static/style.css`: extend the existing 900 px media query and add the 375 px single-column reflow (sidebar stacks, primary targets >= 40 px per FR-017, map keeps its own scroll region as the only horizontal scroller), verify no clipped text or overlapping controls at 200% zoom (SC-004)

**Checkpoint**: All three stories are independently functional — every surface in the inventory carries the new language

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Lock the invariants, sweep the edge cases, prove the success criteria

- [X] T026 Enable the strict no-raw-value scan in `evals/deterministic/test_style_tokens.py`: assert no hex colour or raw `box-shadow` appears outside the token definition blocks of `byo/ops/static/style.css` (design-tokens contract invariant 2)
- [ ] T027 [P] **MANUAL** Run the full [quickstart.md](quickstart.md) sweep in the browser: scenarios 2–3 (five views, both schemes), 4 (live turn or scripted substitute), 5 (keyboard-only, focus return on detail close), 6 (1280/900/375 + 200% zoom), 7 (grayscale 8/8), 8 (edge cases: fresh home, feed drop, live-while-reading, forced colours, long content), 9 (label-by-label parity walkthrough)
- [ ] T028 [P] **MANUAL** (computed half automated in test_style_tokens.py) Verify rendered contrast for every pair in [contracts/design-tokens.md](contracts/design-tokens.md) with the browser inspector's contrast readout on the rendered page (sampled per quickstart scenario 3) in both schemes
- [X] T029 Run `make eval` and `make gate`: the entire deterministic suite passes offline, including the pre-existing `test_map.py`, `test_map_api.py`, `test_turn_detail.py` and `test_api_contract.py` unchanged
- [X] T030 Final self-review against spec success criteria SC-001 through SC-011 with results recorded in [checklists/requirements.md](checklists/requirements.md) notes or a new validation note under `specs/003-neobrutalist-dashboard/`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately
- **Foundational (Phase 2)**: depends on T001/T002 constants — BLOCKS all user stories
- **User Stories (Phases 3–5)**: all depend on the token block (T008) and base grammar (T009)
  - Stories share one file (`style.css`), so they run **sequentially in priority order** P1 → P2 → P3; within a story, markup-hook tasks ([P], different files) can run alongside stylesheet tasks
- **Polish (Phase 6)**: depends on all three stories; T026/T027/T028 are parallel with each other, T029/T029 last

### User Story Dependencies

- **US1 (P1)**: tokens + base only — the MVP
- **US2 (P2)**: tokens + base only; does not touch US1 rules
- **US3 (P3)**: tokens + base only; extends the responsive block started in US1's map work

### Parallel Opportunities

- Phase 1: T001 ∥ T002
- Phase 2 tests: T003 ∥ T004 ∥ T005 ∥ T006 ∥ T007 (five separate test files), then T008 → T009 (same file, sequential)
- US1: T010 ∥ T011 ∥ (T012 → T013 → T014 → T015 sequential in `style.css`) → T016
- US2: T017 ∥ (T018 → T019 → T020 sequential)
- US3: T021 ∥ (T022 → T023 → T024 → T025 sequential)
- Polish: T026 ∥ T027 ∥ T028, then T029 → T030

---

## Parallel Example: Foundational tests

```bash
# Launch all five foundational test tasks together (different files):
Task: "Create evals/deterministic/test_style_tokens.py"
Task: "Create evals/deterministic/test_style_states.py"
Task: "Create evals/deterministic/test_style_offline.py"
Task: "Create evals/deterministic/test_style_parity.py"
Task: "Extend evals/deterministic/test_map_static.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (baseline constants) and Phase 2 (tests fail → tokens + base grammar green)
2. Complete Phase 3: shell + Overview + map with the eight-state cue matrix
3. **STOP and VALIDATE**: quickstart scenarios 2, 3, 5, 7 on Overview; the dashboard already looks and behaves like the new product on its front door

### Incremental Delivery

1. Setup + Foundational → token seam live, tests green
2. + US1 → Overview is the Neobrutalist front door (demoable MVP)
3. + US2 → the daily send-and-watch loop matches
4. + US3 → dense record surfaces and responsive behavior complete the coverage
5. Polish → strict scans on, quickstart sweep recorded, `make gate` green

---

## Notes

- [P] tasks touch different files; all `style.css` rule tasks are sequential within their story
- The four markup hooks (T010, T011, T017, T021) are the **only** permitted script/HTML changes — the allowlist in [contracts/surface-parity.md](contracts/surface-parity.md)
- No API, payload, copy, route or keyboard-shortcut changes anywhere in this feature
- Commit after each task or logical group; stop at any checkpoint to validate the story independently