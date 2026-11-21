"""Weather transport — two HTTP GETs, typed so the service never parses errors.

Mechanism: HttpJsonClient builds a GET with a bounded timeout and a 200 KB read cap,
decodes JSON into a dict, and raises ServiceUnavailable (network, timeout, 429, 5xx)
or BadData (non-JSON, wrong root, oversized body). A timeout or 5xx is retried once
after a short pause, because the observed failures are stalled TLS handshakes to a bad
edge that succeed on a fresh connection; a 429 is not retried (the provider asked us to
slow down). The service maps the final failure onto the person-facing categories.

Rejected alternative: letting the service call urllib directly. The timeout, the body
cap, the retry rule and the error typing would then be copied per endpoint, and every
test would have to monkeypatch urllib.

Rejected alternative: retrying every failure. BadData (a malformed payload) does not
get better on a second request, and a 429 would only deepen a rate limit.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any, Protocol

USER_AGENT = "byo-agent weather tool"
MAX_BYTES = 200_000
ATTEMPTS = 2
RETRY_DELAY = 0.4


class WeatherUpstreamError(Exception):
    """Base for the two transport failures the service maps."""


class ServiceUnavailable(WeatherUpstreamError):
    """The service gave no usable answer: network, timeout, 429 or 5xx."""

    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


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
        attempts: int = ATTEMPTS,
        delay: float = RETRY_DELAY,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.timeout = timeout
        self._open = open_url or urllib.request.urlopen
        self.attempts = max(1, attempts)
        self.delay = delay
        self._sleep = sleep or time.sleep

    def get_json(self, url: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout * self.attempts
        last: ServiceUnavailable | None = None
        made = 0
        for attempt in range(1, self.attempts + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            made = attempt
            try:
                return self._get_once(url, min(self.timeout, max(1.0, remaining)))
            except ServiceUnavailable as exc:
                last = exc
                if not exc.retryable or attempt == self.attempts:
                    break
                self._sleep(min(self.delay, max(0.0, deadline - time.monotonic())))
        assert last is not None
        if last.retryable and made > 1:
            raise ServiceUnavailable(f"{last} (after {made} attempts)", retryable=False)
        raise last

    def _get_once(self, url: str, timeout: float) -> dict[str, Any]:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with self._open(request, timeout=timeout) as response:
                body = response.read(MAX_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise ServiceUnavailable("HTTP 429", retryable=False) from exc
            if 500 <= exc.code < 600:
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
