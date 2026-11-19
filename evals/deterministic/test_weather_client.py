"""Weather transport: status, timeout and body typing, and the request it builds."""

from __future__ import annotations

import urllib.error

import pytest

from byo.weather.client import BadData, HttpJsonClient, ServiceUnavailable


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc) -> bool:
        return False


def make_client(outcome, timeout: float = 3.0):
    seen: dict = {}

    def opener(request, timeout=None):
        seen["request"] = request
        seen["timeout"] = timeout
        if isinstance(outcome, BaseException):
            raise outcome
        return FakeResponse(outcome)

    return HttpJsonClient(timeout=timeout, open_url=opener), seen


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.test/x", code, "error", {}, None)


def test_a_json_object_is_returned():
    client, _ = make_client(b'{"ok": true, "value": 3}')
    assert client.get_json("https://example.test/x") == {"ok": True, "value": 3}


def test_429_is_service_unavailable():
    client, _ = make_client(http_error(429))
    with pytest.raises(ServiceUnavailable):
        client.get_json("https://example.test/x")


def test_5xx_is_service_unavailable():
    client, _ = make_client(http_error(503))
    with pytest.raises(ServiceUnavailable):
        client.get_json("https://example.test/x")


def test_other_http_errors_are_bad_data():
    client, _ = make_client(http_error(404))
    with pytest.raises(BadData):
        client.get_json("https://example.test/x")


def test_timeout_is_service_unavailable():
    client, _ = make_client(TimeoutError("timed out"))
    with pytest.raises(ServiceUnavailable):
        client.get_json("https://example.test/x")


def test_url_error_is_service_unavailable():
    client, _ = make_client(urllib.error.URLError("no route"))
    with pytest.raises(ServiceUnavailable):
        client.get_json("https://example.test/x")


def test_non_json_is_bad_data():
    client, _ = make_client(b"<html>nope</html>")
    with pytest.raises(BadData):
        client.get_json("https://example.test/x")


def test_a_json_array_root_is_bad_data():
    client, _ = make_client(b"[1, 2, 3]")
    with pytest.raises(BadData):
        client.get_json("https://example.test/x")


def test_body_over_the_cap_is_bad_data():
    body = b'{"a": "' + b"x" * 200_001 + b'"}'
    client, _ = make_client(body)
    with pytest.raises(BadData):
        client.get_json("https://example.test/x")


def test_the_request_names_this_build_and_uses_the_timeout():
    client, seen = make_client(b"{}", timeout=4)
    client.get_json("https://example.test/x?y=1")
    assert seen["timeout"] == 4
    request = seen["request"]
    assert request.full_url == "https://example.test/x?y=1"
    assert "byo-agent" in request.get_header("User-agent")
