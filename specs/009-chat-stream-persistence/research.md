# Phase 0 Research — Chat Stream Persistence Across Navigation

**Feature**: Chat Stream Persistence Across Navigation | **Date**: 2026-11-19 | **Spec**: [spec.md](spec.md)

## Executive summary

The reported loss is a **lifetime bug**, not a transport bug. The stream keeps arriving after a
sidebar click, but the page throws the live turn away and then ignores every frame because the
render-owned object that receives them is gone. Chat history cannot fill the gap because a turn
is written to `chat_log` only when it finishes. Two adjacent defects share the same root: selecting
another chat clears the turn, and starting a new chat paints the old live card over the new chat.

Reading the server while planning surfaced a second, independent defect: a running turn does **not**
own the session it started in. `Agent.respond` reads `self.session` throughout, and `new_session()`
replaces it, so a new chat created mid-turn makes `_log` and `note_assistant` write the running
turn into the new chat. Fixing only the browser would leave that attribution bug.

The plan therefore has three parts: (1) keep one session-scoped live turn across in-page
navigation; (2) hand it off atomically to the transcript, with failure and limit endings preserved;
(3) bind a turn to the session it started in on the server. No endpoint, table, dependency or build
step is added.

## Root causes

### RC-1 — Navigation is treated as "leave the turn"

`main.js`'s `hashchange` listener sets `state.live = null` and calls `paintLive()`, which empties
`#chat-live`. The stream callback then begins with `if (!state.live) return`, so every subsequent
`gate`, `text`, `llm` and `tool` frame is discarded. Chat history is not a fallback: `chat_log` is
written in `Agent._log` only after `run_loop` returns, so an in-flight turn has no row to reload.

### RC-2 — Selecting a chat is treated the same way

The `#chat-sessions` change handler also sets `state.live = null`. Choosing a past chat destroys the
sending chat's live turn even though the page never left the dashboard.

### RC-3 — Starting a new chat leaves the old card floating

`#new-chat` swaps `state.session` and calls `refresh()`; it never clears or repaints `#chat-live`.
The previous turn's card therefore remains visible over a chat it does not belong to, while the
turn itself is not associated with any session on the client.

### RC-4 — Completion handoff is neither atomic nor session-aware

After the stream, `send()` runs `refresh()`, then `renderChat()`, then unconditionally sets
`state.live = null`. Three problems:

- the transcript may paint while the live card is still visible, briefly duplicating the reply;
- clearing is unconditional, so a stream that ended in an error (no `done`) loses its partial card;
- clearing is not tied to the turn or the viewed session, so a new send can be cleared by an old
  handoff.

### RC-5 — A running turn does not own its session on the server

`Agent.respond` uses `self.session` for `note_user`, `build_system`, `history`, `note_assistant`,
`recalled`, and `_log`. `Agent.new_session()` replaces `self.session`. If it runs mid-turn, the
completed turn is logged into the **new** chat and the new chat's in-memory history receives the old
assistant reply. The old chat gets no `chat_log` rows at all.

### RC-6 — Failure loses the partial stream

`run_loop` catches `ModelError`, sets `result.reply` to the error text and returns; text deltas that
already streamed are not accumulated. `_log` therefore cannot preserve them, and `_stream` sends
`done` with no failure flag. Separately, `_stream` catches only `BrokenPipeError`; an unexpected
exception after the headers closes the response with no `error` frame, so the client cannot tell a
failed turn from a truncated one.

### RC-7 — The test suite cannot see this class of bug

There is no JavaScript runner (a deliberate repository decision). The static tests assert symbols,
not lifetimes; dashboard tests never navigate; no test creates a new chat mid-turn; and no test
checks a partial stream after a model error.

## Decisions

### D-1 — Keep the live turn in the chat state that already owns it

**Decision**: The single live turn stays in `main.js` as `state.live`; no new JavaScript module or
server store is introduced. The lifetime rules are written down in
[contracts/chat-live-turn.md](contracts/chat-live-turn.md) and enforced by one `clearLive()` helper.

**Rationale**: The defect is a missing lifetime rule, not a missing boundary. `main.js` already owns
the chat (send, frame handling, card painting). A 30-line module would add a script tag, shift four
existing static contracts, and buy no new behaviour. The constitution asks for abstraction that
pays for itself now; this does not.

**Alternatives considered**: a new `chatlive.js` store (rejected: speculative split); a server-side
live-turn store (rejected: replay is out of scope and adds a second source of truth); persisting the
live turn in `sessionStorage` (rejected: stale recovery after reload is explicitly out of scope).

### D-2 — Bind the live turn to the session that sent it

**Decision**: `newLive(message, sessionId)` records `session_id` once. `paintLive()` renders the card
only when `state.live.session_id === (state.viewing || state.session)`; the same predicate drives the
dock notice. The bound id never changes.

**Rationale**: A turn is a fact about one chat. Visual ownership follows that fact, not whichever
chat happens to be selected.

**Alternatives considered**: clear on session switch (the bug); show the card in every chat (FR-006
forbids it); move the live turn into a per-session map (needed only if concurrent turns become
possible — out of scope).

### D-3 — Navigation and session selection never clear the turn

**Decision**: Remove `state.live = null` from `hashchange`, `#chat-sessions` change and `#new-chat`.
Only `clearLive(turnId)` may null the turn, and only after a completed turn's transcript has painted;
a new send replaces a failed/complete turn by assignment.

**Rationale**: These handlers change what is displayed, not what is running. A single writer makes
the lifetime auditable and testable.

**Alternatives considered**: a guard flag per view (duplicated state); clearing only when returning to
Overview (still loses the visible turn while away).

### D-4 — Refuse a second send; never replace a live turn

**Decision**: `send()` returns immediately when `state.live` is in the `live` state. A failed or
completed turn may be replaced by the next send. The server's existing single-turn lock remains the
authority.

**Rationale**: The current code creates a fresh `state.live` unconditionally, so a second submit
overwrites the in-flight turn before the server refuses it. That is the same loss with a different
trigger. Refusing client-side keeps the first turn visible and avoids a spurious error card.

**Alternatives considered**: queue the second message (out of scope); disable the composer (hides the
ability to type); let the server 409 and render it (would still overwrite the live card).

### D-5 — Hand off to the transcript atomically, after it is painted

**Decision**: On `done`, mark `state.live.has_done = true`, store `turn_id`, `reply`, `receipt` and
the ending state, and set `state.handoffTurnId = turn_id`. `renderChat()` fetches history, assigns
`#chat-history`'s HTML, then — in the same continuation — calls `clearLive(handoffTurnId)` and
`paintLive()`. The live card stays visible during the fetch; the transcript replaces it in one
paint. Only `done` sets the handoff.

**Rationale**: This is the only ordering that avoids both a blank gap and a duplicate: the
completed card covers the network gap, and the swap happens in one task before the browser paints.

**Alternatives considered**: clear immediately on `done` (blank gap); clear after `refresh()` with no
handoff binding (the current duplicate/race); keep both (FR-008/013 violation).

### D-6 — Failure and limit endings are preserved, not discarded

**Decision**: For a model error, `respond` accumulates the text deltas that were already emitted and
writes them to `chat_log.meta.partial` (bounded to 4000 characters) together with
`meta.state = failed`; `done` carries `failed: true`. The transcript renders the partial output and a
`failed` chip, then the normal handoff clears the live card. A stream that ends with no `done`
(transport error or unexpected exception) keeps its live card in the `failed` state; the next send
replaces it. Limit endings use the reply the loop already produces and carry `limit_reached`.

**Rationale**: FR-008 wants one transcript entry; FR-010 wants partial output. Moving the partial into
the transcript satisfies both and avoids a stranded live card. The no-`done` case has no transcript
to move into, so the card is the only honest record.

**Alternatives considered**: keep the failed live card beside the transcript (duplicate error record);
drop the partial (FR-010 violation); add a second error table (overkill).

### D-7 — A turn binds its session at the start on the server

**Decision**: `Agent.respond` captures `session = self.session` on entry and uses that object for
history, system assembly, recall, `note_assistant`, and `_log`; `_log` receives the session id and
writes both `chat_log` rows with it.

**Rationale**: A new chat may legitimately be created while a turn runs. The running turn belongs to
the chat that sent it; the new chat must start clean. This is a small local-variable fix with a
direct unit test.

**Alternatives considered**: refuse `new_session` while `dash.lock` is held (the spec's P3 expects a
new chat to work, and the terminal path can also create sessions); route session id through every
loop call (wider seam than needed).

### D-8 — Allow a new chat mid-turn, hide the old card, and say so

**Decision**: `#new-chat` keeps the live turn, switches to the new session, repaints the dock (which
hides the old card) and shows a small `role="status"` line: "A turn is still running in another
chat." The same line appears whenever the live turn is not the viewed chat. Selecting the sending
chat restores the card.

**Rationale**: The user can start a new chat, but cannot send in it until the running turn ends
(one-turn rule). Hiding without explaining would make the composer look broken.

**Alternatives considered**: disable `+ New chat` while live (simpler but contradicts P3 and hides
the reason); show the old card inside the new chat (FR-006 violation).

### D-9 — Test in the repository's established idiom; do not add a JS runner

**Decision**: Add `evals/deterministic/test_chat_lifecycle.py` with (a) a server test that swaps the
session mid-turn, (b) a failing-stream test that proves partial output reaches history, and (c)
static source contracts for the client lifetime, ownership, guard, handoff and notice. Extend
`test_dashboard.py` so a disconnected stream still lands in history. The browser behaviour is a
`quickstart.md` scenario.

**Rationale**: This follows the 006 decision: Python source assertions plus stdlib HTTP round-trips,
no second toolchain in the default test path. The static contracts are aimed at the exact defects
(the null on navigation, the unconditional clear, the missing guard), not at general rendering.

**Alternatives considered**: Node/Playwright (rejected: new toolchain and dependency for a local
static page); jsdom (same); executing the reducers in a Python JS engine (new compiled dependency).

### D-10 — Additive payload and meta fields, no schema change

**Decision**: `chat_log.meta` gains `state` and `partial`; `GET /api/session?action=history` exposes
them on assistant rows; `done` gains `failed`. Old rows default to `complete` and empty partial.
No SQL migration, no new table, no new endpoint.

**Rationale**: `meta` is already the turn-card metadata channel; the partial is a chat artifact, not
a trace event. Bounding it keeps rows small.

**Alternatives considered**: new columns (migration); storing deltas in the JSONL trajectory (volume
and a second replay surface); a new endpoint (unnecessary).

## Rejected alternatives (summary)

| Alternative | Why rejected |
|---|---|
| Server-side live stream buffer/replay | Out of scope; adds a second source of truth and a new endpoint/poll |
| Persist the live card in `sessionStorage` | Reload recovery is out of scope; stale cards after a crash |
| New `chatlive.js` store module | 30 lines, four static-contract shifts, no new behavior |
| Node/Playwright in the default suite | Repository precedent (006); dependency and toolchain cost |
| Block `new chat` while a turn runs | P3 expects it to work; the server fix is small and correct |
| Keep the failed card beside the transcript | Duplicate error record; FR-008/013 |
| Clear the live card on `done` | Blank gap before history arrives |
| Record every text delta in the trajectory | Volume; the transcript's partial is sufficient and bounded |

## Open questions

None. Every Technical Context field is resolved; no `NEEDS CLARIFICATION` remains.
