# Implementation Plan: Agent Execution Visualization

**Branch**: `002-execution-flow-visualization` | **Date**: 2026-11-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-execution-flow-visualization/spec.md`

**Reference**: `~/Projects/Private/waku-agent` — read-only input for the Overview anatomy (the map,
the stage lighting and the per-turn detail behind it). No brand asset or implementation is copied.

## Summary

Add a data-driven runtime architecture map to the dashboard as its landing view. The map shows the
parts this product actually has — surfaces, memory gate, working context, loop, tools, memory,
trajectory and the runtime operations views — and lights up as a turn runs, whether the turn came
from the browser or the terminal. A secondary drill-down opens the selected turn's timeline,
summary, hotspots and raw records behind the map.

The implementation is additive: a server-owned graph description and event map, a live player that
polls the existing trajectory feed, two new read-only endpoints for the map and one turn, and plain
SVG/JS/CSS with no build step. The trajectory schema and the database schema stay unchanged; every
existing route keeps its contract, and the feed gains one additive `skipped` count. The map and its
detail are projections, not a second store.

## Technical Context

**Language/Version**: Python >= 3.11 (same floor as this repository), standard library
`http.server`, `sqlite3`, `json`, `threading`; current development virtualenv is 3.14.

**Primary Dependencies**: none added. The four existing runtime dependencies (`anthropic`,
`openai`, `python-dotenv`, `rich`) and the `pytest`/`ruff` dev extras stay as they are. The
front end remains classic `<script>` files served from `byo/ops/static/` — no bundler, no package
manager, no CDN, no chart library.

**Storage**: no new tables and no new files. The map reads counts from the existing `state.db`
(`facts`, `episodes`, `chat_log`) and the existing `trajectories/YYYY-MM-DD.jsonl` files. The
turn detail and its raw record are projections over those files. Nothing is cached in a new store.

**Testing**: `pytest` under `evals/deterministic/` with temporary homes and golden trajectory
fixtures; new deterministic tests for map integrity, the event map, the map API, the turn detail,
summary/hotspots, static assets and the 200-turn scale. Browser behaviour (lighting order,
keyboard, reduced motion, responsive layout) is verified by the quickstart checklist — there is no
JS test runner in this project and this feature does not add one.

**Target Platform**: macOS 13+ and Linux, one user account, `127.0.0.1` only, one dashboard
process; the terminal and the dashboard may run in separate processes against the same home.

**Project Type**: single project — an installable Python package with a locally served, plain static
web UI. The map, live player and detail live inside the existing dashboard; there is no frontend
project.

**Performance Goals**: with 200 turns in a 7-day window and a turn of 20 steps, a newly recorded
step reaches the map within 1 s, a turn detail opens within 1 s, and expanding a step completes
within 100 ms on the development laptop. The live poll runs at most twice per second; the map's
static graph renders once and only node states/summaries change. The 200-turn payload stays below
200 ms on the same machine.

**Constraints**: no new runtime dependency; no browser build step; no chart or graphics service; no
new trajectory event type, database table or parallel turn store; loopback only; all displayed
values are projections of the recorded trajectory; redaction/truncation already applied at the sink
is preserved; no reference brand asset, font or illustration is copied; the reference checkout is
never modified; the offline suite must keep passing with no network.

**Scale/Scope**: one local user, two surfaces (terminal and dashboard), a 13-node/15-edge map,
four node groups, one live turn at a time, 200 turns / 20 steps in the target window, two new
read-only endpoints, two new static scripts and one new stylesheet section. No new configuration
knob is required; the existing `BYO_*` settings and 7-day window default are reused.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Evidence |
|---|---|---|
| I. Build From Primitives | PASS | The map definition, event map, live player, SVG rendering and detail projection are source in this repository. There is no graph library, UI framework or orchestration addition; the only dependencies remain leaf transports. Each new module carries a design note naming its mechanism and a rejected alternative. |
| II. Provider-Agnostic Model Boundary | PASS | No file under `byo/loop/` or `byo/loop/adapters.py` changes. The map reads recorded turns and local counts; it never calls a model or branches on a provider. |
| III. Small Modules With Narrow Contracts | PASS | `byo/ops/map.py` owns the graph, summaries and event map; `byo/ops/turn_detail.py` owns one-turn projection, summary, hotspots and raw records; `dashboard.py` only routes; `map.js` renders and navigates; `live.js` polls and plays. Each is importable/testable alone; the contracts are written under `contracts/`. |
| IV. Observable by Default | PASS | The visualization consumes the always-on trajectory; it adds no event type and no second store. Every map claim is traceable to a raw record, and `/api/turn` exposes that record read-only. Redaction stays at the sink, so the API cannot unredact. |
| V. Eval-Driven Behavior Change (NON-NEGOTIABLE) | PASS | The feature changes no prompt, tool description, loop or memory policy. It adds deterministic tests for the map graph, event coverage, summaries, hotspots, API payloads, error states, redaction and scale; the visual/live checklist is in `quickstart.md`. Existing golden trajectories are reused, and no baseline score can move because the loop is untouched. |

**Additional constraints check**: dependency count unchanged; no front-end build step; tests run
offline; loopback bind only; no credential is returned by either new endpoint; no brand asset is
copied; the map has no node for a retired capability or for the command-line eval/release tools.

No violations.

## Project Structure

### Documentation (this feature)

```text
specs/002-execution-flow-visualization/
├── plan.md              # this file
├── research.md          # Phase 0: decisions, rationale, rejected alternatives
├── data-model.md        # Phase 1: map graph, read models, states, validation
├── quickstart.md        # Phase 1: runnable validation scenarios
├── contracts/
│   ├── map-graph.md     # node/edge/destination/event-map invariants
│   ├── map-api.md       # GET /api/map, GET /api/turn, feed usage
│   ├── turn-detail.md   # timeline grouping, summary, hotspots, raw record
│   └── live-feed.md     # cursor polling, queue, coalescing, reconnect
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # Phase 2 output (/speckit-tasks), not created here
```

### Source Code (repository root)

```text
byo/
├── ops/
│   ├── map.py                    # [new] graph, groups, event map, node summaries
│   ├── turn_detail.py            # [new] one-turn projection, summary, hotspots, raw
│   ├── dashboard.py              # [modified] GET /api/map, GET /api/turn; additive feed skipped count
│   ├── observability.py          # unchanged read models reused
│   └── static/
│       ├── index.html            # [modified] Overview nav first; load map/live scripts
│       ├── style.css             # [modified] map, states, detail drawer, responsive, motion
│       └── js/
│           ├── api.js            # unchanged fetch/SSE helper
│           ├── render.js         # [modified] canonical stage vocabulary on the card; helpers reused by the detail
│           ├── observe.js        # unchanged Observability page
│           ├── map.js            # [new] map SVG, node states, text list, turn list, detail
│           ├── live.js           # [new] /api/events polling, mapping, queue, catch-up
│           ├── dock.js           # unchanged memory/settings views
│           └── main.js           # [modified] #overview default, map refresh/mount/unmount
└── (loop/, memory/, runtime/, tools/, gateway/ unchanged)

evals/
├── deterministic/
│   ├── test_map.py               # [new] graph integrity, destination, event coverage, summaries
│   ├── test_map_api.py           # [new] /api/map, /api/turn, windows, active turn, 404
│   ├── test_turn_detail.py       # [new] summary, hotspots, raw, failure, unfinished
│   ├── test_map_static.py        # [new] shell, scripts, no external/build asset
│   └── test_map_scale.py         # [new] 200 turns / 20 steps payload budget
└── fixtures/trajectories/        # existing golden and reference fixtures reused

```

**Structure Decision**: single project. The feature is a new pair of operations modules plus a
new pair of static scripts inside the existing dashboard; the terminal, loop, memory and adapters
are untouched. Keeping the map definition in Python means the graph, node links and event mapping
can be tested without a browser, and the JavaScript remains a renderer rather than a second source
of truth. Keeping the detail in its own module avoids growing `dashboard.py` into a view layer and
keeps the existing Observability payload independent.

## Complexity Tracking

None. The map is data-driven rather than a hand-maintained SVG, which removes a class of drift
rather than adding a layer; there is no fourth project, no new dependency and no new service.

## Phase 0: Outline & Research

Complete — see [research.md](research.md). Every Technical Context field is resolved; no
unresolved clarification remains. The decisions that shape the structure are:

- **R1 Map source of truth** — a server-owned graph in `byo/ops/map.py`, rendered from data, rather
  than a hand-authored SVG that can drift from the product.
- **R3 Live feed** — cursor polling of the existing `/api/events`, because the terminal is a
  separate process and an in-process SSE stream cannot see its turns.
- **R5 Event mapping** — one server-owned `EVENT_MAP` for the eight recorded event types, with
  conditional additions for a retrieval and a failed tool, tested against the trajectory vocabulary.
- **R6 Turn detail** — a new single-turn `GET /api/turn` rather than shipping every turn's steps to
  the map and filtering in the browser.
- **R8 Accessibility** — SVG nodes with button roles and a text alternative beside a status live
  region, not a canvas and not a colour-only state.
- **R10 Testing** — deterministic Python tests for every data claim plus a browser quickstart for
  animation, keyboard and responsive behaviour; no JS test runner is added.

## Phase 1: Design & Contracts

Complete — the artifacts below are generated beside this plan:

- [data-model.md](data-model.md) — the map graph, node/edge fields, node states and transitions,
  the turn-detail read model, summary/hotspot rules, data sources and validation.
- [contracts/map-graph.md](contracts/map-graph.md) — the node set, edges, destinations, event map
  and the invariants a test enforces.
- [contracts/map-api.md](contracts/map-api.md) — `GET /api/map`, `GET /api/turn`, feed usage,
  payloads, windows, error codes and the additive relationship to the v1 dashboard contract.
- [contracts/turn-detail.md](contracts/turn-detail.md) — timeline grouping, start/duration
  derivation, summary format, hotspot indexes and the raw-record rules.
- [contracts/live-feed.md](contracts/live-feed.md) — cursor lifecycle, initial replay, queue,
  coalescing, reconnect and the one-second lag bound.
- [quickstart.md](quickstart.md) — the map, live lighting from both surfaces, detail, failure and
  unfinished states, accessibility, scale and offline checks.

No database migration and no trajectory version bump are generated, because none is needed: the
existing record already carries every value the map and detail show.

## Constitution Check (post-design)

Re-evaluated against the artifacts above. Verdicts unchanged: I–V all PASS.

- The graph and event map are source, not configuration in a framework; the live player is a small
  polling loop and a queue.
- No loop, adapter, tool, memory or context file changes; the provider seam is untouched.
- `map.py` and `turn_detail.py` have one job each, and `map.js`/`live.js` split rendering from
  live sequencing. Every data claim has a contract and a test.
- The raw record remains reachable, and the map adds no event type or store; redaction is still the
  sink's responsibility.
- The offline suite remains the bar; the new tests run against temporary homes and fixtures with no
  network or credentials.

One spec precision was carried into design: "runtime map" means the four runtime groups, so the
command-line eval/release tools are deliberately absent from the graph, the event map and the
tests' expected node set (spec Clarifications, Assumptions; SC-011).

## Risks and Sequencing Notes

- **Highest risk: live lighting fidelity.** The map must light the right node for a CLI turn and
  survive a burst. Mitigation: server-owned event map, a fixture-backed test that walks every event
  type, a scripted two-tool turn for the queue, and the quickstart's terminal-plus-browser scenario.
- **Second: accessibility of a graph.** SVG nodes can be mouse-only if built carelessly. Mitigation:
  focusable button roles, a text alternative that mirrors every state, a status live region, and
  the quickstart's keyboard-only path.
- **Third: visual legibility at 1024 px / 200% zoom.** Mitigation: a fixed viewBox in a scrollable
  container, a text list fallback, and a stacked detail panel on narrow screens; the quickstart
  checks both widths.
- **Fourth: polling cost at the target scale.** The existing 7-day read is O(turns) per poll; at 200
  turns it is small, and `test_map_scale.py` guards the budget. If a real home outgrows it, a
  tail-read cursor can be added inside `observability.read_events` without changing this contract.
- **Sequencing.** Build the graph and summaries first (no UI), then the two endpoints, then the
  static map and detail, then the live player, then the accessibility/responsive pass. This order
  lets every server claim be tested before any animation exists.
