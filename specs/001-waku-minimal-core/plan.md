# Implementation Plan: Waku-Parity Minimal Agent Core

**Branch**: `001-waku-minimal-core` | **Date**: 2026-11-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-waku-minimal-core/spec.md`

**Reference**: `~/Projects/Private/waku-agent` — read-only parity source. Every retained module has a
counterpart there; divergences are listed in [research.md](research.md) with their reason.

## Summary

Build `byo`, a single-package Python agent that keeps the reference's four pillars — harness,
loop, memory, operations — reduced to the minimum usable set: terminal chat, a local dashboard,
one SQLite file, six tools, and a JSON Lines trajectory per turn that both surfaces render.

The engineering shape is the reference's, minus everything the clarification session retired.
The one deliberate structural divergence is the model boundary: the reference's loop imports the
Anthropic SDK and speaks its types directly; this plan puts a normalized adapter seam between the
loop and both wire formats, because the project constitution forbids a vendor SDK inside loop,
tools or context code. Everything a person can observe — commands, address, file layout, trajectory
vocabulary, turn-card anatomy — stays equivalent, so the visualization and the operating habits
carry over intact.

## Technical Context

**Language/Version**: Python >= 3.11 (tested on 3.11, 3.12, 3.13; the reference's floor), stdlib
`sqlite3`, `http.server`, `threading`, `json`, `argparse`.

**Primary Dependencies**: `anthropic>=0.40` (Anthropic wire format), `openai>=1.50` (OpenAI wire
format and its compatible providers), `python-dotenv>=1.0`, `rich>=13.0`. Build backend
`hatchling`; dev extras `pytest>=8.0`, `ruff` pinned exactly. No `mcp` (retired), no web framework,
no front-end toolchain.

**Storage**: SQLite 3 with FTS5 — one `state.db` per home; JSON Lines trajectory files under
`trajectories/YYYY-MM-DD.jsonl`; markdown memory mirror (`MEMORY.md` + `memory/<id>.md`); message drafts
as files under `outbox/`.

**Testing**: `pytest` over `evals/deterministic/` (0/1 checks, no network, no credentials), driven by
a scripted model adapter and golden trajectory fixtures. `make eval` runs the suite; `make gate` runs it
with a per-suite report and a non-zero exit on failure.

**Target Platform**: macOS 13+ and Linux, one user account, localhost only; no daemon, no
container, no background service.

**Project Type**: single project — installable CLI plus a locally served web UI whose front end is
plain static files (no build step).

**Performance Goals**: first step visible <= 2 s after send (p95); every step rendered before the
reply finishes; dashboard JSON payload <= 200 ms for a 7-day window; per-turn trajectory recording and UI
overhead <= 50 ms; offline suite <= 3 min.

**Constraints**: no agent-orchestration framework; no new default dependency beyond the four
above; offline-first test path; secrets only from environment or `.env`, redacted at the trajectory
sink; no brand assets copied from the reference; the reference checkout is never modified;
dashboard binds to loopback.

**Scale/Scope**: 1 concurrent user, 1 process, ~8 modules, ~6 tools, 2 surfaces, 37 functional
requirements, 10 success criteria, expected ~5k LOC package + ~1.5k LOC static assets.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Evidence |
|---|---|---|
| I. Build From Primitives | PASS | Loop, tool dispatch, context assembly and memory live in `byo/loop`, `byo/tools`, `byo/runtime`, `byo/memory`. The four dependencies are leaf transports (HTTP/parsing, dotenv, terminal rendering). No orchestration framework is declared. Every module carries a design note naming its mechanism and one rejected alternative. |
| II. Provider-Agnostic Model Boundary | PASS | `byo/loop/types.py` defines the normalized request/response/usage/error types; `byo/loop/adapters.py` holds both wire formats and is the only importer of `anthropic`/`openai`. The core branches on capability flags, never on vendor identity. A scripted adapter proves the suite runs offline. This is a deliberate divergence from the reference, recorded in research R3. |
| III. Small Modules With Narrow Contracts | PASS | One concern per module (config, db, session, loop, adapters, registry, memory stores, gate, consolidation, mirror, trajectory recording, observability, receipt, dashboard, cli). Each is importable and testable alone; contracts are written down under `contracts/`. |
| IV. Observable by Default | PASS | Trajectory recording is on for every turn with no opt-in; records are JSON Lines and replayable through `byo trajectory`; redaction happens in the sink so no caller can bypass it; a defect report carries its trajectory (FR-037). |
| V. Eval-Driven Behavior Change (NON-NEGOTIABLE) | PASS | The default test command is the offline deterministic suite; every behavior-touching change carries an eval delta; golden trajectories under `evals/fixtures/trajectories/` grow with each fixed defect. Judge-scored evals are retired for v1 by the clarification session, which Principle V permits (live-model evals are optional). |

**Additional constraints check**: stack recorded here (stack neutrality satisfied); dependency
budget is four runtime libraries against the reference's five (`mcp` dropped); tests run offline;
model, limits, ports and trajectory destination are configuration; secrets come from env/.env; each
subsystem documents its mechanism and a rejected alternative.

No violations. **Complexity Tracking**: not required — the adapter seam is mandated by Principle II,
not speculative generality; there is no fourth project, no repository indirection, and no plugin
system.

## Project Structure

### Documentation (this feature)

```text
specs/001-waku-minimal-core/
├── plan.md              # this file
├── research.md          # Phase 0: decisions, rationale, rejected alternatives
├── data-model.md        # Phase 1: storage entities, rules, lifecycles
├── quickstart.md        # Phase 1: runnable validation scenarios
├── contracts/           # Phase 1: CLI, HTTP, trajectory, adapter and tool contracts
│   ├── cli.md
│   ├── dashboard-api.md
│   ├── trajectory-schema.md
│   ├── model-adapter.md
│   └── tools.md
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # Phase 2 output (/speckit-tasks), not created here
```

### Source Code (repository root)

```text
byo/                          # the package; layout mirrors the reference's retained modules
├── __init__.py               # the single version number
├── __main__.py               # `byo` entrypoint: bare (chat) | dashboard | trajectory
├── app.py                    # assembly: settings -> db -> tools -> memory -> session -> loop
├── config.py                 # Settings dataclass, BYO_* knobs, home resolution, .env loading
├── db.py                     # schema, PRAGMAs, idempotent migrations
├── gateway/
│   └── cli.py                # terminal chat, live step lines, /memory and /quit
├── loop/
│   ├── agent.py              # the turn loop and its two guardrails
│   ├── types.py              # normalized messages, tool calls, usage, stop reasons, errors
│   ├── adapters.py           # anthropic-wire and openai-wire adapters; the only SDK importers
│   └── trim.py               # shorten already-read tool results between iterations
├── memory/
│   ├── __init__.py           # Memory facade (facts + episodes + gate + consolidation)
│   ├── retrieval_gate.py     # decides whether this turn needs memory
│   ├── consolidation.py      # distils unconsolidated chats into facts + one episode
│   ├── mirror.py             # MEMORY.md and memory/<id>.md writer
│   ├── semantic/store.py     # facts, FTS5 search, top-k
│   └── episodic/store.py     # episodes, FTS5 search
├── runtime/
│   └── session.py            # working-memory assembly, bounded history, clock seam
├── tools/
│   ├── registry.py           # declaration, dispatch, error-as-text
│   ├── calendar.py           # create_event, list_events
│   ├── notes.py              # save_note
│   ├── messages.py           # send_message -> outbox file
│   └── memory_admin.py       # manage_memory, update_persona
└── ops/
    ├── trajectory.py         # sink, redaction, daily JSONL writer
    ├── observability.py      # group turns, build spans, spend aggregation
    ├── receipt.py            # per-turn accounting
    ├── pricing.py            # model price table
    ├── show_trajectory.py    # terminal timeline renderer
    ├── dashboard.py          # stdlib HTTP server: static files, JSON API, SSE
    └── static/               # no build step; plain HTML/CSS/JS
        ├── index.html
        ├── style.css
        └── js/
            ├── api.js        # fetch/SSE helpers
            ├── render.js     # turn card: stages, step rows, reply, receipt
            ├── observe.js    # observability waterfall and spend
            ├── dock.js       # session history, memory and settings views
            └── main.js       # bootstrap and refresh loop (loaded last)

evals/
├── conftest.py               # temp home and trajectory fixture helpers
├── scripted.py               # the ModelAdapter test double that replays fixtures/models/*.json
├── deterministic/            # one test file per module; parity seams in test_parity_seams.py
└── fixtures/
    ├── models/               # scripted model scripts (JSON)
    └── trajectories/         # golden v1 trajectories, including one captured from the reference

pyproject.toml                # hatchling, console script `byo`, ruff line-length 100
Makefile                      # run | dashboard | trajectory | eval | gate | lint
.env.example                  # every BYO_* knob with its default
README.md
```

**Structure Decision**: single project. The reference splits nothing either — one package holds
harness, loop, memory and operations, with its static front end inside the package. Keeping that
shape means a reader who knows the reference can find any module by its job. Tests live under
`evals/` rather than `tests/` so `make eval` and the parity of the test command survive; the
dashboard is served by the stdlib server from `byo/ops/static`, so there is no frontend project
and no build step.

## Phase 0: Outline & Research

Complete — see [research.md](research.md). Every Technical Context field was resolved; no
`NEEDS CLARIFICATION` remains. The decisions that shaped the structure are:

- **R3 Model boundary** — normalized types plus two adapters, rather than the reference's
  SDK-typed loop (required by Principle II).
- **R8 Trajectory format** — daily JSON Lines with the reference's event vocabulary, versioned on the
  first record of each turn, redacted at the sink.
- **R9 Dashboard transport** — stdlib threaded HTTP server, SSE for the running turn, cursor
  polling for the observability refresh; no framework, no dependency.
- **R7 Storage** — the reference's tables and FTS5 triggers minus the retired integration columns,
  WAL enabled so terminal and dashboard can write concurrently.

## Phase 1: Design & Contracts

Complete — the artifacts below are generated beside this plan:

- [data-model.md](data-model.md) — tables, columns, constraints, trajectory-derived read models and
  lifecycles (turn, fact, episode, session).
- [contracts/cli.md](contracts/cli.md) — commands, exit codes, environment knobs and defaults.
- [contracts/dashboard-api.md](contracts/dashboard-api.md) — routes, payloads, SSE framing.
- [contracts/trajectory-schema.md](contracts/trajectory-schema.md) — trajectory v1: event types, fields, units,
  ordering, versioning and redaction.
- [contracts/model-adapter.md](contracts/model-adapter.md) — the protocol, capability flags,
  streaming semantics and typed errors.
- [contracts/tools.md](contracts/tools.md) — the declaration shape and the six tools with their
  arguments, returns and artifact locations.
- [quickstart.md](quickstart.md) — runnable validation scenarios, end to end.

## Constitution Check (post-design)

Re-evaluated against the artifacts above. Verdicts unchanged: I–V all PASS.

- The adapter protocol in `contracts/model-adapter.md` keeps vendor types out of the loop.
- `contracts/trajectory-schema.md` makes observability a written contract, not an implementation detail.
- Every module in the source tree has exactly one job; `app.py` is the only assembler.
- The offline suite in the structure covers each retained behavior plus the parity seams.
- One spec precision fix was made during design: FR-005 now says retained tables keep the columns
  the retained behaviors use, because the reference's `facts.synced`/`facts.scope` columns exist
  only for the retired hosted-memory integration (see [data-model.md](data-model.md)).

## Risks and Sequencing Notes

- **Highest-risk seam**: the trajectory schema, because it is shared with the reference. Mitigation:
  capture one reference trajectory as a fixture before writing the renderer, and test both directions
  (FR-032, SC-010).
- **Second**: the SSE turn card, because "steps before the reply" is a timing contract. Mitigation:
  a scripted adapter that delays a tool by 1.5 s, plus a test that asserts step order relative to
  the reply frame.
- **Order of delivery**: P1 loop and terminal, then P2 dashboard and trajectory, then P3 memory, then
  P4 evals and gate. Each priority lands runnable on its own; `/speckit-tasks` encodes that order.
