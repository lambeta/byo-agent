# Implementation Plan: Working Tools & Memory in the Dashboard

**Branch**: `006-tools-memory-support` | **Date**: 2026-11-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-tools-memory-support/spec.md`

## Summary

Two observed dashboard defects — the Memory view renders "Undefined", and clicking the
Overview map's Tools node is a silent no-op — plus the coverage gap that let them ship.
The fix: repair the Memory view and rebuild it in waku-style sections (gate overview,
facts, episodes, consolidation), add a dedicated Tools view (Available catalog + Results)
with the Tools node navigating to it, and extend the offline suite so dashboard surfaces
are pinned by tests — including the first tests that run the dashboard with memory enabled
and the first render-level checks of the view functions.

Primary requirement (from spec): the existing six tools and the existing memory subsystem
work properly from the dashboard — no new tools. Technical approach (from research): keep
one agent implementation shared by CLI and dashboard; add one read-only API (`/api/tools`)
and extend `/api/memory` with gate/consolidation status; add one JS view module for tools
and fix the ASI defect in `memoryView`; change the Tools node's destination from `turn`
to the new `#tools` route.

## Technical Context

**Language/Version**: Python 3.14 (backend), dependency-free vanilla JS (dashboard static assets)

**Primary Dependencies**: None added. Backend stays stdlib (http.server, sqlite3); frontend stays build-free classic scripts. Dev tooling unchanged: pytest + ruff. (Node-executed render tests are considered and rejected — see research.md.)

**Storage**: Existing SQLite state.db + JSONL trajectories — no schema change. The Tools view's Results and the Memory view's gate/consolidation sections are read from the recorded trajectory and existing tables.

**Testing**: pytest offline deterministic suite (`make eval` / `make gate`), extended with: dashboard-path tests that run with memory enabled, `/api/tools` contract tests, Memory-view API round-trip tests, and static source-contract tests for the JS views (existing test_map_static.py style).

**Target Platform**: macOS/Linux local machine; browser dashboard at 127.0.0.1:7777

**Project Type**: local-first agent (CLI + local web dashboard)

**Performance Goals**: No new goals — local single-user surface; view payloads reuse already-bounded queries (facts LIMIT 100, episodes LIMIT 50, trajectory tail).

**Constraints**: Offline-first default test path (no network, no credentials); no new runtime dependencies; secrets redacted at the trace boundary; one agent implementation shared by all surfaces.

**Scale/Scope**: Two dashboard views (Tools new, Memory fixed/restructured), one new read-only API endpoint, one extended API endpoint, one map destination change, plus tests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Evidence |
|-----------|---------|--------|
| I. Build From Primitives | PASS | No framework added; views stay hand-written JS, server stays stdlib http.server. |
| II. Provider-Agnostic Model Boundary | PASS | Adapters untouched; no model-call change. |
| III. Small Modules With Narrow Contracts | PASS | One new JS view module (tools view) beside dock.js/observe.js; one read-only API handler beside existing ones; each carries a design note with a rejected alternative. |
| IV. Observable by Default | PASS | Tools Results and gate overview are read from the recorded trajectory — the surface stays a projection of the record. Redaction unchanged at the sink. |
| V. Eval-Driven Behavior Change | PASS | This is a defect-fix on surfaces, not a behavior change to prompts/loop/memory policy; new offline tests pin the fixed behavior and become the regression net (the suite grows with every fixed bug, as required). |

Post-design re-check: PASS (no design decision below introduces a violation; no Complexity Tracking entries needed).

## Project Structure

### Documentation (this feature)

```text
specs/006-tools-memory-support/
├── plan.md              # This file
├── research.md          # Phase 0 output — root causes and decisions
├── data-model.md        # Phase 1 output — payload shapes (no DB change)
├── quickstart.md        # Phase 1 output — validation scenarios
├── contracts/           # Phase 1 output — dashboard API + navigation contract
│   └── dashboard-api.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
byo/
├── ops/
│   ├── dashboard.py          # + GET /api/tools; extend /api/memory payload (gate, consolidation)
│   ├── map.py                # Tools node destination "turn" -> "tools"
│   └── static/
│       ├── index.html        # + nav link #tools, + js/tools.js script tag
│       └── js/
│           ├── dock.js       # FIX memoryView ASI defect; restructure into sections
│           ├── tools.js      # NEW — toolsView (Available catalog + Results)
│           └── main.js       # route #tools; memory view sections unchanged in spirit
evals/
└── deterministic/
    ├── test_dashboard.py     # + memory-enabled dashboard turn; /api/tools contract
    └── test_views_static.py  # NEW — view functions defined, no dangling-return pattern,
                              #       nav/route/destination consistency
```

**Structure Decision**: single project, existing layout. The change touches one server
module, one map payload module, two JS files (one new, one fixed), the shell HTML, and the
deterministic eval suite. No new packages, no build step.

## Complexity Tracking

No constitution violations; nothing to justify.
