"""Offline doubles for the weather client and clock.

Mechanism: FakeClient returns recorded payloads by URL family and records every URL;
FakeClock is a callable aware datetime the service can read and a test can advance.
Together they let the real service, tool and loop run with no network and no monkeypatch.
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from byo.weather.client import BadData

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "weather"


def load_fixture(name: str) -> dict:
    path = FIXTURES / (name if name.endswith(".json") else f"{name}.json")
    return json.loads(path.read_text(encoding="utf-8"))


class FakeClient:
    def __init__(self, geocode=None, forecast=None, error=None):
        self.geocode = geocode
        self.forecast = forecast
        self.error = error
        self.calls: list[str] = []

    def get_json(self, url: str) -> dict:
        self.calls.append(url)
        if self.error is not None:
            raise self.error
        if "geocoding-api" in url:
            if self.geocode is None:
                raise BadData("no geocode fixture configured")
            return copy.deepcopy(self.geocode)
        if self.forecast is None:
            raise BadData("no forecast fixture configured")
        return copy.deepcopy(self.forecast)

    def geocode_calls(self) -> int:
        return sum(1 for url in self.calls if "geocoding-api" in url)

    def forecast_calls(self) -> int:
        return sum(1 for url in self.calls if "api.open-meteo.com/v1/forecast" in url)


class FakeClock:
    def __init__(self, now: datetime | None = None) -> None:
        self.now = now or datetime(2026, 11, 19, 6, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)
