# Contract — Record additions for live highlighting

**Version**: 1 · **Owner**: `byo/ops/trajectory.py` with `byo/app.py` and `byo/loop/agent.py` ·
**Tests**: `test_record_additions.py`, `test_observability.py`, `test_parity_seams.py`

The trajectory stays one append-only JSON Lines file per day with the same envelope. This contract
adds record types and fields; it removes nothing, renames nothing and reorders nothing. A reader that
knows only the original eight types must keep working.

## 1. Additive vocabulary

```text
gate_start          before the memory decision's model call       {model}
context             after the working context is assembled        {recalled, recalled_chars, duration_ms}
llm_start           before a model request                        {iteration, model}
tool_start          before a tool executes                        {tool, call_id}
consolidation_start before consolidation's model call             {pending}
```

Fields added to existing records:

```text
turn_start.pid        writer process id, integer, present when known
gate.degraded         true when the gate failed open; absent means false
turn_end.state        "complete" | "failed" | "limited"; absent means derive as before
```

**Consumers MUST ignore unknown types**, as they already must for `error` and any future type.

## 2. When each record is written

1. `gate_start` immediately before `Memory.gate()`; `gate` after it returns, unchanged in shape.
2. `context` immediately after `Session.build_system()` returns, with the assembly's duration and
   whether a memory block was included. No `context_start`: assembly is bounded and is not a stage the
   person waits on.
3. `llm_start` immediately before an adapter call, carrying the iteration; the existing `llm`
   completion record follows with model, usage, duration and stop reason.
4. `tool_start` immediately before `ToolRegistry.execute()`, carrying the tool name and call id; the
   existing `tool` completion record follows.
5. `consolidation_start` only when consolidation will actually run (the pending backlog reached the
   configured size). The existing `consolidation` record follows when it produced a note.
6. `turn_end` is always written once per turn, including when the turn raises: the app records
   `error` with `stage: "turn"` and then `turn_end` with `state: "failed"` before re-raising.

## 3. Guarantees a reader may rely on

- A `*_start` record precedes its completion record and shares the turn id.
- Steps are sequential: at most one unmatched start exists at any time in a turn.
- A start record never carries a result, cost, usage or token count.
- Timestamps are non-decreasing within a turn.
- Every field, including the new ones, passes through the sink's redaction and truncation.

## 4. Compatibility

| Reader situation | Required behaviour |
|---|---|
| Record without the new types | Renders as ordered history; no running interval is claimed |
| Record without `pid` | The turn is never considered live |
| Record without `gate.degraded` | Treated as `false` |
| Record without `turn_end.state` | State derived exactly as before this contract |
| Unknown type from the future | Named as unmapped in the status line; no component lit; the rest of the turn still renders |

## 5. Amendments to `002`

- **FR-009** (light every recorded event in order) stands; the new start records make the *start* of a
  step observable, which is what this feature adds.
- **FR-010** (lighting reflects what happened) is tightened by [highlight-cues.md](highlight-cues.md):
  skipped, not reached, not configured and partial become distinct, explicit outcomes.
- **FR-013** (no silent drops, ≤1 s lag) stands; catch-up jumps to the true state instead of replaying.
- **FR-014** (settle) stands, plus: an unfinished turn never settles into a running state.
- **FR-025** ("no new event types") is amended narrowly: new types are allowed **only** as additive
  observations through the existing sink. Its prohibition on a second turn store, a parallel status
  model and reordering remains in force, and no displayed value may be invented.

## 6. What this contract does not change

- The file location, rotation, naming and retention.
- The envelope fields or the redaction rules.
- `trajectory_version`: it stays `1`; absence of the new types is the version signal.
- The database schema, the chat log or the mirror files.
