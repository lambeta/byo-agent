# Contract — Trajectory schema v1

**Version**: 1 (integer, carried on every `turn_start`) · **Owner**: `byo/ops/trajectory.py` ·
**Consumers**: `byo/ops/observability.py`, `byo/ops/show_trajectory.py`, the dashboard, and the
reference's timeline renderer · **Tests**: `test_trajectory_contract.py`, `test_show_trajectory.py`

The trajectory is the product's ground truth for *what happened and what it cost*. It is append-only
JSON Lines, one object per line, one file per local day.

> **Naming**: the reference calls this artifact a trace. The schema below is what both renderers
> read; only the name and the directory are this project's own.

## 1. Files

```text
<home>/trajectories/YYYY-MM-DD.jsonl      # local day, appended, never rewritten
```

A new file starts each local day (not UTC — a person's day). Lines are written with one short
append per event so a concurrent dashboard read never blocks a turn. A partially written final line
(process killed mid-write) is skipped by readers and reported, never fatal.

## 2. Envelope

Every record is a JSON object. Fields common to all records inside a turn:

| Field | Type | Rule |
|---|---|---|
| `type` | string | one of the event types below |
| `ts` | string | ISO 8601 local time with offset, millisecond precision (e.g. `2026-11-18T16:20:03.114+08:00`) |
| `turn_id` | string | `t_` + 16 lowercase hex characters; identical for every record of one turn |

`turn_start` additionally carries `trajectory_version`. Readers MUST ignore unknown fields; writers MUST
NOT rename or repurpose an existing one without a version bump.

## 3. Event types

### `turn_start` — exactly one per turn, first

| Field | Type | Notes |
|---|---|---|
| `trajectory_version` | int | `1` |
| `turn_id` | string | `t_<16 hex>` |
| `user_message` | string | what the person typed, redacted |
| `source` | string | `cli` or `dashboard` |
| `session_id` | string | conversation label, `default` when none |
| `model`, `provider` | string | the configuration in force for this turn |

### `gate` — at most one, before the first `llm`

| Field | Type | Notes |
|---|---|---|
| `decision` | string | `retrieve` or `skip` |
| `reason` | string | one sentence; for a failure, the failure kind |
| `found` | int | optional; number of facts retrieved |

A gate that cannot decide writes `retrieve` and says why — it never blocks a turn.

### `llm` — one per model call

| Field | Type | Notes |
|---|---|---|
| `iteration` | int | 1-based; the tools-off call after the limit is `max_iterations + 1` |
| `kind` | string | `loop` (default) or `final` |
| `model` | string | as sent |
| `stop_reason` | string | `end_turn`, `tool_use`, `max_tokens`, `refusal`, `other` |
| `usage` | object | `{"in": int, "out": int}` tokens |
| `duration_ms` | int | wall time of the call |

### `tool` — one per tool call

| Field | Type | Notes |
|---|---|---|
| `tool` | string | tool name |
| `args` | object | arguments as the model sent them, redacted |
| `output` | string | the full text the model observed, redacted; readers bound what they show |
| `ok` | bool | `false` when the call raised or was unknown |
| `duration_ms` | int | wall time |
| `call_id` | string | the model's tool-call id, for correlation |

### `consolidation` — at most one per turn

| Field | Type | Notes |
|---|---|---|
| `new_facts` | int | facts kept |
| `kept` | array | `[{"content": string}]`, at most 5 entries in a trajectory |
| `episode` | string | optional one-line summary of the episode written |

### `receipt` — at most one, immediately before `turn_end`

| Field | Type | Notes |
|---|---|---|
| `total_usd` | number | sum of this turn's `llm` costs, 6 decimal places |
| `tokens_in`, `tokens_out` | int | sums |
| `iterations`, `tool_calls` | int | counts |
| `estimate` | bool | true when any call's model is missing from the pricing table |

The dashboard read model exposes the same figure as `usd` (see
[dashboard-api.md](dashboard-api.md)); the file keeps `total_usd`. One number, two
names, normalized in `ops/observability.py`.

### `error` — one per failed stage, before the end

| Field | Type | Notes |
|---|---|---|
| `stage` | string | `gate`, `llm`, `tool` or `consolidation` |
| `error_kind` | string | `Refused`, `Transport`, `RateLimited`, `BadResponse`, or `Internal` for a non-model failure such as consolidation storage |
| `message` | string | a human sentence, redacted |
| `status` | int | optional HTTP status for `Refused` / `RateLimited` |

### `turn_end` — exactly one, last

| Field | Type | Notes |
|---|---|---|
| `reply` | string | the text the person saw, redacted |
| `iterations` | int | model calls made, including the final one |

## 4. Order and invariants

1. `turn_start` first; `turn_end` last; nothing of another turn in between (turns never nest).
2. `gate` (if any) precedes the first `llm`.
3. Each `tool` follows the `llm` record whose response requested it.
4. `receipt` is the record immediately before `turn_end`.
5. A turn with no `turn_end` is **unfinished** and is rendered as such; it does not shift later
   records' indentation.
6. Exactly one trajectory line per event — no duplication on retry, no silent drops.

## 5. Units and rounding

Timestamps: ISO 8601 with offset, milliseconds. Durations: integer milliseconds. Tokens: integers.
Money: US dollars, float rounded to 6 decimals. Characters: Unicode code points (a preview's cap is
measured after decoding).

## 6. Redaction (enforced at the sink)

Redaction lives in `ops/trajectory.py` and runs on the assembled record, before the write, for every
event — callers cannot bypass it.

- **By field name**: any key matching `(?i)(api[_-]?key|token|secret|password|authorization|credential)`
  is replaced by `"[redacted]"`.
- **By value shape**: provider-shaped credentials (`sk-…`, `sk-ant-…`, `ghp_…`, 32+ char hex or
  base64-ish strings presented as a key) are replaced wherever they appear in a string.
- **Bound**: strings longer than 20 000 characters are cut to 20 000 with `[…truncated]` appended.
- Redaction is idempotent: redacting twice equals redacting once.

## 7. Versioning and cross-implementation compatibility

- The version is an integer on `turn_start`. Additive fields keep version 1; removing/renaming a
  field, changing a unit, or changing an invariant bumps to 2.
- A reader that meets an **unknown `type`** — including the reference's `hook`, `report`, `score`,
  `route`, `triage`, `graph` and `text` records — renders one generic row (type + first fields) and
  continues. It never errors and never drops the rest of the turn.
- The reference's renderer reads this schema unchanged because `turn_start`/`turn_end` framing and
  the field names above are the ones it already groups on (spec FR-032, SC-010).
- Golden fixtures: `evals/fixtures/trajectories/golden-cli.jsonl` (ours) and
  `evals/fixtures/trajectories/reference-sample.jsonl` (captured from the reference, read-only).

## 8. Worked example

```json
{"type":"turn_start","trajectory_version":1,"turn_id":"t_9f2c1d4a7b3e5c60","user_message":"book a catch-up with Alex on Friday","source":"cli","session_id":"terminal","model":"claude-sonnet-4-5","provider":"anthropic","ts":"2026-11-18T16:20:03.114+08:00"}
{"type":"gate","decision":"retrieve","reason":"asks about a person","found":1,"turn_id":"t_9f2c1d4a7b3e5c60","ts":"2026-11-18T16:20:03.402+08:00"}
{"type":"llm","iteration":1,"kind":"loop","model":"claude-sonnet-4-5","stop_reason":"tool_use","usage":{"in":812,"out":96},"duration_ms":1840,"turn_id":"t_9f2c1d4a7b3e5c60","ts":"2026-11-18T16:20:05.253+08:00"}
{"type":"tool","tool":"create_event","args":{"title":"Catch-up","start":"2026-11-20T09:00:00+08:00"},"output":"Created event 7 ...","ok":true,"duration_ms":12,"call_id":"toolu_01","turn_id":"t_9f2c1d4a7b3e5c60","ts":"2026-11-18T16:20:05.268+08:00"}
{"type":"llm","iteration":2,"kind":"loop","model":"claude-sonnet-4-5","stop_reason":"end_turn","usage":{"in":940,"out":58},"duration_ms":1260,"turn_id":"t_9f2c1d4a7b3e5c60","ts":"2026-11-18T16:20:06.533+08:00"}
{"type":"receipt","total_usd":0.0075,"tokens_in":1752,"tokens_out":154,"iterations":2,"tool_calls":1,"estimate":false,"turn_id":"t_9f2c1d4a7b3e5c60","ts":"2026-11-18T16:20:06.540+08:00"}
{"type":"turn_end","reply":"Booked for Friday 20 Nov, 09:00 (event 7, in state.db).","iterations":2,"turn_id":"t_9f2c1d4a7b3e5c60","ts":"2026-11-18T16:20:06.541+08:00"}
```
