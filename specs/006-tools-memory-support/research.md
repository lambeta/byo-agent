# Research: Working Tools & Memory in the Dashboard

**Date**: 2026-11-19 | **Spec**: [spec.md](spec.md)

All unknowns were resolvable from repository source and the waku reference checkout; no
external research was needed. Findings are grouped as root causes (why the symptoms
happen) and decisions (how the fix is shaped).

## Root causes (confirmed by code inspection)

### RC-1: Memory view renders "Undefined"

`byo/ops/static/js/dock.js` — `memoryView()` begins with:

```js
return
    '<div class="grid">' + ...
```

JavaScript's automatic semicolon insertion turns `return`-newline into `return;`, so the
function returns `undefined`; `main.js` assigns it to `innerHTML`, which stringifies to
the text "Undefined". Matches the reported symptom exactly.

### RC-2: Tools node click is a silent no-op

`byo/ops/map.py` gives the `tools` node `"destination": "turn"`. `mapNodeClick` then
calls `mapOpenSelected()`, which — when no turn exists in the selected window — only
writes a one-line status message ("No turn yet — send a message to start one."). No
navigation, no panel; to the person clicking, nothing happens.

### RC-3: The coverage gap that let both ship

- Every dashboard test constructs `Agent(..., memory=None)` — memory is disabled in all
  dashboard-path tests.
- No test renders a view function: `test_map_static.py` asserts JS *symbols exist as
  strings*, so a function that returns `undefined` passes.
- Result: two surface defects survived a 223-test green suite.

## Decisions

### D-1: Fix `memoryView` and restructure Memory into waku-style sections

- Decision: repair the return statement; render the Memory view as sections — gate
  overview (retrieve/skip counts), facts, episodes, consolidation status — following
  waku's `#memory/*` organization, minus retired capabilities (skills, soul file editor).
- Rationale: the user explicitly chose waku's interaction model; byo already stores every
  datum these sections need (facts/episodes tables, gate + consolidation events in the
  trajectory, pending-row count in `consolidation_mod`).
- Alternatives considered: minimal fix only (repair the return, keep the flat layout) —
  rejected: it closes the crash but not the "memory 正常工作" visibility the feature asks
  for, and the user picked the waku interaction model.

### D-2: Add a dedicated Tools view; Tools node navigates to it

- Decision: new hash route `#tools` rendering (a) **Available** — one card per tool with
  name, description and input schema, taken from the live registry — and (b) **Results** —
  recent tool-call outcomes read from the recorded trajectory, with an explicit empty
  state. `map.py` changes the Tools node destination `turn` → `tools`; `mapNodeClick`
  routes `tools` → `#tools`.
- Rationale: this is waku's `#tools` view (Available + Results tabs), reduced to byo's
  retired-MCP/hooks/Apple reality; it replaces the silent no-op with a view that directly
  answers "what can the agent do, and what did its tools do".
- Alternatives considered: keep `destination: "turn"` and only add a loud empty state —
  rejected by the user's clarification. Port waku's MCP/hooks tabs — rejected: spec 001
  retired those capabilities; out of scope.

### D-3: One read-only API for tools; extend the memory payload

- Decision: `GET /api/tools` returns `{ tools: [{name, description, input_schema}],
  results: [recent tool events from the trajectory] }`. `GET /api/memory` gains
  `gate` (retrieve/skip counts from trajectory events) and `consolidation` (pending
  count, threshold, last run) fields. No writes added; `POST /api/memory` unchanged.
- Rationale: the registry and the trajectory are the two sources of truth the views must
  project; both are already in-process for the dashboard server.
- Alternatives considered: render the catalog from a static list duplicated in JS —
  rejected: two sources of truth would drift; the registry already knows the truth.

### D-4: Close the coverage gap in the existing static style — no Node test harness

- Decision: extend the deterministic suite with (a) dashboard-path tests that build the
  agent **with memory enabled** and drive a turn through `/api/chat` + `/api/chat/stream`,
  (b) `/api/tools` contract tests, (c) Memory API round-trip tests asserting store/mirror
  consistency, and (d) static source-contract tests: every view function referenced by
  `main.js` is defined; no view builder has a bare `return` immediately followed by a
  newline (the RC-1 pattern); nav links, routes in `main.js`, and map destinations agree.
- Rationale: matches the repo's existing test idiom (Python assertions over source +
  stdlib HTTP round-trips), keeps the default test path dependency-free, and each fixed
  bug adds a regression case as the constitution requires.
- Alternatives considered: execute the JS views under Node in tests — rejected: it adds a
  second toolchain to the default test path for marginal gain over source contracts plus
  API round-trips; the dependency budget argues against it. (Documented here per the
  constitution's rejected-alternative duty.)

### D-5: Node destination map (post-fix)

| Node | Destination after fix |
|------|-----------------------|
| chat / session | chat dock (existing) |
| gate, facts, episodes, consolidation (memory group) | `#memory` (existing route, fixed view) |
| model / loop / reply | turn detail (existing byo behavior — not reported broken) |
| **tools** | **`#tools` (new)** |
| trajectory / observability group | `#observe` (existing) |

- Rationale: only the Tools destination changes; every other node already navigates
  somewhere visible. FR-003a's "every node navigates to its own view" is satisfied as:
  every click produces navigation or a visible panel — verified by the static
  destination/route consistency test.
