"""Weather transport: status, timeout and body typing, retry, and the request it builds."""

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


def make_client(outcomes, timeout: float = 3.0, **kwargs):
    """A client whose opener replays outcomes in order (an exception or a body)."""
    seen: dict = {"calls": [], "sleeps": []}
    queue = list(outcomes) if isinstance(outcomes, list) else [outcomes]

    def opener(request, timeout=None):
        seen["calls"].append((request, timeout))
        if not queue:
            raise AssertionError("opener called more times than scripted")
        outcome = queue.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return FakeResponse(outcome)

    kwargs.setdefault("sleep", lambda seconds: seen["sleeps"].append(seconds))
    return HttpJsonClient(timeout=timeout, open_url=opener, **kwargs), seen


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.test/x", code, "error", {}, None)


def test_a_json_object_is_returned():
    client, _ = make_client(b'{"ok": true, "value": 3}')
    assert client.get_json("https://example.test/x") == {"ok": True, "value": 3}


def test_a_stalled_handshake_is_retried_once():
    client, seen = make_client([TimeoutError("handshake timed out"), b'{"ok": true}'])
    assert client.get_json("https://example.test/x") == {"ok": True}
    assert len(seen["calls"]) == 2
    assert seen["sleeps"] == [0.4]


def test_a_5xx_is_retried_once():
    client, seen = make_client([http_error(503), b'{"ok": true}'])
    assert client.get_json("https://example.test/x") == {"ok": True}
    assert len(seen["calls"]) == 2


def test_a_429_is_not_retried():
    client, seen = make_client([http_error(429), b'{"ok": true}'])
    with pytest.raises(ServiceUnavailable) as caught:
        client.get_json("https://example.test/x")
    assert caught.value.retryable is False
    assert len(seen["calls"]) == 1


def test_a_429_is_service_unavailable():
    client, _ = make_client(http_error(429))
    with pytest.raises(ServiceUnavailable):
        client.get_json("https://example.test/x")


def test_5xx_exhausts_the_attempts_and_says_so():
    client, seen = make_client([http_error(503), http_error(503)])
    with pytest.raises(ServiceUnavailable) as caught:
        client.get_json("https://example.test/x")
    assert "after 2 attempts" in str(caught.value)
    assert caught.value.retryable is False
    assert len(seen["calls"]) == 2


def test_other_http_errors_are_bad_data():
    client, _ = make_client(http_error(404))
    with pytest.raises(BadData):
        client.get_json("https://example.test/x")


def test_timeouts_exhaust_the_attempts():
    client, seen = make_client([TimeoutError("timed out"), TimeoutError("timed out")])
    with pytest.raises(ServiceUnavailable) as caught:
        client.get_json("https://example.test/x")
    assert "after 2 attempts" in str(caught.value)
    assert len(seen["calls"]) == 2


def test_url_errors_are_retried_then_reported():
    client, seen = make_client(
        [urllib.error.URLError("no route"), urllib.error.URLError("no route")]
    )
    with pytest.raises(ServiceUnavailable):
        client.get_json("https://example.test/x")
    assert len(seen["calls"]) == 2


def test_attempts_one_disables_the_retry():
    client, seen = make_client([TimeoutError("timed out"), b'{"ok": true}'], attempts=1)
    with pytest.raises(ServiceUnavailable):
        client.get_json("https://example.test/x")
    assert len(seen["calls"]) == 1


def test_non_json_is_bad_data_and_not_retried():
    client, seen = make_client(b"<html>nope</html>")
    with pytest.raises(BadData):
        client.get_json("https://example.test/x")
    assert len(seen["calls"]) == 1


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
    request, timeout = seen["calls"][-1]
    assert timeout == 4
    assert request.full_url == "https://example.test/x?y=1"
    assert "byo-agent" in request.get_header("User-agent")
