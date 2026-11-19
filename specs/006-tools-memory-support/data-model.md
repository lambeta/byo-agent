# Data Model: Working Tools & Memory in the Dashboard

**Date**: 2026-11-19 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

No database schema change. This feature introduces two read-only payload shapes and one
navigation contract; all data comes from the existing registry, tables and trajectory.

## Entities (existing, unchanged)

| Entity | Source of truth | Fields used by this feature |
|--------|-----------------|------------------------------|
| Tool | live `ToolRegistry` | `name`, `description`, `input_schema` (exactly what the model is offered) |
| Fact | `facts` table | `id`, `subject`, `content`, `source`, `created_at` |
| Episode | `episodes` table | `id`, `happened_at`, `summary` |
| Gate decision | trajectory `gate` events | `decision` (`retrieve` / `skip`), reason, timestamp |
| Consolidation | trajectory `consolidation` events + `chat_log` pending rows | pending count, threshold (`settings.consolidate_every`), last run time |
| Trajectory tool event | trajectory `tool` / `tool_start` events | `tool`, `args`, `output` (preview), `ok`, `duration_ms`, `turn_id` |

## New payload: `GET /api/tools`

```json
{
  "tools": [
    { "name": "create_event", "description": "...", "input_schema": { "type": "object", "...": "..." } }
  ],
  "results": [
    {
      "tool": "list_events",
      "args": { "...": "..." },
      "output": "preview text (bounded)",
      "ok": true,
      "duration_ms": 12,
      "turn_id": "t_...",
      "at": "2026-11-19T09:00:00+08:00"
    }
  ]
}
```

- `tools`: the six registered tools, in registry order; served from the live registry, never a duplicated static list.
- `results`: most recent tool events across the selected window, newest first, bounded (e.g. 50); `output` is a bounded preview, redacted exactly as trajectory reads are today.
- Empty states: `results: []` is normal (no recorded calls yet) and MUST render an explicit empty state, never an error.

## Extended payload: `GET /api/memory` (additive only)

Existing fields (`facts`, `episodes`, `mirror_path`) unchanged. Added:

```json
{
  "gate": { "retrieve": 12, "skip": 30, "last_decision": "retrieve", "last_reason": "..." },
  "consolidation": { "pending": 3, "threshold": 10, "last_run_at": "2026-11-19T08:00:00+08:00" }
}
```

- Gate counts aggregate `gate` events in the current window; `last_*` fields are null when no gate event exists.
- `consolidation.pending` uses the same `pending_rows` source the runtime gate uses, so the view can never disagree with what the agent will do next turn.

## Memory view sections (rendering contract)

| Section | Data | Empty state |
|---------|------|-------------|
| Gate overview | `gate` counts + last decision | "no gate decisions recorded yet" |
| Facts | `facts` rows + add/edit/forget actions | "nothing remembered yet" |
| Episodes | `episodes` rows | "no episodes yet" |
| Consolidation | `consolidation` pending/threshold/last run | "not run yet" |

## Validation rules (from spec requirements)

- Tools view catalog MUST equal the registry the model sees (FR-003b): a tool present in the view but not offered to the model (or vice versa) is a defect.
- Every Memory view mutation MUST leave `facts` table, view payload and mirror file consistent (FR-006).
- Results and gate data MUST come from the recorded trajectory, redacted at the same boundary as every other surface (FR-012).
- No section may render `undefined`/blank on valid data or on empty data (SC-007).

## State transitions

None introduced. The only lifecycle touched is the existing one: chat rows → consolidation
threshold → facts/episodes → mirror rewrite — surfaced read-only by the new sections.
