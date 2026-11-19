# Phase 1 Data Model — Chat Stream Persistence Across Navigation

**Feature**: Chat Stream Persistence Across Navigation | **Date**: 2026-11-19

This feature adds no table and no migration. It defines the **in-page live turn** the dashboard
holds, the existing **transcript row** it hands off to, and two additive metadata fields on
`chat_log.meta`. Types below are conceptual; the browser implements them as plain objects.

## 1. LiveTurn

One in-flight turn, held in `main.js` as `state.live`. At most one exists.

| Field | Type | Rule |
|---|---|---|
| `session_id` | string | Required. Set once by `newLive(message, sessionId)`; never reassigned |
| `user_message` | string | The text the person sent |
| `source` | string | `"dashboard"`; shown in the card meta |
| `state` | enum | `live` → `complete` \| `limited` \| `failed` |
| `items` | LiveItem[] | Append-only within the turn; order is arrival order |
| `reply` | string | Final reply once known; may be empty while live |
| `receipt` | object \| null | The `receipt` frame |
| `turn_id` | string \| null | Set once from `done.turn_id` |
| `has_done` | boolean | True only after a `done` frame |
| `started_at` | string | ISO timestamp (client clock) for the card |

Validation:

- `session_id` MUST be non-empty and MUST equal the current chat at `begin`.
- `turn_id` MUST be null until `done`; once set it MUST NOT change.
- `state` MUST move only along the transitions in section 3.
- A turn with `has_done = false` MUST NOT be handed off.

## 2. LiveItem

One lane in the live card. `render.js` already renders this shape; the model is unchanged.

| Field | Type | Used by |
|---|---|---|
| `type` | `gate` \| `streaming` \| `thinking` \| `tool` \| `output` \| `error` | Lane class |
| `node` | string | `data-node` for the map light |
| `title` | string | Lane heading |
| `body` | string | Lane text (Markdown for output/streaming) |
| `pending` | string | "running…" / "deciding…" while open |
| `live` | boolean | Caret and `data-open` |
| `meta` | string | Rendered duration / count |
| `iteration` | number | Model round label |
| `tool` | string | Tool name |
| `call_id` | string | Tool call identity |

Invariants:

- Items are appended, never reordered; a `text` fragment appends to the open `streaming` item.
- A completed `tool`/`llm` closes the matching open item; `closeLive` closes anything still open.
- A failed turn MAY contain both an `output` item (the partial text) and an `error` item.

## 3. LiveTurn state transitions

~~~text
                 begin(message, session)
   idle ─────────────────────────────────▶ live
     ▲                                      │
     │                                      ├─ gate_start / gate / llm_start / text /
     │                                      │  llm / tool_start / tool / consolidation /
     │                                      │  receipt ───────────────▶ live (item appended)
     │                                      │
     │                                      ├─ done (failed=false, limit=false) ─▶ complete
     │                                      ├─ done (failed=false, limit=true)  ─▶ limited
     │                                      ├─ done (failed=true)               ─▶ failed
     │                                      └─ stream ends, no done             ─▶ failed
     │
     ├── clearLive(turn_id) after transcript paint (has_done) ◀── complete / limited / failed
     ├── next send replaces (no clear event)                  ◀── failed / complete
     └── page load                                            ◀── any (not persisted)
~~~

Rules:

- **Navigation** (destination change, back/forward, map-node route) is not a transition.
- **Session selection** and **new chat** are not transitions.
- Dock collapse/resize, theme, trace expansion, turn-detail opening are not transitions.
- `clearLive(turnId)` is a no-op unless `state.live.turn_id === turnId`; this prevents an old
  handoff from clearing a newer turn.
- A second `begin` while `state === live` is refused; the caller does not replace the turn.

## 4. ViewState

The existing `state` object in `main.js` supplies the visibility inputs.

| Field | Meaning |
|---|---|
| `session` | The current chat the composer sends to |
| `viewing` | A past chat selected from the history picker, or null |
| `handoffTurnId` | The completed turn waiting for its transcript paint, or null |
| `chatGen` | Generation guard for concurrent history loads (existing) |

**Visibility predicate**:

~~~text
visible(live) = live !== null
             && live.session_id === (state.viewing || state.session)
~~~

The predicate controls the card and the dock notice; it never mutates the live turn.

## 5. TranscriptMessage

An assistant row returned by `GET /api/session?action=history`.

| Field | Source | Rule |
|---|---|---|
| `role` | `chat_log.role` | `user` or `assistant` |
| `content` | `chat_log.content` | The user text or the final reply / error text |
| `created_at` | `chat_log.created_at` | Existing timestamp |
| `turn_id` | `meta.turn_id` | Assistant only; drives the folded trace |
| `state` | `meta.state` (new) | `complete` \| `limited` \| `failed`; default `complete` |
| `partial` | `meta.partial` (new) | Text streamed before a model error; empty otherwise |

Backward compatibility: rows written before this change have no `state`/`partial`; the client
defaults to `complete` and renders no partial block.

## 6. TurnMeta (chat_log.meta, additive)

~~~json
{
  "turn_id": "t_...",
  "iterations": 2,
  "tools": ["list_events"],
  "limit_reached": false,
  "elapsed_ms": 1234,
  "state": "complete",
  "partial": ""
}
~~~

Rules:

- `state` is `failed` when `result.error` is set, `limited` when `result.limit_reached`, otherwise
  `complete`.
- `partial` is the concatenation of streamed `text` deltas **only for a failed turn**, truncated to
  4000 characters. It is empty for complete/limited turns.
- No credential is added; the field carries model output already shown in the dock.
- JSON meta is optional on old rows; readers MUST tolerate missing fields.

## 7. Done payload (additive)

~~~json
{
  "turn_id": "t_...",
  "reply": "...",
  "receipt": { "...": "..." },
  "limit_reached": false,
  "failed": false
}
~~~

`failed` is true exactly when `result.error` is set. The client uses it to choose the ending state;
`limit_reached` remains the limit signal.

## 8. Server turn/session binding

`Agent.respond` holds a local `session` for the whole turn:

~~~text
session = self.session            # bind at entry, before any await/IO
trajectory.start(..., session_id=session.session_id, ...)
session.note_user(message)
system = session.build_system(message)
result = run_loop(..., list(session.history), ...)
session.note_assistant(result.reply)
self._log(..., session_id=session.session_id)
maybe_consolidate(recalled=session.recalled, ...)
~~~

Invariant: a turn's `chat_log` rows, trajectory session id, and assistant history update all use the
same session id, even if `new_session()` runs concurrently.

## 9. Handoff sequence

~~~text
done frame
  → live.has_done = true, live.turn_id = done.turn_id, live.state = ending
  → state.handoffTurnId = live.turn_id
  → refresh()/render()/renderChat()
      → GET history for (viewing || session)
      → #chat-history.innerHTML = transcript
      → clearLive(handoffTurnId)      (same continuation)
      → paintLive()                   (empty or the next turn)
      → state.handoffTurnId = null
~~~

If the history fetch fails, the handoff id stays set and the live card remains; the next successful
`renderChat()` completes the swap. If a newer `chatGen` wins, only the winning continuation clears.

## 10. Invariants checklist

1. One live turn at most; `state.live` is either null or the object above.
2. `session_id` never changes after `begin`.
3. Navigation, session selection, new chat, dock collapse/resize, theme and trace expansion never
   clear or mutate `state.live`.
4. A second send while `state === live` is refused and does not replace the turn.
5. `clearLive` is the only writer that sets `state.live = null`, and it matches `turn_id`.
6. A turn is handed off only after `done`, and only after its transcript has painted.
7. A failed turn's partial text is present in `chat_log.meta.partial` and rendered in the transcript.
8. The live card is rendered only for the chat that owns it.
9. No new table, column, endpoint, dependency or build step.
