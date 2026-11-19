"""Weather transport — two HTTP GETs, typed so the service never parses errors.

Mechanism: HttpJsonClient builds a GET with a bounded timeout and a 200 KB read cap,
decodes JSON into a dict, and raises ServiceUnavailable (network, timeout, 429, 5xx)
or BadData (non-JSON, wrong root, oversized body). The service maps those two types
onto the person-facing categories.

Rejected alternative: letting the service call urllib directly. The timeout, the body
cap and the error typing would then be copied per endpoint, and every test would have
to monkeypatch urllib.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any, Protocol

USER_AGENT = "byo-agent weather tool"
MAX_BYTES = 200_000


class WeatherUpstreamError(Exception):
    """Base for the two transport failures the service maps."""


class ServiceUnavailable(WeatherUpstreamError):
    """The service gave no usable answer: network, timeout, 429 or 5xx."""


class BadData(WeatherUpstreamError):
    """The service answered, but not with the JSON object we need."""


class JsonClient(Protocol):
    def get_json(self, url: str) -> dict[str, Any]:
        ...


class HttpJsonClient:
    def __init__(
        self,
        timeout: float = 5.0,
        open_url: Callable[..., Any] | None = None,
    ) -> None:
        self.timeout = timeout
        self._open = open_url or urllib.request.urlopen

    def get_json(self, url: str) -> dict[str, Any]:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with self._open(request, timeout=self.timeout) as response:
                body = response.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code == 429 or 500 <= exc.code < 600:
                raise ServiceUnavailable(f"HTTP {exc.code}") from exc
            raise BadData(f"HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ServiceUnavailable(str(exc)) from exc
        if len(body) > MAX_BYTES:
            raise BadData("the weather service response exceeded 200 KB")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BadData("the weather service response was not JSON") from exc
        if not isinstance(payload, dict):
            raise BadData("the weather service response was not a JSON object")
        return payload
