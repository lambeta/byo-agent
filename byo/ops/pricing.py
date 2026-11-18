"""Model prices, kept in one table so a receipt is never a guess.

Mechanism: US dollars per million tokens, per model. Unknown models cost 0.0 and mark
the receipt as an estimate, so a missing row is visible rather than silently free.

Rejected alternative: asking the provider for pricing. No provider exposes it
uniformly, and a network call would make receipts fail offline.
"""

from __future__ import annotations

# model -> (input USD per 1M tokens, output USD per 1M tokens)
PRICES: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-haiku-4-5": (0.8, 4.0),
    "claude-opus-4-1": (15.0, 75.0),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.6),
    "gpt-4.1": (2.0, 8.0),
    "deepseek-chat": (0.27, 1.1),
    "kimi-k2": (0.6, 2.5),
}


def cost(provider: str, model: str, usage: dict[str, int]) -> tuple[float, bool]:
    """(usd, estimate). An unknown model is an estimate, never a false zero."""
    prices = PRICES.get(model)
    if prices is None:
        return 0.0, True
    tokens_in = int(usage.get("in", 0) or 0)
    tokens_out = int(usage.get("out", 0) or 0)
    usd = (tokens_in * prices[0] + tokens_out * prices[1]) / 1000000
    return round(usd, 6), False
