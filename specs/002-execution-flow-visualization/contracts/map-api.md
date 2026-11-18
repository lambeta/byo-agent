# Contract — Map HTTP API

**Version**: 1 · **Owner**: `byo/ops/dashboard.py` · **Tests**: `test_map_api.py`, `test_map_scale.py`

These routes are **additive** to the v1 dashboard contract in
[`specs/001-waku-minimal-core/contracts/dashboard-api.md`](../../001-waku-minimal-core/contracts/dashboard-api.md).
No existing route, existing payload field or status code changes; the one addition to an existing
route is the feed's `skipped` count in §3. The house error shape is unchanged:

```json
{"error": {"code": "bad_request", "message": "window must be today, 7d or all"}}
```

Server: the existing loopback `ThreadingHTTPServer`; JSON responses; at most 1 MiB request bodies
(these routes are GET-only). No authentication, matching the local single-user product.

## 1. `GET /api/map?window=today|7d|all`

Returns the runtime map, its node summaries, the window's turn list, the live feed cursor and the
active turn's already-recorded events. This is the landing payload; it is a projection, not a
store.

### Query

| Parameter | Default | Rule |
|---|---|---|
| `window` | `7d` | one of `today`, `7d`, `all`; anything else is `400 bad_request` |

The `window` controls the turn list and the node summaries that are window-scoped. It does not
change the live feed: the feed always reads the most recent 7 days so a turn that started late
yesterday is still observable.

### Response 200

```json
{
  "window": "7d",
  "generated_at": "2026-11-18T19:30:00+08:00",
  "map": {
    "version": 1,
    "groups": [
      {"id": "harness", "label": "HARNESS", "x": 184, "y": 64, "w": 600, "h": 250}
    ],
    "nodes": [
      {
        "id": "gate", "label": "Memory gate", "group": "harness", "stage": "gate",
        "shape": "diamond", "x": 208, "y": 100, "w": 120, "h": 80,
        "summary": "3 skip · 2 retrieve", "destination": "memory"
      }
    ],
    "edges": [
      {"id": "e-surfaces-gate", "source": "surfaces", "target": "gate",
       "label": "message in", "dashed": false}
    ],
    "event_map": {
      "turn_start": {"nodes": ["surfaces"], "edges": ["e-surfaces-gate"], "label": "message in"}
    }
  },
  "turns": [
    {
      "turn_id": "t_9f2c1d4a7b3e5c60",
      "started_at": "2026-11-18T16:20:03.114+08:00",
      "ended_at": "2026-11-18T16:20:09.882+08:00",
      "source": "dashboard",
      "state": "complete",
      "iterations": 2,
      "tool_calls": 1,
      "usd": 0.0075,
      "estimate": false
    }
  ],
  "active": {
    "turn": {
      "turn_id": "t_9f2c1d4a7b3e5c60",
      "source": "dashboard",
      "started_at": "2026-11-18T16:20:03.114+08:00",
      "state": "unfinished"
    },
    "events": [
      {"type": "turn_start", "turn_id": "t_9f2c...", "ts": "...", "source": "dashboard"}
    ]
  },
  "cursor": 42,
  "skipped_lines": 0
}
```

Field rules:

- `map.groups`, `map.nodes`, `map.edges` and `map.event_map` are the full graph defined by
  [`map-graph.md`](map-graph.md). The example above is abbreviated; the response always carries
  every node and edge. The `summary` field is filled on every node.
- `turns` is the window's turns, **newest first**, projected from the trajectory. It is a
  lightweight summary: no `steps` and no `reply`. Fields are required; `ended_at` is `null` for an
  unfinished turn; `usd` is `null` when no receipt was recorded; `estimate` is `false` in that
  case. A malformed trajectory line increments `skipped_lines` and does not remove other turns.
- `active` is the newest **unfinished** turn in the 7-day feed, or `null`. It carries only the
  identifying fields and the raw events already recorded for that turn (the same records the raw
  view shows). The client replays these before polling; it never duplicates them because `cursor`
  already counts them.
- `cursor` is an integer count over the 7-day feed, the same cursor `GET /api/events` accepts.
  It is the position after the payload's events.
- `generated_at` is local ISO 8601 with offset.
- An empty home returns all nodes with summaries, `turns: []`, `active: null`, `cursor: 0`,
  `skipped_lines: 0` and `200`, never a blank or error page.

### Errors

| Status | Code | When |
|---|---|---|
| 400 | `bad_request` | `window` is not `today`, `7d` or `all` |
| 404 | `not_found` | no route (existing behaviour) |
| 500 | `server_error` | an unexpected projection failure; the message is human-readable and contains no secret |

## 2. `GET /api/turn?turn_id=<id>&window=today|7d|all`

Returns one turn, its server-built summary, its hotspot indexes and its raw records.

### Query

| Parameter | Default | Rule |
|---|---|---|
| `turn_id` | — | required; the `t_` prefix + 16 hex from `turn_start` |
| `window` | `7d` | `today`, `7d`, `all`; anything else is `400` |

### Response 200

```json
{
  "window": "7d",
  "turn": {
    "turn_id": "t_9f2c1d4a7b3e5c60",
    "source": "dashboard",
    "session_id": "default",
    "user_message": "book a catch-up with Alex on Friday",
    "started_at": "2026-11-18T16:20:03.114+08:00",
    "ended_at": "2026-11-18T16:20:09.882+08:00",
    "state": "complete",
    "iterations": 2,
    "reply": "Booked for Friday 09:00 ...",
    "gate": {"decision": "retrieve", "reason": "asked about a person"},
    "steps": [
      {"kind": "gate", "ts": "...03.402+08:00", "decision": "retrieve", "reason": "..."},
      {"kind": "llm", "ts": "...05.253+08:00", "iteration": 1, "model": "claude-sonnet-4-5",
       "in": 812, "out": 96, "usd": 0.0039, "duration_ms": 1840, "ok": true},
      {"kind": "tool", "ts": "...05.268+08:00", "tool": "create_event",
       "args": "{...}", "output": "Created event 7 ...", "duration_ms": 12, "ok": true},
      {"kind": "llm", "ts": "...06.533+08:00", "iteration": 2, "model": "claude-sonnet-4-5",
       "in": 940, "out": 58, "usd": 0.0036, "duration_ms": 1260, "ok": true}
    ],
    "receipt": {"iterations": 2, "tool_calls": 1, "tokens_in": 1752,
                "tokens_out": 154, "usd": 0.0075, "estimate": false}
  },
  "summary": "question → memory retrieved → 2 model calls · 1 tool · 6.8 s · $0.0075",
  "hotspots": {"slowest": 1, "most_usd": 1},
  "raw": [
    {"type": "turn_start", "turn_id": "t_9f2c...", "ts": "...", "user_message": "...", "source": "dashboard"},
    {"type": "gate", "turn_id": "t_9f2c...", "ts": "...", "decision": "retrieve", "reason": "..."},
    {"type": "llm", "turn_id": "t_9f2c...", "ts": "...", "iteration": 1, "duration_ms": 1840},
    {"type": "tool", "turn_id": "t_9f2c...", "ts": "...", "tool": "create_event", "ok": true},
    {"type": "turn_end", "turn_id": "t_9f2c...", "ts": "...", "reply": "Booked for Friday 09:00 ..."}
  ],
  "skipped_lines": 0
}
```

Rules:

- `turn` is the existing v1 projected turn, unchanged. `summary`, `hotspots` and `raw` are the
  only additions.
- `summary` follows [`turn-detail.md`](turn-detail.md) §2 exactly; it is a single line and uses
  only recorded values.
- `hotspots` indexes into `turn.steps`; each is an integer or `null`. A single timed step is
  allowed to be the slowest; a single costed step is allowed to be the most expensive.
- `raw` is every record for the turn in file order, including unknown types and a reference
  `text` record. Values are the sink's redacted, bounded values; the route does not transform
  them. A malformed line is counted, not fatal.
- The route is read-only. It never starts, cancels or mutates a turn.

### Errors

| Status | Code | When |
|---|---|---|
| 400 | `bad_request` | `turn_id` missing, or `window` invalid |
| 404 | `not_found` | the id is not in the selected window |
| 500 | `server_error` | an unexpected projection failure |

## 3. `GET /api/events?cursor=<int>` (existing, reused)

The map's live player polls this route every 500 ms. It is unchanged from the v1 contract:

```json
{"events": [{"type": "tool", "...": "..."}], "cursor": 43, "complete": true, "skipped": 0}
```

- `cursor` is the count over the 7-day read; the client sends the last value it saw.
- The response contains only records after that cursor, in file order.
- `skipped` is an **additive** count of malformed lines met during this read; the existing field set
  is unchanged, so a v1 client can ignore it. The live player names it when it is non-zero.
- It is read-only and never acquires the turn lock; any number of viewers can poll.
- A bad cursor returns `400 bad_request`.
- The map's initial cursor comes from `/api/map`; the two routes read the same 7-day feed, so the
  counts line up.

## 4. Security and compatibility

- Both new routes are loopback-only, unauthenticated (single-user local product) and read-only.
- No route returns a credential. The raw list contains only values the trajectory sink already
  redacted and truncated; no extra endpoint exposes unredacted data.
- Existing routes and payloads are untouched. The new routes are additive; a v1 client that never
  calls them sees no change.
- The map's node set and event map are versioned with the route (`map.version: 1`). Adding a node
  is additive; removing/renaming one changes the map contract and its tests in the same commit.
