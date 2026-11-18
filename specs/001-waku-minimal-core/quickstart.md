# Quickstart — validation scenarios

**Feature**: Waku-Parity Minimal Agent Core · **Date**: 2026-11-18

Five end-to-end scenarios, one per success criterion cluster. Run them in order; each names what
"pass" looks like. Implementation lives in `tasks.md`, contracts in `contracts/`, storage rules in
`data-model.md`.

## 0. Prerequisites

- macOS or Linux, Python >= 3.11.
- One provider key (Anthropic-wire or OpenAI-wire provider).
- Scenarios 4–6 also run offline; you can do those first if you want a no-key smoke test.

## 1. Install and first turn (SC-001)

```bash
uv venv && uv pip install -e ".[dev]"
export BYO_API_KEY=...          # the only required variable
uv run byo
```

Type: `book a catch-up with Alex on Friday`.

Pass when, in order: the panel prints the home path and model; a `gate` line, a `tool ·
create_event(...)` line and a second model call appear **before** the reply; the reply names the
time and says the event is in `state.db`; and `byo trajectory` then shows the same turn.

Count your commands: install, export, run, ask — four, inside five minutes.

## 2. The dashboard turn card (SC-002, SC-003)

```bash
uv run byo dashboard        # → http://127.0.0.1:7777
```

Send the same request in the browser. Pass when:

- the gate decision appears first, then one row per loop iteration and one row per tool call;
- each row shows duration and outcome, and the tool row shows args and a result preview;
- the reply streams in; the receipt's tokens and cost equal the `receipt` record in the trajectory;
- opening the observability view shows the same turn as a waterfall with one closed row per loop.

Timing check: with a tool slowed to 1.5 s (scripted model fixture), the tool row is visible while
the reply is still streaming.

## 3. Memory across processes (SC-004)

```bash
uv run byo            # say: "Remember that Alex prefers morning meetings."
# quit, start again
uv run byo            # ask: "When should I book Alex?"
```

Pass when the second process recalls the fact, the turn's card shows it was retrieved, and
`<home>/MEMORY.md` plus `<home>/memory/<id>.md` contain it. Then ask something that needs no memory
(`what is 2+2?`) and pass when the gate records `skip` with a reason.

## 4. Offline suite and release gate (SC-005)

```bash
make eval     # pytest over evals/deterministic, no network, no key
make gate     # same checks, one line each, non-zero exit if any fails
```

Pass when `make eval` passes with networking disabled in under three minutes, every retained
behavior has at least one check, and `make gate` prints a per-check report. Break one on purpose
(lower `BYO_MAX_ITERATIONS` to 1 in a test) and pass when the gate exits non-zero naming that check.

## 5. Trajectory replay and cross-rendering (SC-003, SC-010)

```bash
uv run byo trajectory                     # newest trajectory in <home>/trajectories/
uv run byo trajectory <path>.jsonl        # a specific one
```

Pass when the timeline indents the turn's events, shows durations, usage and cost, and reports (but
survives) a deliberately corrupted line. Then render `evals/fixtures/trajectories/reference-sample.jsonl`
(captured from the reference) — pass when its extra event types appear as generic rows and nothing
is dropped. Finally, render our golden trajectory through the reference's timeline renderer — pass when
it parses with zero errors.

## 6. Secrets and parity (SC-008, SC-006)

```bash
grep -r "sk-" <home>/trajectories/ && echo LEAK || echo CLEAN
```

Pass when the grep finds nothing, including after a turn whose prompt accidentally contains a
key-shaped string. Parity pass: run one scripted turn through both agents and compare commands,
route shapes, file layout, trajectory vocabulary and card anatomy against the checklist in
`specs/001-waku-minimal-core/spec.md` (Parity Seams).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Missing BYO_API_KEY` on start | no key in env or `.env` | export it or write `<home>/.env` |
| Port 7777 already in use | a dashboard is already running | `BYO_PORT=7778 uv run byo dashboard` |
| Dashboard shows a turn as "unfinished" | the process died mid-turn | expected; the trajectory is intact — re-run the turn |
| Receipt shows "estimate" | model missing from the pricing table | add it to `ops/pricing.py` |
| `database is locked` | two writers without WAL | check `PRAGMA journal_mode` on the home database |
