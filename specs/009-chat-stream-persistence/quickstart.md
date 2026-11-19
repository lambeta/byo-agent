# Quickstart — Validating Chat Stream Persistence Across Navigation

**Feature**: specs/009-chat-stream-persistence | **Date**: 2026-11-19

These scenarios prove the fix end to end. The offline group needs no network and no key; the browser
group needs one provider key because it runs real turns. Shapes and rules live in
[data-model.md](data-model.md) and [contracts/chat-live-turn.md](contracts/chat-live-turn.md).

## 0. Prerequisites

- macOS or Linux, Python >= 3.11, `uv` installed.
- A clean home is recommended: `export BYO_HOME=/tmp/byo-chat-live`.
- One provider key for the browser scenarios (`BYO_API_KEY`, or `BYO_PROVIDER` plus the matching
  key).
- Restart `byo dashboard` after any Python change; static files are served fresh (hard-refresh the
  browser if a JS file changed).

~~~bash
uv venv && uv pip install -e ".[dev]"
~~~

## 1. Offline checks (primary gate)

~~~bash
make eval     # deterministic suite: no network, no key; baseline 349 + new cases
make gate     # one line per check, non-zero on failure
make lint
~~~

Pass when every target is green and the new `test_chat_lifecycle.py` cases are present:

- a running turn keeps the session it started in when `new_session()` runs mid-turn;
- a failing stream preserves its partial text and the transcript reports `failed`;
- a disconnected stream still leaves the completed turn in `chat_log`;
- the client source contracts pin: no live-turn clear on `hashchange` or chat selection, a
  session-scoped visibility predicate, a second-send guard, a `clearLive` single writer, and a
  handoff that clears only after the transcript is assigned.

## 2. Mid-stream sidebar navigation (SC-001, SC-002, US1)

Start:

~~~bash
byo dashboard   # http://127.0.0.1:7777
~~~

1. Send a request that produces a long answer, for example:
   `Write a 400-word explanation of how a local agent loop works, with a short list at the end.`
2. After a few words have streamed, click **Tools** in the sidebar. Stay there for 3–5 seconds.
3. Click **Overview**.

Pass when:

- the chat dock on **Tools** continues to show the thinking/tool/output lanes updating;
- on return, every fragment received while away is present, in order, exactly once;
- the stream continues from where it was — no restart, no gap, no duplicated text;
- the composer still has any draft you typed while away.

Repeat with **Memory**, **Observability**, **Settings**, browser Back/Forward, and a map-node link.
All must behave the same.

## 3. Completion while away (SC-003, SC-008, US2)

1. Send a request that streams for several seconds.
2. While it streams, click **Memory** and wait for the turn to finish there.

Pass when:

- the chat dock shows the completed turn once, without a page reload and without changing the
  selected destination;
- returning to **Overview** shows exactly one user message and one assistant reply for the turn;
- the final text matches what streamed; there is no duplicate reply and no missing tail;
- the live card is gone; the folded trace opens the turn's thinking and tool calls.

## 4. Chat selection and a new chat (SC-003, US3)

1. Send a request that streams for several seconds.
2. While it streams, select a past chat from the history picker.
3. Return to the sending chat.
4. Start another slow turn, then click **+ New chat** while it streams.

Pass when:

- the past chat shows only its own history; the live turn is not shown there and is not cancelled;
- returning to the sending chat restores the full accumulated live turn;
- the new chat does not show the previous turn's card; the dock's status line says a turn is still
  running in another chat;
- after the old turn completes, selecting its chat shows exactly one transcript entry.

## 5. Shell actions (US3)

With a turn streaming:

- collapse and reopen the chat dock;
- drag the dock resizer;
- toggle the theme;
- resize the window to 900 and 375 px and confirm the notice line does not overlap the composer;
- expand a folded trace in the transcript;
- open a turn detail from the map.

Pass when the accumulated live content is intact after every action and the stream finishes normally.
Collapsing hides the card but does not stop it; reopening shows the accumulated content and the
running indicator.

## 6. Failure and step limit (SC-004, SC-009)

**Failed turn (browser).** Start with a valid key but an invalid model, or a model the provider
rejects:

~~~bash
BYO_MODEL=definitely-not-a-model byo dashboard
~~~

Send a message, then click **Memory** before it fails. Pass when:

- the transcript shows the assistant row with a `failed` cue and the error text;
- if any partial text streamed before the failure, it appears above the error under a "partial
  output" label;
- no blank or stranded live card remains;
- the same row is present after switching away and back.

**Step limit (browser).** Run with `BYO_MAX_ITERATIONS=1` and ask for something that needs two
tools ("check my calendar and then save a note"). Pass when the reply plainly says the step limit
was reached, the transcript carries a `limited` cue, and navigating away mid-turn does not lose it.

## 7. Reload and disconnect (SC-005, FR-012)

1. Start a slow turn, then reload the page mid-turn.
2. After the turn would have finished, reload once more.

Pass when:

- the live stream does not resume in the page (explicitly out of scope), but the turn still finishes
  on the server;
- the next load shows the completed turn once in its chat's history;
- closing the tab does not cancel the turn (the existing disconnect test also covers this).

## 8. Regression (SC-007)

- With no turn running, switch between all five destinations: each renders as before.
- The Tools, Memory, Observability and Settings views are unchanged.
- The terminal `byo` chat still works; `byo trajectory` still renders the turn.
- `make eval` remains green; `make lint` is clean.
- No new external request: the dashboard still loads only `/static/*` and its own `/api/*` routes.

## 9. What "pass" is not

- A live card that keeps the old text but stops updating is a failure.
- A transcript that shows the reply twice (live card plus bubble) is a failure.
- A new chat that shows the old live card is a failure.
- A failed turn that silently disappears is a failure.
- A fix that only hides the symptom by disabling navigation or the composer is not accepted.

## Validation record — 2026-11-19

Method: headless Chrome (CDP) against a scripted slow adapter that streams 20 fragments 150 ms
apart, with a fresh `BYO_HOME` and no provider key. The automated suite adds the failure, unexpected
exception and step-limit cases; the browser scenarios cover navigation, completion, chat ownership,
shell actions and reload.

| Scenario | Method | Result | Evidence |
|---|---|---|---|
| 2 mid-stream sidebar navigation | browser | PASS | On Tools the output kept growing (fragments 1–14); returning to Overview continued from fragment 15 with no restart or gap; the draft stayed in the composer. |
| 3 completion while away | browser | PASS | Completed on Memory: live card empty, exactly 2 bubbles, full reply through fragment-20, no notice, no duplicate after returning. |
| 4 chat selection and new chat | browser | PASS | New chat hid the card and showed “A turn is still running in another chat”; selecting `default` restored the live output at fragment-11; completion left 4 bubbles in that chat. |
| 5 shell actions | browser | PASS | Collapse/reopen, theme toggle, 1280/900/375 px viewports (no notice/composer overlap, no horizontal overflow), trace expansion and a second send all kept the stream; the refused second send kept its draft. |
| 6 failure and step limit | browser + pytest | PASS | Browser: a failed turn shows the FAILED chip and “partial-1 … partial-3” above “Refused: provider refused”; the live card is empty. Pytest: failed stream, unexpected exception and limit-turn state. |
| 7 reload and disconnect | browser + pytest | PASS | Reload mid-turn did not resume the live card; after completion the next load showed 4 bubbles and the full reply. The disconnect test also asserts the chat_log rows. |
| 8 regression | pytest | PASS | 369 tests, `make lint` clean, seven static scripts unchanged, no new external request. |
