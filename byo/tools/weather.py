"""query_weather — the model-facing weather capability.

Mechanism: the tool declares the schema, maps expected failures to text and renders a
bounded report from the service. It returns a string; it never raises for an expected
failure, so the registry's ok flag and the trajectory stay honest.

Rejected alternative: letting the model call the upstream API through a generic HTTP
tool. The person would then depend on the model choosing URLs, and every failure would
leak transport detail into the conversation.
"""

from __future__ import annotations

from byo.tools.registry import Tool
from byo.weather.client import HttpJsonClient
from byo.weather.service import UNITS, WeatherFailure, WeatherReport, WeatherService

DESCRIPTION = (
    "Look up current weather and a short daily forecast (today plus the next three days) "
    "for a city. Returns temperature, conditions, humidity, wind and precipitation with units."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "place": {
            "type": "string",
            "description": (
                "city name, optionally with region or country, "
                "e.g. 'Springfield, Illinois'"
            ),
        },
        "start": {
            "type": "string",
            "description": (
                "ISO date (YYYY-MM-DD) to start from; "
                "default today in the place's time zone"
            ),
        },
        "end": {
            "type": "string",
            "description": (
                "ISO date to end at; default the same day as start; "
                "at most three days after today"
            ),
        },
        "units": {
            "type": "string",
            "enum": ["metric", "imperial"],
            "description": "temperature, wind and precipitation units; default metric",
        },
    },
    "required": ["place"],
}


def render(report: WeatherReport) -> str:
    labels = UNITS[report.units]
    temperature = labels["temperature"]
    wind = labels["wind"]
    precipitation = labels["precipitation"]
    current = report.current
    lines = [
        f"Weather for {report.place.display()} ({report.timezone}) — "
        f"read {report.fetched_at} local.",
        (
            f"Now: {current.temperature:.1f} {temperature} "
            f"(feels {current.apparent:.1f} {temperature}), {current.condition}, "
            f"humidity {current.humidity}%, wind {current.wind_speed:.1f} {wind} "
            f"from {current.wind_compass}, "
            f"precipitation {current.precipitation:.1f} {precipitation}."
        ),
        "Daily:",
    ]
    for day in report.daily:
        lines.append(
            f"{day.date}: {day.condition}, {day.low:.1f}–{day.high:.1f} {temperature}, "
            f"rain chance {day.precip_chance}%, {day.precip_sum:.1f} {precipitation}"
        )
    lines.append("Weather data by Open-Meteo.com")
    return "\n".join(lines)


def failure_text(failure: WeatherFailure) -> str:
    if failure.category == "place ambiguous" and failure.candidates:
        listed = "; ".join(failure.candidates)
        return f"Error: place ambiguous: {failure.message} Ask which one: {listed}."
    if failure.category == "service unavailable":
        return (
            f"Error: service unavailable: {failure.message} "
            "Do not call query_weather again for this place this turn; tell the person "
            "the weather service is temporarily unavailable and they can ask again shortly."
        )
    return f"Error: {failure.category}: {failure.message}"


def make_tools(conn, settings, client=None, clock=None) -> list[Tool]:
    if not getattr(settings, "weather_enabled", True):
        return []
    transport = client if client is not None else HttpJsonClient(
        timeout=settings.weather_timeout_seconds
    )
    service = WeatherService(
        transport, clock=clock, default_place=settings.weather_default_place
    )

    def query_weather(
        place: str = "",
        start: str | None = None,
        end: str | None = None,
        units: str = "metric",
    ) -> str:
        try:
            report = service.report(place=place, start=start, end=end, units=units)
        except WeatherFailure as failure:
            return failure_text(failure)
        except ValueError as exc:
            return f"Error: argument error: {exc}"
        return render(report)

    return [Tool("query_weather", DESCRIPTION, SCHEMA, query_weather)]
