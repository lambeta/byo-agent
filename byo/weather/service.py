"""Weather service — place resolution, shaping, caching and typed failures.

Mechanism: report() cleans the place, resolves it against the geocoding endpoint with a
candidate/population rule, validates the requested dates in the place's time zone, fetches
the four-day forecast, and shapes one WeatherReport. Two TTL caches keep the upstream
calls to one per place and unit system in a turn. Every expected failure is a
WeatherFailure carrying the category the tool renders.

Rejected alternative: folding this into the tool. The tool would then own HTTP, ranking,
dates and rendering, and none of those could be tested without the tool. Keeping the
service addressable behind a JsonClient is the same seam the model adapter uses.

Rejected alternative: resolving to the first geocoding hit. That is the silent guess the
spec forbids; a dominant population (five times the runner-up) is the rule instead.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from byo.weather.client import BadData, JsonClient, ServiceUnavailable

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
SOURCE = "Open-Meteo"

CANDIDATE_COUNT = 8
SHOWN_CANDIDATES = 5
DOMINANCE = 5.0
GEOCODE_TTL = 3600
FORECAST_TTL = 60
CACHE_MAX = 128
OUT_OF_RANGE = "request out of range"
NOT_RECOGNISED = "place not recognised"
AMBIGUOUS = "place ambiguous"
SERVICE_UNAVAILABLE = "service unavailable"
DATA_UNAVAILABLE = "data unavailable"

_CURRENT_FIELDS = (
    "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,"
    "wind_speed_10m,wind_direction_10m,precipitation"
)
_DAILY_FIELDS = (
    "weather_code,temperature_2m_max,temperature_2m_min,"
    "precipitation_probability_max,precipitation_sum"
)

WEATHER_CODES = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    56: "light freezing drizzle",
    57: "dense freezing drizzle",
    61: "slight rain",
    63: "moderate rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "heavy freezing rain",
    71: "slight snowfall",
    73: "moderate snowfall",
    75: "heavy snowfall",
    77: "snow grains",
    80: "slight rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    85: "slight snow showers",
    86: "heavy snow showers",
    95: "thunderstorm",
    96: "thunderstorm with slight hail",
    99: "thunderstorm with heavy hail",
}

COMPASS = (
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
)

UNITS = {
    "metric": {
        "temperature": "°C",
        "wind": "km/h",
        "precipitation": "mm",
        "params": {
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
        },
        "wind_units": {"km/h"},
        "precipitation_units": {"mm"},
    },
    "imperial": {
        "temperature": "°F",
        "wind": "mph",
        "precipitation": "inch",
        "params": {
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
        },
        "wind_units": {"mp/h", "mph"},
        "precipitation_units": {"inch"},
    },
}


class WeatherFailure(Exception):
    """An expected weather failure, already carrying the category the tool renders."""

    def __init__(
        self,
        category: str,
        message: str,
        candidates: list[str] | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.message = message
        self.candidates = list(candidates or [])
        self.retryable = retryable


@dataclass(frozen=True)
class Place:
    name: str
    admin1: str = ""
    admin2: str = ""
    country: str = ""
    country_code: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    timezone: str = ""
    population: int = 0

    def display(self) -> str:
        parts = [self.name] + [part for part in (self.admin1, self.country) if part]
        return ", ".join(parts)


@dataclass(frozen=True)
class CurrentReading:
    at: str
    temperature: float
    apparent: float
    humidity: int
    weather_code: int
    condition: str
    wind_speed: float
    wind_direction: int
    wind_compass: str
    precipitation: float


@dataclass(frozen=True)
class DailyForecast:
    date: str
    weather_code: int
    condition: str
    high: float
    low: float
    precip_chance: int
    precip_sum: float


@dataclass(frozen=True)
class WeatherReport:
    place: Place
    units: str
    timezone: str
    current: CurrentReading
    daily: list[DailyForecast]
    source: str = SOURCE
    fetched_at: str = ""


@dataclass
class _CacheEntry:
    stored_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)


def condition_for(code: int) -> str:
    return WEATHER_CODES.get(code, f"WMO code {code}")


def compass(degrees: float) -> str:
    return COMPASS[int(round((degrees % 360) / 22.5)) % 16]


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= character <= "\u9fff" for character in text)


def _search_name(place: str) -> str:
    return place.split(",")[0].strip()


def _hint_matches(place: Place, hint: str) -> bool:
    if hint == place.country_code.casefold():
        return True
    for value in (place.admin1, place.admin2, place.country):
        text = (value or "").casefold()
        if text and (hint == text or text.startswith(hint)):
            return True
    return False


class WeatherService:
    def __init__(
        self,
        client: JsonClient,
        clock: Callable[[], datetime] | None = None,
        default_place: str = "",
    ) -> None:
        self.client = client
        self.default_place = default_place
        self._clock = clock or (lambda: datetime.now(UTC))
        self._cache: dict[tuple[Any, ...], _CacheEntry] = {}
        self._lock = threading.Lock()

    def now(self) -> datetime:
        return self._clock()

    def report(
        self,
        place: str = "",
        start: str | None = None,
        end: str | None = None,
        units: str = "metric",
    ) -> WeatherReport:
        if units not in UNITS:
            raise ValueError(f"units must be 'metric' or 'imperial', got {units!r}")
        query = (place or "").strip()
        if not query:
            query = self.default_place.strip()
        if not query:
            raise WeatherFailure(
                NOT_RECOGNISED,
                "no place was given and no default place is configured; ask which city.",
            )
        resolved = self._resolve(query)
        today = self._local_date(resolved)
        first, last = self._window(resolved, today, start, end)
        payload = self._forecast(resolved, units)
        report = self._shape(resolved, units, payload, first, last)
        return report

    # -- resolution -----------------------------------------------------

    def _resolve(self, query: str) -> Place:
        language = "zh" if _has_cjk(query) else "en"
        key = ("geocode", " ".join(query.casefold().split()), language)
        params = urlencode(
            {
                "name": _search_name(query),
                "count": CANDIDATE_COUNT,
                "language": language,
                "format": "json",
            }
        )
        payload = self._cached(
            key,
            GEOCODE_TTL,
            lambda: self._fetch(f"{GEOCODE_URL}?{params}"),
        )
        results = payload.get("results") or []
        if not isinstance(results, list):
            raise WeatherFailure(DATA_UNAVAILABLE, _incomplete())
        candidates = [_place_from(item) for item in results if isinstance(item, dict)]
        candidates = [
            place
            for place in candidates
            if place.name
            and -90.0 <= place.latitude <= 90.0
            and -180.0 <= place.longitude <= 180.0
        ]
        if not candidates:
            raise WeatherFailure(
                NOT_RECOGNISED,
                f"no city matched {query!r}; ask for a clearer name or add a region.",
            )
        hints = [
            part.strip().casefold()
            for part in query.split(",")[1:]
            if part.strip()
        ]
        if hints:
            narrowed = [
                place for place in candidates if any(_hint_matches(place, hint) for hint in hints)
            ]
            if not narrowed:
                raise WeatherFailure(
                    NOT_RECOGNISED,
                    f"no city matched {query!r} in the region you named; "
                    "ask for the city and region again.",
                )
            candidates = narrowed
        head = _search_name(query).casefold()
        exact = [place for place in candidates if place.name.casefold() == head]
        pool = exact or candidates
        pool.sort(key=lambda place: place.population, reverse=True)
        if len(pool) == 1:
            return pool[0]
        top, second = pool[0], pool[1]
        if top.population > 0 and top.population >= DOMINANCE * second.population:
            return top
        raise WeatherFailure(
            AMBIGUOUS,
            f"several places match {query!r}.",
            candidates=[place.display() for place in pool[:SHOWN_CANDIDATES]],
        )

    # -- dates ----------------------------------------------------------

    def _local_date(self, place: Place) -> date:
        try:
            zone = ZoneInfo(place.timezone or "UTC")
        except (ZoneInfoNotFoundError, ValueError):
            zone = ZoneInfo("UTC")
        return self._clock().astimezone(zone).date()

    def _window(
        self,
        place: Place,
        today: date,
        start: str | None,
        end: str | None,
    ) -> tuple[date, date]:
        horizon = today + timedelta(days=3)
        if start:
            first = self._date(start, "start")
            last = self._date(end, "end") if end else first
        else:
            first = today
            last = self._date(end, "end") if end else horizon
        window = f"today..today+3 ({today.isoformat()}..{horizon.isoformat()})"
        if first > last:
            raise WeatherFailure(
                OUT_OF_RANGE,
                f"start {first.isoformat()} is after end {last.isoformat()}; "
                f"supported window: {window}.",
            )
        if first < today or last > horizon:
            raise WeatherFailure(
                OUT_OF_RANGE,
                f"{first.isoformat()}..{last.isoformat()} is outside the supported window; "
                f"supported window: {window}.",
            )
        return first, last

    def _date(self, value: str, field: str) -> date:
        try:
            return date.fromisoformat(value.strip())
        except (AttributeError, ValueError) as exc:
            raise WeatherFailure(
                OUT_OF_RANGE,
                f"{field} {value!r} is not an ISO date.",
            ) from exc

    # -- upstream -------------------------------------------------------

    def _forecast(self, place: Place, units: str) -> dict[str, Any]:
        params = {
            "latitude": f"{place.latitude}",
            "longitude": f"{place.longitude}",
            "current": _CURRENT_FIELDS,
            "daily": _DAILY_FIELDS,
            "timezone": "auto",
            "forecast_days": "4",
            **UNITS[units]["params"],
        }
        key = ("forecast", round(place.latitude, 4), round(place.longitude, 4), units)
        return self._cached(
            key,
            FORECAST_TTL,
            lambda: self._fetch(f"{FORECAST_URL}?{urlencode(params)}"),
        )

    def _fetch(self, url: str) -> dict[str, Any]:
        try:
            return self.client.get_json(url)
        except ServiceUnavailable as exc:
            raise WeatherFailure(
                SERVICE_UNAVAILABLE,
                f"the weather service did not answer ({exc}).",
                retryable=True,
            ) from exc
        except BadData as exc:
            raise WeatherFailure(DATA_UNAVAILABLE, _incomplete()) from exc

    def _cached(
        self,
        key: tuple[Any, ...],
        ttl: int,
        fetch: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        moment = self._clock()
        with self._lock:
            entry = self._cache.get(key)
            if entry is not None and (moment - entry.stored_at).total_seconds() < ttl:
                return entry.payload
        payload = fetch()
        with self._lock:
            if len(self._cache) >= CACHE_MAX:
                oldest = min(self._cache, key=lambda item: self._cache[item].stored_at)
                self._cache.pop(oldest, None)
            self._cache[key] = _CacheEntry(moment, payload)
        return payload

    # -- shaping --------------------------------------------------------

    def _shape(
        self,
        place: Place,
        units: str,
        payload: dict[str, Any],
        first: date,
        last: date,
    ) -> WeatherReport:
        current = payload.get("current")
        daily = payload.get("daily")
        if not isinstance(current, dict) or not isinstance(daily, dict):
            raise WeatherFailure(DATA_UNAVAILABLE, _incomplete())
        self._check_units(payload.get("current_units"), payload.get("daily_units"), units)
        reading = CurrentReading(
            at=_text(current.get("time")),
            temperature=_number(current.get("temperature_2m")),
            apparent=_number(current.get("apparent_temperature")),
            humidity=int(_number(current.get("relative_humidity_2m"))),
            weather_code=int(_number(current.get("weather_code"))),
            condition=condition_for(int(_number(current.get("weather_code")))),
            wind_speed=_number(current.get("wind_speed_10m")),
            wind_direction=int(_number(current.get("wind_direction_10m"))),
            wind_compass=compass(_number(current.get("wind_direction_10m"))),
            precipitation=_number(current.get("precipitation")),
        )
        times = daily.get("time")
        if not isinstance(times, list) or not times:
            raise WeatherFailure(DATA_UNAVAILABLE, _incomplete())
        keys = (
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_probability_max",
            "precipitation_sum",
        )
        arrays = {}
        for key in keys:
            values = daily.get(key)
            if not isinstance(values, list) or len(values) != len(times):
                raise WeatherFailure(DATA_UNAVAILABLE, _incomplete())
            arrays[key] = values
        try:
            first_index = times.index(first.isoformat())
            last_index = times.index(last.isoformat())
        except ValueError as exc:
            raise WeatherFailure(DATA_UNAVAILABLE, _incomplete()) from exc
        if last_index < first_index:
            raise WeatherFailure(DATA_UNAVAILABLE, _incomplete())
        shaped: list[DailyForecast] = []
        for index in range(first_index, last_index + 1):
            shaped.append(
                DailyForecast(
                    date=str(times[index]),
                    weather_code=int(_number(arrays["weather_code"][index])),
                    condition=condition_for(int(_number(arrays["weather_code"][index]))),
                    high=_number(arrays["temperature_2m_max"][index]),
                    low=_number(arrays["temperature_2m_min"][index]),
                    precip_chance=int(
                        _number(arrays["precipitation_probability_max"][index])
                    ),
                    precip_sum=_number(arrays["precipitation_sum"][index]),
                )
            )
        moment = payload.get("timezone") or place.timezone
        if not isinstance(moment, str) or not moment:
            raise WeatherFailure(DATA_UNAVAILABLE, _incomplete())
        return WeatherReport(
            place=place,
            units=units,
            timezone=moment,
            current=reading,
            daily=shaped,
            fetched_at=reading.at.replace("T", " "),
        )

    def _check_units(
        self,
        current_units: Any,
        daily_units: Any,
        units: str,
    ) -> None:
        expected = UNITS[units]
        if not isinstance(current_units, dict) or not isinstance(daily_units, dict):
            raise WeatherFailure(DATA_UNAVAILABLE, _incomplete())
        if current_units.get("temperature_2m") != expected["temperature"]:
            raise WeatherFailure(DATA_UNAVAILABLE, _incomplete())
        if current_units.get("apparent_temperature") != expected["temperature"]:
            raise WeatherFailure(DATA_UNAVAILABLE, _incomplete())
        if current_units.get("wind_speed_10m") not in expected["wind_units"]:
            raise WeatherFailure(DATA_UNAVAILABLE, _incomplete())
        if current_units.get("precipitation") not in expected["precipitation_units"]:
            raise WeatherFailure(DATA_UNAVAILABLE, _incomplete())
        if daily_units.get("temperature_2m_max") != expected["temperature"]:
            raise WeatherFailure(DATA_UNAVAILABLE, _incomplete())
        if daily_units.get("temperature_2m_min") != expected["temperature"]:
            raise WeatherFailure(DATA_UNAVAILABLE, _incomplete())
        if daily_units.get("precipitation_sum") not in expected["precipitation_units"]:
            raise WeatherFailure(DATA_UNAVAILABLE, _incomplete())


def _place_from(item: dict[str, Any]) -> Place:
    return Place(
        name=str(item.get("name") or ""),
        admin1=str(item.get("admin1") or ""),
        admin2=str(item.get("admin2") or ""),
        country=str(item.get("country") or ""),
        country_code=str(item.get("country_code") or ""),
        latitude=float(item.get("latitude") or 0.0),
        longitude=float(item.get("longitude") or 0.0),
        timezone=str(item.get("timezone") or ""),
        population=int(item.get("population") or 0),
    )


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise WeatherFailure(DATA_UNAVAILABLE, _incomplete())
    return float(value)


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise WeatherFailure(DATA_UNAVAILABLE, _incomplete())
    return value


def _incomplete() -> str:
    return "the weather service returned an incomplete reading for this place."
