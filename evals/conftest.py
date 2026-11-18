"""Shared fixtures: a throwaway home, a database, and the scripted model."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scripted import script  # noqa: E402

from byo.config import Settings, load_settings  # noqa: E402
from byo.db import connect  # noqa: E402


@pytest.fixture
def home(tmp_path: Path) -> Path:
    path = tmp_path / "home"
    path.mkdir()
    return path


@pytest.fixture
def settings(home: Path) -> Settings:
    return load_settings(env={"BYO_HOME": str(home)}, home=home)


@pytest.fixture
def conn(settings: Settings):
    connection = connect(settings.home)
    yield connection
    connection.close()


@pytest.fixture
def model():
    return script
