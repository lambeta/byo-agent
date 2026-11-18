"""Configuration: defaults, precedence, and the message a person can act on."""

from __future__ import annotations

from pathlib import Path

import pytest

from byo.config import ConfigError, load_settings, missing_key_message, resolve_home


def test_defaults_match_the_contract(home: Path):
    settings = load_settings(env={}, home=home)
    assert settings.provider == "anthropic"
    assert settings.max_iterations == 15
    assert settings.max_tokens == 8192
    assert settings.history_turns == 12
    assert settings.consolidate_every == 6
    assert settings.retrieval_top_k == 4
    assert settings.port == 7777


def test_byo_home_wins(home: Path):
    assert resolve_home({"BYO_HOME": str(home)}, user_home=Path("/tmp/other")) == home


def test_dotenv_loses_to_the_environment(home: Path):
    (home / ".env").write_text("BYO_MODEL=from-file\nBYO_PORT=7000\n", encoding="utf-8")
    settings = load_settings(env={"BYO_MODEL": "from-env"}, home=home)
    assert settings.model == "from-env"
    assert settings.port == 7000


def test_unknown_provider_is_a_config_error(home: Path):
    with pytest.raises(ConfigError):
        load_settings(env={"BYO_PROVIDER": "mystery"}, home=home)


def test_missing_key_message_names_the_variable_and_the_file(home: Path):
    settings = load_settings(env={}, home=home)
    message = missing_key_message(settings)
    assert "BYO_API_KEY" in message
    assert str(home / ".env") in message
