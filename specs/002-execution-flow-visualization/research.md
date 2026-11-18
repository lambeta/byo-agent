# Research — Phase 0 decisions

**Feature**: Agent Execution Visualization · **Date**: 2026-11-18

Every Technical Context field in [plan.md](plan.md) is resolved; no unresolved clarification
survived the specification and the two clarification answers (map primary, runtime-only map). Each decision
below names what was chosen, why, and what was rejected — the constitution requires that "why" to
sit next to the "how". The read-only reference at `~/Projects/Private/waku-agent` informed the
anatomy (its `diagram.js`, `render.js` stage strip and `observe.js` waterfall); no reference code or
asset is copied.

---

## R1. The map's source of truth

**Decision**: `byo/ops/map.py` owns the graph as Python data: groups, nodes (id, label, group, shape,
layout box, summary key, destination), edges (id, source, target, label, dashed) and the event map.
`GET /api/map` serves that data plus freshly computed node summaries; the browser renders it and
never keeps a second hand-written copy. Tests assert unique ids, valid edge endpoints, valid
destinations and coverage of the trajectory vocabulary.

**Rationale**: FR-002, FR-003, FR-033 and SC-011 require the map to be the product's real parts, with
no retired or command-line-only nodes, and every node link resolving. A data structure can be
validated in a unit test; a hand-authored SVG cannot. The reference's own `archSVG` is byte-frozen
and its README warns that the node ids and the `STAGE` map must be changed together — a drift hazard
this project can avoid because the whole app is ours.

**Alternatives considered**: a frozen inline SVG (rejected: visual edits and route changes can drift
silently; the reference already carries this warning); defining the graph only in JavaScript
(rejected: no Python test can assert destinations or retired-node absence); generating the graph
from module introspection at request time (rejected: brittle, and the architecture is deliberately
smaller than the module tree).

## R2. Rendering medium and accessibility

**Decision**: render the map as an SVG scene generated from the graph data, with each node a
`<g role="button" tabindex="0">` carrying a visible label, a visible state word and an evolving
`aria-label`. Group panels and edges are `aria-hidden`. Beside the scene, a native `<details>` text
view lists every node with its state, summary and destination as real links/buttons. The status line
is a `role="status" aria-live="polite"` region. CSS honours `prefers-reduced-motion`.

**Rationale**: SVG draws labelled directed edges without a dependency, scales with a viewBox, and
matches the reference's visual grammar. The text alternative plus button roles addresses FR-008,
FR-028 and SC-012 without pretending SVG is fully accessible on its own. A canvas would be
unreadable to assistive technology; a pure HTML/CSS grid makes crossing edges and the loop cycle
hard to draw.

**Alternatives considered**: canvas (rejected: no DOM semantics, no focus, no text alternative);
HTML nodes with a CSS grid and SVG connectors (rejected: two coordinate systems and fragile edge
routing for the loop); a third-party graph library (rejected: new dependency and a build-ish
surface for a diagram this small).

## R3. Live feed: polling the existing trajectory endpoint

**Decision**: the live player polls `GET /api/events?cursor=<int>` every 500 ms and advances an
integer cursor. The cursor counts records over the existing 7-day read. `GET /api/map` returns the
current cursor and the active turn's already-recorded raw events so a viewer joining mid-turn can
replay what it missed.

**Rationale**: the terminal and the dashboard are separate processes; the dashboard's SSE stream
only carries turns that process started. The trajectory file is the one feed every surface writes,
so polling it is the only mechanism that satisfies FR-011 (any surface, labelled) and FR-012
(read-only multi-viewer). At the target scale the 7-day read is small (200 turns × ~6 records), and
the endpoint already exists and is tested. The reference uses the same cursor-polling shape for its
map animation.

**Alternatives considered**: SSE only (rejected: cannot see terminal turns); a WebSocket or a
server-sent broadcast (rejected: a second transport and still blind to the other process); a file
watcher (`watchdog`/inotify) (rejected: platform-specific dependency and more moving parts than a
poll at the target scale); a new database event table (rejected: a second store, forbidden by
FR-025).

## R4. Cursor lifecycle, replay and catch-up

**Decision**: `/api/map` returns `cursor` (the 7-day record count) and `active` (the newest turn if
unfinished, plus its raw events). On load the player starts from the map's cursor and replays the
active turn's raw events in order. Each poll appends new events to a queue. The player shows one
highlight every 450–650 ms; if the queue is longer than 8 events or the oldest queued event is more
than 2 s old, it drops intermediate highlights, applies the latest complete state, and the status
line says "caught up". A failed poll sets "reconnecting" and retries on the next tick; a reconnect
resumes from the last cursor.

**Rationale**: FR-013 requires no silent drops and no more than one second of lag; FR-030 requires a
visible stale state and a catch-up. Replaying the active turn is what FR-011 means for a viewer who
joins mid-turn. The queue and timer are small enough to reason about and are checked manually in the
quickstart.

**Alternatives considered**: re-read all events on every page load and animate them (rejected:
animates history and duplicates); a server-side "current highlight" state (rejected: a second status
model, and it cannot serve two viewers at different read speeds); skipping the active turn on load
(rejected: a viewer who opens the map mid-turn would see nothing until the next event).

## R5. Event-to-node mapping

**Decision**: `EVENT_MAP` in `byo/ops/map.py` covers `turn_start`, `gate`, `llm`, `tool`,
`consolidation`, `receipt`, `error` and `turn_end`, plus the conditional additions for a
`retrieve` gate and the `stage` field of an `error`. It is served inside `/api/map`; the player
applies it, with three explicit rules the server describes: `gate.when.decision == "retrieve"` adds
the memory nodes/edges, `tool.ok == false` marks the tool failed, and `error.stage` selects the
failed node. A test asserts the map's keys equal the trajectory vocabulary and a second test walks
each event type to the expected ids.

**Rationale**: FR-009 and FR-010 require a total, correct mapping; keeping it in Python makes it
testable and keeps the browser a renderer. The three conditions are small enough to be stated in the
contract rather than building a rule engine.

**Alternatives considered**: a JavaScript `switch` (rejected: the only place the vocabulary is
tested would be a manual browser check); a generic rule language (rejected: unnecessary machinery for
three conditions); server-side per-event node resolution at poll time (rejected: duplicates the
projection and couples the feed to the current map layout).

## R6. One-turn detail endpoint

**Decision**: add `GET /api/turn?turn_id=<id>&window=today|7d|all` returning one projected turn,
its server-built summary, its hotspot indexes and its raw records. The map's turn list comes from
`/api/map` as lightweight summaries. `/api/observability` remains unchanged for the existing
Observability page.

**Rationale**: the map needs a turn list and one detail; shipping every turn's steps on every map
refresh would be wasteful and would make the detail's failure state depend on a large payload. A
single endpoint gives a clear 404 for a missing/out-of-window turn and bounds the raw record to one
turn. It is additive: no v1 route or payload changes.

**Alternatives considered**: reuse `/api/observability?window=` and filter client-side (rejected:
large payload, no 404, and the map would carry the whole observability projection); put the full
detail in `/api/map` (rejected: every refresh pays for it); a generic query language (rejected:
overkill for one id).

## R7. Summary and hotspot rules

**Decision**: `byo/ops/turn_detail.py` builds the one-line summary from the projected turn:
`question → memory skipped|retrieved → N model call(s) · N tool(s) · duration · cost`, appending
`failed at <stage>` or `unfinished` where true. Duration is `ended_at - started_at` (or the last
record when unfinished), one decimal second; cost is the receipt's USD with `~` when it is an
estimate and "cost not recorded" when absent. `hotspots` returns the index of the maximum
`duration_ms` and the maximum `usd` among steps, ties to the earlier step, `null` when there is no
candidate.

**Rationale**: FR-016/FR-017 and SC-003/SC-008 require exact, consistent numbers; computing them
once on the server makes the map, the list and the detail agree and makes them testable. The
reference's `story()` and `hotspots()` are the same idea; this is a smaller version with this
project's vocabulary.

**Alternatives considered**: build the summary in JavaScript (rejected: no Python test can pin it,
and the map/turn list would need duplicate formatters); reuse the receipt line verbatim (rejected:
it omits the gate decision and the failure/unfinished state, which are the questions the map
answers).

## R8. Timeline geometry

**Decision**: the detail uses one axis from `turn.started_at` to `turn.ended_at` (or the last step
when unfinished). A model or tool bar starts at `ts - duration_ms` and is as wide as
`duration_ms`; a gate, memory write, receipt or error is a minimum-width marker at `ts` labelled
"not timed". Rows are grouped: the gate, one row per `llm` (with the following `tool` steps nested),
then the reply at `ended_at`, the consolidation and the receipt. Failures are shown on the row
without expanding. A zero-length or missing axis falls back to record order with a minimum bar.

**Rationale**: the trajectory records the end timestamp and the duration of model/tool calls, not
their start; `ts - duration` is the only honest reconstruction and is already used by the existing
waterfall. Instant steps have no duration and must not pretend to. This satisfies FR-016 and the
"instant or unrecorded duration" edge case.

**Alternatives considered**: place every step at `ts` (rejected: overlaps long calls and hides
latency); invent a start for the gate (rejected: fabricates data); add a new `started_at` field to
the trajectory (rejected: a schema change for a value derivable from what is already recorded).

## R9. Map layout, groups and responsive behaviour

**Decision**: a fixed `viewBox` (1040 × 680) with four group panels: Surfaces, Harness, Memory and
Operations. Nodes carry a layout box; edges are computed from node centres by the renderer, so the
graph data has no path coordinates. On narrow or zoomed screens the diagram container scrolls
horizontally with a minimum width, the detail panel stacks below, and the text view is always
available. No node is placed outside the viewBox; a test checks bounds and unique ids.

**Rationale**: a fixed canvas is what makes the map readable as a picture, and computing edges from
boxes keeps the data small and the layout adjustable. The text view and horizontal scroll satisfy
the 1024 px / 200% requirement without trying to reflow a graph into a single column.

**Alternatives considered**: responsive graph reflow (rejected: complex and changes the picture's
meaning at every width); absolute pixel HTML (rejected: edges and zoom are harder); drawing only the
turn path (rejected: the chosen option B is the whole runtime map).

## R10. Testing and the 200-turn budget

**Decision**: deterministic pytest covers the graph invariants, summaries, event map, both endpoints,
summary/hotspots, raw records, failure/unfinished states, static assets and a 200-turn payload
budget. Browser-only behaviour (lighting order, focus, reduced motion, responsive scroll) is checked
by the quickstart; no JS test runner or headless browser is added. The existing 7-day read is reused
for polling; `test_map_scale.py` builds 200 turns and asserts correctness and a generous one-second
budget on the development machine.

**Rationale**: the project has no JS test infrastructure, and adding one would violate the
no-new-dependency constraint. The server-side claims — which are most of the spec's measurable
criteria — are fully testable. The scale test catches an accidental O(N²) or a payload explosion;
the manual check covers the visual 1 s/100 ms targets.

**Alternatives considered**: Playwright/Selenium (rejected: a browser automation dependency and a
second test runtime); jsdom (rejected: a Node toolchain for a no-build front end); no scale test
(rejected: the 200-turn target would be unguarded).

## R11. Landing view and the chat dock

**Decision**: the dashboard's default hash becomes `#overview`; the nav gains Overview first. The
global chat dock remains. Sending from the dock while on Overview starts the turn and keeps the map
in place (the map lights); it does not replace the view with the chat card. Sending from Chat keeps
the existing live card. The detail opens as a non-modal panel beside/below the map, with a close
button, so the map stays in view.

**Rationale**: US1's journey is "send and watch the map"; switching to Chat would hide the very
thing the story asks the person to watch. Keeping the dock means no second input or new surface.
A non-modal panel keeps the map context and avoids a focus trap around a live animation.

**Alternatives considered**: a chat-only input on Overview (rejected: duplicate input); a modal
dialog for detail (rejected: hides the map and the lighting); switching to Chat on send (rejected:
contradicts the primary view).

## R12. Unknown events, errors and stale states

**Decision**: an event type outside `EVENT_MAP` updates the status line to "unmapped step: <type>",
lights no node and is still shown as a generic row in the raw record. A failed poll or a gap shows
"reconnecting"/"catching up" in the status line and keeps the last complete node state marked
stale; the next successful poll resumes from the cursor. A missing map/turn/destination is reported
in place, never as a blank view.

**Rationale**: FR-024/FR-030 and the corresponding edge cases. The trajectory schema explicitly
requires unknown event types to render generically; the map must inherit that tolerance instead of
crashing or inventing a node.

**Alternatives considered**: a generic "other" node (rejected: advertises a part the product does
not have); dropping unknown events silently (rejected: violates "never silently dropped"); resetting
the map on a failed poll (rejected: loses the last honest state).
