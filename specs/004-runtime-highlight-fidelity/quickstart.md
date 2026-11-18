# Quickstart — validation scenarios

**Feature**: Runtime-Accurate Live Highlighting · **Date**: 2026-11-19

These scenarios prove that what the Overview map lights is what the agent actually did. The offline
group needs no network and no key; the browser group needs one provider key because it runs real
turns. Contracts live in [contracts/](contracts/); the data rules are in [data-model.md](data-model.md).

## 0. Prerequisites

- macOS or Linux, Python >= 3.11, `uv` installed.
- One provider key for the browser scenarios (`BYO_API_KEY`, or `BYO_PROVIDER` plus the matching key).
- A clean home is recommended: `export BYO_HOME=/tmp/byo-live-home`.
- Restart `byo dashboard` after any Python change; static files are served fresh.
- A second terminal for the CLI scenarios.

```bash
uv venv && uv pip install -e ".[dev]"
```

## 1. Offline checks (SC-001 to SC-005, SC-007, SC-009)

```bash
make eval     # deterministic suite: no network, no key
make gate     # one line per check, non-zero on failure
make lint
```

Pass when every target is green **and** `pytest evals/deterministic/test_highlight_eval.py -s`
prints a before/after table like:

```text
correspondence   baseline   post-change
start aligned      0%         100%
phantom lights     9          0
silent omissions   6          0
final state ok     62%        100%
```

The eval runs the same fixtures through the current playback reference and through
`highlight.py`; the numbers must match the table's direction, not its exact baseline.

## 2. A live turn: the lit component is the one working (SC-001, SC-002, US1)

With the dashboard open on Overview, send from the dock:
`read my notes and then list what is on my calendar on Friday` (a request that makes several model
calls and at least one tool call).

Pass when:

- Surfaces lights at the instant the message is recorded, not after the memory decision;
- while the memory decision runs, **Memory gate** is the only step component reading `running`;
- while the model reasons, **Model** reads `running` for the whole call — a two-second thought is a
  two-second light, not a pulse — and the status line reads `loop 1 · model reasons`;
- while a tool executes, **Tools** reads `running` and the status line names the tool and this turn's
  tool-call count;
- each model call and each tool call is a separate, countable transition; no two steps merge;
- the final call is labelled `final answer` and is distinguishable from a tool-requesting iteration;
- **Trajectory** reads `running` for the whole turn and `done` when it ends;
- when the turn ends the finished picture holds for 0.5–2 s and returns to idle; node positions never
  move and no new scrollbar appears.

## 3. States after the turn (SC-004, US2)

| Scenario | How to produce it | Pass when |
|---|---|---|
| Skipped memory | Ask `what time is it` (no people/projects mentioned) | gate shows `skipped` with its reason; Fact memory, Episodes and Persona show `skipped`, never `not reached` |
| Retrieved memory | Ask a question about a person or project you have stored | gate and the memory path light together; memory components settle to `done` |
| Failed tool | Ask for a calendar read with an impossible date | only Tools reads `failed`, the status names the failure, Reply and Trajectory still complete |
| Memory not configured | `BYO_MEMORY=0 byo dashboard` (or the project's memory-off setting) and send a turn | gate stays `idle` and its text says not configured; it is not skipped, failed or not reached |
| Gate degraded | Point the gate at an unavailable small model, or use a scripted adapter whose gate raises | gate reads `degraded` with the failure reason; the turn still runs |
| Operations untouched | any completed turn | Observability and Spend keep their idle summaries; they are never `not reached` |

## 4. Join mid-turn (SC-006, US3)

1. Start a slow turn in the terminal.
2. Two seconds later open Overview in a browser, and keep a second browser window that was already
   open on Overview.

Pass when:

- the browser that just opened shows the step in flight **now** and the status says it caught up; it
  does not replay the earlier steps as if they were live;
- both windows show the same steps in the same order from the join point and the same final state;
- neither window delays or alters the terminal turn, and closing one changes nothing for the other.

## 5. An interrupted turn never poses as live (SC-005)

Deterministic version:

```bash
export BYO_HOME=/tmp/byo-interrupted
mkdir -p "$BYO_HOME/trajectories"
cat > "$BYO_HOME/trajectories/$(date +%Y-%m-%d).jsonl" <<'JSON'
{"type":"turn_start","turn_id":"t_dead","ts":"2026-11-19T10:00:00.000+08:00","source":"cli","pid":999999,"user_message":"hi","session_id":"default"}
{"type":"gate_start","turn_id":"t_dead","ts":"2026-11-19T10:00:00.100+08:00","model":"small"}
{"type":"gate","turn_id":"t_dead","ts":"2026-11-19T10:00:01.000+08:00","decision":"skip","reason":"no memory needed"}
{"type":"llm_start","turn_id":"t_dead","ts":"2026-11-19T10:00:01.200+08:00","iteration":1,"model":"big"}
JSON
uv run byo dashboard
```

Open Overview. Pass when, within five seconds of loading:

- the status line says the turn is not running (interrupted) and names where it stopped;
- Model reads `partial`; nothing reads `running`; nothing is replayed or animated;
- reloading the page repeats the same truthful state rather than starting a fake live view.

Then reproduce it for real: start a slow turn in the terminal and `kill -9` the CLI. Pass when the
map switches to interrupted within one poll and never returns to running.

## 6. Keyboard, reduced motion, text alternative (SC-008, SC-011, FR-023)

- Tab through the map: every node is reachable, each announces its label, summary and state word.
- Enable "reduce motion" in the OS and repeat §2: the same steps light in the same order with instant
  changes; the status line still names each step.
- Watch the text view under the map during §2: it names the same running component, in the same
  order, with the same state words as the drawing.

## 7. Legacy records (SC-009)

Copy a trajectory file written before this change into a fresh home and open Overview.

Pass when the turn list and the detail are unchanged, the raw record still opens, and the map never
shows a step as running for that turn: history is shown in recorded order without a claimed interval.

## 8. Performance (SC-012)

- With 200 turns in the 7-day window, `/api/live` answers in under 20 ms p95 (checked by
  `test_live_api.py`), and typing in the composer stays under 100 ms echo while a turn streams.
- Watch the dashboard's process: steady-state polling during a turn is one request per 100 ms with
  only newly appended bytes read; idle polling drops to one request per second.

## 9. Nothing else changed (regression)

- Chat, Memory, Observability and Settings render as before.
- The turn card in Chat still streams its steps; the terminal `byo trajectory` still renders a turn
  (new record types appear as their own readable lines).
- `/api/map`, `/api/turn` and `/api/events` answer exactly as documented in
  `specs/002-execution-flow-visualization/contracts/`; `active` in `/api/map` is now `null` for a
  finished or interrupted turn.
