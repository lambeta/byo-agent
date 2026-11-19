# Contracts: Dashboard API & Navigation

**Date**: 2026-11-19 | **Feature**: specs/006-tools-memory-support

The dashboard's external surface is its local HTTP API (127.0.0.1, loopback only) plus the
hash routes the SPA understands and the map destinations that target them.

## HTTP API

### `GET /api/tools` — NEW

Read-only. Returns the tool catalog and recent tool-call results.

- **Response 200**: `{ "tools": ToolCard[], "results": ToolResultEntry[] }` (shapes in [data-model.md](../data-model.md)).
- **Errors**: none of its own; a server failure follows the existing `500 {"error": {...}}` envelope.
- **Guarantees**: `tools` equals the live registry (six tools today); `results` newest-first, bounded, redacted.

### `GET /api/memory` — EXTENDED (additive)

Existing response gains `gate` and `consolidation` objects ([data-model.md](../data-model.md)).
Additive only: no existing key is renamed, removed or re-typed.

### `POST /api/memory` — UNCHANGED

`{action: add|edit|forget, ...}` — the Memory view's mutations keep using it; the response
already includes the refreshed memory payload.

### `POST /api/chat` and `POST /api/chat/stream` — UNCHANGED

Contract reaffirmed by this feature's tests: a dashboard turn behaves like a terminal turn
(same tools offered, same memory gate, same trajectory records), and the SSE stream emits
`tool_start` before `tool` before the final reply frames.

## Hash routes (SPA)

| Route | View | Status |
|-------|------|--------|
| `#overview` | runtime map | existing |
| `#tools` | Tools view (Available + Results) | **new** |
| `#memory` | Memory view (gate / facts / episodes / consolidation sections) | fixed |
| `#observe` | Observability | existing |
| `#settings` | Settings | existing |

Unknown hashes keep the existing fallback to `#overview`.

## Map node destinations

`byo/ops/map.py` `destination` values and their routes after the fix:

| Node id(s) | Destination | Route / panel |
|------------|-------------|---------------|
| `chat`, `session` | chat | chat dock (existing) |
| memory-group nodes (`gate`, memory stores, consolidation) | memory | `#memory` |
| `tools` | **tools** | **`#tools`** |
| `model`, `loop`, `reply` | turn | turn detail panel (existing) |
| trajectory / observability nodes | observability | `#observe` |

Consistency rule (pinned by test): every `destination` value in `map.py` is handled by
`mapNodeClick` in `map.js`, and every navigated hash is a route `main.js` renders.
