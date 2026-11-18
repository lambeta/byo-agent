# Contract — Highlight cues

**Version**: 1 · **Owner**: `byo/ops/highlight.py` · **Tests**: `test_highlight.py`,
`test_highlight_eval.py`

One turn's records become one ordered list of **cues** and one **final state map**. The browser
applies cues; it never derives them. This contract is the definition of "one-to-one".

## 1. Cue grammar

```json
{"seq": 7, "at": "2026-11-19T12:00:03.100+08:00", "step": "llm_start",
 "states": {"model": "live"}, "edges": ["e-context-model"],
 "label": "loop 2 · model reasons", "role": "step"}
```

| Field | Rule |
|---|---|
| `seq` | strictly increasing from 0 within a turn; the client's delta key |
| `at` | always a recorded `ts` |
| `step` | the record type that caused it, or `synthetic` for a projection rule |
| `states` | node id ⇒ one of the eight visual states; empty only for a status-only cue |
| `edges` | the complete set of connections live after this cue; the client idles every other edge |
| `label` | the status line for this instant; never empty |
| `role` | `step` or `mark` (turn-level indicator) |

## 2. Correspondence rules

1. **Start alignment.** A `*_start` record produces one `live` cue for its component at its `ts`.
   Its completion record produces one settle cue at the completion `ts`.
2. **One settle per step.** A settle cue touches exactly the components its start cue lit. No
   component is settled twice for one step, and no settle cue appears without a start — except a
   legacy record that was written before start records existed, which produces its settle cue only.
3. **No phantom lights.** A component appears in a cue only if its step happened in this turn.
   Specifically: `context` lights on the `context` record only; `llm` never lights `context`;
   `cost` lights on `receipt` only; `record` is a `mark` spanning the turn.
4. **No silent omissions.** Every record that names a component produces a cue; a record with no
   component still produces a status-only cue so the status line can name it.
5. **Edges follow their step.** An edge lights with the transition that uses it: `e-context-model`
   when a model call starts, `e-model-tools` when a tool starts, `e-tools-model` when the tool
   result flows back, `e-model-reply` and `e-reply-surfaces` at `turn_end`. Because each cue carries
   the complete live set, an edge that is no longer in a cue goes dark: a connection can never
   outlive the flow it depicts.

## 3. Mapping (source of truth)

| Record | Components | Edges | Cue label |
|---|---|---|---|
| `turn_start` | `surfaces` (live→done), `record` (live) | `e-surfaces-gate` | `message in · <source>` |
| `gate_start` | `gate` | — | `memory decision` |
| `gate` (decision) | `gate` → done/skipped/degraded | — | `memory decision · <decision>` |
| `gate` (retrieve) | `facts`, `episodes`, `persona` → done | `e-gate-facts`, `e-gate-episodes`, `e-gate-persona` | unchanged |
| `gate` (skip) | `facts`, `episodes`, `persona` → skipped | — | `memory skipped · <reason>` |
| `context` | `context` live→done | `e-gate-context` | `context assembled` |
| `llm_start` | `model` | `e-context-model` | `loop <n> · model reasons` |
| `llm` | `model` → done | — | `loop <n> · model answered`; `final answer` when stop reason ends the turn |
| `tool_start` | `tools` | `e-model-tools` | `tool <name> · <k> tool calls` |
| `tool` | `tools` → done/failed | `e-tools-model` | `tool <name> · done` / `failed` |
| `consolidation_start` | `consolidation` | — | `memory write` |
| `consolidation` | `consolidation`, `facts` → done | `e-consolidation-facts` | `memory written · <n> facts` |
| `receipt` | `cost` live→done | `e-record-cost` | `costed` |
| `error` | stage node → failed | — | `failed: <stage>` |
| `turn_end` | `reply` live→done, `record` → done; untouched stage nodes → not-reached | `e-model-reply`, `e-reply-surfaces`, `e-reply-record` | `reply` / `reply · failed` |
| `synthetic` (interrupted) | last started node → partial | — | `not running · interrupted at <step>` |
| unknown type | — | — | `unmapped step · <type>` |

A row that shows two states for one component (the `turn_start` and `turn_end` rows) is emitted as
two cues with the same `at`; the client's short-dwell rule keeps the first perceptible.

## 4. Final states

`final_states(records, memory_enabled)` returns `{node_id: state}` for the settled map:

- A component with an `error` for its stage, or a failed tool, is `failed`.
- `gate` is `skipped` / `degraded` per its record; memory components are `skipped` when the decision
  was skip, `idle` when memory is not configured, and `done` only when the decision was retrieve.
- Stage components the turn did not reach after a failure or an interruption are `not-reached`.
- Operations components are always `idle` in the settled view.
- The last started component of an interrupted turn is `partial`.
- Everything else is `idle`.

## 5. Timing rules

- A settle cue's `at` is the completion record's `ts`. A step that took 2.5 s is shown running for
  2.5 s; nothing is rescaled. A step whose start was not recorded (a legacy turn) gets its settle
  cue only — no running interval is invented.
- A step shorter than 150 ms is held by the client for at most 150 ms so it is perceivable; the hold
  never reorders cues and is abandoned when it would put the display more than 1 s behind.
- Cues dated in the past are applied as history without animation; only the state that ends up on
  screen matters for history.

## 6. Status line

- `label` is the single source of the step line. Notices (skipped lines, reconnect, catch-up) go to a
  separate note element and never replace the step line (spec FR-012).
- For `interrupted`, the status line says the turn is not running and names the step where it stopped.

## 7. Determinism

Given the same records, the same configuration and the same `now`, the cue list and final state map
are byte-identical. Only the synthetic interrupted cue and the client's history/current split depend
on `now`.
