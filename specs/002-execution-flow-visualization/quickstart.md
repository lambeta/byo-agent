# Quickstart — validation scenarios

**Feature**: Agent Execution Visualization · **Date**: 2026-11-18

These scenarios prove the map, its lighting and its detail end to end. The offline group needs no
network or key; the browser group needs one provider key because it runs real turns. Contracts live
in [`contracts/`](contracts/); the data rules are in [`data-model.md`](data-model.md).

## 0. Prerequisites

- macOS or Linux, Python >= 3.11, `uv` installed.
- One provider key for the browser scenarios (`BYO_API_KEY`, or `BYO_PROVIDER` plus the matching
  key). The offline group does not need it.
- A clean home is recommended for the first run: `export BYO_HOME=/tmp/byo-map-home`.
- The dashboard reads static files on every request, but Python changes need a restart of
  `byo dashboard`. Restart after pulling code.

```bash
uv venv && uv pip install -e ".[dev]"
```

## 1. Offline checks (SC-002, SC-003, SC-005, SC-006, SC-007, SC-011, SC-012)

```bash
make eval     # the deterministic suite, no network, no key
make gate     # the same checks, one line each, non-zero on failure
make lint
```

Pass when every target is green, including the new map, detail and scale tests. The map tests pin
the graph invariants, the event coverage, the summary and hotspot rules, both endpoints, the raw
record, the failure/unfinished states and the 200-turn budget.

## 2. The map is the landing view (FR-001 to FR-008, SC-011)

```bash
export BYO_API_KEY=...
uv run byo dashboard        # → http://127.0.0.1:7777
```

Pass when:

- the dashboard opens on **Overview**, the new nav item is first, and Chat/Memory/Observability/
  Settings are still reachable;
- the map shows 13 nodes in four groups: Surfaces; Harness (Memory gate, Working context, Model,
  Tools, Reply); Memory (Fact memory, Episodes, Persona, Consolidation); Operations (Trajectory,
  Observability, Spend);
- **no** evals/release node and no retired voice/graph/MCP/hosted node is present;
- the status line says the agent is idle;
- every node has a one-line summary (model id, counts, spend, etc.) and no empty node;
- clicking Surfaces opens Chat, Working context opens the session/history, Memory gate and the
  memory nodes open Memory, the Loop/Tools/Reply nodes open the selected turn's detail, Trajectory
  and Spend open Observability;
- the text view under the map lists every node with the same state and destination.

## 3. A dashboard turn lights the map (FR-009 to FR-014, SC-002, SC-004)

With the map open, type in the dock: `book a catch-up with Alex on Friday`.

Pass when:

- the view stays on Overview; it does **not** jump to the Chat card;
- the status line advances through `message in`, `memory decision`, `model reasons`,
  `tool runs`, `costed` (where a receipt is recorded), `memory written` (where consolidation ran)
  and `reply`;
- Surfaces, the gate, Working context, Model, the tool node, Reply and Trajectory light in the
  recorded order; a node not involved in the turn never lights;
- the highlighted stage and the node's visible state word agree;
- after the turn ends the map holds the final state for 0.5–2 s, then returns to idle; the node
  summaries and the recent-turn list reflect the new turn;
- the same turn appears in the detail (scenario 5).

Then send `what is 2 + 2?`. Pass when the gate records **skip**, the memory nodes stay dark, and
the rest of the path still lights. Send a question that needs a remembered fact: pass when the gate
records **retrieve** and the memory path lights.

## 4. A terminal turn lights the same map (FR-011, FR-012, SC-004, SC-010)

Keep the dashboard open on Overview. In a second terminal:

```bash
uv run byo
# ask: what is on my calendar on Friday?
```

Pass when:

- the open map lights within two seconds without a refresh;
- the status names the **cli** surface, not the dashboard;
- the path and the turn appear in the recent-turn list;
- opening the same map in a second tab lights the same sequence; neither tab blocks the turn;
- closing the tab mid-turn does not cancel or slow the terminal turn; reopening shows the
  completed turn.

## 5. The detail tells the timed story (FR-015 to FR-021, SC-003, SC-008)

Click the Loop, Tools or Reply node, or a recent-turn entry.

Pass when:

- the detail opens beside/below the map, the map stays visible, and closing it returns to the same
  map state;
- the header shows the one-line summary (for example
  `question → memory retrieved → 2 model calls · 1 tool · 6.8 s · $0.0075`);
- the timeline uses one shared axis, one row per loop, tool calls nested under the loop that
  requested them, then the reply, any memory write and the receipt;
- model bars start at their recorded end minus duration and are proportional; the gate and other
  instant steps are minimum markers labelled `not timed`;
- the slowest and most expensive rows carry text badges and match the receipt;
- opening a step shows its recorded arguments/input, output preview, duration, outcome, model,
  tokens, stop reason and cost; a truncated value says it is truncated;
- the raw record opens read-only and contains the turn's events in order;
- changing the window (Today / 7 days / All) changes the turn list and keeps the detail selection
  when the turn is still in range.

## 6. Failure, unfinished and empty states (FR-007, FR-008, FR-022, FR-024, SC-005)

The deterministic fixtures cover these without a key:

```bash
uv run pytest -q evals/deterministic/test_turn_detail.py -k "failed or unfinished"
uv run pytest -q evals/deterministic/test_map_api.py -k "unknown or empty"
```

Pass when the tests show:

- a failed model call marks the failing node/row and leaves later rows `not reached`;
- a recovered tool error keeps the tool failed while the reply still renders and the turn is
  complete;
- an unfinished turn shows a `partial` last row, no invented reply and no invented cost;
- an unknown event type is named in the status and appears as a generic raw row without breaking
  the rest;
- an empty home renders the full map with idle summaries and a how-to-start hint.

For a browser view of recorded history, point a throwaway home at the golden fixture and start
the dashboard with a dummy key; the map is idle, the turn is in the list, and its detail renders the
recorded turn. The unfinished and failed variants are covered by the tests above:

```bash
export BYO_HOME=/tmp/byo-map-history
mkdir -p "$BYO_HOME/trajectories"
cp evals/fixtures/trajectories/golden-cli.jsonl "$BYO_HOME/trajectories/2026-11-18.jsonl"
BYO_API_KEY=dummy uv run byo dashboard
```

## 7. Keyboard, zoom and reduced motion (FR-026, FR-028, SC-012)

- Unplug the mouse: Tab reaches every map node and the text-view links; Enter/Space opens the
  destination; the focus ring is visible; the status line is announced.
- Zoom the browser to 200% at a 1024 px window: the map pans/scrolls without clipping labels, the
  text view is usable, and the detail stacks below.
- Set the OS/browser to reduced motion: the sequence becomes an immediate state change; the status
  line and state words still tell the story; nothing depends on animation.

## 8. Restart, history and raw traceability (FR-020 to FR-025, SC-009)

1. Run two turns (one from the dashboard, one from the terminal).
2. Stop and restart `byo dashboard`; reopen Overview.
3. Pass when the map is idle, both turns are in the recent-turn list, both details render from the
   trajectory, and the raw record matches the file lines. Nothing is lost with the process.
4. Open a trajectory file in an editor, add a deliberately corrupted line between two turns, and
   reload. Pass when the bad line is counted/reported and every other turn still renders.

## 9. Scale (SC-006)

```bash
uv run pytest -q evals/deterministic/test_map_scale.py
```

Pass when the 200-turn / 20-step fixture builds the map and one detail within the test's budget and
the summary/hotspot values remain exact. For the browser, use the development laptop and the same
fixture; the target is a step visible within 1 s, detail open within 1 s, and step expansion within
100 ms.

## 10. Secrets (SC-007)

```bash
grep -r "sk-" "$BYO_HOME/trajectories/" && echo LEAK || echo CLEAN
uv run pytest -q evals/deterministic/test_redaction.py
```

Pass when the trajectory is clean, the redaction tests pass, and neither the map nor the detail
shows a key-shaped value. The raw view shows only what the sink wrote.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Overview is blank | `/api/map` failed | check the browser console/network tab, then restart the dashboard; the route should return JSON, not HTML |
| The map does not light for a terminal turn | the dashboard is looking at a different home | both processes must share `BYO_HOME` |
| The map stays lit after a turn | a stale tab, or the hold is in progress | wait 2 s; reload; check the status line for `reconnecting` |
| Detail says `no such turn` | the turn is outside the selected window | switch to 7 days/All, or open a turn from that window |
| Node link does nothing | the destination view is not loaded | check the console; the map must report the missing destination in place |
| Numbers disagree | a stale process | restart the dashboard; node summaries and detail are projections, not cached |
| 200-turn test slow on CI | shared machine | re-run on the development laptop; the budget is specified there |

## Definition of done for this quickstart

The offline group is green, the browser group shows the map lighting for both surfaces, the detail
reproduces a recorded turn exactly, the failure/unfinished/empty states are honest, the keyboard and
reduced-motion paths work, and a restart loses nothing.
