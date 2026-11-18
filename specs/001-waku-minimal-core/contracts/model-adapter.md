# Contract — Model adapter

**Version**: 1 · **Owner**: `byo/loop/types.py`, `byo/loop/adapters.py` ·
**Consumers**: `byo/loop/agent.py`, `byo/memory/*`, `byo/app.py` · **Tests**: `test_adapters.py`,
`test_fake_model.py`

The seam exists so that no vendor type, SDK import or vendor-name branch reaches the loop
(constitution II, spec FR-012). Two adapters ship; a third is a new file plus its conformance tests.

## 1. Types

```python
@dataclass(frozen=True)
class ToolSpec:          # what the model is told about a tool
    name: str
    description: str
    input_schema: dict

@dataclass(frozen=True)
class TextBlock:
    text: str

@dataclass(frozen=True)
class ToolCallBlock:
    id: str
    name: str
    args: dict

@dataclass(frozen=True)
class ToolResultBlock:
    tool_call_id: str
    content: str

@dataclass(frozen=True)
class Message:
    role: str                     # "user" | "assistant"
    blocks: tuple[TextBlock | ToolCallBlock | ToolResultBlock, ...]

@dataclass(frozen=True)
class Request:
    model: str
    system: str
    messages: tuple[Message, ...]
    tools: tuple[ToolSpec, ...] = ()
    max_tokens: int = 4096
    tool_choice: str = "auto"     # "auto" | "none"

@dataclass(frozen=True)
class Usage:
    input_tokens: int
    output_tokens: int

@dataclass(frozen=True)
class Response:
    blocks: tuple[TextBlock | ToolCallBlock, ...]
    stop_reason: str              # "end_turn" | "tool_use" | "max_tokens" | "refusal" | "other"
    usage: Usage
    model: str
```

## 2. Capabilities

```python
@dataclass(frozen=True)
class Capabilities:
    streaming: bool      # text deltas can be yielded while the call runs
    tool_calls: bool     # tool declarations and tool_use blocks
    usage: bool          # token counts are returned
    tool_choice_none: bool  # the provider accepts "do not call a tool"
```

The loop reads capabilities, never a provider name. A missing capability degrades, never crashes:
no `streaming` falls back to one call; no `tool_choice_none` sends the same request with a system
note instead of the choice parameter.

## 3. Protocol

```python
class ModelAdapter(Protocol):
    capabilities: Capabilities

    def complete(self, request: Request) -> Response: ...
    def stream(self, request: Request) -> Iterator[str] | Response:
        """Yield text deltas as they arrive, then return the final Response."""
```

`stream` yields `str` deltas; the returned value is the assembled `Response` (including tool calls,
which are never streamed in v1). The loop appends the response's blocks to its working memory
exactly once.

## 4. Mapping obligations

| Normalized | Anthropic wire | OpenAI wire |
|---|---|---|
| `system` | `system` parameter | a leading `system` message |
| `Message(role="user", blocks=(TextBlock,))` | `{"role":"user","content":[{"type":"text",…}]}` | `{"role":"user","content":"…"}` |
| `ToolCallBlock` in an assistant message | `{"type":"tool_use","id","name","input"}` | `tool_calls` array with JSON-string arguments |
| `ToolResultBlock` | `{"type":"tool_result","tool_use_id","content"}` in a user message | `{"role":"tool","tool_call_id","content"}` |
| `ToolSpec` | `{"name","description","input_schema"}` | `{"type":"function","function":{…}}` |
| `stop_reason` | `end_turn`/`tool_use`/`max_tokens` | `stop` + whether tool calls exist |
| `tool_choice` | `{"type":"auto"\|"none"}` | `"auto"`/`"none"` |

Adapters convert usage to `Usage` and must not leak raw SDK objects into the `Response`.

## 5. Errors

| Kind | Meaning | Loop behaviour |
|---|---|---|
| `Refused(status, message)` | the provider looked at the request and said no (4xx except 429) | end the turn; the message is shown verbatim; no retry (a retry buys the same answer twice) |
| `RateLimited(status, retry_after)` | 429 | one retry after a short wait, then `Refused`-style end |
| `Transport(cause)` | network, timeout, truncated stream | one retry, then end with a readable sentence |
| `BadResponse(detail)` | the provider answered, but not in a shape the adapter can map | end; recorded as `BadResponse` |

Every error is recorded as an `error` trajectory event (`stage`, `error_kind`, `message`) before the turn
ends, and the card marks the step failed.

## 6. Conformance suite

A new adapter is done when these pass against it (`evals/deterministic/test_adapters.py`):

1. text-only turn — one `end_turn`, one text block;
2. one tool call — a `ToolCallBlock` with parsed arguments, `stop_reason` `tool_use`;
3. two tool calls in one response — both survive in order;
4. tool result round-trip — the second call sees the result as a `ToolResultBlock`;
5. refusal — a 4xx becomes `Refused` with the provider's sentence;
6. transport fault — a timeout becomes `Transport` and is retried once;
7. streaming — deltas concatenate to the final text, and the final `Response` matches the
   non-streaming call;
8. usage — token counts are non-negative integers for every call.

## 7. The scripted adapter (test double)

`evals/fixtures/models/*.json` describe a conversation: a list of responses keyed by call index,
each with text, optional tool calls, stop reason and usage, plus optional delays. The scripted
adapter implements the same protocol, so:

- the entire offline suite exercises the real loop, the real registry and the real trajectory writer;
- the same script can be replayed to reproduce a defect (spec FR-037);
- no test needs a network, a credential, or a monkeypatched SDK.
