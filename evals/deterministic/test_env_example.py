"""The example environment file must describe exactly the knobs the code reads."""

from __future__ import annotations

import tomllib
from pathlib import Path

from byo.config import load_settings

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {
    "BYO_HOME",
    "BYO_PROVIDER",
    "BYO_API_KEY",
    "BYO_BASE_URL",
    "BYO_MODEL",
    "BYO_SMALL_MODEL",
    "BYO_MAX_ITERATIONS",
    "BYO_MAX_TOKENS",
    "BYO_HISTORY_TURNS",
    "BYO_CONSOLIDATE_EVERY",
    "BYO_RETRIEVAL_TOP_K",
    "BYO_PORT",
    "BYO_WEATHER_ENABLED",
    "BYO_WEATHER_TIMEOUT_SECONDS",
    "BYO_WEATHER_DEFAULT_PLACE",
}


def example() -> dict[str, str]:
    values = {}
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def test_every_knob_is_documented():
    assert set(example()) == EXPECTED


def test_documented_numeric_defaults_match_the_code(settings):
    values = example()
    loaded = load_settings(env={}, home=settings.home)
    assert int(values["BYO_MAX_ITERATIONS"]) == loaded.max_iterations
    assert int(values["BYO_MAX_TOKENS"]) == loaded.max_tokens
    assert int(values["BYO_HISTORY_TURNS"]) == loaded.history_turns
    assert int(values["BYO_CONSOLIDATE_EVERY"]) == loaded.consolidate_every
    assert int(values["BYO_RETRIEVAL_TOP_K"]) == loaded.retrieval_top_k
    assert int(values["BYO_PORT"]) == loaded.port
    assert values["BYO_PROVIDER"] == loaded.provider
    assert int(values["BYO_WEATHER_TIMEOUT_SECONDS"]) == loaded.weather_timeout_seconds
    assert loaded.weather_enabled is True


def test_runtime_dependency_budget():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert len(data["project"]["dependencies"]) == 4
