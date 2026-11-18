# Contract — Map graph and event map

**Version**: 1 · **Owner**: `byo/ops/map.py` · **Consumers**: `byo/ops/dashboard.py`, `map.js`, `live.js`, tests · **Tests**: `test_map.py`, `test_map_api.py`

The map is a **runtime** architecture map. It describes the four groups this product actually has
and deliberately omits the retired capabilities and the command-line eval/release tools (spec
Clarifications, 2026-11-18; FR-002, SC-011). The graph is source data, not a stored table and not a
hand-maintained SVG; the browser renders what this contract returns.

## 1. Groups

The viewBox is 1040 × 680. Each group is a labelled panel; nodes sit inside their group.

| Group id | Label | Box (x, y, w, h) |
|---|---|---|
| `surfaces` | SURFACES | 20, 64, 152, 180 |
| `harness` | HARNESS | 184, 64, 600, 250 |
| `memory` | MEMORY | 24, 340, 560, 300 |
| `operations` | OPERATIONS | 620, 340, 396, 300 |

## 2. Nodes

Every node has `id`, `label`, `group`, `shape`, `x`, `y`, `w`, `h`, `summary` and
`destination`. Boxes are in viewBox units. `shape` is `box` except the gate, which is a diamond.

| Id | Label | Group | Shape | Box | Destination |
|---|---|---|---|---|---|
| `surfaces` | Surfaces | surfaces | box | 32, 110, 128, 56 | `chat` |
| `gate` | Memory gate | harness | diamond | 208, 100, 120, 80 | `memory` |
| `context` | Working context | harness | box | 360, 110, 140, 56 | `session` |
| `model` | Model | harness | box | 520, 110, 140, 56 | `turn` |
| `tools` | Tools | harness | box | 520, 190, 140, 56 | `turn` |
| `reply` | Reply | harness | box | 680, 110, 100, 56 | `turn` |
| `facts` | Fact memory | memory | box | 44, 390, 150, 60 | `memory` |
| `episodes` | Episodes | memory | box | 214, 390, 150, 60 | `memory` |
| `persona` | Persona | memory | box | 384, 390, 150, 60 | `memory` |
| `consolidation` | Consolidation | memory | box | 44, 510, 240, 60 | `memory` |
| `record` | Trajectory | operations | box | 640, 390, 160, 60 | `observability` |
| `observability` | Observability | operations | box | 820, 390, 176, 60 | `observability` |
| `cost` | Spend | operations | box | 820, 480, 176, 60 | `observability` |

Allowed destinations: `chat` (the chat view), `session` (the current session/history), `memory`
(the memory view), `turn` (the selected turn's detail) and `observability` (the existing
Observability view, including its spend section).

Every node also carries `stage`: `gate` for the gate, `loop` for the model, `tool` for tools,
`reply` for the reply, and its group name otherwise. The compact turn card, the map and the detail
use those same four stage terms; the map's node-level live states are presentation states, not a
second turn vocabulary.

### 2.1 Summary rules

`summary` is one short line; it is recomputed per request and never contains an unmeasured number.

| Node | Summary |
|---|---|
| `surfaces` | `terminal · dashboard` |
| `gate` | `N skip · M retrieve` for the window; `not configured` when memory is disabled; `no turns yet` when the window has no turns |
| `context` | `<session_id> · N messages` (the current session; `empty` at 0) |
| `model` | `settings.effective_model()` |
| `tools` | `N tools` (the registry's enabled set) |
| `reply` | `idle` or `last HH:MM` from the newest turn |
| `facts` | `N facts` |
| `episodes` | `N episodes` |
| `persona` | `PERSONA.md` or `not created yet` |
| `consolidation` | `N pending · every M` |
| `record` | `N turns` for the window |
| `observability` | `N tool calls` for the window |
| `cost` | `USD 0.0006` or `no spend` |

### 2.2 Shared vocabulary

The compact turn card, the map and the detail use one stage vocabulary: `gate`, `loop` (the model
call and the tools it requested), `tool` and `reply`; and one turn vocabulary: `complete`, `failed`,
`unfinished`. The map's node live states (`idle`, `live`, `done`, `skipped`, `degraded`, `failed`,
`not-reached`, `partial`) are presentation states. The card's `loop(s)`/`tool(s)` chips are the same
stages as the map's loop/model and tools nodes; its reply section is the reply stage. No synonym is
introduced.

## 3. Edges

Every edge has `id`, `source`, `target`, `label` and `dashed`. Both endpoints must name a node in
§2. The renderer computes a curved path between the node boxes; the contract carries no path
coordinates.

| Id | Source → target | Label | Dashed |
|---|---|---|---|
| `e-surfaces-gate` | surfaces → gate | message in | no |
| `e-gate-context` | gate → context | assemble | no |
| `e-gate-facts` | gate → facts | only if needed | yes |
| `e-gate-episodes` | gate → episodes | only if needed | yes |
| `e-gate-persona` | gate → persona | only if needed | yes |
| `e-context-model` | context → model | prompt | no |
| `e-model-tools` | model → tools | act | no |
| `e-tools-model` | tools → model | observe | no |
| `e-model-reply` | model → reply | answer | no |
| `e-reply-surfaces` | reply → surfaces | reply out | no |
| `e-reply-record` | reply → record | save | no |
| `e-reply-consolidation` | reply → consolidation | saved chats | yes |
| `e-consolidation-facts` | consolidation → facts | distill | no |
| `e-record-observability` | record → observability | read | no |
| `e-record-cost` | record → cost | price | no |

## 4. Event map

The keys are exactly the product's recorded trajectory vocabulary. An unknown type is not in the
map and is handled by `live-feed.md` §5.

| Event type | Nodes | Edges | Status label | Condition |
|---|---|---|---|---|
| `turn_start` | `surfaces` | `e-surfaces-gate` | message in | — |
| `gate` | `gate` | `e-gate-context` | memory decision | `decision == retrieve` adds `facts`, `episodes`, `persona` and the three `e-gate-*` edges; `skip` leaves them dark |
| `llm` | `context`, `model` | `e-context-model` | model reasons | `kind == final` changes the label to `final answer` |
| `tool` | `tools` | `e-model-tools`, `e-tools-model` | tool runs | `ok == false` marks the tool `failed` |
| `consolidation` | `consolidation`, `facts` | `e-consolidation-facts` | memory written | — |
| `receipt` | `cost`, `record` | `e-record-cost` | costed | — |
| `error` | the failed stage's node | — | failed | `stage`: `gate`→`gate`, `llm`→`model`, `tool`→`tools`, `consolidation`→`consolidation` |
| `turn_end` | `reply`, `record` | `e-model-reply`, `e-reply-surfaces`, `e-reply-record` | reply | — |

The event map is a JSON object with the same keys:

```json
{
  "turn_start": {"nodes": ["surfaces"], "edges": ["e-surfaces-gate"], "label": "message in"},
  "gate": {
    "nodes": ["gate"], "edges": ["e-gate-context"], "label": "memory decision",
    "retrieve": {"nodes": ["facts", "episodes", "persona"],
                 "edges": ["e-gate-facts", "e-gate-episodes", "e-gate-persona"]}
  },
  "llm": {"nodes": ["context", "model"], "edges": ["e-context-model"], "label": "model reasons",
          "final_label": "final answer"},
  "tool": {"nodes": ["tools"], "edges": ["e-model-tools", "e-tools-model"], "label": "tool runs"},
  "consolidation": {"nodes": ["consolidation", "facts"],
                    "edges": ["e-consolidation-facts"],
                    "label": "memory written"},
  "receipt": {"nodes": ["cost", "record"], "edges": ["e-record-cost"], "label": "costed"},
  "error": {"nodes": [], "edges": [], "label": "failed",
            "stage_nodes": {"gate": "gate", "llm": "model", "tool": "tools",
                            "consolidation": "consolidation"}},
  "turn_end": {"nodes": ["reply", "record"],
               "edges": ["e-model-reply", "e-reply-surfaces", "e-reply-record"],
               "label": "reply"}
}
```

The three condition shapes are the whole rule set: the `retrieve` object is applied only when
`event.decision == "retrieve"`; a tool's `failed` state is applied only when `event.ok == false`;
`stage_nodes` selects the failed node from `event.stage`. No other conditional language exists.

## 5. Invariants (tested)

1. Group, node and edge ids are unique.
2. Every edge's `source` and `target` exist; no self-loop.
3. Every node's `destination` is in the allowed set.
4. Every node and group box is inside the 1040 × 680 viewBox and inside its group.
5. No node or edge id contains a retired capability name or an eval/release name.
6. The event map keys equal the recorded vocabulary
   `turn_start, gate, llm, tool, consolidation, receipt, error, turn_end`.
7. Every node and edge referenced by the event map exists in the graph.
8. Every node has a non-empty summary on an empty home and on a populated home.
9. The graph returned by `GET /api/map` is a deep copy; a caller cannot mutate module state.
10. `test_map.py` fails if any of the above changes without the test changing.
