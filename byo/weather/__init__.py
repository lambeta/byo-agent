"""Weather: a keyless public service behind one small, injectable seam.

Mechanism: the client speaks JSON over HTTPS; the service resolves a place, shapes a
report and caches the two upstream calls; the tool renders text for the model.

Rejected alternative: a weather SDK. It would own HTTP and parsing, add a dependency,
and still need the same failure mapping this package already has.
"""

from __future__ import annotations

from byo.weather.client import BadData, HttpJsonClient, JsonClient, ServiceUnavailable
from byo.weather.service import (
    WeatherFailure,
    WeatherReport,
    WeatherService,
)

__all__ = [
    "BadData",
    "HttpJsonClient",
    "JsonClient",
    "ServiceUnavailable",
    "WeatherFailure",
    "WeatherReport",
    "WeatherService",
]
