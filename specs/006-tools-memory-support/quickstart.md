# Quickstart: Validating Working Tools & Memory in the Dashboard

**Feature**: specs/006-tools-memory-support | **Date**: 2026-11-19

Runnable scenarios that prove the feature end to end. Prerequisites: `uv venv && uv pip install -e ".[dev]"`
(or the existing `.venv`); no API key or network is needed for the offline scenarios.

## Scenario 1 — The two reported defects stay fixed (offline, primary gate)

```bash
make eval
```

Expected: the suite passes, including the new cases that —
- build the dashboard agent **with memory enabled** and drive a tool-calling turn through
  `/api/chat/stream`, asserting `tool_start` precedes `tool` precedes the reply frames;
- assert `GET /api/tools` returns the six registry tools and trajectory-derived results;
- assert Memory add/edit/forget leaves the store, the `/api/memory` payload and the
  `MEMORY.md` mirror consistent;
- assert every view function referenced by `main.js` is defined and no view builder
  contains the bare-`return`-newline pattern (the "Undefined" regression);
- assert every `map.py` destination is handled by `mapNodeClick` and routes to a hash
  `main.js` renders (the silent-no-op regression).

## Scenario 2 — Memory view renders (browser, 2 minutes)

```bash
export BYO_API_KEY=...   # real key for a live turn
byo dashboard            # http://127.0.0.1:7777
```

1. Open **Memory** in the sidebar. Expected: sections for gate overview, facts, episodes
   and consolidation — content or explicit empty states; the page never shows "Undefined".
2. Add a fact in the view, then check `~/.byo/MEMORY.md`: the fact appears in both.
3. Forget it from the view: it disappears from the view and the mirror.

## Scenario 3 — Tools node and Tools view (browser, 2 minutes)

1. On **Overview**, click the **Tools** node. Expected: the dashboard navigates to the
   Tools view — six tool cards (name, description, schema) plus a Results area.
2. In the chat dock, ask for something needing a tool ("what's on my calendar this week?").
   Expected: a tool lane appears live in the dock before the reply; afterwards the Tools
   view's Results area lists that call with its outcome and duration.
3. Re-open Overview and click Tools again: the same view opens. A click is never silent.

## Scenario 4 — CLI/dashboard parity (offline)

Covered by `make eval`: one scripted tool-and-memory scenario runs through both the
terminal path and the dashboard chat path; the recorded trajectories carry the same
event-kind sequence (gate → loop(s) → tool(s) → reply → receipt).

## Scenario 5 — Live smoke (optional, uses the real model)

With `BYO_API_KEY` set: teach the agent a fact in one session ("remember that I take my
coffee black"), start a new chat later, and ask something that needs it. Expected: the
gate decides to retrieve (visible on the map and in the Memory view's gate overview), and
the reply uses the fact.
