# Research — Phase 0 decisions

**Feature**: Waku-Parity Minimal Agent Core · **Date**: 2026-11-18

Every Technical Context field in [plan.md](plan.md) is resolved; no `NEEDS CLARIFICATION` marker
survived the spec and clarification session. Each decision below names what was chosen, why, and
what was rejected — the constitution requires that "why" to live next to the "how".

---

## R1. Language and runtime

**Decision**: Python >= 3.11, standard library wherever it can do the job (`sqlite3`,
`http.server`, `json`, `threading`). CI runs 3.11, 3.12 and 3.13.

**Rationale**: The spec's parity requirement is a stack requirement. The reference ships
`requires-python = ">=3.11"` and its readers are expected to step through plain Python. A different
runtime would make every contract a translation exercise, and the constitution forbids frameworks
that would own control flow.

**Alternatives considered**: Python 3.12+ only (rejected: narrows parity with the reference's
floor for no gain); Go or TypeScript (rejected: destroys parity, and the dashboard already has a
no-build answer in plain JS).

## R2. Packaging, entrypoint and repository tooling

**Decision**: One package `byo/` with `hatchling` as the build backend, one console script `byo`,
version in `byo/__init__.py` only. Dev tooling: `pytest` over `evals/deterministic/`, `ruff` with
`line-length = 100` and a pinned version, and a `Makefile` with `run | dashboard | trajectory | eval |
gate | lint`.

**Rationale**: These are the reference's exact conventions, so install/run/lint commands carry over.
A single version location prevents the drift the reference documented (two version numbers for four
releases).

**Alternatives considered**: `setuptools` (rejected: hatchling is what the reference uses, so
build behaviour matches); `src/` layout (rejected: the reference's flat package is what readers
navigate by module job); a task runner such as `nox`/`tox` (rejected: adds a dependency to do what
`make` and `pytest` already do).

## R3. Model boundary: normalized types plus adapters

**Decision**: `byo/loop/types.py` defines the vocabulary the loop speaks — request, message, tool
declaration, tool call, response, usage, stop reason, and typed errors. `byo/loop/adapters.py`
implements two adapters (Anthropic wire, OpenAI wire) and is the only module that imports a vendor
SDK. The loop receives an adapter object and an explicit capability set (streaming, tool calls,
usage, structured output).

**Rationale**: Constitution Principle II makes this non-negotiable, and the spec's FR-012 says the
same. It also pays off immediately: the scripted adapter used by the offline suite implements the
same protocol, so the whole test path runs with no network.

**Alternatives considered**: the reference's approach — loop imports `anthropic` and speaks its
response types (rejected: violates Principle II, and the fake model would have to impersonate a
vendor type); `litellm` as a universal adapter (rejected: a new dependency that *is* the model
boundary, which is exactly what Principle I forbids); per-provider branching inside the loop
(rejected: FR-012 forbids branching on vendor identity).

## R4. Provider transport, streaming and error taxonomy

**Decision**: Each adapter uses the provider's official SDK for transport (HTTP, retries, streaming
frames) and converts to the normalized types at its edge. Errors are normalized to four kinds:
`Refused` (4xx — a decision, never retried), `Transport` (retried once, then surfaced),
`RateLimited`, and `BadResponse`. Streaming is a capability flag; when unavailable the turn falls
back to a single call.

**Rationale**: The reference's best operational lessons transfer: a 4xx is never retried (it doubles
what a metered user pays to be told no), and the two wire formats already cover the provider list.
Typed errors are what the loop branches on, so no vendor check leaks inward.

**Alternatives considered**: raw `httpx` calls (rejected: re-implements retries and stream parsing
the SDK already ships, and `httpx` would become a direct dependency); treating every failure as
retryable (rejected: duplicates spend and hides refusals); retrying 4xx on a different model
(rejected: out of scope for v1, and an implicit provider-switching policy the spec never asked for).

## R5. Loop guardrails and context trimming

**Decision**: Two exits only — the model stops asking for tools, or the step limit (default 15,
`BYO_MAX_ITERATIONS`) is reached. On the limit, the turn makes one tools-off call with the gathered
history and a note telling the model to answer from what it has; if that call fails, a fixed sentence
is returned. Tool failures are converted to text results. Between iterations, tool results the model
has already read are shortened (`loop/trim.py`) so one large result is not re-sent verbatim.

**Rationale**: Identical to the reference's loop semantics, which is what FR-009/FR-010/FR-011
require. The final tools-off call is the difference between a usable answer and "iteration limit"
with nothing.

**Alternatives considered**: raising the limit until it never trips (rejected: unbounded spend);
silently truncating history (rejected: re-sending a large tool result is cheaper to detect and
explain than to guess at); streaming tool results into the model (rejected: out of scope).

## R6. Tool contract and the closed tool set

**Decision**: A tool is one declaration: name, model-facing description, JSON-schema arguments and
a callable returning a string. The registry dispatches by name, converts exceptions to text, and
records the call for the trajectory. The set is closed at six tools — `create_event`, `list_events`,
`save_note`, `send_message`, `manage_memory`, `update_persona` — each stating in its output exactly
where its artifact landed.

**Rationale**: FR-016 to FR-018. Declaring a tool once and deriving both the model schema and the
documentation avoids the drift the reference warned about (its own registry docstring notes the
registry pattern was adapted once and then copied).

**Alternatives considered**: tool decorators with reflection-driven schemas (rejected: the schema
becomes implicit, which is the opposite of the project's purpose); one tool per calendar provider
(rejected: an adapter-shaped problem pushed into the model's tool list).

## R7. Storage: one SQLite file, FTS5, WAL

**Decision**: `state.db` in the home directory, with the reference's tables — `calendar_events`,
`facts` (+ `facts_fts` and its triggers), `episodes` (+ `episodes_fts`), `chat_log` — minus the two
columns that exist only for the retired hosted-memory integration (`facts.synced`, `facts.scope`).
`PRAGMA journal_mode=WAL` plus `busy_timeout=3000`; idempotent additive migrations in `db.py`.

**Rationale**: FR-005 and FR-020. WAL is a deviation from the reference and is justified by the
spec's edge case that terminal chat and dashboard may write at once; without it, a dashboard write
during a turn surfaces "database is locked" to the person. FTS5 keeps retrieval offline, which the
constitution's offline-first test constraint requires.

**Alternatives considered**: keeping the reference's rollback journal (rejected: two writers, and the
edge case explicitly forbids the lock error); a vector store or embeddings (rejected: a network call
and a service for a local single-user assistant, and the reference's own choice is keyword search);
one file per fact instead of a database (rejected: search over thousands of files is slower than FTS5
and the reference's "open one file" promise weakens).

## R8. Trajectory format, versioning and redaction

**Decision**: One JSON Lines file per local day: `trajectories/YYYY-MM-DD.jsonl`. Event vocabulary is the
reference's: `turn_start`, `gate`, `llm`, `tool`, `consolidation`, `receipt`, `turn_end`, plus
`error` for a failed call. Every `turn_start` carries `trajectory_version: 1`, the turn id, the surface and
the user message. Timestamps are ISO 8601 with an offset; durations are integer milliseconds; usage is
`{"in": n, "out": n}`. Redaction runs in the sink, by field name and by value shape, before the line
is written.

**Rationale**: FR-028 to FR-033. The vocabulary is the compatibility contract: the reference's
renderer groups turns by `turn_start`/`turn_end` and ignores fields it does not know, so our records
render there, while our renderer must tolerate the reference's extra event types.

**Alternatives considered**: a database table for events (rejected: the spec's replay and "open the
file" promise, and the reference's tooling reads JSONL); OpenTelemetry only (rejected: a dependency
and a collector for a local product; JSONL is the always-on floor and OTel can be layered later);
one file per turn (rejected: harder to scan a day, and the reference's daily file is the shape the
timeline command defaults to).

## R9. Dashboard transport

**Decision**: `http.server.ThreadingHTTPServer` with a small router. Static files for the UI; JSON
for reads; Server-Sent Events for the running turn (`/api/chat/stream`); cursor polling for the
observability refresh (`/api/events?cursor=`). One process-wide lock around the shared SQLite
connection; the dashboard builds its own agent instance.

**Rationale**: FR-026/FR-027 and the parity table's Address row. The reference does exactly this,
and it keeps the dependency count at four. SSE is the mechanism that satisfies "steps before the
reply": the loop's observer writes into the response as each step completes.

**Alternatives considered**: FastAPI/uvicorn (rejected: a framework and two dependencies to serve
six routes); WebSockets (rejected: SSE is one-directional, which is all the turn needs, and works
without extra client code); polling only (rejected: fails the "step appears within 2 s" criterion
under a slow provider call).

## R10. Front end: plain files, no build, own visual identity

**Decision**: `index.html`, `style.css` and five classic scripts under `byo/ops/static/js/`, loaded in
order, sharing one global scope, no bundler. The layout reproduces the reference's information
architecture — chat dock, turn card with a stage row and step rows, observability waterfall, memory
and settings views — with this project's own neutral palette and type choices. No reference mark,
font file or design token is copied.

**Rationale**: FR-007 and the parity table's Turn card / Waterfall rows. A build step would break
"one install command" and add a toolchain the constitution's dependency budget does not allow.
Copying the reference's design tokens is forbidden by its brand license, and a neutral palette loses
nothing that the spec asks for.

**Alternatives considered**: a React/Vite front end (rejected: build step, lockfile, and a second
language in a Python repo); reusing the reference's CSS tokens (rejected: license); server-rendered
HTML only (rejected: the turn card must update live while a turn runs).

## R11. Memory policy

**Decision**: A retrieval gate asks one small-model question per turn ("does answering need what we
remember?") and **fails open** — any error means retrieve, with the reason recorded. Retrieval is
FTS5 top-k (default 4). Consolidation runs after a configurable number of unconsolidated exchanges
(default 6), asks the model for candidate facts plus one episode, keeps every proposed fact except one
that only repeats text already recalled this turn, marks the consumed chat rows, and rewrites the
mirror. Nothing is deleted automatically.

**Rationale**: FR-019 to FR-024, and the reference's documented behaviour: the gate is the
distinctive mechanism, and failing open means a slow judge never costs a memory. Dropping exact
repeats of recalled text prevents the "remember what you just told me" loop without a dedupe engine.

**Alternatives considered**: always retrieve (rejected: pointless spend and noise on every turn, and
it removes the mechanism the project exists to show); a vector index (rejected in R7); hash-based
fact dedupe (rejected: near-duplicates with different wording survive a hash and the model is better
at naming them); deleting consolidated chats (rejected: the spec says nothing is deleted
automatically).

## R12. Eval strategy and release gate

**Decision**: `evals/deterministic/` holds pytest files, one per module plus `test_parity_seams.py`.
All model calls go through a scripted adapter fed by JSON scripts in `evals/fixtures/models/`;
golden trajectories live in `evals/fixtures/trajectories/`. `make eval` runs the suite; `make gate` runs it,
prints one line per check, and exits non-zero when any check fails.

**Rationale**: Principle V and FR-034/FR-035. Deterministic 0/1 checks are the only kind that can run
in the default path with no credentials; the golden trajectories double as the replay corpus for FR-037.

**Alternatives considered**: LLM-as-judge in v1 (retired by the clarification session, and the
constitution allows it to be opt-in); snapshot testing of full replies (rejected: brittle against
wording, and it hides *which* behaviour moved); mocking the adapter with `unittest.mock` (rejected:
a scripted adapter is a readable record of the expected conversation and doubles as a fixture).

## R13. Configuration and identity

**Decision**: `BYO_*` knobs with the reference's meanings and defaults: `BYO_HOME`, `BYO_PROVIDER`,
`BYO_API_KEY`, `BYO_BASE_URL`, `BYO_MODEL`, `BYO_SMALL_MODEL`, `BYO_MAX_ITERATIONS` (15),
`BYO_MAX_TOKENS` (8192), `BYO_HISTORY_TURNS` (12), `BYO_CONSOLIDATE_EVERY` (6),
`BYO_RETRIEVAL_TOP_K` (4), `BYO_PORT` (7777). Default home `~/.byo`; persona file `PERSONA.md`;
database `state.db`; trajectories `trajectories/`; mirror `MEMORY.md` and `memory/`; drafts `outbox/`.

**Rationale**: The clarification session chose own names with structure parity. Same defaults keep
the visual and behavioural expectations identical; a distinct prefix and home keep the two agents
from sharing one database.

**Alternatives considered**: reusing the reference's prefix and home (rejected in the clarification:
two agents writing one `state.db`); a TOML config file (rejected: the reference's env + `.env` flow
is what "one key and run" depends on); per-project local homes with migration rules (rejected: extra
resolution logic for a single-user tool).

## R14. Concurrency

**Decision**: Every entry point opens its own SQLite connection; WAL mode plus a 3 s busy timeout;
the dashboard serialises its own writes behind one lock; the trajectory writer appends to the day's file
with a single short-lived append per event.

**Rationale**: The spec's edge case forbids "database is locked" when terminal and dashboard are
used together, and it forbids the visualization from delaying a turn. Appending one line per event
keeps the write window short enough that a dashboard read never waits.

**Alternatives considered**: a single shared process (rejected: the terminal chat and the dashboard
are separate commands); a queue with a writer thread (rejected: unnecessary for one local user, and
it makes "the trajectory is on disk after the turn" harder to guarantee); per-event files (rejected in
R8).

## R15. Clock, timezone and determinism

**Decision**: The session composes the current local date-time with its timezone name and offset,
from a clock seam that tests can replace. Relative-date behaviour is exercised through scripted model
scripts that assert the prompt contains the injected time.

**Rationale**: FR-014 and the edge case about "in 30 minutes". Without a seam, any test that touches
the system prompt is a time bomb; without the timezone name, the model cannot resolve "tomorrow
morning" reliably.

**Alternatives considered**: UTC everywhere (rejected: a personal assistant on a laptop answers in the
person's local day); freezing the clock globally via an environment variable (rejected: it leaks test
concerns into production config).

## R16. Brand and assets

**Decision**: No reference asset is copied — no mark, no font file, no design token, no illustration.
The UI uses system fonts and a neutral token set defined in `style.css`. The reference's layout and
component anatomy are reproduced, not its visual identity.

**Rationale**: FR-007. The reference's code is MIT but its brand files are explicitly excluded
(`LICENSE-BRAND`), and the spec requires the distinction.

**Alternatives considered**: copying the token file and recolouring (rejected: still a copied asset
under a non-MIT licence); shipping the reference's fonts (rejected: same licence problem, and system
fonts remove a binary from the package).
