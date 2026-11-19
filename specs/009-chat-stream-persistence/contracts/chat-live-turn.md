# Contract — Live Chat Turn and Turn/Session Binding

**Feature**: Chat Stream Persistence Across Navigation | **Date**: 2026-11-19

This contract is the seam between the chat dock, the stream frames, the transcript and the server.
It is internal (no public API), but each clause is stated as a MUST so code and tests can point at
it. Test obligations are in section 10; the shapes are in [../data-model.md](../data-model.md).

## 1. Scope

In scope: one in-flight dashboard turn, the existing SSE stream, the existing history endpoint, and
the turn's session binding inside `Agent.respond`. Out of scope: stream replay after reload,
multi-tab, concurrent turns, queues, and any new endpoint, table or dependency.

## 2. Retention (C1)

- **C1.1** Selecting any sidebar destination, following a map-node link, or using browser
  back/forward MUST NOT clear, pause, truncate, restart or replace the live turn.
- **C1.2** Selecting a chat from the history picker MUST NOT clear or cancel the live turn.
- **C1.3** Starting a new chat MUST NOT clear, cancel or repaint the old live turn inside the new
  chat.
- **C1.4** Collapsing/reopening the dock, resizing it, changing the theme, expanding a history trace
  or opening a turn detail MUST NOT clear or mutate the live turn.
- **C1.5** The live turn is in-memory page state; a full reload discards it (out of scope), but the
  server turn continues and the completed turn appears in history on the next load.

## 3. Frame application (C2)

- **C2.1** While a live turn exists, every stream frame MUST be applied to it regardless of the
  destination currently displayed or the chat currently selected.
- **C2.2** A `text` delta appends to the open `streaming` item; order is delivery order.
- **C2.3** No delta may be dropped, duplicated or reordered by navigation, session selection, new
  chat, or re-render.
- **C2.4** The frame grammar itself is unchanged: `gate_start`, `gate`, `llm_start`, `text`, `llm`,
  `tool_start`, `tool`, `consolidation`, `receipt`, `error`, `done`. New fields are additive only.

## 4. Ownership and visibility (C3)

- **C3.1** `newLive(message, sessionId)` binds the turn to exactly one session id; the id never
  changes.
- **C3.2** The live card is rendered only when
  `live.session_id === (state.viewing || state.session)`.
- **C3.3** While the live turn belongs to another chat, the dock MUST show a
  `role="status"` line saying whether a turn is running or has ended in another chat; the card MUST
  NOT be shown there, and the line MUST change only when that condition changes.
- **C3.4** Returning to the sending chat MUST show the accumulated turn immediately (no reload, no
  wait for the turn to finish).

## 5. Send admission (C4)

- **C4.1** `send()` MUST refuse to begin while `state.live.state === "live"`.
- **C4.2** A refused send MUST NOT replace, clear or mutate the live turn.
- **C4.3** A failed or completed turn MAY be replaced by the next send; the fresh turn starts with a
  new `session_id` and `has_done = false`, and any pending handoff for the replaced turn is cleared.
- **C4.4** The server's single-turn lock remains the final authority; the client guard exists to
  protect the visible turn, not to replace server enforcement.

## 6. Completion handoff (C6)

- **C6.1** A `done` frame sets `has_done = true`, `turn_id`, `reply`, `receipt` and the ending state:
  `failed` (from `done.failed`), `limited` (from `done.limit_reached`), otherwise `complete`.
- **C6.2** Only a turn with `has_done = true` is handed off.
- **C6.3** The handoff sequence is: history fetch succeeds → transcript HTML is assigned →
  `clearLive(turn_id)` → `paintLive()`, all in the same continuation.
- **C6.4** While the history fetch is in flight, the live card MUST remain visible; the reply MUST
  never be visible twice and MUST never be absent.
- **C6.5** `clearLive(turnId)` MUST be a no-op unless the current turn's `turn_id` equals `turnId`.
- **C6.6** A failed history fetch MUST leave the live card in place and keep the handoff pending for
  a later successful render.

## 7. Failure and limit (C7)

- **C7.1** A model error that produced partial deltas MUST persist that partial text in
  `chat_log.meta.partial` (≤4000 characters), set `meta.state = "failed"`, and expose both on the
  assistant history row.
- **C7.2** The transcript MUST render the partial text and a `failed` state cue; the live card is
  then handed off normally (one transcript entry, no stranded card).
- **C7.3** A stream that ends without a `done` frame MUST leave the live turn in `failed` state with
  its accumulated items; the next send replaces it; it is never handed off.
- **C7.4** A turn at the step limit MUST set `state = "limited"` on the live card and
  `meta.state = "limited"` in the transcript; the loop's limit reply remains the body.
- **C7.5** An unexpected server exception after the response headers MUST send one `error` frame
  (stage `turn`) and close; it MUST NOT send a fabricated `done`.

## 8. Server turn/session binding (C8)

- **C8.1** `Agent.respond` MUST bind `session = self.session` before any other work and use that
  object for system assembly, history, recall, `note_user`, `note_assistant` and `_log`.
- **C8.2** `_log` MUST write the user and assistant rows with the bound session id.
- **C8.3** If `new_session()` runs during the turn, the new session MUST start with empty history
  and MUST NOT receive the running turn's rows.
- **C8.4** The trajectory `turn_start.session_id` and the `chat_log` rows MUST agree.

## 9. Transcript state (C9)

- **C9.1** Assistant history rows MUST expose `state` (default `complete` for old rows) and `partial`
  (default empty).
- **C9.2** The assistant bubble MUST show a `failed` or `limited` cue when the state is not
  `complete`.
- **C9.3** A non-empty `partial` MUST render as plain, escaped, pre-wrapped text above the final
  reply; it MUST NOT be interpreted as raw HTML.
- **C9.4** Old rows lacking the fields MUST render exactly as they do today.

## 10. Test obligations

| Clause | Evidence |
|---|---|
| C1.1–C1.5 | Static contracts in `evals/deterministic/test_chat_lifecycle.py`; browser quickstart |
| C2.1–C2.4 | Static contracts; existing stream grammar tests in `test_dashboard.py` |
| C3.1–C3.4 | Static contracts; browser quickstart (session/new chat) |
| C4.1–C4.4 | Static contracts; existing 409 test plus guard source |
| C6.1–C6.6 | Static contracts + browser quickstart |
| C7.1–C7.5 | Failing-stream HTTP test, history payload test, static render contract |
| C8.1–C8.4 | Server session-swap unit test; trajectory/history assertions |
| C9.1–C9.4 | History payload test; static render contract |
| Regression | Full `make eval` (349 baseline + new cases) and `make lint` |

## 11. Explicit non-goals

- No server-side live buffer, replay, or late-join endpoint.
- No persistence of the live card across reloads or tabs.
- No concurrent turns or queued messages.
- No change to stream event names, model adapters, prompts, tools or memory policy.
- No new dependency, build step, table or column.
