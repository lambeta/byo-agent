# Data Model: Runtime-Accurate Live Highlighting

**Date**: 2026-11-19 | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

Two data sets are modelled here: the **record** the runtime already owns (extended, additively) and
the **cue** the projection derives from it. Nothing is stored twice; the cue list and the state map
are pure functions of the record plus the memory configuration.

## 1. Turn record (extended)

### 1.1 Envelope (unchanged)

Every line is one JSON object: `type`, `ts` (local ISO 8601 with offset, millisecond precision),
`turn_id` (`t_` + 16 hex), plus type-specific fields. The sink adds the envelope, redacts the whole
record and appends it under a lock. `text` records (streaming deltas) are not persisted.

### 1.2 Additions

| Type | Written when | Fields | Read by |
|---|---|---|---|
| `gate_start` | immediately before the memory decision's model call | `model` | cue projection |
| `context` | after the working context is assembled | `recalled` (bool), `recalled_chars` (int), `duration_ms` | cue projection |
| `llm_start` | immediately before a model request | `iteration` (int), `model` | cue projection, status line |
| `tool_start` | immediately before a tool executes | `tool` (name), `call_id` | cue projection, status line |
| `consolidation_start` | immediately before a consolidation model call | `pending` (int) | cue projection |

Additive fields on existing records:

| Record | Field | Meaning | Backward rule |
|---|---|---|---|
| `turn_start` | `pid` (int) | writer process id; absent on older records | absent ⇒ the turn is never live |
| `gate` | `degraded` (bool) | the gate failed open (subject unavailable, refusal, unparseable answer) | absent ⇒ `false` |
| `turn_end` | `state` | `complete` (normal), `failed` (raised), `limited` (step limit) | absent ⇒ derive as today |

### 1.3 Ordering guarantees

1. Within a turn, records are appended in the order the steps happened; a `*_start` always precedes
   the completion record of the same step.
2. Steps are sequential in this product: at most one `*_start` may be unmatched at any instant.
3. `turn_start` is the first record of a turn; `turn_end` is the last, and is always written — even
   when `Agent.respond` raises, in which case an `error` (`stage: "turn"`) precedes it.
4. A start record never carries a result, a cost or a token count; it carries only what is known
   before the step begins.

### 1.4 Validation rules

- `ts` is monotonically non-decreasing within a turn (millisecond resolution may tie two records).
- `llm_start.iteration` matches the `iteration` of its completion record.
- `tool_start.call_id` matches `tool.call_id`; `tool_start.tool` matches `tool.tool`.
- A redacted field is redacted in start records too (the sink applies to every field).
- Unknown record types remain readable by every consumer; a reader must not fail on one.

## 2. Liveness model

A turn is in exactly one of four states, derived only from its records and the writer's pid:

| State | Condition |
|---|---|
| `running` | no `turn_end`, `pid` present and alive |
| `interrupted` | no `turn_end`, and (`pid` absent or not alive) |
| `complete` | `turn_end.state` is `complete` or absent and no `error` record |
| `failed` | `turn_end.state == "failed"` or any `error` record |

The pid check is `os.kill(pid, 0)`: `ProcessLookupError` ⇒ dead, `PermissionError` ⇒ alive. Pids
`<= 0` and the current pid are handled explicitly. The check is injected where it is tested.

## 3. Cue (derived, never stored)

One **cue** is one component-state transition at one instant.

| Field | Type | Rule |
|---|---|---|
| `seq` | int | 0-based position in the turn's cue list; strictly increasing; the client's delta key |
| `at` | str (ISO 8601) | the recorded instant of the transition; for a completed step this is its start (or end for the settle cue) |
| `step` | str | the record type that caused the cue (for example `llm_start`, `llm`, `turn_start`), or `synthetic` for a projection rule (the interrupted turn) |
| `states` | object | node id ⇒ the state applied to it in this cue; one entry per changed node |
| `edges` | list[str] | the complete set of connections live after this cue; the client idles every other edge |
| `label` | str | the status line for this instant, in the product's own words |
| `role` | str | `step` (selects the step line) or `mark` (turn-level, e.g. the trajectory indicator) |

Invariants:

- **Coverage**: every record with a component produces at least one cue; every cue names an existing
  node and edge from `map.graph()`.
- **Order**: `seq` order equals `(at, record order)`; no cue may be dated before its recorded cause.
- **One-to-one**: a completion record produces exactly one settle cue for the components its start
  cue lit; no component is settled twice for the same step.
- **No invention**: a cue's `at` is always a recorded `ts`. Nothing is derived from wall-clock time
  except the synthetic interrupted cue, which is labelled `synthetic`. A step that has no start
  record therefore has no `live` cue.

## 4. Component state table

The eight visual states and the record fact that justifies each one. Nothing else may produce them.

| State | Justified by |
|---|---|
| `live` (word "running") | an unmatched `*_start` for this component |
| `done` | the completion record of a step that started on this component and reported no failure |
| `skipped` | `gate.decision == "skip"`: the gate itself, and the memory components it deliberately did not use |
| `degraded` | `gate.degraded == true` |
| `failed` | a `tool` with `ok == false` on `tools`; an `error` whose `stage` maps to the component |
| `partial` | the last component with an unmatched start in an `interrupted` turn |
| `not-reached` | a **stage** component the turn provably did not reach (a failure or an interruption cut the path short) |
| `idle` | everything else, including the operations group and a capability that is not configured |

Rules:

- `not-reached` is reserved for stage components cut off by a failure or an interruption. It is never
  applied to the operations group, and never applied because a decision said "not needed" (that is
  `skipped`).
- The trajectory component is a turn-level indicator: `live` from `turn_start` to `turn_end`,
  `done` afterwards. It is a `mark`, not a step, and is excluded from the "one step, one light" audit.
- A component that was lit in a turn keeps its final state until the settle window ends, then returns
  to `idle`.

## 5. Feed cache (read model)

`feed.Feed` keeps, per day file, `(size, mtime_ns, byte_offset, events)` plus one merged list and a
skipped-line counter.

| Invariant | Meaning |
|---|---|
| Incremental equals full | For any sequence of appends, the cached list equals `read_events(home, window)` |
| Append-only fast path | A poll reads only bytes after `byte_offset` |
| Safe fallback | Size shrunk, mtime older, or a new file appears ⇒ reload that file (or the window) |
| Window bound | The 7-day window is applied on the merged list exactly as `read_events` does |
| Thread safety | One lock around refresh; readers get an immutable snapshot |

## 6. Read models

`GET /api/live` (contract in [contracts/live-api.md](contracts/live-api.md)) returns:

```json
{
  "generated_at": "2026-11-19T12:00:04.020+08:00",
  "active": true,
  "turn": {"turn_id": "t_9f2c...", "source": "cli", "started_at": "...", "state": "running"},
  "seq": 11,
  "cues": [{"seq": 10, "at": "...", "step": "llm_start", "states": {"model": "live"},
            "edges": ["e-context-model"], "label": "loop 2 · model reasons", "role": "step"}],
  "status": "loop 2 · model reasons · 1 tool call",
  "skipped": 0,
  "poll_ms": 100
}
```

`/api/map` keeps its shape; `active` now means *live*, so an interrupted or finished turn is `null`
there. `/api/events` keeps its v1 payload and reads through the cache.

## 7. What is deliberately not modelled

- No turn table, no cue table, no status file: cues are recomputed per request from the record.
- No per-token highlight: a streaming model call is one step.
- No rewrite of stored records: a legacy turn is projected, never migrated.
- No new visual state and no new map node.
