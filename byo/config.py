"""Configuration — one Settings object, read once, passed down.

Mechanism: load_settings() merges the process environment over a <home>/.env file
and returns a Settings dataclass. Everything else receives that object; nothing
else reads os.environ, so every knob has exactly one reader.

Rejected alternative: a TOML config file. Tidier for twelve knobs, but "paste one
key and run" is the product, and .env already carries a secret without adding a
second parser and a second precedence rule.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

PROVIDERS = ("anthropic", "openai")
DEFAULT_PORT = 7777


class ConfigError(RuntimeError):
    """A configuration problem a person can fix, with the fix in the message."""


def _dotenv_values(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines. Uses python-dotenv when it is importable, else the
    12-line parser below, so a checkout with zero extra installs still runs."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    try:
        from dotenv import dotenv_values

        return {k: v for k, v in dotenv_values(path).items() if v is not None}
    except Exception:
        pass
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return values
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def resolve_home(env: Mapping[str, str] | None = None, user_home: Path | None = None) -> Path:
    """BYO_HOME wins; otherwise ~/.byo. No other rule, so data has one location."""
    env = os.environ if env is None else env
    user_home = Path.home() if user_home is None else user_home
    raw = (env.get("BYO_HOME") or "").strip()
    return Path(raw).expanduser() if raw else user_home / ".byo"


@dataclass
class Settings:
    home: Path = field(default_factory=lambda: Path.home() / ".byo")
    provider: str = "anthropic"
    api_key: str = ""
    base_url: str | None = None
    model: str = ""
    small_model: str = ""
    max_iterations: int = 15
    max_tokens: int = 8192
    history_turns: int = 12
    consolidate_every: int = 6
    retrieval_top_k: int = 4
    port: int = DEFAULT_PORT
    weather_enabled: bool = True
    weather_timeout_seconds: int = 5
    weather_default_place: str = ""

    @property
    def dotenv_path(self) -> Path:
        return self.home / ".env"

    @property
    def db_path(self) -> Path:
        return self.home / "state.db"

    @property
    def trajectories_dir(self) -> Path:
        return self.home / "trajectories"

    @property
    def outbox_dir(self) -> Path:
        return self.home / "outbox"

    @property
    def memory_dir(self) -> Path:
        return self.home / "memory"

    @property
    def persona_path(self) -> Path:
        return self.home / "PERSONA.md"

    @property
    def mirror_path(self) -> Path:
        return self.home / "MEMORY.md"

    def ensure_home(self) -> Path:
        """Create the home layout. Idempotent, so every entry point can call it."""
        for directory in (self.home, self.trajectories_dir, self.outbox_dir, self.memory_dir):
            directory.mkdir(parents=True, exist_ok=True)
        return self.home

    def effective_model(self) -> str:
        if self.model:
            return self.model
        return "claude-sonnet-4-5" if self.provider == "anthropic" else "gpt-4o-mini"

    def effective_small_model(self) -> str:
        return self.small_model or self.effective_model()


def _bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = (env.get(name) or "").strip().lower()
    if not raw:
        return default
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    raise ConfigError(f"{name} must be true or false, got {raw!r}.")


def _int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = (env.get(name) or "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError as exc:
        raise ConfigError(f"{name} must be a whole number, got {raw!r}.") from exc


def load_settings(
    env: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Settings:
    """Environment over .env over defaults. The home decides where .env lives."""
    env = dict(os.environ) if env is None else dict(env)
    home_path = Path(home) if home is not None else resolve_home(env)
    merged = {**_dotenv_values(home_path / ".env"), **env}
    provider = (merged.get("BYO_PROVIDER") or "anthropic").strip().lower()
    if provider not in PROVIDERS:
        raise ConfigError(
            f"BYO_PROVIDER is {provider!r}; this build speaks {' or '.join(PROVIDERS)}."
        )
    base_url = (merged.get("BYO_BASE_URL") or "").strip() or None
    return Settings(
        home=home_path,
        provider=provider,
        api_key=(merged.get("BYO_API_KEY") or "").strip(),
        base_url=base_url,
        model=(merged.get("BYO_MODEL") or "").strip(),
        small_model=(merged.get("BYO_SMALL_MODEL") or "").strip(),
        max_iterations=_int(merged, "BYO_MAX_ITERATIONS", 15),
        max_tokens=_int(merged, "BYO_MAX_TOKENS", 8192),
        history_turns=_int(merged, "BYO_HISTORY_TURNS", 12),
        consolidate_every=_int(merged, "BYO_CONSOLIDATE_EVERY", 6),
        retrieval_top_k=_int(merged, "BYO_RETRIEVAL_TOP_K", 4),
        port=_int(merged, "BYO_PORT", DEFAULT_PORT),
        weather_enabled=_bool(merged, "BYO_WEATHER_ENABLED", True),
        weather_timeout_seconds=min(
            30, _int(merged, "BYO_WEATHER_TIMEOUT_SECONDS", 5)
        ),
        weather_default_place=(merged.get("BYO_WEATHER_DEFAULT_PLACE") or "").strip(),
    )


def missing_key_message(settings: Settings) -> str:
    return f"Missing BYO_API_KEY. Export it, or put BYO_API_KEY=... in {settings.dotenv_path}."
