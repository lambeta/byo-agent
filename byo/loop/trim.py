"""Keep one large tool result from being re-sent on every later iteration.

Mechanism: before iteration 2 and later, any tool result longer than the cap is cut
to its opening with a marker. The model already read it once.

Rejected alternative: dropping old results entirely. A cut result keeps the fact
that it happened and the beginning of the answer, which is what the model needs to
stay honest about what it did.
"""

from __future__ import annotations

from byo.loop.types import Message, ToolResultBlock

CAP = 2000
MARKER = "\n[…shortened]"


def shrink(messages: list[Message], cap: int = CAP) -> None:
    # The last message is the fresh tool output the next request sends for the
    # first time: the model has not read it yet, so it goes out in full.
    for index, message in enumerate(messages[:-1]):
        if not any(isinstance(b, ToolResultBlock) and len(b.content) > cap for b in message.blocks):
            continue
        blocks = []
        for block in message.blocks:
            if isinstance(block, ToolResultBlock) and len(block.content) > cap:
                blocks.append(ToolResultBlock(block.tool_call_id, block.content[:cap] + MARKER))
            else:
                blocks.append(block)
        messages[index] = Message(message.role, tuple(blocks))
