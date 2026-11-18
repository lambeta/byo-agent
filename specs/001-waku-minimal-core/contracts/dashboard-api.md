# Contract — Dashboard HTTP API

**Version**: 1 · **Owner**: `byo/ops/dashboard.py` · **Tests**: `test_dashboard.py`, `test_api_contract.py`

Server: `ThreadingHTTPServer` bound to `127.0.0.1:BYO_PORT` (default 7777). No authentication — the
product is a single-user local tool (spec Assumptions). Request bodies are JSON, at most 1 MiB.
Responses are `application/json; charset=utf-8` unless noted. Errors use one shape:

```json
{ "error": { "code": "bad_request", "message": "human-readable sentence" } }
```

Codes: `bad_request` (400), `not_found` (404), `method_not_allowed` (405), `too_large` (413),
`conflict` (409, a turn is already running), `server_error` (500).

## Routes

| Method + path | Purpose | Returns |
|---|---|---|
| `GET /` | the application shell | `text/html`, `index.html` |
| `GET /static/<path>` | CSS, JS, the favicon | the file, or 404; `..` and absolute paths are refused |
| `GET /api/data` | everything the UI needs on refresh | `{ home, settings, turns, memory, spend, sessions }` |
| `GET /api/observability?window=today\|7d\|all` | the observability page | `{ window, turns, tools, memory, spend, generated_at }` |
| `GET /api/events?cursor=<int>` | new trajectory events since a cursor | `{ events, cursor, complete }` |
| `GET /api/session?action=history&session_id=<id>` | one thread's messages | `{ session_id, messages }` |
| `GET /api/session?action=state` | thread list and current thread | `{ sessions, current }` |
| `GET /api/memory?action=list` | facts and episodes | `{ facts, episodes, counts, mirror_path }` |
| `POST /api/memory` | `{"action":"add"\|"edit"\|"forget", "id"?, "subject"?, "content"?}` | `{ ok, facts }` |
| `GET /api/settings` | provider, model, whether a key is set | `{ provider, model, has_key, home }` |
| `POST /api/settings` | `{"provider"?, "model"?, "api_key"?}` | `{ ok, settings }` — the key is never returned |
| `GET /api/health` | liveness | `{ ok: true, version }` |
| `POST /api/chat` | one turn, no streaming (scripts) | `{ turn_id, reply }` |
| `POST /api/chat/stream` | one turn, streamed as SSE | `text/event-stream` |

## Turn card payload

Every turn in `/api/data` and `/api/observability` has the shape below. It is a projection over the
trajectory ([trajectory-schema.md](trajectory-schema.md)), never a separate store.

```json
{
  "turn_id": "t_9f2c1d4a7b3e5c60",
  "source": "dashboard",
  "session_id": "default",
  "user_message": "book a catch-up with Alex on Friday",
  "started_at": "2026-11-18T16:20:03.114+08:00",
  "ended_at": "2026-11-18T16:20:09.882+08:00",
  "state": "complete",
  "iterations": 2,
  "reply": "Booked for Friday 09:00 ...",
  "gate": { "decision": "retrieve", "reason": "asked about a person" },
  "steps": [
    { "kind": "llm",   "iteration": 1, "in": 812, "out": 96,  "usd": 0.0039, "duration_ms": 1840, "ok": true },
    { "kind": "tool",  "tool": "create_event", "args": "{title: 'Catch-up', start: '...'}", "output": "Created event 7 ...", "duration_ms": 12, "ok": true },
    { "kind": "llm",   "iteration": 2, "in": 940, "out": 58,  "usd": 0.0036, "duration_ms": 1260, "ok": true }
  ],
  "receipt": { "iterations": 2, "tool_calls": 1, "tokens_in": 1752, "tokens_out": 154, "usd": 0.0075, "estimate": false }
}
```

`state` is `complete` (`turn_end` present), `unfinished` (no `turn_end`) or `failed` (an `error`
record before the end). Previews are capped at 2000 characters.

## Streaming (SSE)

`POST /api/chat/stream` responds with `text/event-stream` and frames of the form:

```text
event: tool
data: {"tool":"create_event","args":{...},"output":"...","duration_ms":12,"ok":true}

event: text
data: {"delta":"Booked"}

event: done
data: {"turn_id":"t_9f2c...","reply":"Booked for Friday 09:00","receipt":{...}}
```

Frame kinds, in the order they occur: `gate`, `llm`, `tool`, `text` (zero or more deltas, only while
the model streams), `consolidation`, `receipt`, `done`; `error` replaces `done` on failure. Guarantees:

- every step frame is written **before** the model call that produces the reply finishes, so the card
  fills in while the turn runs (spec FR-027);
- `done` or `error` is always the last frame;
- a client disconnect does not cancel the turn — it runs to completion and is recorded as usual;
- one turn at a time per server; a second concurrent `/api/chat/stream` returns 409.

## Static assets

`index.html`, `style.css` and `js/*.js` are served as-is; no build step, no source maps, no CDN.
Content types are fixed by extension; anything else is `application/octet-stream`.

## Security and parity

- Loopback bind only; no CORS headers; no cookies; no auth (documented non-goal for a local tool).
- No endpoint ever returns a credential; `POST /api/settings` reports `has_key: true/false` only.
- Trajectory previews are already redacted at the sink, so the API cannot leak what the sink removed.
- Route names and payload field names follow the reference's so the same mental model applies
  (spec Parity Seams: Address).
