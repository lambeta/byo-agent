# Contract — Tools

**Version**: 1 · **Owner**: `byo/tools/registry.py` and the five tool modules ·
**Consumers**: `byo/app.py`, the loop, the trajectory · **Tests**: `test_tools.py`, `test_calendar.py`,
`test_memory_admin.py`

A tool is one declaration: a name the model calls, a description the model reads, a JSON schema for
its arguments, and a callable that returns text. That is the whole contract — there is no decorator
magic and no reflection.

## 1. Declaration

```python
@dataclass(frozen=True)
class Tool:
    name: str                  # snake_case, stable, what the model calls
    description: str           # one or two sentences, written for the model
    input_schema: dict         # JSON Schema object with "type": "object"
    fn: Callable[..., str]     # returns text; raises only for bugs
```

The registry exposes `schemas()` (what the model is told) and `execute(name, args)`. `schemas()` and
the model-facing documentation are generated from the same declarations, so they cannot drift.

## 2. Dispatch rules

| Situation | Result the model observes |
|---|---|
| Name not registered | `Error: unknown tool '<name>'` — never an exception |
| Arguments fail validation | `Error: <tool> needs <field> ...` |
| The callable raises | `Error: <exception type>: <message>` — the turn continues (FR-011) |
| Success | the tool's text, unmodified |

A tool never prints, never writes to stderr and never opens a network connection. A tool that needs
the clock reads it from the session's clock seam, never from `datetime.now()` directly.

## 3. The six tools (closed set — FR-017)

### `create_event`
Arguments: `title` (string, required), `start` (ISO 8601 with offset, required), `end` (ISO 8601,
optional), `attendees` (string, optional, comma-separated), `notes` (string, optional).
Writes one row to `calendar_events`. Returns: `Created event <id>: <title> at <start> (saved in
<home>/state.db).`

### `list_events`
Arguments: `start` (ISO date or datetime, optional), `end` (optional). Defaults to today.
Reads `calendar_events` in range, ordered by `start`. Returns one line per event
(`<id> · <start> · <title> (<attendees>)`) or `No events between <a> and <b>.`

### `save_note`
Arguments: `subject` (string, required), `content` (string, required).
Writes one `facts` row with `source = 'tool'` and regenerates the mirror. Returns:
`Saved: [<subject>] <content> (in <home>/state.db and <home>/memory/<id>.md).`

### `send_message`
Arguments: `to` (string, required), `body` (string, required).
Writes one markdown file under `outbox/` (`<timestamp>-<slug>.md`, front matter `to/created_at`).
Returns: `Drafted to <home>/outbox/<file> — not sent anywhere.` The wording is intentional: there is
no transport in v1 and the tool must not imply one (FR-018).

### `manage_memory`
Arguments: `action` (`"list"`, `"edit"` or `"forget"`, required), `id` (int, required for edit and
forget), `subject` (optional), `content` (optional).
`list` returns the newest facts (bounded); `edit` updates a fact and its mirror; `forget` deletes the
row, its FTS entry and its memory file. Returns a sentence naming what changed and where.

### `update_persona`
Arguments: `content` (string, required) — the complete new persona text.
Rewrites `PERSONA.md` (keeping the old file as `PERSONA.md.bak`) and reports the byte count.
Returns: `Persona saved to <home>/PERSONA.md (<n> bytes). The next turn uses it.`

## 4. Output rules

1. **Say where it landed.** Every output names the concrete path or row id. "Saved" without a
   location is a defect (FR-018).
2. **Never claim a sync.** Nothing leaves the machine. The outbox wording is the canonical example.
3. **Paths are absolute or home-relative, never invented.** The home comes from settings.
4. **Text only.** No markdown tables the model must parse, no JSON envelope unless a list needs one.
5. **Bounded lists.** `list_events` and `manage_memory` cap at 20 rows and say how many more exist.

## 5. Validation and failure

- `create_event` rejects a `start` that does not parse, with the expected format in the message.
- `send_message` slugifies `to` and falls back to `message` when the slug is empty.
- `manage_memory` with an unknown id returns `No fact with id <n>.`, not an error exception.
- Every tool catches its own storage errors and returns them as `Error: …` so the model can explain
  them; the loop's error containment is the second line of defence, not the first.

## 6. Tests

Each tool has a test that (a) writes through the registry, (b) asserts the stored row or file, and
(c) asserts the returned text names it. `test_tools.py` covers the dispatch rules (unknown tool,
bad arguments, raising callable) once, for all tools.
