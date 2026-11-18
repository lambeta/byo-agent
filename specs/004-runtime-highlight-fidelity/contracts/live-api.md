# Contract — Live HTTP API

**Version**: 1 · **Owner**: `byo/ops/dashboard.py` (routing) with `byo/ops/highlight.py` (projection) ·
**Tests**: `test_live_api.py`, `test_highlight.py`

Additive to the v1 dashboard contract. No existing route, payload or status code changes. The house
error shape is unchanged.

## 1. `GET /api/live`

Returns the newest turn's cues and state. Read-only; it never starts, stops or mutates a turn.

### Query

None. The route always reads the 7-day feed, like the map's live cursor.

### Response 200

```json
{
  "generated_at": "2026-11-19T12:00:04.020+08:00",
  "active": true,
  "turn": {
    "turn_id": "t_9f2c1d4a7b3e5c60",
    "source": "cli",
    "started_at": "2026-11-19T12:00:01.900+08:00",
    "ended_at": null,
    "state": "running"
  },
  "seq": 12,
  "cues": [
    {"seq": 11, "at": "2026-11-19T12:00:04.000+08:00", "step": "llm_start",
     "states": {"model": "live"}, "edges": ["e-context-model"],
     "label": "loop 2 · model reasons", "role": "step"}
  ],
  "status": "loop 2 · model reasons · 1 tool call",
  "skipped": 0,
  "poll_ms": 100
}
```

Field rules:

- `turn` is the newest turn in the feed, or `null` when the home has no turns.
  `state` is one of `running`, `interrupted`, `complete`, `failed`.
- `active` is `true` only while `state == "running"`.
- `cues` is the **whole** cue list of that turn (bounded by its record count), not a delta. The client
  diffs by `seq`; the list is what makes a completion between two polls impossible to miss.
- `seq` equals the number of cues.
- `status` is the label of the last cue, or `Agent idle` when `turn` is `null`.
- `skipped` counts malformed lines met during the read; it never errors the request.
- `poll_ms` suggests the client's next interval: 100 while `active`, 1000 otherwise. The client may
  clamp it; the value is a hint, not a setting.
- An empty home returns `turn: null`, `active: false`, `cues: []`, `seq: 0`, `status: "Agent idle"`
  and `200`.

### Client mount rule (part of the contract)

- `state: "running"` on first load ⇒ apply the existing cues as history, then continue from `seq`.
- `state: "interrupted"` on first load ⇒ apply the final state map once, status `not running`;
  nothing animates.
- `state: "complete"` / `"failed"` on first load ⇒ idle; history is read through the turn list, never
  replayed on the map.
- A turn already being watched ⇒ apply cues with `seq` greater than the last applied, in order.

### Errors

| Status | Code | When |
|---|---|---|
| 500 | `server_error` | an unexpected projection failure; the message is human-readable and contains no secret |

No 400 path: the route takes no input. No authentication, loopback only, matching the product.

## 2. Relationship to the other routes

| Route | Change |
|---|---|
| `GET /api/map` | Unchanged shape. `active` now means *live only*; an interrupted or finished turn is `null` there. |
| `GET /api/events` | Unchanged contract; reads through the cached feed. No longer used by the map. |
| `GET /api/turn` | Unchanged; its `raw` list now also shows start records, which is the point. |
| `POST /api/chat`, `/api/chat/stream` | Unchanged; start notifications may appear as additional stream frames. |

## 3. Polling and cost

- The client polls with a chained `setTimeout`, never overlapping requests.
- While `active` is true the interval is `poll_ms` (100 ms); otherwise 1000 ms.
- Hidden tabs do not poll; becoming visible resumes immediately.
- The server must answer a 200-turn, 7-day home in under 20 ms p95, reading only appended bytes
  through `feed.Feed`.

## 4. Determinism and privacy

- Two requests at the same instant return the same payload.
- No credential, raw secret or unredacted value can appear: the cue projection only reads values the
  sink already redacted and truncates labels itself.
- The route never acquires the turn lock and never blocks a running turn.
