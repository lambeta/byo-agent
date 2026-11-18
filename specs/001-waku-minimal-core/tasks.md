---

description: "Task list for the Waku-parity minimal agent core"
---

# Tasks: Waku-Parity Minimal Agent Core

**Input**: Design documents from `specs/001-waku-minimal-core/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md),
[data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required. Spec FR-034 makes the offline deterministic suite the default test command and
the project constitution (Principle V) forbids a behavior change without an eval. Test tasks come
first in each story phase and must fail before the implementation task they cover.

**Organization**: One phase per user story (P1 → P4), so each phase is a runnable increment.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency on an incomplete task
- **[Story]**: the user story a task serves (US1–US4); setup, foundational and polish tasks carry no label
- Every task names the exact file it creates or changes

## Path Conventions

Single project at the repository root: package `byo/`, tests and fixtures under `evals/`,
contracts under `specs/001-waku-minimal-core/contracts/` (documents, not code).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: A installable, lintable, testable skeleton before any behavior.

- [x] T001 Create `pyproject.toml`: hatchling backend, `requires-python = ">=3.11"`, runtime deps `anthropic>=0.40`, `openai>=1.50`, `python-dotenv>=1.0`, `rich>=13.0`, dev extras `pytest>=8.0` + pinned `ruff`, console script `byo = "byo.__main__:main"`, `[tool.ruff] line-length = 100`, `[tool.pytest.ini_options] testpaths = ["evals"]`
- [x] T002 [P] Create `Makefile` with targets `run`, `dashboard`, `trajectory`, `eval`, `gate`, `lint` (`PY` picks `.venv/bin/python` when present)
- [x] T003 [P] Create `.env.example` listing every knob from `contracts/cli.md` with its default, and `.gitignore` for `.venv/`, `.byo/`, `__pycache__/`, `.pytest_cache/`
- [x] T004 [P] Create the `byo/` package skeleton (`__init__.py` with the single version string, empty subpackages `gateway/`, `loop/`, `memory/`, `runtime/`, `tools/`, `ops/`) and `evals/{deterministic,fixtures/models,fixtures/trajectories}/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The seams every story depends on. No story work starts before this phase is green.

**⚠️ CRITICAL**: US1–US4 all build on these four modules and the test double.

- [x] T005 Implement `byo/config.py`: `Settings` dataclass with every `BYO_*` knob and the defaults in `contracts/cli.md`, home resolution (`BYO_HOME` → `~/.byo`), `.env` loading where the process environment wins, and a startup check that names the missing variable
- [x] T006 [P] Implement `byo/db.py`: the `data-model.md` `1` schema verbatim (tables, FTS5 virtual tables, triggers, the three additive indexes), `PRAGMA journal_mode=WAL` and `busy_timeout=3000`, and idempotent `PRAGMA table_info`-based migrations
- [x] T007 [P] Implement `byo/loop/types.py` per `contracts/model-adapter.md` `1–2`: normalized `Message`/`TextBlock`/`ToolCallBlock`/`ToolResultBlock`/`Request`/`Response`/`Usage`/`ToolSpec`, `Capabilities`, and the four error classes `Refused`/`RateLimited`/`Transport`/`BadResponse`
- [x] T008 [P] Implement `byo/tools/registry.py`: `Tool` dataclass, `schemas()`, `execute(name, args)` with the dispatch table in `contracts/tools.md` `2` (unknown name, bad arguments, raising callable → text, never an exception)
- [x] T009 Implement `byo/loop/adapters.py`: one adapter per wire format (Anthropic, OpenAI) conforming to the `ModelAdapter` protocol, the block mapping table in `contracts/model-adapter.md` `4`, streaming that yields deltas and returns the assembled response, and error normalization per `5` — this is the only module allowed to import `anthropic` or `openai`
- [x] T010 Implement the test double in `evals/scripted.py`: a `ModelAdapter` that replays a JSON script (`evals/fixtures/models/*.json`) with per-response text, tool calls, stop reason, usage and optional `delay_ms`, plus a `scripted_adapter(path)` helper and a `tmp_home` fixture in `evals/conftest.py`

**Checkpoint**: `byo/config.py`, `byo/db.py`, the types, the registry, both adapters and the scripted double exist; a scratch test can build a registry and complete a scripted turn.

---

## Phase 3: User Story 1 - A working agent in the terminal (Priority: P1) 🎯 MVP

**Goal**: `byo` runs a real turn — model call, tool dispatch, observation, reply — and prints each
step as it happens. Three tools land: calendar create/list, note save, message draft.

**Independent Test**: With `evals/fixtures/models/two-step.json` and a temp home, `byo` answers a
request that needs one tool call, the event row exists in `state.db`, and stdout shows the tool step
before the reply.

### Tests for User Story 1 (write first, must fail)

- [x] T011 [P] [US1] Write `evals/deterministic/test_adapters.py`: the eight conformance checks in `contracts/model-adapter.md` `6` against the scripted adapter, plus a static check that `byo/loop/agent.py` imports neither vendor SDK
- [x] T012 [P] [US1] Write `evals/deterministic/test_loop.py`: text-only turn, tool turn, two tool calls in one response, tool exception → text result and the turn continues, step limit → exactly one tools-off call with `kind: "final"`, `trim` shortens an already-read result before iteration 2
- [x] T013 [P] [US1] Write `evals/deterministic/test_tools.py`: dispatch rules from `contracts/tools.md` `2`, plus one write-through per tool asserting the stored row/file and that the returned text names it
- [x] T014 [P] [US1] Write `evals/deterministic/test_config.py` and `evals/deterministic/test_db.py`: knob defaults equal `contracts/cli.md`, `BYO_HOME` wins over the default, `.env` loses to the process environment, schema objects exist after `connect()`, migrations are idempotent on a second call

### Implementation for User Story 1

- [x] T015 [US1] Implement `byo/runtime/session.py`: `PERSONA.md` creation on first run from a short default, system-prompt assembly (persona + local date-time with timezone + active model/provider), the clock seam, and a history bounded by `BYO_HISTORY_TURNS`
- [x] T016 [US1] Implement `byo/loop/agent.py`: the loop per `plan.md` and `research.md` R5 — observer events `gate`/`llm`/`tool`, guardrail 1 (no tool call), guardrail 2 (step limit → one `tool_choice: none` call, `limit_reached` flag), error containment
- [x] T017 [P] [US1] Implement `byo/loop/trim.py`: shorten tool results the model has already read before later iterations, leaving the first read untouched
- [x] T018 [P] [US1] Implement `byo/tools/calendar.py`: `create_event` (`title` required, `start` ISO 8601 with offset required) and `list_events` (default today, 20-row cap) writing/reading `calendar_events`, each output naming the database path
- [x] T019 [P] [US1] Implement `byo/tools/notes.py`: `save_note` writes one `facts` row with `source = 'tool'` and returns the row id and both paths (the markdown mirror wiring arrives in US3)
- [x] T020 [P] [US1] Implement `byo/tools/messages.py`: `send_message` writes `outbox/<timestamp>-<slug>.md` with `to`/`created_at` front matter and returns the `not sent anywhere` wording
- [x] T021 [US1] Implement `byo/app.py`: assembly and injection seams (`settings`, `client`, `conn`), `build_registry()` for the US1 tool set, `respond(message, observer, source)` returning the loop result
- [x] T022 [US1] Implement `byo/gateway/cli.py`: rich panel with home and model, `/memory` snapshot, `/quit`/`/exit`, live step lines (`tool · …`, `gate · …`) printed as they complete and the reply after them
- [x] T023 [US1] Implement `byo/__main__.py`: dispatch `byo` | `dashboard` | `trajectory` | `--version`/`--help`, the exit codes in `contracts/cli.md`, and the missing-key path that prints one actionable line and exits 2
- [x] T024 [US1] Write `evals/deterministic/test_cli.py` and `evals/deterministic/test_session.py`: exit codes, missing-key message, step lines appearing before the reply, persona created on first run, history bounded at `BYO_HISTORY_TURNS`
- [x] T025 [US1] Run `make eval` (target in `Makefile`); every US1 check under `evals/deterministic/` must pass with networking disabled

**Checkpoint**: `byo` is a working terminal agent; `byo trajectory` still prints usage (arrives in US2).

---

## Phase 4: User Story 2 - The same turn, watchable in the browser (Priority: P2)

**Goal**: Every turn appends a trajectory; the dashboard renders it live and the observability view
renders the waterfall; `byo trajectory` replays any recorded turn in the terminal.

**Independent Test**: One scripted two-tool turn, driven through `POST /api/chat/stream`, yields a
`trajectories/YYYY-MM-DD.jsonl` file whose records match `contracts/trajectory-schema.md`, a card
payload with two loop rows and two tool rows, and the same turn in `/api/observability`.

### Tests for User Story 2 (write first, must fail)

- [x] T026 [P] [US2] Write `evals/deterministic/test_trajectory_contract.py`: required fields per event type, one `turn_start`/`turn_end` per turn, `trajectory_version` on the start record, ordering invariant 4 (`receipt` immediately before `turn_end`), unknown event types render as a generic row
- [x] T027 [P] [US2] Write `evals/deterministic/test_api_contract.py`: every route in `contracts/dashboard-api.md`, the turn payload shape, SSE frame order with `done` last, `409` on a concurrent turn, `404` for `../` static traversal
- [x] T028 [P] [US2] Write `evals/deterministic/test_observability.py`: grouping by turn, an unfinished turn renders unindented, one closed row per loop, failures flagged, spend summed from receipts
- [x] T029 [P] [US2] Write `evals/deterministic/test_redaction.py`: field-name and value-shape rules from `contracts/trajectory-schema.md` `6`, idempotence, and a key-shaped string inside a tool output never reaching disk
- [x] T030 [P] [US2] Write `evals/deterministic/test_receipt.py` and `evals/deterministic/test_pricing.py`: totals equal the sum of `llm` records within 1e-6, unknown model sets `estimate: true`
- [x] T031 [P] [US2] Write `evals/deterministic/test_show_trajectory.py`: renders a turn indented, defaults to the newest file, skips and reports a corrupted line, exits 1 when no file exists

### Implementation for User Story 2

- [x] T032 [US2] Implement `byo/ops/trajectory.py`: turn ids, the event writers for `turn_start`/`gate`/`llm`/`tool`/`consolidation`/`receipt`/`error`/`turn_end`, daily file append, and the redaction pass in the sink (`contracts/trajectory-schema.md` `3, `6`) — callers cannot bypass it
- [x] T033 [P] [US2] Implement `byo/ops/pricing.py`: a versioned per-model price table, `cost(provider, model, usage)` returning 0.0 plus an estimate flag for an unknown model
- [x] T034 [US2] Implement `byo/ops/receipt.py`: per-turn sums (iterations, tool calls, tokens, cost) built from the turn's `llm` records
- [x] T035 [US2] Implement `byo/ops/observability.py`: `group_turns(events)`, `build_turn(current, events)` producing the payload in `contracts/dashboard-api.md`, spend buckets by day and model, and the memory summary
- [x] T036 [US2] Implement `byo/ops/show_trajectory.py`: the rich timeline (turn flush left, events indented, durations/usage/cost, generic row for unknown types)
- [x] T037 [US2] Implement `byo/ops/dashboard.py`: `ThreadingHTTPServer` on `127.0.0.1:BYO_PORT`, the route table, static serving with traversal refusal, `/api/events?cursor=`, and `/api/chat/stream` SSE that emits each loop observer event as it happens
- [x] T038 [P] [US2] Create `byo/ops/static/index.html` and `byo/ops/static/style.css`: chat dock, turn card, observability, memory and settings views laid out as in the reference, with this project's own neutral tokens and system fonts (no reference mark, font file or token — `research.md` R16)
- [x] T039 [P] [US2] Create `byo/ops/static/js/api.js` and `byo/ops/static/js/main.js`: fetch/SSE helpers, the `refresh() → render()` loop, hash routing
- [x] T040 [P] [US2] Create `byo/ops/static/js/render.js`: the turn card — stage row, step rows with duration/outcome, streamed reply, receipt, failure state
- [x] T041 [P] [US2] Create `byo/ops/static/js/observe.js`: the waterfall on one time axis and the spend cards
- [x] T042 [P] [US2] Create `byo/ops/static/js/dock.js`: session history, memory table, settings form (never rendering a key)
- [x] T043 [US2] Wire the dashboard into `byo/app.py` and `byo/__main__.py`: one agent instance for the server, an observer that feeds both the tracer and the SSE stream, and the `trajectory` subcommand
- [x] T044 [US2] Write `evals/deterministic/test_dashboard.py`: an end-to-end scripted turn through the HTTP server asserting the card payload, the trajectory file, and the waterfall
- [x] T045 [US2] Run `make eval` (target in `Makefile`); every US1+US2 check under `evals/deterministic/` must pass offline

**Checkpoint**: US1 and US2 both work; a turn is visible in the terminal, in the browser, and in the trajectory file.

---

## Phase 5: User Story 3 - Memory that earns its place (Priority: P3)

**Goal**: A retrieval gate decides per turn, facts and episodes persist with keyword search,
consolidation distils chats on a schedule, and the mirror stays readable.

**Independent Test**: With a temp home, save a fact in one process and recall it in a new one; six
exchanges produce facts plus one episode; a no-memory turn records `skip` with a reason.

### Tests for User Story 3 (write first, must fail)

- [x] T046 [P] [US3] Write `evals/deterministic/test_memory.py`: fact and episode write/read, FTS5 keyword search, top-k bounded by `BYO_RETRIEVAL_TOP_K`, subject index used
- [x] T047 [P] [US3] Write `evals/deterministic/test_gate.py`: `retrieve`/`skip` decisions from a scripted small model, and a failing model call → `retrieve` with the failure as the reason
- [x] T048 [P] [US3] Write `evals/deterministic/test_consolidation.py`: runs at `BYO_CONSOLIDATE_EVERY`, marks consumed rows 0→1 once, keeps proposed facts, drops a fact that only repeats text recalled this turn, a failure leaves rows unconsolidated, one episode per batch
- [x] T049 [P] [US3] Write `evals/deterministic/test_mirror.py`: `MEMORY.md` and `memory/<id>.md` agree row-for-row with the store; deleting a fact removes its file and the combined line

### Implementation for User Story 3

- [x] T050 [P] [US3] Implement `byo/memory/semantic/store.py`: insert, update, delete, `search(query, k)` over `facts_fts`, and `recent(n)`
- [x] T051 [P] [US3] Implement `byo/memory/episodic/store.py`: append and search over `episodes_fts`
- [x] T052 [US3] Implement `byo/memory/retrieval_gate.py`: one small-model question, `retrieve` on any failure with the kind as the reason, result carries the decision for the trajectory
- [x] T053 [US3] Implement `byo/memory/consolidation.py`: batch selection, prompt, parse, suppression of exact repeats of `recalled` text, row marking, episode write, failure containment
- [x] T054 [US3] Implement `byo/memory/mirror.py`: regenerate `MEMORY.md` and one file per fact after every turn and every edit
- [x] T055 [US3] Implement `byo/memory/__init__.py`: the `Memory` facade (stores + gate + consolidation + mirror) with the interface `app.py` consumes
- [x] T056 [US3] Implement `byo/tools/memory_admin.py`: `manage_memory` (`list`/`edit`/`forget`) and `update_persona` (`PERSONA.md` rewrite keeping a `.bak`)
- [x] T057 [US3] Extend `byo/runtime/session.py` and `byo/app.py`: retrieval block in the system prompt, `recalled` text for consolidation, `gate` and `consolidation` observer events, `save_note` wired to the mirror
- [x] T058 [US3] Add the memory routes to `byo/ops/dashboard.py` and the memory view wiring in `byo/ops/static/js/dock.js` (``/api/memory` per `contracts/dashboard-api.md`)
- [x] T059 [US3] Write `evals/deterministic/test_memory_admin.py` and extend `test_dashboard.py` with the edit/forget path
- [x] T060 [US3] Run `make eval` (target in `Makefile`); every US1–US3 check under `evals/deterministic/` must pass offline

**Checkpoint**: All three functional stories work; memory is visible in the terminal, the card and the mirror.

---

## Phase 6: User Story 4 - Prove it, offline (Priority: P4)

**Goal**: A golden trajectory corpus, the parity checklist, a replay procedure for defects, and the
release gate.

**Independent Test**: `make gate` passes offline in under three minutes and fails, naming the check,
when one is broken; both fixtures render in both renderers.

### Tests and fixtures for User Story 4

- [x] T061 [P] [US4] Author `evals/fixtures/trajectories/golden-cli.jsonl`: one complete turn with `turn_start`, `gate`, two `llm`, one `tool`, `receipt`, `turn_end`, matching `contracts/trajectory-schema.md` `8`
- [x] T062 [P] [US4] Author `evals/fixtures/trajectories/reference-sample.jsonl`: a turn containing the reference's extra event types (`hook`, `report`, `score`, `route`) to prove the generic-row rule
- [x] T063 [US4] Write `evals/deterministic/test_parity_seams.py`: asserts the SC-006 checklist mechanically — command set, dashboard address and route shape, home file layout, trajectory vocabulary, card payload keys
- [x] T064 [US4] Write `evals/deterministic/test_replay.py`: a failing turn is reproduced from its trajectory alone through the scripted adapter (FR-037), and the rendered timeline names the failing step
- [x] T065 [US4] Write `evals/deterministic/test_make_targets.py`: `make -n gate` invokes pytest over `evals/deterministic` and `make -n eval` matches `make gate` in scope

### Implementation for User Story 4

- [x] T066 [US4] Finalize the `gate` target in `Makefile`: run the suite verbosely, print a one-line result per check, propagate the non-zero exit
- [x] T067 [US4] Add the replay note to `README.md` (how a bug report becomes a fixture and a test) and cross-link `quickstart.md` `5`
- [x] T068 [US4] Run the suite through the `gate` target in `Makefile` with networking disabled, record wall time in `quickstart.md`, and fix any check under `evals/deterministic/` slower than the three-minute budget

**Checkpoint**: All four stories pass; the build is provable from a trace alone.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T069 [P] Write `README.md`: what it is, install, first run, the four pillars, where data lives, no brand assets
- [x] T070 [P] Run `ruff check byo/ evals/` and fix every finding; confirm `line-length = 100` in `pyproject.toml` and no `# noqa` additions
- [x] T071 [P] Verify `.env.example` against the knob table in `contracts/cli.md` with a test in `evals/deterministic/test_env_example.py`
- [x] T072 Measure the SC-002 timings with a scripted 1.5 s tool call in `evals/deterministic/test_timing.py`: first step < 2 s, every step before the reply, tracing overhead < 50 ms
- [x] T073 Run every scenario in `quickstart.md` end to end and fix any drift between the document and the product
- [x] T074 [P] Write `evals/deterministic/test_scope.py`: no retired capability exists (no `byo/gateway/` module besides `cli.py`, no mcp/plugin/graph/arena/voice modules, no retired subcommand in `byo --help`) and `pyproject.toml` declares exactly the four runtime dependencies
- [x] T075 Final `make lint`, `make eval`, `make gate` on a clean checkout; confirm zero credentials in `trajectories/` and `.env.example`

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (Phase 1)**: no dependencies.
- **Foundational (Phase 2)**: needs Phase 1. Blocks every story — T005–T010 define the seams.
- **US1 (Phase 3)**: needs Phase 2. Delivers the MVP.
- **US2 (Phase 4)**: needs US1 — it visualizes US1's turns and traces the loop's observer events.
- **US3 (Phase 5)**: needs US1 (tools, session, app) and US2 (the `gate`/`consolidation` trajectory records it renders).
- **US4 (Phase 6)**: needs US1–US3, because the parity checklist and the replay test exercise all of them.
- **Polish (Phase 7)**: needs the stories it documents.

### Within a story

Tests first (they must fail), then modules in dependency order: types → storage → service → surface.
T016 depends on T015; T021 depends on T015–T020; T023 depends on T021/T022.

### Parallel opportunities

- T002–T004 (setup files, different paths).
- T006–T008 (db, types, registry — independent).
- T011–T014 (four test files, different modules).
- T017–T020 (four tool/utility modules, no shared file).
- T026–T031 (six test files).
- T033 (pricing) alongside T032 (trajectory sink).
- T038–T042 (five static files).
- T046–T049 (four memory test files).
- T050–T051 (two stores).
- T061–T062 (two fixtures).

---

## Parallel Execution Examples

### US1: the loop and its tools

```text
T015 session.py ──┬─> T016 agent.py ──> T021 app.py ──> T022 cli.py ──> T023 __main__.py
                  ├─> T017 trim.py
                  └─> T018/T019/T020 tools (parallel: calendar, notes, messages)
```

### US2: the visualization stack

```text
T032 trajectory.py ──> T034 receipt.py ──> T035 observability.py ──> T037 dashboard.py
T033 pricing.py  ──┘                                                └─> T038–T042 static files (parallel)
```

### US3: memory

```text
T050 facts store ─┐
T051 episode store ┴─> T052 gate ──> T055 facade ──> T057 session/app wiring ──> T058 dashboard memory
                       T053 consolidation ──┘
                       T054 mirror ─────────┘
```

---

## Implementation Strategy

**MVP first**: Phases 1–3 (US1). At the checkpoint, `byo` answers a real request with a real tool
call and shows its steps in the terminal — that alone is a usable product and the earliest point to
demo.

**Incremental delivery**:

1. **US1** — terminal agent (MVP).
2. **US2** — trajectory + dashboard + waterfall (the "watch it think" promise).
3. **US3** — memory gate, consolidation, mirror.
4. **US4** — proof: fixtures, parity checklist, replay, gate.
5. **Polish** — docs, lint, timings, quickstart walkthrough.

**Stop-and-verify points**: after each phase, `make eval` must pass offline; after US2, a scripted
turn must appear identically in the terminal timeline and the dashboard waterfall; after US4,
`make gate` must fail when a check is deliberately broken.

**Notes**

- `make gate` runs the same suite as `make eval` with per-check output; there is no second suite in
  v1 (judge evals are retired by the clarification session).
- The scripted adapter lives in `evals/scripted.py`, outside the package, so the shipped wheel never
  contains test doubles.
- Every module gets a design note in its docstring: what it implements and one rejected alternative
  (constitution I and the documentation duty).

## Phase 8: Convergence

- [x] T076 Redact every surface before display: apply the sink's redaction to tool args/output in the SSE frames of `byo/ops/dashboard.py` and in the step lines of `byo/gateway/cli.py`, and add `evals/deterministic/test_redaction.py` cases proving a key-shaped string never reaches the SSE body or the terminal output per FR-033 (partial)
- [x] T077 Make a browser disconnect non-fatal: catch `BrokenPipeError` inside the SSE `send()` of `byo/ops/dashboard.py`, let the turn finish, and add a test that drops the client mid-turn and asserts the trajectory still ends with `turn_end` per FR-027 and SC-009 (contradicts)
- [x] T078 Contain consolidation failures: wrap the `maybe_consolidate` call in `byo/app.py` so an exception becomes an `error` trajectory record instead of escaping `respond`, and add a case whose consolidation raises per FR-021 (partial)
- [x] T079 Exercise the reference fixture: render `evals/fixtures/trajectories/reference-sample.jsonl` from `evals/deterministic/test_show_trajectory.py`, assert every line renders and nothing is skipped, and state in `README.md` which direction of SC-010 is verified per SC-010 and FR-032 (partial)
- [x] T080 Assert the consolidation record in the trajectory: add an application-level case in `evals/deterministic/test_consolidation.py` that runs a scripted turn with six pending rows and asserts a `consolidation` event carrying the kept facts per FR-028 (partial)
- [x] T081 Cover the terminal memory view: add a `test_cli.py` case that seeds a fact and a pending chat row, runs `/memory`, and asserts both appear per FR-024 (partial)
- [x] T082 Resolve the redaction off-switch: an operator-settable `BYO_TRAJECTORY_REDACT=0` disables a MUST, so either remove the knob or confine it to tests, updating `byo/config.py`, `.env.example`, `contracts/cli.md` and `evals/deterministic/test_env_example.py` together per FR-033 (contradicts)
- [x] T083 Restore the model-script fixture path: create `evals/fixtures/models/` with at least one JSON script loaded through `load_script` in `evals/scripted.py`, whose `FIXTURES` constant currently points at a directory that does not exist per plan: fixtures/models and FR-037 (missing)
- [x] T084 Cover the default trajectory target: add a `byo.ops.show_trajectory.main([])` case with `BYO_HOME` pointed at a temp home holding one file, asserting exit 0 and the newest turn rendered per FR-031 (partial)
- [x] T085 Document the receipt naming seam: note in `contracts/trajectory-schema.md` section 3 that the read model exposes the same figure as `usd` per plan: data model section 3 (partial)
- [x] T086 Measure SC-002 over a corpus: add a scripted multi-turn timing case that asserts every step precedes the reply and records first-step latency, so the 95% claim has an apparatus per SC-002 (partial)
