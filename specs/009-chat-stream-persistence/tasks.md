# Tasks: Chat Stream Persistence Across Navigation

**Input**: Design documents from `specs/009-chat-stream-persistence/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/chat-live-turn.md, quickstart.md

**Tests**: REQUIRED by spec FR-014 and SC-006. Write each test group first, run it, and confirm it
fails for the expected reason before implementing the matching tasks. The repository has no
JavaScript runner (006 D-4), so client behaviour is pinned by Python source contracts plus the
browser quickstart; server behaviour is pinned by offline pytest + HTTP.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested and
demonstrated on its own. All client tasks edit `byo/ops/static/js/main.js`; only one person should
hold that file at a time.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different file, no dependency on an incomplete task
- **[Story]**: US1, US2 or US3 only in user-story phases
- Every task names an exact file path

## Path Conventions

Single project at the repository root: `byo/` for the package, `evals/deterministic/` for tests,
`specs/009-chat-stream-persistence/` for this feature's documents.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: prepare the regression module and the design notes the constitution requires; no
behaviour change yet.

- [X] T001 [P] Create `evals/deterministic/test_chat_lifecycle.py` with a module docstring and shared helpers `read_static(name)`, `between(text, start, end)` and `function_body(source, name)`; no assertions yet (FR-014).
- [X] T002 [P] Add the chat-block design note to `byo/ops/static/js/main.js`: one session-scoped live turn, atomic handoff, single `clearLive` writer; rejected alternatives server replay, a new `chatlive.js` module, and `sessionStorage` (Constitution I/III).
- [X] T003 [P] Add the turn-owner design note to `byo/app.py` above `Agent.respond`/`_log`: bind the starting `Session`, accumulate partial text, rejected alternatives blocking new chat and a second store (Constitution I/III).
- [X] T004 [P] Run `make eval` and `make lint` from the repo root (`Makefile`) and record the 349-test baseline in the implementation PR notes; stop if either target fails (SC-006/SC-007).

**Checkpoint**: test module and design notes exist; baseline is recorded.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: the LiveTurn shape and the single clear path every story uses.

**⚠️ CRITICAL**: no user-story work begins until this phase passes.

- [X] T005 Add foundational source contracts to `evals/deterministic/test_chat_lifecycle.py`: `clearLive` exists with the turn-id guard; `newLive` accepts `sessionId` and sets `session_id`; `state.handoffTurnId` exists (data-model sections 1, 4 and 10.5).
- [X] T006 [P] Extend `newLive(message, sessionId)` in `byo/ops/static/js/main.js` with the LiveTurn fields: `session_id` (required, set once), `state = 'live'`, `has_done = false`, `turn_id = null`, `started_at`, `receipt = null`. Constraint: "`session_id` MUST be non-empty and MUST equal the current chat at `begin`"; "`turn_id` MUST be null until `done`; once set it MUST NOT change" (data-model section 1).
- [X] T007 Add `clearLive(turnId)` to `byo/ops/static/js/main.js` and `state.handoffTurnId: null` to the `state` initializer. Constraint: "`clearLive(turnId)` MUST be a no-op unless `state.live.turn_id === turnId`"; it is the only writer that sets `state.live = null` (data-model sections 3 and 10.5; C6.5).
- [X] T008 Run the foundational contracts from `evals/deterministic/test_chat_lifecycle.py` with `make eval` (`Makefile`); they must pass, and the 349 existing tests must stay green.

**Checkpoint**: the LiveTurn shape, the single clear path and the handoff slot exist; stories can start.

---

## Phase 3: User Story 1 - A streaming answer survives sidebar navigation (Priority: P1) 🎯 MVP

**Goal**: clicking any sidebar destination during a stream neither clears nor pauses the live turn;
the dock keeps updating while away, and returning shows every fragment exactly once.

**Independent Test**: run the `us1` contracts in `evals/deterministic/test_chat_lifecycle.py`, then
quickstart section 2: with a slow stream, switch to Tools after the fifth fragment, return after ten more,
and confirm fragments 1–20 are present once, in order, with the stream still flowing.

### Tests for User Story 1

- [X] T009 [US1] Add US1 source contracts to `evals/deterministic/test_chat_lifecycle.py`: the `hashchange` handler contains neither `state.live = null` nor `clearLive`; `renderChat` calls `paintLive()` before and after the history fetch; the `send` frame callback has no destination/view gate and handles `gate_start`, `text`, `llm`, `tool_start` and `tool`. Constraint: "Navigation, session selection and new chat are not transitions" (data-model section 3; C1.1, C2.1, C2.3).
- [X] T010 [US1] Remove `state.live = null` and the clearing `paintLive()` call from the `hashchange` listener in `byo/ops/static/js/main.js`; keep `MapLive.stop()` so only the map pauses, and let `renderChat`/`paintLive` reconcile the dock (FR-001, FR-004; C1.1).
- [X] T011 [US1] Make `paintLive()` in `byo/ops/static/js/main.js` render from `state.live` regardless of the current destination, and call it at the start and end of `renderChat()` so `#chat-live` survives `#view` re-renders (FR-002, FR-004; C1.4, C2.1).
- [X] T012 [US1] Keep every stream frame applying to `state.live` while another destination is displayed in `byo/ops/static/js/main.js`: remove any view/destination guard in the `send` callback, append each `text` delta once to the open `streaming` item, and keep `paintLive()`/`scrollChat()` per frame (FR-003, FR-005; C2.1–C2.3).
- [X] T013 [US1] Run the `us1` contracts in `evals/deterministic/test_chat_lifecycle.py` and `make eval` (`Makefile`); confirm idle navigation still renders every view unchanged (FR-015, SC-007).

**Checkpoint**: US1 is independently demonstrable; this is the MVP.

---

## Phase 4: User Story 2 - Completion while away leaves one clean transcript (Priority: P2)

**Goal**: a turn that finishes while another destination or chat is displayed becomes exactly one
transcript entry, with no duplicate reply, no missing tail, and an honest failed/limited ending.

**Independent Test**: run the `us2` contracts and the failing-stream HTTP test in
`evals/deterministic/test_chat_lifecycle.py`, then quickstart sections 3 and 6: switch to Memory before
completion and confirm one user message plus one assistant reply, no duplicate, and a failed
turn's partial text above the error.

### Tests for User Story 2

- [X] T014 [US2] Add US2 handoff contracts to `evals/deterministic/test_chat_lifecycle.py`: `done` sets `has_done`, `turn_id` and the ending state; `state.handoffTurnId` is set only when `has_done`; `renderChat` assigns `#chat-history` before `clearLive` and `paintLive`; a failed history fetch keeps the card; a no-`done` stream marks the turn failed. Constraint: "Only a turn with `has_done = true` is handed off"; while the fetch is in flight the card remains visible and the reply is never twice or absent (C6.2–C6.6, C7.3).
- [X] T015 [US2] Add the failing-stream HTTP test to `evals/deterministic/test_chat_lifecycle.py`: a custom adapter emits text deltas then raises `Refused`; assert `done.failed = true`, the assistant history row has `state = 'failed'` and `partial` equal to the streamed text, and the trajectory records the failure; add an unexpected adapter exception case that sends one `error` frame and no `done`. Constraint: "`partial` is the concatenation of streamed `text` deltas only for a failed turn, truncated to 4000 characters" (C7.1, C7.5; data-model section 6).
- [X] T016 [US2] Add transcript render contracts to `evals/deterministic/test_chat_lifecycle.py`: `bubble()` reads `message.state` and `message.partial`; `.bubble-partial` is escaped and pre-wrapped; a `failed`/`limited` cue is rendered for non-complete rows; the live card renders a `limited` cue. Constraint: "A non-empty `partial` MUST render as plain, escaped, pre-wrapped text above the final reply; it MUST NOT be interpreted as raw HTML" (C9.2–C9.4).

### Implementation for User Story 2

- [X] T017 [P] [US2] In `byo/app.py`, accumulate the `text` deltas emitted during the turn and write `meta.state` (`failed` when `result.error`, `limited` when `limit_reached`, otherwise `complete`) and `meta.partial` (failed only, max 4000 chars) in `_log` (C7.1; data-model section 6).
- [X] T018 [P] [US2] In `byo/ops/dashboard.py`, add `failed: bool(result.error)` to the `done` frame, expose `state`/`partial` on assistant history rows, and catch an unexpected exception in `_stream` to send one `error` frame with stage `turn` and no fabricated `done` (C7.5, C9.1; data-model sections 5 and 7).
- [X] T019 [US2] In `byo/ops/static/js/main.js`, handle `done`: set `has_done`, `turn_id`, `reply`, `receipt` and the ending state from `failed`/`limit_reached`; set `state.handoffTurnId` only when `has_done`; mark a no-`done` stream failed and keep the card; remove the unconditional clear after `refresh()` (C6.1–C6.6, C7.3).
- [X] T020 [US2] Render the failed/limited transcript and card in `byo/ops/static/js/main.js`, `byo/ops/static/js/render.js` and `byo/ops/static/style.css`: `.bubble-partial` with escaped pre-wrapped text, `failed`/`limited` cues, and a live-card `limited` cue; old rows without fields render as today (C9.2–C9.4).
- [X] T021 [US2] Run the `us2` contracts in `evals/deterministic/test_chat_lifecycle.py` and `make eval` (`Makefile`); confirm the failing-stream history row and the atomic handoff pass.

**Checkpoint**: US2 works with US1; completion away is one clean entry.

---

## Phase 5: User Story 3 - Other shell actions do not disturb the live turn (Priority: P3)

**Goal**: dock collapse/resize, theme, trace detail, chat selection and a new chat never cancel,
blank, restart or duplicate the live turn; a turn belongs to the chat that sent it, and a second
send is refused without replacing it.

**Independent Test**: run the `us3` contracts and the server session-swap test in
`evals/deterministic/test_chat_lifecycle.py`, then quickstart sections 4 and 5: select a past chat mid-stream,
return, start a new chat, and confirm the card is never shown in the wrong chat and the old turn
survives.

### Tests for User Story 3

- [X] T022 [US3] Add US3 ownership/visibility contracts to `evals/deterministic/test_chat_lifecycle.py` for `byo/ops/static/js/main.js`, `byo/ops/static/index.html` and `byo/ops/static/style.css`: `newLive` binds `session_id`; `paintLive` uses `visible(live) = live !== null && live.session_id === (state.viewing || state.session)`; `#chat-sessions` and `#new-chat` contain no clear; `#chat-notice` exists with `role="status"`/`aria-live="polite"` and `.chat-notice:empty` CSS; the notice changes only when its condition changes (C3.1–C3.4, C1.2–C1.3).
- [X] T023 [US3] Add US3 send-admission contracts to `evals/deterministic/test_chat_lifecycle.py`: the guard appears before `newLive`; `send()` refuses while `state.live.state === "live"`; a refused send does not replace, clear or mutate the turn; a new send clears a pending handoff. Constraint: "A refused send MUST NOT replace, clear or mutate the live turn" (C4.1–C4.3).
- [X] T024 [US3] Add the server session-swap test to `evals/deterministic/test_chat_lifecycle.py`: an adapter calls `agent.new_session()` mid-turn; assert both `chat_log` rows keep the starting session id, the new session's history is empty, and the trajectory's `turn_start.session_id` agrees. Constraint: "`session_id` never changes after `begin`"; C8.1–C8.4.
- [X] T025 [US3] Add the shell-action contract to `evals/deterministic/test_chat_lifecycle.py` for `byo/ops/static/js/main.js` and `byo/ops/static/js/map.js`: the dock collapse/reopen, resize, theme, trace expansion and turn-detail handlers contain no `clearLive`/`state.live = null`, and `clearLive` is the only writer of `state.live = null`; C1.4, data-model section 10.5.

### Implementation for User Story 3

- [X] T026 [US3] In `byo/ops/static/js/main.js`, implement the visibility predicate in `paintLive()` and a `syncChatNotice()` that hides/shows the card and updates `#chat-notice` only when the running/ended-in-another-chat condition changes (C3.2–C3.3).
- [X] T027 [US3] In `byo/ops/static/js/main.js`, remove `state.live = null` from the `#chat-sessions` and `#new-chat` handlers; call `paintLive()`/`renderChat()` instead so a past chat shows only its own history and a new chat never paints the old card (C1.2–C1.3, C3.3).
- [X] T028 [US3] In `byo/ops/static/js/main.js`, add the second-send guard at the top of `send()` before the `state.viewing` reset and `newLive`, and clear any pending `state.handoffTurnId` when a failed/completed turn is replaced; never replace a `live` turn (C4.1–C4.3; FR-016).
- [X] T029 [P] [US3] Add `#chat-notice` after `.sesshead` in `byo/ops/static/index.html` with `role="status"` and `aria-live="polite"`, and token-based `.chat-notice`/`.chat-notice:empty` rules in `byo/ops/static/style.css` (C3.3).
- [X] T030 [P] [US3] In `byo/app.py`, bind `session = self.session` at the top of `Agent.respond` and use that object for `trajectory.start(..., session_id=session.session_id)`, `note_user`, `build_system`, `history`, `note_assistant`, `recalled` and `_log`; `_log` takes the bound session id, so a new chat created mid-turn starts empty and the turn stays in its own chat (C8.1–C8.4).
- [X] T031 [US3] Run the `us3` contracts, the server session-swap test and `make eval` (`Makefile`); confirm no regression in the seven-script shell or the existing session tests (SC-007).

**Checkpoint**: all three stories work; the live turn is session-scoped and guarded.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: verification, browser evidence, backward compatibility and the final diff review.

- [X] T032 [P] Extend `evals/deterministic/test_dashboard.py` with `test_a_disconnected_stream_still_records_the_turn`: after the socket closes and the trajectory reaches `turn_end`, the `default` session's `chat_log` contains the user and assistant rows (FR-012, SC-005).
- [X] T033 [P] Add the backward-compatibility case to `evals/deterministic/test_chat_lifecycle.py`: an assistant row with no `state`/`partial` meta renders as `complete` with no partial block (C9.4; data-model section 5).
- [X] T034 [P] Confirm the shell still loads exactly seven scripts and makes no external request by running `evals/deterministic/test_map_static.py` and reviewing `byo/ops/static/index.html` (FR-015, SC-007).
- [X] T035 Run `make eval`, `make gate` and `make lint` from `Makefile` after T032–T034; confirm 349 baseline tests plus every new case pass and no dependency, endpoint, table or build step was added.
- [X] T036 [P] Execute quickstart sections 2–7 in `specs/009-chat-stream-persistence/quickstart.md` at 1280/900/375 px with a real key or the scripted slow adapter (tool-lane frames are pinned by the static and HTTP contracts); record the pass/fail table in the implementation notes and stop on any failed scenario (SC-001–SC-005, SC-008).
- [X] T037 [P] Review the diff against the Constitution in `specs/009-chat-stream-persistence/plan.md`: confirm `byo/loop/*`, `byo/memory/*`, `byo/tools/*`, `byo/config.py`, `byo/db.py` and `byo/runtime/session.py` are untouched, and no credential/redaction path changed (Constitution I–V).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies; T001–T004 are independent files/commands.
- **Foundational (Phase 2)**: T005 depends on T001; T006 depends on T002; T007 depends on T006; T008 depends on T005–T007. Blocks all stories.
- **User Stories (Phase 3–5)**: each depends on Phase 2. US2 integrates with US1; US3 integrates with US1/US2 because all three edit `main.js`.
- **Polish (Phase 6)**: depends on every delivered story; T035 depends on T032–T034.

### User Story Dependencies

- **US1 (P1)**: starts after T008; no dependency on US2/US3.
- **US2 (P2)**: starts after T008; the handoff assumes the US1 live turn, so implement after T010–T012 for one developer, or coordinate the `main.js` owner.
- **US3 (P3)**: starts after T008; the visibility and new-chat work assume T010–T012, and the guard assumes T019. Server work T030 can run in parallel with client tasks T026–T028 once its test T024 exists.
- **Recommended delivery**: US1 → US2 → US3. All client work touches one file; one owner avoids conflicts.

### Within Each Story

- Tests T009/T014–T016/T022–T025 come first and must fail for the expected reason.
- In US2, T017 (app.py) and T018 (dashboard.py) are parallel; T019/T020 edit `main.js`/render/style and follow.
- In US3, T026–T028 edit `main.js` sequentially; T029 (HTML/CSS) and T030 (app.py) are parallel with them.

### Parallel Opportunities

- **Setup**: T001, T002, T003, T004 all run in parallel (different files/commands).
- **Foundational**: T005 (test file) and T006 (main.js) run in parallel after T001/T002; T007 follows T006.
- **US2 server**: T017 (`app.py`) and T018 (`dashboard.py`) run in parallel.
- **US3 side surfaces**: T029 (`index.html`/`style.css`) and T030 (`app.py`) run in parallel with the `main.js` tasks T026–T028.
- **Polish**: T032–T034 are independent once the stories are complete; T035 depends on them; T036–T037 are independent.
- Tests for a story all live in `test_chat_lifecycle.py`, so they are sequential within that file.

---

## Parallel Example: Server and side surfaces (US2/US3)

~~~bash
# US2: two different server files, same contract
Task: T017 "Write meta.state/meta.partial in byo/app.py"
Task: T018 "done.failed + history state/partial in byo/ops/dashboard.py"

# US3: markup/styles and the turn owner can land beside the client work
Task: T029 "#chat-notice markup + .chat-notice CSS"
Task: T030 "Bind the turn to its Session in byo/app.py"
~~~

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup T001–T004.
2. Complete Foundational T005–T008.
3. Complete US1 T009–T013.
4. **STOP and VALIDATE**: run the `us1` contracts and quickstart section 2.
5. Deliver the P1 fix (navigation no longer loses the stream).

### Incremental Delivery

1. Foundation ready (T001–T008).
2. US1 → validate → demo (MVP).
3. US2 → validate the atomic handoff and failure/limit transcript → demo.
4. US3 → validate session ownership, new chat and the guard → demo.
5. Polish T032–T037 → full suite, browser record, diff review.

### Parallel Team Strategy

- **Server owner**: T017/T018 (US2) and T030 (US3) after their tests exist.
- **Client owner**: T010–T012 and T019/T020 and T026–T028; these share `main.js` and must be serialized.
- **Test owner**: T005/T009/T014–T016/T022–T025 plus T032–T033; coordinate with the client owner so tests land before implementation.
- **Docs/validation**: T036/T037 after the code is stable.

---

## Notes

- `[P]` means a different file and no dependency on an incomplete task.
- `[US1]/[US2]/[US3]` map every story-phase task to the spec's priorities.
- Tests are required by FR-014/SC-006; run `make eval` after each story.
- Do not add a JavaScript runner, dependency, endpoint, table or build step.
- Commit after each story checkpoint; keep `main.js` edits single-owner.