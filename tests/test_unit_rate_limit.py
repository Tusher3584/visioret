"""Unit tests for backend/rate_limit.py, using minimal request stand-ins."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend import rate_limit


def fake_request(host):
    return SimpleNamespace(client=SimpleNamespace(host=host))


def test_allows_up_to_limit_then_blocks_with_429():
    req = fake_request("10.0.0.1")
    for _ in range(3):
        rate_limit.enforce(req, "login", max_attempts=3, window_seconds=60)
    with pytest.raises(HTTPException) as exc:
        rate_limit.enforce(req, "login", max_attempts=3, window_seconds=60)
    assert exc.value.status_code == 429
    assert int(exc.value.headers["Retry-After"]) > 0


def test_clients_are_counted_separately():
    a, b = fake_request("10.0.0.1"), fake_request("10.0.0.2")
    for _ in range(3):
        rate_limit.enforce(a, "login", 3, 60)
    rate_limit.enforce(b, "login", 3, 60)  # b is unaffected by a's attempts


def test_scopes_are_counted_separately():
    req = fake_request("10.0.0.1")
    for _ in range(3):
        rate_limit.enforce(req, "login", 3, 60)
    rate_limit.enforce(req, "register", 3, 60)


def test_clear_attempts_resets_the_client():
    req = fake_request("10.0.0.1")
    for _ in range(3):
        rate_limit.enforce(req, "login", 3, 60)
    rate_limit.clear_attempts(req, "login")
    rate_limit.enforce(req, "login", 3, 60)


def test_window_expiry_frees_the_client(monkeypatch):
    req = fake_request("10.0.0.1")
    now = [1000.0]
    monkeypatch.setattr(rate_limit.time, "monotonic", lambda: now[0])
    for _ in range(3):
        rate_limit.enforce(req, "login", 3, 60)
    now[0] += 61  # the whole window has elapsed
    rate_limit.enforce(req, "login", 3, 60)
