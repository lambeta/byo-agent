# Implementation Plan: Runtime-Accurate Live Highlighting

**Branch**: `004-runtime-highlight-fidelity` | **Date**: 2026-11-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-runtime-highlight-fidelity/spec.md`

**Amends**: `specs/002-execution-flow-visualization` FR-009/010/013/014/025 as recorded in
[contracts/record-additions.md](contracts/record-additions.md) and
"Relationship to prior specifications" in the spec. The map graph, its identity and its routes stay as
they are.

## Summary

Make the Overview map tell the truth about a run. Today the map lights a component only when its step
has finished, holds "running" for a fixed 650 ms, replays on a fabricated 550 ms beat, and reports
states the record does not support. The fix has three parts:

1. **The record learns when a step starts.** Four start records (`gate_start`, `llm_start`,
   `tool_start`, `consolidation_start`) plus one `context` record join the existing append-only
   trajectory, additively, so the trace alone can reconstruct the timeline. A turn also records the
   writer's pid so a dead turn is never mistaken for a live one, and a turn always ends with a
   terminal record even when the process raises.
2. **One projection owns the correspondence.** A new pure module, `byo/ops/highlight.py`, turns one
   turn's records into an ordered list of component-state cues and the turn's final state map. It is
   the only place that decides what lights, when, and in which state; the browser no longer maps
   events.
3. **The browser becomes a sequencer.** `live.js` polls a new read-only `GET /api/live` (100 ms while
   a turn runs, 1 s when idle), applies the cues it is given, holds sub-150 ms steps long enough to be
   seen, and jumps — announcing catch-up — when it is behind. It never invents a rhythm, never replays
   old steps as running, and never overrides the step name in the status line.

A small cached, incremental feed reader (`byo/ops/feed.py`) keeps 10 polls per second cheap on a
200-turn, 7-day home, and a pid check (`byo/ops/liveness.py`) answers the one question the record
cannot: is the writer still there?

## Technical Context

**Language/Version**: Python >= 3.11 (repository floor; the development virtualenv is 3.14) for the
record, projection and HTTP layer; plain ES2017 in classic `<script>` files for the browser. No
TypeScript, no framework.

**Primary Dependencies**: none added. The four runtime dependencies and the `pytest`/`ruff` extras
stay as they are. The new server code uses the standard library only (`json`, `os`, `threading`,
`http.server`); the new browser code uses `fetch` and `setTimeout` only.

**Storage**: no new tables and no new store. New record **types and fields** in the existing
`trajectories/YYYY-MM-DD.jsonl`, written by the existing `Trajectory` sink so redaction, truncation
and the append-only guarantee are unchanged. `state.db` is untouched. The turn list, node summaries
and detail remain projections over the same files.

**Testing**: `pytest` under `evals/deterministic/` with temporary homes, scripted model adapters and
golden trajectory fixtures. New byte-level tests for the record additions, unit tests for the cue
projection and the final-state table, API tests for `/api/live`, a feed-cache test, a pid-liveness
test, and an offline **correspondence eval** that prints baseline and post-change scores. Browser
timing, keyboard and reduced-motion behaviour are checked by `quickstart.md`; no JS test runner is
added, and the client contains no correspondence logic to test.

**Target Platform**: macOS 13+ and Linux, one user account, `127.0.0.1` only. The terminal and the
dashboard remain separate processes against the same home; the dashboard serves every viewer from
one process and may itself run the turn.

**Project Type**: single project — an installable Python package with a locally served, plain static
web UI. No frontend project, no bundler, no build step.

**Performance Goals**: a recorded step reaches the paint within **150 ms** of its recorded start
(SC-002); the displayed state never lags the record by more than **1 s**; `GET /api/live` returns in
under 20 ms p95 on a 200-turn, 7-day home; the feed reader costs O(new bytes) per poll, not O(file)
and never O(window); the composer keeps its sub-100 ms echo while a turn streams.

**Constraints**: no new runtime dependency or service; loopback only; every displayed value derived
from the record; redaction and truncation preserved at the sink; the eight visual states unchanged;
the map's graph, labels, destinations and layout unchanged; legacy turns must open correctly and
must never claim a running interval the record cannot support; the offline suite must keep passing.

**Scale/Scope**: one live turn at a time, 7-day window, 200 turns and 20 steps per turn in the target
home, 2–3 concurrent viewers, 4 new start records + 1 mark record + 3 additive fields (`pid`,
`degraded`, `turn_end.state`), 1 new read-only endpoint, 3 new Python modules, 1 rewritten static
script.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Evidence |
|---|---|---|
| I. Build From Primitives | PASS | The cue projection, feed cache, liveness check and browser sequencer are source in this repository. Nothing is delegated to a framework, a graph library, a telemetry SDK or a browser animation library. Each new module carries the house design note (mechanism + rejected alternative). |
| II. Provider-Agnostic Model Boundary | PASS | No adapter file changes. The start records are emitted by the app and the loop around the adapter; the gate's degraded flag is set in `retrieval_gate`, which already owns that failure path. Nothing branches on a provider. |
| III. Small Modules With Narrow Contracts | PASS | `highlight.py` is pure (records in, cues out, no I/O, no clock beyond an injected `now`); `feed.py` owns incremental reading only; `liveness.py` answers one boolean; `dashboard.py` routes. `live.js` shrinks to a scheduler and renderer. Cards are written in `contracts/` and each module is testable alone. |
| IV. Observable by Default | PASS, strengthened | These are the first changes that make the trace able to answer *when*, not only *what*: a captured trajectory now replays the timeline exactly. Redaction still happens inside `Trajectory.record` before anything is written, so start records cannot leak. No second store and no parallel status model is introduced. |
| V. Eval-Driven Behavior Change (NON-NEGOTIABLE) | PASS | The loop and app gain observation points, so an eval is mandatory. The plan adds an offline correspondence eval that scores a fixture set twice: once through a simulation of today's playback rules (light at completion, 550 ms beat, 650 ms pulse) and once through the new projection, reporting baseline and post-change numbers plus one regression case per fixed defect. Model requests, prompts, tool descriptions and memory policy are unchanged, so the existing golden set must not move and is run unchanged as the "no behavior drift" evidence. |
| Additional constraints | PASS | Dependency count unchanged; no build step; tests run offline; loopback bind only; no credential reaches a new payload; the eight non-hue state cues and their CSS selectors are untouched; the map has still no node for a retired capability. |

### Amendment recorded (not a violation)

`002` FR-025 forbade new event types. The intent was to forbid a *second turn store* and a
*parallel status model*, both of which this plan also forbids. Truthful start alignment is
impossible without the record saying when a step began, so the plan uses the existing sink to add
**additive** record types and fields, keeps readers tolerant of records that lack them, and treats
"the record is the only source" as the rule that governs every new field. The amendment, its
backward-compatibility rules and the consumers' obligations are written in
[contracts/record-additions.md](contracts/record-additions.md). The parity test that asserted the
exact eight-type vocabulary is updated to assert the growth explicitly rather than being deleted.

## Project Structure

### Documentation (this feature)

```text
specs/004-runtime-highlight-fidelity/
├── plan.md              # this file
├── research.md          # Phase 0: decisions, rationale, rejected alternatives
├── data-model.md        # Phase 1: records, cues, states, liveness, feed
├── quickstart.md        # Phase 1: runnable validation scenarios
├── contracts/
│   ├── record-additions.md   # new record types/fields, additivity, compatibility
│   ├── highlight-cues.md     # cue grammar, ordering, state and timing rules
│   └── live-api.md           # GET /api/live, cadence, errors, relationship to v1 routes
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # Phase 2 output (/speckit-tasks), not created here
```

### Source Code (repository root)

```text
byo/
├── app.py                        # [modified] gate_start/context/consolidation_start records;
│                                 #            RECORDED vocabulary; guaranteed terminal record
├── loop/
│   └── agent.py                  # [modified] notify llm_start / tool_start around each step
├── memory/
│   ├── __init__.py               # [modified] consolidation reports when it begins
│   └── retrieval_gate.py         # [modified] gate records a structured degraded flag
└── ops/
    ├── trajectory.py             # [modified] turn_start carries the writer pid; turn_end state
    ├── feed.py                   # [new] cached incremental JSONL reader (O(new bytes))
    ├── liveness.py               # [new] is this pid still alive?
    ├── highlight.py              # [new] records -> ordered cues + final state map
    ├── observability.py          # [modified] start records never become turn steps or spend
    ├── map.py                    # [modified] event map covers the new records; active = live only
    ├── dashboard.py              # [modified] GET /api/live; /api/events uses the cached feed
    ├── show_trajectory.py        # [modified] readable lines for the new record types
    └── static/
        ├── js/map.js             # [modified] status line split (step vs transport note); helpers
        ├── js/live.js            # [rewritten] /api/live polling, cue sequencer, catch-up, settle
        ├── js/main.js            # [modified] mount rule: complete turn is idle, running is current
        └── style.css             # [modified] the note element; no new states, no new hues

evals/
├── deterministic/
│   ├── test_record_additions.py  # [new] new records are additive, redacted, ordered, compatible
│   ├── test_highlight.py         # [new] cue projection + final-state table for every case
│   ├── test_highlight_eval.py    # [new] the correspondence eval, prints baseline vs post score
│   ├── test_feed.py              # [new] incremental read equals a full read; truncation reload
│   ├── test_liveness.py          # [new] dead pid -> interrupted; live pid -> running
│   ├── test_live_api.py          # [new] /api/live payload, cadence hints, errors, idle, legacy
│   ├── test_map.py               # [modified] event map covers start records + context
│   ├── test_map_api.py           # [modified] active means live; interrupted turns are not active
│   ├── test_timing.py            # [modified] observer vocabulary now includes start notices
│   ├── test_loop.py              # [modified] same observer sequence, start notices included
│   ├── test_dashboard.py         # [modified] same streamed kinds, start notices included
│   ├── test_parity_seams.py      # [modified] the vocabulary amendment is asserted, not dropped
│   └── test_map_static.py        # [modified] live.js polls /api/live and owns no pacing constant
└── fixtures/
    ├── models/                   # existing scripts; two gain delay_ms for the live scenarios
    └── trajectories/             # [new] one v1 legacy turn and one turn with start records
```

Existing contracts: `specs/002-execution-flow-visualization/contracts/live-feed.md` is superseded for
the Overview map by [contracts/live-api.md](contracts/live-api.md); during implementation it gains a
one-line "superseded by 004" pointer so a reader of the old contract is not misled. The v1
`/api/events` route and its contract are **not** changed.

**Structure Decision**: single project, and the correspondence lives on the server. The decisive
choice is that the browser must not decide what lights: if the mapping lived in JavaScript, the
project could not test the claim that the map matches the run without adding a JS test runner, and
the browser would become a second source of truth — exactly the failure this feature fixes. Putting
the projection in `highlight.py` makes every acceptance criterion of the spec testable offline
against a recorded turn, keeps `live.js` to scheduling and rendering, and preserves the existing
split where `map.py` owns the graph and `dashboard.py` only routes.

## Complexity Tracking

None. The three new modules each replace logic that already existed elsewhere (playback pacing in
`live.js`, ad-hoc event mapping, per-poll full-file reads) rather than adding layers; there is no new
dependency, no new service, no new store and no new visual state.

## Phase 0: Outline & Research

Complete — see [research.md](research.md). Every Technical Context field is resolved; no unresolved
clarification remains. The decisions that shape the structure are:

- **R1 Where "a step started" comes from** — additive start records in the existing sink, because the
  trace is the only source of truth and the client must not guess.
- **R2 Record shape** — distinct `*_start` types rather than a `phase` field, so existing projections
  (`_step`, spend, turn summary) ignore them with no change to their logic.
- **R3 Where the correspondence lives** — a pure Python projection behind `GET /api/live`, not a
  client-side event map.
- **R4 Transport and cadence** — 100 ms polling of an incremental feed cache while live, 1 s when
  idle; no SSE, no long-poll, no fixed animation beat.
- **R5 Dead turns** — the writer's pid in `turn_start` plus a guaranteed terminal record, not a
  heartbeat, a lock file or a timeout guess.
- **R6 State vocabulary** — keep the eight visual states; "not used" is skipped-with-a-reason and
  "not configured" is an idle component whose text says so.
- **R7 Sub-100 ms steps and catch-up** — a short client-side dwell bounded by the one-second lag
  rule, instead of a global pace.
- **R8 Final states** — computed once per turn from its records and the memory configuration, not
  accumulated by the browser.
- **R9 Legacy records** — read as ordered history with no running interval, never back-filled.
- **R10 Verification** — an offline correspondence eval plus the existing manual quickstart; no JS
  test runner.

## Phase 1: Design & Contracts

Complete — the artifacts below are generated beside this plan:

- [data-model.md](data-model.md) — the record additions, the cue entity, the eight-state truth
  table, the liveness model and the feed cache invariants.
- [contracts/record-additions.md](contracts/record-additions.md) — new types and fields, ordering and
  redaction guarantees, consumer obligations and backward compatibility.
- [contracts/highlight-cues.md](contracts/highlight-cues.md) — the cue sequence, one-to-one rules,
  state mapping, timing rules, status labels and interrupted/legacy behaviour.
- [contracts/live-api.md](contracts/live-api.md) — `GET /api/live`, its payload, the mount rule the
  client applies, polling cadence, errors and its additive relationship to `/api/map` and
  `/api/events`.
- [quickstart.md](quickstart.md) — the live, skip, retrieve, failed-tool, degraded-gate, interrupted,
  join-mid-turn, reduced-motion, text-view and legacy checks.

No database migration is generated. No trajectory version bump is taken: the additions are additive
and readers tolerate records that lack them, which is cheaper and safer than invalidating a week of
existing turns. The amendment is a vocabulary change recorded in the contract, not a format break.

## Constitution Check (post-design)

Re-evaluated against the artifacts above. Verdicts unchanged: I–V all PASS.

- The correspondence is source, not configuration: `highlight.py` contains the mapping table and the
  state rules, and a test walks every record type.
- The provider seam is untouched; no file under `byo/loop/adapters.py` or the adapters package changes,
  and the loop's new notifications are provider-neutral callbacks.
- Each module has one job and a contract: records (`trajectory.py`), reading (`feed.py`), liveness
  (`liveness.py`), correspondence (`highlight.py`), transport (`live-api.md`), sequencing (`live.js`).
- The trace now reconstructs a run's timeline, and every new record passes through the same sink
  redaction. No second store appears.
- The eval-driven gate is satisfied by `test_highlight_eval.py` reporting baseline and post-change
  correspondence, plus a regression case per fixed defect; the existing golden trajectories are run
  unchanged to prove the loop's behavior did not move.

One spec precision carried into design: the eight visual states do not grow (FR-007). "Not used this
turn" is the skipped state with its recorded reason, and "not configured" is an idle component whose
summary already says so. This keeps `003`'s state-cue contract and its CSS tests intact.

## Risks and Sequencing Notes

- **Highest risk: the record change.** Adding types to an append-only file that other projections read
  can quietly double counts (spend, step lists) if a consumer treats every line as a step. Mitigation:
  the new types are ignored by `_step` and `spend` by construction, a contract states the obligation,
  and a test runs a full turn through every projection to prove step counts, spend and the turn
  summary are unchanged.
- **Second: polling cost.** Ten requests per second must not walk 7 days of files. Mitigation:
  `feed.py` reads only appended bytes, keyed by size and mtime, with a full-reload fallback on
  truncation; `test_feed.py` proves incremental equals full and `test_live_api.py` guards the p95.
- **Third: a racing completion.** A turn can end between two polls. Mitigation: `/api/live` always
  returns the newest turn with its cues and an `active` flag, so the last cues are always delivered;
  the client's mount rule (a completed turn on load is idle) prevents history from playing.
- **Fourth: legacy records and the dead-turn rule.** Old turns have no pid and no start records.
  Mitigation: a missing pid means "not live", and the projection emits ordered history with no
  running interval; two fixtures (legacy and new) pin both paths.
- **Fifth: the min-dwell rule drifting into a fake rhythm.** Mitigation: dwell is capped by the
  one-second lag rule and applies only to running/settle pairs closer than 150 ms; a static test
  asserts `live.js` contains no global cadence constant and reads `at` from the cue.
- **Sequencing.** (1) record additions + projections unchanged; (2) liveness and interrupted turns;
  (3) cue projection + final-state table; (4) feed cache + `/api/live`; (5) the browser sequencer and
  the status-line split; (6) compatibility, contract pointers and quickstart. Each step leaves the
  suite green, and the eval can be run after step 3 against fixtures before any UI exists.
