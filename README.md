<p align="center">
  <img src="byo/ops/static/brand/wordmark.svg" alt="byo — a small, local-first agent" height="140">
</p>

# byo-agent

A small, local-first agent you can read in an afternoon: **harness, loop, memory, operations**.
One SQLite file, one JSON Lines trajectory per day, a terminal chat and a local dashboard that
shows every step of a turn while it runs.

This is a minimal rebuild that keeps the operating shape of `waku-agent` — the four pillars, the
same trace vocabulary, the same turn-card anatomy — with its own name, variable prefix and home
directory. It is not a fork: the model boundary, the trace sink and the dashboard are written here.

## Install

```bash
uv venv && uv pip install -e ".[dev]"
export BYO_API_KEY=...        # the only required setting
uv run byo
```

Without a key, the agent prints the one variable to set and exits 2.

## Use

```bash
byo                      # chat in the terminal; drag while it works
byo dashboard            # http://127.0.0.1:7777 — Overview, Chat, Memory and Observability
byo trajectory           # render the newest recorded trajectory
make eval                # the offline deterministic suite (no key, no network)
make gate                # the same checks, one line each, non-zero on failure
make lint
```

The dashboard opens on **Overview**: the runtime map of surfaces, the memory gate, working
context, the loop and tools, the reply, the memory stores, the trajectory and spend. It lights a
part when its step actually starts and keeps it lit for as long as the step runs — a two-second
model call is a two-second light, not a pulse — and every round and tool call stays countable. From
the browser or the terminal, the map is a projection of the recorded turn, never a re-enactment. Click a node to open its view;
click a loop, tool or reply (or a turn in the list) to read one turn's summary, one-axis timeline,
hotspots and raw record. Evals and release stay command-line tools and are deliberately not on the
map.

## What lives where

```text
~/.byo/               (BYO_HOME)
├── state.db          calendar, facts, episodes, chat log (SQLite + FTS5, WAL)
├── trajectories/     YYYY-MM-DD.jsonl — one line per event, append-only
├── MEMORY.md         the readable mirror, regenerated from state.db
├── memory/<id>.md    one file per fact
├── outbox/           drafted messages (nothing is sent anywhere)
├── PERSONA.md        the persona and standing instructions
└── .env              optional; the process environment wins
```

## How a turn works

1. The **gate** asks one small-model question: does answering need memory? Any failure retrieves
   anyway, and the reason is recorded.
2. **Working memory** is assembled: persona, local clock with timezone, active model, retrieved
   facts, a bounded history.
3. The **loop** calls the model, runs any tools, feeds results back, and repeats until the model
   stops asking or the step limit is hit. At the limit it makes one tools-off call so the person
   still gets an answer.
4. Every step is appended to the **trajectory** before it reaches a surface, so the card and the
   file cannot disagree.
5. Every N exchanges, **consolidation** distils the chat into facts and one episode.

## Reproducing a defect from a trajectory

A bug report should arrive with its trajectory. The procedure:

1. Copy the failing turn's lines out of `trajectories/YYYY-MM-DD.jsonl` into a fixture under
   `evals/fixtures/trajectories/` (or point a test at the file).
2. Read the `tool` and `error` records to see exactly which step failed and with what arguments.
3. Rebuild the same conversation as a script in `evals/fixtures/models/` — the scripted adapter
   replays it with no network — and assert the failure.
4. Fix the defect; the new test stays in `evals/deterministic/` as the regression case.

`byo trajectory <file>` renders any recorded turn; a turn that died mid-way shows as unfinished
rather than disappearing.

## Compatibility with the reference trajectory format

Our timeline renders a trajectory written by the reference project — the fixture
`evals/fixtures/trajectories/reference-sample.jsonl` is checked in and rendered by a test,
including its `hook`, `report`, `score` and `route` records, which appear as generic rows.

The other direction (the reference's renderer reading a trajectory written here) is **not**
verified in this repository: it needs the reference checkout to run. The schema, event names
and field names are kept identical so that direction is expected to work, and `golden-cli.jsonl`
is the file to try it with.

## Layout

```text
byo/            config, db, app, loop/, memory/, tools/, runtime/, gateway/, ops/
evals/          deterministic suite, scripted model scripts, golden trajectories
specs/          the specification, plan, contracts and task list for this build
```

## Notes

- No agent framework: the loop, the tool registry and the context assembly are source here.
- No front-end build step: the dashboard is plain HTML, CSS and five scripts.
- No brand assets from the reference project are used; the layout is the same, the identity is not.
- Nothing is deleted automatically. Your data is yours.
