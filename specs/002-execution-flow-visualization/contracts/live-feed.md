# Contract — Live feed and lighting

**Version**: 1 · **Owner**: `byo/ops/static/js/live.js` with `map.js` · **Tests**: manual quickstart; server-side mapping in `test_map.py`

The live layer turns the trajectory feed into one short highlight sequence. It never starts, stops or
changes a turn, and it never writes anything. Two viewers can run it independently against the same
home.

## 1. Load

1. `GET /api/map?window=<current window>`.
2. Render the graph from `map.groups/nodes/edges`; set every node to `idle`.
3. If `active` is present, set the status to the turn's source and replay its `events` in order
   through the same event map. This is the "joined mid-turn" path.
4. Set the cursor to the payload's `cursor` and start polling.

The active replay must not re-apply events that the first poll will return: `cursor` is after the
active turn's recorded events, so the poll starts at the next one.

## 2. Poll and queue

- Poll `GET /api/events?cursor=<last>` every 500 ms.
- On success, append `events` to a queue and advance the cursor to the response's `cursor`.
- Play one highlight every 450–650 ms (a fixed value in that range; the exact value is a CSS/JS
  constant, not a user setting).
- A highlight lasts 1 s; a node's state remains visible until the turn ends or another state
  replaces it.
- A node only moves forward in a turn. A new `turn_start` resets the graph to idle and starts the
  next turn.

## 3. Applying an event

```text
turn_start   -> surfaces + edge to gate; status "message in"; reset graph
gate         -> gate; status "memory decision";
                decision=skip -> gate "skipped", memory nodes untouched;
                decision=retrieve -> memory nodes/edges; status stays "memory decision"
llm          -> context + model; status "model reasons" or "final answer"
tool         -> tools; status "tool runs"; ok=false -> tools "failed"
consolidation-> consolidation + facts; status "memory written"
receipt      -> cost + record; status "costed"
error        -> stage node "failed"; status "failed: <stage>"; turn is failed
turn_end     -> reply + record; status "reply"; untouched nodes become "not-reached"
unknown      -> status "unmapped step: <type>"; no node lit; raw still gets the record
```

The event map in [`map-graph.md`](map-graph.md) §4 is the source of the node/edge ids. The three
conditions are exactly: `gate.decision == "retrieve"` adds memory; `tool.ok == false` marks failed;
`error.stage` selects the failed node.

## 4. Lag and catch-up

- The displayed state must never lag the record by more than 1 s.
- If the queue is longer than 8 events, or the oldest queued event is older than 2 s, drop the
  intermediate highlights and apply the latest complete state. Set the status to
  `caught up` and keep it until the next new event.
- If a poll reports `skipped > 0`, keep going and add `skipped N bad line(s)` to the status; the
  valid events in that poll are still applied.
- If a poll fails, set the status to `reconnecting`, keep the last complete node state visibly
  stale (a `data-stale` attribute and a text note), and retry on the next tick. On success, resume
  from the last cursor and clear the stale mark.
- If the map is opened after the turn ended, `active` is `null`; the map is idle and the recent
  turn list is the entry to the detail. Do not animate history.

## 5. Turn end and reset

- On `turn_end`, hold the final state for 0.5–2 s, then reset nodes to idle. The last turn's
  summaries stay in the node summary line and the turn list.
- If a new turn starts before the hold ends, the new turn takes over immediately; no stale
  highlight remains.
- The status line is a `role="status" aria-live="polite"` region. The text alternative list and
  each node's `aria-label` carry the state in words.

## 6. Reduced motion and accessibility

- With `prefers-reduced-motion: reduce`, highlights are applied immediately; the sequence and the
  status line still convey the order. No animation is required to understand the turn.
- The map is operable by keyboard: nodes are focusable buttons; Enter/Space opens the destination.
- The text alternative is the same graph as a list of nodes with state, summary and destination; it
  updates with the map.

## 7. Lifecycle

- Polling starts when the Overview view is mounted and stops when the user leaves it or the tab is
  hidden (the browser's `visibilitychange` pauses; returning resumes from the last cursor).
- A second tab runs its own cursor; the two do not share state and neither blocks the server.
- Closing the tab ends only that viewer; the turn continues and its trajectory is complete.

## 8. Manual checks

1. Start the dashboard, open Overview, send a tool-using message from the dock: the map stays
   visible and lights in order.
2. Start a turn in the terminal with the map open: the map lights and the status names `cli`.
3. Open Overview mid-turn: the already-recorded steps replay, then new steps continue.
4. Run two tabs: both light the same sequence; neither blocks the turn.
5. Kill the dashboard mid-turn and restart: the completed turn is in the list and detail; the map
   is idle, not stuck live.
6. Force a feed gap (close the laptop, reopen): the status says reconnecting/caught up and the map
   catches the latest state rather than replaying every old step.
7. Keyboard-only: tab to every node, open a destination, read the text list.
8. Reduced motion: the sequence is still readable, with no motion.
