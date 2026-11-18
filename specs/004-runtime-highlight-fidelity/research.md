# Research: Runtime-Accurate Live Highlighting

**Date**: 2026-11-19 | **Plan**: [plan.md](plan.md) | **Spec**: [spec.md](spec.md)

Scope: resolve every unknown in the plan's Technical Context and choose the mechanism for each
piece of the correspondence. Each decision records what was chosen, why, and what was rejected.

## Evidence gathered before deciding

Three measurements were taken against this checkout, and they drive several decisions below.

1. **Completion stamps, not activity.** A scripted turn with a 1.2 s gate decision and two 2.5 s model
   calls recorded `turn_start` at 0.00 s, `gate` at 1.21 s, `llm` at 3.71 s, `tool` at 3.71 s,
   `llm` at 6.22 s, `receipt` and `turn_end` both at 6.22 s. Every highlight therefore fires only
   after its step has finished; the map is exactly one step behind.
2. **A fixed beat.** `live.js` plays one highlight per 550 ms and flips "running" to "done" after
   650 ms, independent of the recorded `duration_ms` values (1.2 s and 2.5 s in the run above).
3. **A dead turn stays active.** A record with `turn_start`, `gate` and `llm` and no `turn_end`,
   written two days earlier, is still returned by `/api/map` as `active`: `map._active` has no
   liveness test and no age bound, and the browser replays it as live on every visit.

The trajectory today has no record of when a step began, which is why (1) cannot be fixed by
computation in the browser: the information does not exist.

## R1 — Where "a step started" comes from

**Decision**: the runtime writes an additive start record the moment a step begins
(`gate_start`, `llm_start`, `tool_start`, `consolidation_start`), through the existing
`Trajectory.record` sink. The completion records stay exactly as they are.

**Rationale**: the constitution requires one machine-readable, replayable trace and requires every
displayed value to come from it. Start records make the trace able to answer *when*, so a captured
run can be replayed at its true pace — a property the project claims but currently cannot deliver.
Writing through the sink keeps redaction, truncation, locking and the file format in one place.

**Alternatives rejected**: (a) deriving start times from `ts - duration_ms` on the completion record
— correct for a replay but useless while the step is in flight, which is the whole point; (b) a
client-side timer that assumes "model calls take about a second" — a fabricated rhythm, the defect
being fixed; (c) an out-of-band status file the dashboard watches — a second source of truth, and it
would go stale when the writer dies.

## R2 — Shape of the record addition

**Decision**: new distinct types suffixed `_start`, plus one `context` mark record. A `pid` field is
added to `turn_start` and a `degraded` flag to `gate`. The trajectory version stays `1`.

**Rationale**: existing projections iterate over record types. A distinct type falls through
`observability._step` (returns `None`), `spend` (ignores anything that is not `receipt`/`llm`) and
`build_turn.failed`, so step counts, summaries and spend keep their current meaning with no new
branching. A `phase` field on the existing type would instead force every projection to filter and
would silently double counts if one forgot.

**Alternatives rejected**: (a) `phase: start|end` on `llm`/`tool`/`gate`; (b) a single `step` record
with a `step` name and a phase — both put a filtering obligation on every existing consumer.
Version bump to 2 was rejected too: the additions are additive, a bump invalidates nothing
useful, and a reader can detect their absence.

## R3 — Where the correspondence lives

**Decision**: a pure Python module `byo/ops/highlight.py` turns a turn's records into an ordered cue
list and a final state map; the browser applies what it is given.

**Rationale**: the feature's acceptance criteria are claims about correspondence, and the project has
no JS test runner. Keeping the mapping in Python makes every claim testable offline against a
recorded turn, keeps one implementation instead of two (server map + client map), and matches the
project's existing split where the map is a renderer of a server-owned graph.

**Alternatives rejected**: (a) keep the event map in `live.js` and extend it — untestable without a
browser, and it is the arrangement that produced the drift; (b) ship raw events and let a shared
Python/JS algorithm exist twice — guaranteed divergence; (c) compute the current state server-side
only and never send cues — the polling interval would then drop short steps entirely.

## R4 — Transport and cadence

**Decision**: a new read-only `GET /api/live` returns the newest turn, its cues and an `active` flag.
The client polls it every **100 ms** while a turn is running and every **1000 ms** when idle, using a
chained `setTimeout`. `/api/events` keeps its v1 contract and is no longer used by the map.

**Rationale**: 100 ms polling plus a local render fits inside the 150 ms start budget without new
infrastructure. The cue list arrives complete each time, so a completion that happens between polls is
never lost: the next response carries the end cues and `active: false`. Polling is read-only and every
viewer is independent, which the existing contract already promises.

**Alternatives rejected**: (a) server-sent events — `002` already rejected an in-process broadcast
because the terminal is a separate process, and a file watcher plus fan-out is a much larger change;
(b) long-polling — one blocked thread per viewer and a second delivery mechanism for the same data;
(c) keeping 500 ms polling — cannot meet the 150 ms start budget.

## R5 — Telling a live turn from a dead one

**Decision**: `turn_start` records the writer's pid. A turn is live only when it has no end record
*and* its pid is alive; otherwise it is `interrupted`. `Agent.respond` also guarantees a terminal
record (an `error` plus `turn_end`) when it raises, so a failed turn inside a live process is closed
rather than left dangling.

**Rationale**: the record already says *what* happened but cannot say *whether anyone is still there*;
a pid is the smallest honest answer on the two supported platforms, needs no new file, and makes the
dead-turn case immediate instead of heuristic. The guaranteed terminal record removes the common
in-process variant of the same bug.

**Alternatives rejected**: (a) an inactivity watchdog — a legitimate 60 s model call would be mangled
into "interrupted", trading one lie for another; (b) a heartbeat record — more writes, more parsing,
and the same staleness question; (c) an advisory lock file held for the turn — correct but adds a file,
a lifecycle and cross-platform `fcntl` questions for a single boolean; (d) "no end after N minutes"
— unbounded false positives with long turns.

## R6 — The state vocabulary

**Decision**: keep the eight visual states (`idle`, `live`, `done`, `skipped`, `degraded`,
`failed`, `not-reached`, `partial`). A skipped decision puts the gate *and* the memory components in
`skipped`; a missing capability leaves the component `idle` with its existing "not configured"
summary; an interrupted turn marks the last started component `partial`.

**Rationale**: `003` fixed the eight states with pairwise non-hue cues and tests them; adding
"not-used" and "not-configured" states would change that contract and its CSS for no gain, since the
word plus the component's summary and accessible name already carry the distinction. What was broken
was the *assignment*, not the vocabulary: memory was marked "not reached" when it was deliberately
skipped.

**Alternatives rejected**: two new states (breaks the documented state matrix and needs new cues);
reusing `not-reached` (that is the bug); a per-turn summary rewrite for memory nodes (changes the
information each component carries, which the spec forbids).

## R7 — Short steps and catch-up

**Decision**: the browser applies cues in order and, when a step's running and settle cues fall within
150 ms of each other, holds the running state for that short floor before settling. The floor never
delays a later cue and is abandoned when applying it would put the display more than one second
behind the record. Catching up jumps to the true current state and sets the status to `caught up`.

**Rationale**: a tool that returns in 0 ms must still be visible, but a global pace is exactly the
fabrication being removed. A bounded per-pair floor keeps short steps perceivable without inventing a
rhythm for long ones.

**Alternatives rejected**: no floor (sub-frame steps disappear); a global 550 ms beat (the defect); a
server-side queue that replays at a fixed rate (same defect, moved).

## R8 — Computing the final states

**Decision**: `highlight.final_states(records, memory_enabled)` computes the settled map for a turn;
the projection also emits the settle cues at `turn_end`. The browser never accumulates state from
individual transitions alone for the idle view.

**Rationale**: the idle map is what a person reads after the fact, and it must be recomputable from
the record alone — including for a page opened a week later. A server-computed map makes the
truthfulness tests trivial and keeps the client from needing turn-history knowledge.

**Alternatives rejected**: client-side accumulation (a second state machine, untestable); reusing the
event map's implicit behaviour (that is what caused phantom and missing lights).

## R9 — Records written before this feature

**Decision**: a turn without start records is projected as ordered history: each completion record
produces a `done`-type cue at its own timestamp with its recorded duration, no running interval, and a
status line that reads as a replay. A turn without a pid is never live; without `turn_end` it is
interrupted.

**Rationale**: the week of existing trajectories must keep working, and the one thing they must never
do is claim a step is running when the record cannot say so. Back-filling is out of scope by the spec.

**Alternatives rejected**: estimating starts from durations on the *live* path (fabrication); refusing
to render old turns (data loss).

## R10 — Verification strategy

**Decision**: an offline **correspondence eval** (`test_highlight_eval.py`) over recorded fixtures
that reports baseline and post-change scores for four metrics — start alignment, phantom lights,
silent omissions and final-state accuracy — plus unit tests per module and a manual quickstart for
anything that needs real paint timing. The baseline is reproduced by a simulation of today's
playback rules kept inside the test (completion-time lighting, a 550 ms beat, a 650 ms pulse), so the
before/after comparison is mechanical rather than anecdotal.

**Rationale**: the constitution requires a measured before/after for any loop or prompt change, and
the project has no browser test harness. Measuring the *projection* offline covers every semantic
claim; the manual quickstart covers the last mile of paint latency and perceivability.

**Alternatives rejected**: adding Playwright or a JS test runner (a new dependency and a new build
path for one feature); asserting only static text (would not measure correspondence).

## Decisions that need no research

- **No dependency, no build step, no service** — inherited constraints; the design uses the standard
  library and `fetch`.
- **Loopback only, unauthenticated** — unchanged from the existing dashboard.
- **Redaction** — unchanged; the sink redacts every field of a new record exactly as it does today.
- **Map graph, labels, destinations, layout** — unchanged; only what each component's state says,
  and when, is in scope.
