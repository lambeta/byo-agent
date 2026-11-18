# Contract — Turn detail

**Version**: 1 · **Owner**: `byo/ops/turn_detail.py` · **Tests**: `test_turn_detail.py`

The detail is the secondary view behind the map. It answers *what happened in this turn* and
*could not happen if the record does not say it*. Everything here is derived from the projected turn
in [`map-api.md`](map-api.md) §2 and the trajectory records; nothing is persisted.

## 1. Inputs

- `turn`: the v1 projected turn (`steps`, `gate`, `receipt`, `started_at`, `ended_at`,
  `state`).
- `raw`: every record for the turn, in file order.

## 2. Summary line

One line, built in this order:

1. `question`
2. `memory skipped` or `memory retrieved` — only when a gate step exists. Omit the part when
   memory is not configured (no gate record).
3. `N model call(s)` — count of `llm` steps, including a `final` call. Singular when 1.
4. `N tool(s)` — count of `tool` steps. Singular when 1.
5. `X.Y s` — `ended_at - started_at`; when no end, last record's `ts` minus start, plus
   `unfinished`.
6. `$X.XXXX` — the receipt's `usd`; `~` prefix when `estimate`; `cost not recorded` when no receipt.
7. `failed at <stage>` when the state is `failed`; `unfinished` when the state is `unfinished`.

Example outputs:

```text
question → memory skipped → 2 model calls · 1 tool · 3.2 s · $0.004
question → memory retrieved → 1 model call · 0 tools · 0.9 s · $0.0006 · failed at llm
question → memory skipped → 2 model calls · 0 tools · 1.4 s · cost not recorded · unfinished
```

Rules:

- The arrow is `→`; parts are separated by ` · `; the number of seconds has one decimal.
- A duration under 0.05 s rounds to `0.0 s`; it is still a measured value, not "not timed".
- A summary never includes the user's message, a raw argument, a reason phrase or an inferred cause.
- A number that is missing is never rendered as 0; use `cost not recorded` or omit the part where
  the rule says omit.
- The summary is built on the server so the map, the turn list and the detail cannot disagree.

## 3. Timeline

### 3.1 Axis and placement

- Axis start: `turn.started_at`; axis end: `turn.ended_at` if present, else the last record's `ts`.
- `llm` and `tool` steps have a `duration_ms` and a `ts` that is the **end** of the call. Their
  bar starts at `ts - duration_ms` and is as wide as `duration_ms`.
- `gate`, `memory_write`, `error` and the receipt have no duration. They are a minimum-width
  marker at their `ts` (the receipt's `ts` comes from its raw record; if absent, `ended_at`),
  labelled `not timed`.
- `turn_start` is the axis origin; `turn_end` supplies the reply at `ended_at`.
- If the axis has zero length, every marker gets the minimum width and the detail says
  `not timed`; order follows the record, never a guessed timestamp.

### 3.2 Rows

```text
gate                  [ marker ]  memory decision
loop 1                [============]  model · 1.84 s · $0.0039
  tool create_event            []   12 ms · ok
loop 2                [=======]  model · 1.26 s · $0.0036
reply                 [ marker ]  at the end
consolidation         [ marker ]  optional
receipt               [ marker ]  optional
```

- One collapsed row per loop; the row's header is the `llm` step (iteration, model, duration,
  tokens, cost) and its `tool` steps are nested under it. The row can be opened to show the nested
  steps; a failure is visible without opening.
- A `final` `llm` is its own loop row labelled `final answer`.
- A step after the last loop (reply, consolidation, receipt) gets its own row.
- The whole turn has one shared axis; rows are not individually normalized.
- Every row exposes a detail toggle with the recorded input/arguments, output preview, duration,
  outcome, model, token counts, stop reason, cost and error where present. Long values carry the
  sink's truncation marker and the UI does not claim completeness.
- The detail shows the summary and hotspot badges above the rows; the raw record is a `<details>`
  section below them.

### 3.3 Hotspots

- `slowest`: index of the maximum `duration_ms` among steps with a recorded duration; tie to the
  earlier step; `null` when there is no timed step.
- `most_usd`: index of the maximum `usd` among steps with a recorded cost; tie to the earlier
  step; `null` when there is no costed step.
- The row is marked with the words `slowest` and `most $` (text, not only colour). If the value is
  missing, the badge is absent and the legend says `no timed steps` / `no costed steps`.

## 4. Failure, unfinished and unknown

| Case | Detail behaviour |
|---|---|
| `state == failed` | The failing step is marked `failed`, the error text is visible without expanding, rows after it read `not reached`, and the summary ends `failed at <stage>`. |
| Recovered tool error | The tool row stays `failed`; later rows and the reply still render; the turn may be `complete`. |
| `state == unfinished` | The last row is `partial`; no reply row and no cost are invented; the summary ends `unfinished`. |
| Unknown event type | A generic raw row with `type` and the first fields; it does not break the timeline. |
| Corrupted line | Skipped and counted in `skipped_lines`; other records render. |
| Missing duration | Minimum marker, `not timed`; no invented start or duration. |
| Missing cost | `cost not recorded` in the summary; the row shows `not recorded`, never `$0`. |
| Zero-length axis | Minimum markers in record order; a `not timed` note. |

## 5. Raw record

- The raw list is every record for the turn, in file order, including `text`, unknown types and the
  reference's extra event types.
- It is read-only and redacted at the sink. The detail never reconstructs a removed value.
- The raw section is closed by default and does not auto-scroll; it is a `<details>` with a
  `<pre>` of one JSON object per line.
- A huge output is already bounded by the sink; the raw section shows the bounded value and the
  truncation marker.

## 6. Test scenarios

1. A complete two-loop, two-tool turn: row count, order, axis placement, summary exact, hotspots
   point to the right steps.
2. A failed model call: failing row visible, downstream rows `not reached`, summary ends
   `failed at llm`.
3. A recovered tool error: tool row `failed`, reply row present, turn `complete`.
4. An unfinished turn: last row `partial`, no reply, summary ends `unfinished`.
5. A zero-duration/gate-only turn: markers are minimum width, `not timed`.
6. An unknown event type in raw: generic row, rest of the turn unchanged.
7. A truncated tool output: truncation marker present, no full value.
8. A turn with no receipt: `cost not recorded`.
