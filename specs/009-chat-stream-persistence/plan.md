# Implementation Plan: Chat Stream Persistence Across Navigation

**Branch**: `009-chat-stream-persistence` | **Date**: 2026-11-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/009-chat-stream-persistence/spec.md`

## Summary

Fix the reported loss of a streaming chat answer when the person switches sidebar destinations.
The cause is a lifetime bug: the navigation handler nulls the live turn, the stream callback then
drops every later frame, and chat history cannot fill the gap because a turn is logged only when it
finishes. The fix keeps one **session-scoped** live turn across in-page navigation, refuses a second
send without replacing it, and hands the completed turn to the transcript in one atomic swap.

Two adjacent defects share the same surface and are fixed with it: selecting a past chat currently
destroys the live turn, starting a new chat paints the old card over the new chat, and a running
turn does not own its session on the server (a new chat created mid-turn steals the turn's
`chat_log` rows). Failure endings are made honest too: partial text streamed before a model error is
stored in `chat_log.meta.partial`, exposed on the history row, rendered with a `failed` cue, and the
live card is still handed off cleanly. A stream that ends without a `done` keeps its failed live card
until the next send.

No new endpoint, table, dependency or build step; no change to prompts, tools, the loop, context or
memory policy. The change lives in `main.js`, `render.js`, `index.html`, `style.css`, `app.py` and
`dashboard.py`, and is pinned by offline source contracts plus HTTP tests; the browser behaviour is
the `quickstart.md` scenario.

## Technical Context

**Language/Version**: Python >= 3.11 (repository floor; the checkout runs 3.14) for the server and
tests; plain ES2017 in classic `<script>` files for the dashboard. No TypeScript, no bundler.

**Primary Dependencies**: none added. The four runtime dependencies (`anthropic`, `openai`,
`python-dotenv`, `rich`) and the `pytest`/`ruff` dev extras are unchanged. The client keeps using
`fetch`, `setTimeout` and the DOM.

**Storage**: no schema change and no migration. The existing SQLite `chat_log` gains two optional
keys in its `meta` JSON (`state`, `partial`), and the existing JSONL trajectory is untouched. The
partial is bounded to 4000 characters.

**Testing**: `pytest` under `evals/deterministic/`. Baseline: 349 tests passing, `make eval` and
`make lint` green. New: `test_chat_lifecycle.py` (server session-swap test, failing-stream partial
test, static client lifetime/ownership/handoff contracts), plus extensions to
`test_dashboard.py` (a disconnected stream still lands in history). No JavaScript runner is added
(repository precedent, 006 D-4); the browser is validated by `quickstart.md`.

**Target Platform**: macOS 13+ and Linux, one local user, loopback `127.0.0.1` only. Browser:
current Chrome, Safari, Firefox and Edge; desktop and the existing responsive layout.

**Project Type**: single project — an installable Python package with a locally served, plain static
web UI. The change touches one existing server turn owner (`app.py`), one dashboard route module
(`dashboard.py`), three dashboard static assets and one stylesheet; no frontend project.

**Performance Goals**: navigation adds no new request beyond the existing history fetch;
keystroke-to-echo and stream paint stay as they are; the live turn is O(items) in memory; one turn
at a time; the partial field adds at most 4 KB to a failed row.

**Constraints**: no new runtime dependency, endpoint, table or build step; one live turn, no queue;
the default test path runs offline with no credentials; redaction stays at the trace sink; the
stream event grammar is unchanged (additive fields only); the server still finishes a turn when the
client disconnects; one-turn concurrency remains the server's lock.

**Scale/Scope**: five destinations (Overview, Tools, Memory, Observability, Settings), one live turn,
up to 500 history messages per chat, seven static scripts. No new view or script.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Evidence |
|---|---|---|
| I. Build From Primitives | PASS | The lifetime rules, handoff, session binding and partial capture are source in this repository. No framework, state library, router or UI kit is added. The chat block carries the design note (mechanism + rejected alternatives); `research.md` records the alternatives. |
| II. Provider-Agnostic Model Boundary | PASS | No adapter, prompt or provider branch changes. `app.py` only accumulates `text` deltas the loop already emits; the model boundary is untouched. The offline tests use the existing scripted adapters. |
| III. Small Modules With Narrow Contracts | PASS | The live turn stays in the chat owner (`main.js`), with one documented contract (`contracts/chat-live-turn.md`) and one writer (`clearLive`). A separate 30-line store was rejected as speculative: it would add a script and four static-contract shifts without new behaviour. The server turn binding stays in `Agent.respond`, the turn owner; `_log` takes the bound id as one narrow parameter. |
| IV. Observable by Default | PASS, strengthened | The trajectory is unchanged; the transcript remains a projection of `chat_log`. The new `meta.state`/`meta.partial` make a failed turn visible in the record instead of only in an ephemeral card. No second store, no parallel status model, redaction at the sink untouched. |
| V. Eval-Driven Behavior Change (NON-NEGOTIABLE) | PASS | No prompt, tool description, loop logic, context strategy or memory policy changes, so no eval baseline can move. `respond` bookkeeping changes are covered by deterministic tests: session binding, partial capture, disconnect history and the full suite must stay green. The regression net grows with the fixed bug, as the constitution requires. |
| Additional constraints | PASS | Dependency count unchanged; no build step; offline suite; loopback only; no credential reaches a new field; one-turn lock preserved; no new destination, and the transcript's state cues reuse the existing chip styles. |

**Post-design re-check**: PASS. Phase 1 adds no dependency, schema change, second writer or
model-facing behaviour. No Complexity Tracking entries are needed.

## Project Structure

### Documentation (this feature)

~~~text
specs/009-chat-stream-persistence/
├── plan.md                       # this file
├── research.md                   # Phase 0: root causes, decisions, rejected alternatives
├── data-model.md                 # Phase 1: live turn, transitions, meta/payload fields
├── quickstart.md                 # Phase 1: offline + browser validation scenarios
├── contracts/
│   └── chat-live-turn.md         # client lifetime + handoff + server session binding
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md                      # Phase 2 output (/speckit-tasks), not created here
~~~

### Source Code (repository root)

~~~text
byo/
├── app.py                        # [modified] bind the turn's Session; accumulate partial;
│                                 #            write state/partial into chat_log.meta
├── ops/
│   ├── dashboard.py              # [modified] done.failed; history exposes state/partial;
│   │                             #            one error frame for an unexpected stream exception
│   └── static/
│       ├── index.html            # [modified] role="status" chat notice line
│       ├── style.css             # [modified] .chat-notice, .bubble-partial, state cue spacing
│       └── js/
│           ├── main.js           # [modified] session-scoped live lifetime, clearLive, guard,
│           │                     #            visibility, atomic handoff, failure handling,
│           │                     #            partial/state rendering in the bubble
│           └── render.js         # [modified] live card cue for "limited" (natural size change)
evals/
├── scripted.py                   # unchanged (reused by the new tests)
└── deterministic/
    ├── test_chat_lifecycle.py    # [new] server session swap + failing stream + static contracts
    └── test_dashboard.py         # [modified] disconnected stream leaves the turn in history
~~~

Unchanged: `byo/loop/*`, `byo/memory/*`, `byo/tools/*`, `byo/config.py`, `byo/db.py`,
`byo/runtime/session.py`, `byo/ops/map.py`, `byo/ops/live.js`, `byo/ops/api.js`,
`byo/ops/dock.js`, `byo/ops/observe.js`, `byo/ops/tools.js`.

**Structure Decision**: keep the existing single-project layout and the existing seams. The live
turn is not a new subsystem: it is chat state that already belongs to `main.js`, and the defect is a
missing lifetime rule. The server already owns the turn in `Agent.respond`; binding the session
there is a local correction, not a new layer. The only new file is the feature's regression test.

## Complexity Tracking

No constitution violations; nothing to justify.

## Phase 0: Outline & Research

Complete — see [research.md](research.md). Every Technical Context field is resolved; no
`NEEDS CLARIFICATION` remains. The decisions that shape the structure:

1. **D-1** Keep the live turn in `main.js`; no new JS module, server store or `sessionStorage`.
2. **D-2** Bind it to its sending session; visibility is
   `session_id === (state.viewing || state.session)`.
3. **D-3** Navigation, chat selection and new chat never clear it; one `clearLive` writer.
4. **D-4** Refuse a second send; never replace a live turn.
5. **D-5** Hand off only after `done`, and only after the transcript is assigned in the same
   continuation.
6. **D-6** Persist partial text for failed turns in `chat_log.meta`, render it, and hand off; a
   no-`done` stream keeps its failed live card.
7. **D-7** Bind the server turn to the `Session` it started in, so a new chat cannot steal it.
8. **D-8** Allow a new chat mid-turn; hide the old card and explain it in a status line.
9. **D-9** Test in the repository's idiom: Python source contracts + HTTP; no JS runner.
10. **D-10** Additive meta/payload fields only; old rows default safely.

## Phase 1: Design & Contracts

Complete.

- [data-model.md](data-model.md) defines the `LiveTurn`, `LiveItem`, transitions, `ViewState`
  visibility predicate, `TranscriptMessage`, `TurnMeta`, the `done` payload and the handoff sequence.
- [contracts/chat-live-turn.md](contracts/chat-live-turn.md) states the MUSTs for retention, frame
  application, ownership, send admission, handoff, failure/limit, server binding, transcript state
  and the test obligations.
- [quickstart.md](quickstart.md) gives the offline gate and the browser scenarios for mid-stream
  navigation, completion away, chat/new-chat, shell actions, failure/limit, reload and regression.

Key design points:

- `newLive(message, sessionId)` records the owner; `paintLive` renders only for the viewed chat.
- `clearLive(turnId)` is the only null writer; it checks `turn_id` so an old handoff cannot clear a
  newer turn.
- `state.handoffTurnId` bridges `done` and `renderChat`; the transcript and the cleared card land in
  one task.
- `done.failed` and `limit_reached` choose the ending state; `chat_log.meta.partial` carries the
  text already streamed before a model error.
- `Agent.respond` binds `session = self.session` at entry; `_log` writes with that id.
- `#chat-notice` is a `role="status"` line, empty unless the live turn belongs to another chat.

## Implementation sequence

1. **Server turn binding and failure fidelity** (red then green):
   - `Agent.respond`: local `session`; use it for `note_user`, `build_system`, `history`,
     `note_assistant`, `recalled` and `_log`.
   - Accumulate `text` deltas; `_log` writes `meta.state` and `meta.partial` (failed only, 4000
     chars).
   - `dashboard.py`: `done.failed`; `history()` exposes `state`/`partial`; `_stream` catches an
     unexpected exception and sends one `error` frame.
   - Tests: session swap mid-turn; failing stream with partial text; history payload; disconnect
     leaves the turn in history.

2. **Client live-turn lifetime**:
   - `newLive(message, sessionId)`; `clearLive(turnId)`; remove the clears from `hashchange`,
     `#chat-sessions` and `#new-chat`; add the second-send guard; a new send clears any pending
     handoff.
   - `paintLive` applies the visibility predicate; `renderChat` calls it before and after the fetch.
   - Tests: static contracts for each removed clear and the guard.

3. **Atomic handoff and endings**:
   - `done` sets `has_done`, `turn_id`, ending state; `state.handoffTurnId` is set only when
     `has_done`.
   - `renderChat` assigns history, then `clearLive` + `paintLive` in the same continuation; a failed
     fetch leaves the card.
   - A no-`done` stream marks the live card failed and does not hand off.
   - Tests: static ordering contract; browser completion-during-switch.

4. **Transcript and notice rendering**:
   - Bubble: `state` cue (`failed`/`limited`) and a `partial` block (escaped, pre-wrapped).
   - Live card: a `limited` cue beside the existing `failed` cue.
   - `#chat-notice` + `.chat-notice`; `paintLive` keeps it in sync.
   - Tests: static source + CSS + ARIA; old-row defaults.

5. **Verification**:
   - `make eval` (349 baseline + new), `make gate`, `make lint`.
   - Run `quickstart.md` sections 2–7 with a real key; record the pass/fail table.
   - Confirm no new request, table, dependency or build step.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Static source contracts are structural, not behavioural | Pair them with HTTP session/partial tests and the browser quickstart; keep assertions aimed at the specific defects, not general code shape |
| Handoff still shows a duplicate in an unusual timing | Single-continuation swap (history assignment then clear); quickstart repeats completion-during-switch; source contract pins the order |
| A new chat mid-turn still steals the turn | Unit test swaps the session inside the adapter; assert both `chat_log` rows and the new session's empty history |
| `meta.partial` breaks old rows or grows without bound | Default `complete`/empty in the client; 4000-character bound; additive JSON only; no schema change |
| A failed stream loses its card after reload | Explicitly out of scope for live resume; the server error text remains in history for model errors; trajectory records the exception |
| Notice line changes the dock layout | One line, token-based CSS, `:empty` hides it; quickstart at 1280/900/375 |
| No JS runner means no automated browser proof | Repository precedent; the quickstart is the behavioural gate, and the static contracts make the lifetime rules reviewable |

## Success-criteria evidence

| Spec | Evidence |
|---|---|
| SC-001 (no loss/dup across switches) | Static retention/frame contracts + quickstart section 2 |
| SC-002 (immediate on return) | `paintLive` visibility contract + quickstart section 2 |
| SC-003 (one transcript entry) | Handoff contract + quickstart sections 3–4 |
| SC-004 (failure/limit preserved) | Failing-stream HTTP test + transcript state test + quickstart section 6 |
| SC-005 (zero cancelled turns) | Existing disconnect test extended to history + trajectory |
| SC-006 (offline suite) | `make eval` with the new cases |
| SC-007 (no regression) | Full 349-test baseline plus quickstart section 8 |
| SC-008 (atomic completion timing) | Handoff source contract + quickstart section 3 |
