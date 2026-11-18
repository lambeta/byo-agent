# Data Model — Phase 1

**Feature**: Agent Execution Visualization · **Date**: 2026-11-18

This feature adds **no persisted shape**. It is a set of read-only projections over the two stores
that already exist:

1. **`state.db`** — facts, episodes, chat log (the counts the map shows).
2. **`trajectories/YYYY-MM-DD.jsonl`** — the only source for turns, steps, summaries, hotspots and
   the raw record behind the detail.

The map graph itself is source (Python data in `byo/ops/map.py`), not a database table. The
trajectory schema is unchanged; its contract remains
[`specs/001-waku-minimal-core/contracts/trajectory-schema.md`](../001-waku-minimal-core/contracts/trajectory-schema.md).
This document covers the graph model, the derived read models, the client states and the rules that
keep the map honest.

## 1. Map graph (source, not stored)

`byo/ops/map.py` exposes one `graph()` value. The API deep-copies it and adds summaries; the browser
never defines a second copy.

### Group

| Field | Type | Rule |
|---|---|---|
| `id` | string | `surfaces`, `harness`, `memory`, `operations`; unique |
| `label` | string | human label drawn on the panel |
| `x`, `y`, `w`, `h` | int | within the 1040 × 680 viewBox, non-overlapping with other groups |

### Node

| Field | Type | Rule |
|---|---|---|
| `id` | string | stable, lowercase; unique; appears in edges and the event map |
| `label` | string | short visible name |
| `group` | string | one of the four group ids |
| `stage` | string | `gate`, `loop`, `tool` or `reply` for the four stages; the group name otherwise |
| `shape` | string | `box` or `diamond` (the gate) |
| `x`, `y`, `w`, `h` | int | within its group and the viewBox |
| `summary` | string | one line, computed per request; never empty |
| `destination` | string | `chat`, `session`, `memory`, `turn` or `observability` |

The node set is deliberately small (13 nodes):

| Group | Nodes | Destination |
|---|---|---|
| surfaces | `surfaces` | `chat` |
| harness | `gate` `context` `model` `tools` `reply` | `memory` / `session` / `turn` / `turn` / `turn` |
| memory | `facts` `episodes` `persona` `consolidation` | `memory` (all) |
| operations | `record` `observability` `cost` | `observability` (all) |

### Edge

| Field | Type | Rule |
|---|---|---|
| `id` | string | stable, unique; appears in the event map |
| `source`, `target` | string | must name nodes that exist; no self-loop |
| `label` | string | short, drawn where the flow is not obvious |
| `dashed` | bool | true for an optional path (memory retrieval, saved chats) |

The edge set (15 edges) encodes the actual flow: `surfaces → gate` (message in),
`gate → context` (assemble), `gate → facts|episodes|persona` (only if needed, dashed),
`context → model` (prompt), `model ↔ tools` (act/observe), `model → reply` (answer),
`reply → surfaces` (reply out), `reply → record` (save), `reply → consolidation` (saved chats,
dashed), `consolidation → facts` (distill), `record → observability` (read) and `record → cost`
(price). The exact list and its invariants are in
[`contracts/map-graph.md`](contracts/map-graph.md).

### Event map

One entry per recorded event type; each entry carries `nodes`, `edges` and a status `label`, plus
three explicit conditional shapes described in the contract: a retrieval adds memory nodes/edges, a
failed tool sets the tool failed, and an error's `stage` selects the failed node. The keys are
exactly `turn_start`, `gate`, `llm`, `tool`, `consolidation`, `receipt`, `error` and
`turn_end`. An unknown type is not in the map and is handled by the status line (see §5).

### Node summaries

Summaries are computed by `map.summaries(conn, settings, turns, spend, memory_enabled, tool_count,
session_id)` and copied onto the nodes by the API. They are one short line and every number is
measured:

| Node | Summary source |
|---|---|
| `surfaces` | constant `terminal · dashboard` |
| `gate` | counts of `skip`/`retrieve` in the window; `not configured` when memory is `None`; `no turns yet` with no turns |
| `context` | current session id + `chat_log` message count for it |
| `model` | `settings.effective_model()` |
| `tools` | registry tool count (6) |
| `reply` | `idle` or the last turn's local time |
| `facts`, `episodes` | `COUNT(*)` from the tables |
| `persona` | `PERSONA.md` present or `not created yet` |
| `consolidation` | pending `chat_log` rows + `settings.consolidate_every` |
| `record` | turn count in the window |
| `observability` | turn/tool count in the window |
| `cost` | `observability.spend()` total, or `no spend` |

No node shows a number that the database or trajectory did not produce.

## 2. Turn (existing read model, reused)

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
  "gate": {"decision": "retrieve", "reason": "asked about a person"},
  "steps": [
    {"kind": "llm", "ts": "...06.953+08:00", "iteration": 1, "in": 812, "out": 96, "usd": 0.0039, "duration_ms": 1840, "ok": true},
    {"kind": "tool", "ts": "...05.268+08:00", "tool": "create_event", "args": "...", "output": "...", "duration_ms": 12, "ok": true},
    {"kind": "llm", "ts": "...06.533+08:00", "iteration": 2, "in": 940, "out": 58, "usd": 0.0036, "duration_ms": 1260, "ok": true}
  ],
  "receipt": {"iterations": 2, "tool_calls": 1, "tokens_in": 1752, "tokens_out": 154, "usd": 0.0075, "estimate": false}
}
```

The field meanings and the `state` values (`complete`, `failed`, `unfinished`) are the existing v1
contract and do not change. The detail adds, beside the turn, the fields below.

## 3. Turn detail (derived, not stored)

`GET /api/turn` returns:

| Field | Type | Derivation |
|---|---|---|
| `turn` | object | the projected turn above |
| `summary` | string | one line, built only from the turn's gate, model/tool counts, duration, receipt and state (see §4) |
| `hotspots` | object | `{ "slowest": int|null, "most_usd": int|null }`, indexes into `turn.steps` |
| `raw` | array | every record for this turn in file order, redacted at the sink |
| `window` | string | the requested `today` / `7d` / `all` |
| `skipped_lines` | int | malformed trajectory lines skipped during the read |
| `found` | bool | false only in the 404 body's error (the route returns 404 instead) |

### 3.1 Summary

```text
question → memory skipped|retrieved → 2 model calls · 1 tool · 3.2 s · $0.004
question → memory skipped → 1 model call · 0 tools · 0.8 s · $0.0006 · failed at llm
question → memory retrieved → 2 model calls · 0 tools · 1.4 s · cost not recorded · unfinished
```

Rules:

- `memory skipped` / `memory retrieved` only when a gate record exists; otherwise omit the part
  (memory is not configured, not "skipped").
- `N model call(s)` counts `llm` steps (including the tools-off final call); `N tool(s)` counts
  `tool` steps; singular/plural is correct.
- Duration is `ended_at - started_at` in seconds, one decimal; when there is no end, the last
  record's `ts` is the end and the word `unfinished` is appended.
- Cost is the receipt's `usd`; `~` prefixes it when `estimate` is true; `cost not recorded` when
  there is no receipt.
- `failed at <stage>` is appended when the state is `failed`; `unfinished` when the state is
  `unfinished`.
- No other words, numbers or inferred reasons are added.

### 3.2 Hotspots

Leaves are steps with a recorded duration or a recorded USD cost. `slowest` is the index of the
maximum `duration_ms` (ties to the earlier step); `most_usd` is the index of the maximum `usd`
(ties to the earlier step). `null` when no step has that value. The detail labels those rows; it
does not recompute or round differently from the payload.

### 3.3 Raw record

The raw list is every JSON object whose `turn_id` matches, in file order, including an unknown type
or a `text` record from a reference trajectory. Values are already redacted and bounded by the sink;
the API adds no transformation and cannot unredact. Malformed lines are counted, not fatal.

## 4. Client-only state

The server never sends a "currently highlighted" state; each viewer derives it.

### Map view state

```text
idle ──turn_start──> live ──turn_end──> done (hold 0.5–2 s) ──> idle
                      │
                      ├── error / stage failed ──> failed (hold) ──> idle
                      └── unfinished record ──> partial (hold) ──> idle
```

`caught up` is the status when a reconnect or a backlog has skipped intermediate highlights; it is
not a node state.

### Node state

| State | Meaning | Applied by |
|---|---|---|
| `idle` | no turn or not yet reached | turn start / reset |
| `live` | the step is happening now | event mapping |
| `done` | the step completed | next event / turn end |
| `skipped` | the memory decision skipped retrieval | `gate.decision == skip` |
| `degraded` | the memory decision failed and fell back to retrieve | gate reason / error |
| `failed` | the step failed | `tool.ok == false` or `error.stage` |
| `not-reached` | the turn ended without this node | turn end |
| `partial` | the last reached node of an unfinished turn | unfinished active turn |

Rules: a node only moves forward within a turn; a new `turn_start` resets every node to `idle`;
at `turn_end` every untouched node becomes `not-reached`; the failed node stays failed even when
the model recovers; the last node of an unfinished turn becomes `partial` rather than `done`.

## 5. Unknown and invalid input

| Input | Rule |
|---|---|
| Unknown event type | status line `unmapped step: <type>`; no node lit; generic row in raw |
| Corrupted trajectory line | skipped, counted in `skipped_lines` (history/map) or the feed's `skipped` (live), rest of turn rendered |
| Unknown turn id / outside window | `404 not_found` with the house error shape |
| Invalid window | `400 bad_request`, message names `today`, `7d`, `all` |
| Event burst | queue/coalesce; catch up to the latest complete state; never invent a step |
| Failed poll | status `reconnecting`; last complete state marked stale; resume from cursor |
| Missing destination | the click reports it in place; the map keeps its state |

## 6. Validation rules

| Rule | Where enforced | Test |
|---|---|---|
| Node ids are unique and lowercase | `map.py` + test | `test_map.py` |
| Every edge endpoint names a node; no self-loop | `map.py` + test | `test_map.py` |
| Every destination is one of the five view tokens | `map.py` + test | `test_map.py` |
| No retired id or command-line eval/release node | `map.py` + test | `test_map.py`, `test_map_static.py` |
| Every event type the product emits has an event-map entry | `map.py` + test | `test_map.py` |
| Every node/group box is inside the 1040 × 680 viewBox | `map.py` + test | `test_map.py` |
| Every node has a non-empty summary on an empty home | `map.py` + test | `test_map.py` |
| Summary uses only recorded values; no unmeasured number | `turn_detail.py` + test | `test_turn_detail.py` |
| Hotspot indexes point into `steps` or are null | `turn_detail.py` + test | `test_turn_detail.py` |
| Raw records are redacted at the sink | `trajectory.py` + test | `test_redaction.py` |
| `/api/map` and `/api/turn` are read-only | `dashboard.py` + test | `test_map_api.py` |
| A 200-turn window builds within the budget | `map.py` + test | `test_map_scale.py` |

## 7. Relationships

```text
Turn 1 ── N Step (recorded)
Turn 1 ── 0..1 Gate (a step)
Turn 1 ── 0..N Loop iteration (an llm step plus its tool steps conceptually)
Turn 1 ── 0..1 Receipt (accounting, not a step)
MapNode 1 ── N Event-map entry (one node can light for several event types)
MapEdge 1 ── N Event-map entry
Turn 1 ── 0..1 Detail (summary + hotspots + raw), derived on request
```

A turn is never stored in the map; the map is a lens on the turn list and the local counts. The
detail is recomputed from the trajectory each time it is opened, so closing the browser or
restarting the process cannot lose it.
