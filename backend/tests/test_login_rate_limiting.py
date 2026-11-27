"""Sign-in rate limiting (core/login_throttle.py and the shared SlowAPI limit).

Real routes, real SlowAPI middleware and storage; only password checking is
replaced by a fast stand-in so dozens of attempts run quickly.
"""

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from core.config import settings
from domain.models.user import LoginResponse, UserOut

pytestmark = pytest.mark.anyio

RIGHT = "Right-Pass-1!"


@pytest.fixture
async def make_client(monkeypatch):
    from api.routes import auth
    from core import audit
    from core.rate_limiting import limiter

    monkeypatch.setattr(limiter, "enabled", True)
    limiter.reset()  # fresh counters for each test
    monkeypatch.setattr(audit, "log_audit", AsyncMock())

    async def authenticate(login_id, org_password, employee_password):
        if org_password != RIGHT or employee_password != RIGHT:
            return None
        user = UserOut(employee_id=login_id, name=login_id, email=f"{login_id.lower()}@example.com",
                       role="DEVELOPER", dept="Engineering", org_id="O1")
        return LoginResponse(token=f"token-{login_id}", user=user)

    monkeypatch.setattr(auth.auth_service, "authenticate_user", authenticate)
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.include_router(auth.router, prefix="/api/auth")
    clients = []

    def make(ip="10.0.0.1"):
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=(ip, 50000)), base_url="http://test")
        clients.append(client)
        return client

    yield make
    for client in clients:
        await client.aclose()
    limiter.reset()


def body(identifier, password=RIGHT):
    return {"identifier": identifier, "organisation_password": RIGHT, "employee_password": password}


async def attempt(client, identifier, password=RIGHT, path="/api/auth/login"):
    return await client.post(path, json=body(identifier, password))


# ── Ordinary use ────────────────────────────────────────────────────────────

async def test_many_people_signing_in_from_one_shared_ip_are_not_blocked(make_client):
    office = make_client("203.0.113.10")
    for number in range(25):  # was blocked after 5 under the old per-IP limit
        response = await attempt(office, f"EMP-{number:04d}")
        assert response.status_code == 200, number


async def test_one_person_signing_in_repeatedly_is_not_blocked(make_client):
    client = make_client()
    for _ in range(10):
        assert (await attempt(client, "EMP-0001")).status_code == 200


# ── Repeated failures ───────────────────────────────────────────────────────

async def test_account_and_ip_failures_are_limited(make_client):
    client = make_client()
    for _ in range(settings.MAX_LOGIN_ATTEMPTS):
        assert (await attempt(client, "EMP-0001", "wrong")).status_code == 401
    blocked = await attempt(client, "EMP-0001")  # even the right password waits
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    assert "Too many sign-in attempts" in blocked.json()["detail"]
    # Other people on the same address are unaffected.
    assert (await attempt(client, "EMP-0002")).status_code == 200
    # The same person from another address is unaffected (below the account limit).
    assert (await attempt(make_client("10.0.0.2"), "EMP-0001")).status_code == 200


async def test_identifier_case_and_spaces_do_not_reset_the_count(make_client):
    client = make_client()
    for identifier in ["EMP-0001", "emp-0001", " EMP-0001 ", "Emp-0001", "EMP-0001 "]:
        assert (await attempt(client, identifier, "wrong")).status_code == 401
    assert (await attempt(client, "eMp-0001")).status_code == 429


async def test_a_successful_sign_in_clears_that_accounts_failures(make_client):
    client = make_client()
    for _ in range(settings.MAX_LOGIN_ATTEMPTS - 1):
        assert (await attempt(client, "EMP-0001", "wrong")).status_code == 401
    assert (await attempt(client, "EMP-0001")).status_code == 200
    for _ in range(settings.MAX_LOGIN_ATTEMPTS - 1):  # a fresh allowance after success
        assert (await attempt(client, "EMP-0001", "wrong")).status_code == 401
    assert (await attempt(client, "EMP-0001")).status_code == 200


async def test_login_and_login_full_share_one_policy(make_client):
    client = make_client()
    paths = ["/api/auth/login", "/api/auth/login/full"] * 3
    for path in paths[:settings.MAX_LOGIN_ATTEMPTS]:
        assert (await attempt(client, "EMP-0001", "wrong", path)).status_code == 401
    assert (await attempt(client, "EMP-0001", path="/api/auth/login")).status_code == 429
    assert (await attempt(client, "EMP-0001", path="/api/auth/login/full")).status_code == 429


# ── Abuse ───────────────────────────────────────────────────────────────────

async def test_distributed_guessing_on_one_account_is_limited(make_client):
    per_address = settings.MAX_LOGIN_ATTEMPTS - 1  # stays under the account + IP limit
    failures = 0
    address = 0
    while failures < settings.LOGIN_MAX_FAILURES_PER_ACCOUNT:
        address += 1
        client = make_client(f"198.51.100.{address}")
        for _ in range(min(per_address, settings.LOGIN_MAX_FAILURES_PER_ACCOUNT - failures)):
            assert (await attempt(client, "EMP-TARGET", "wrong")).status_code == 401
            failures += 1
    fresh = make_client("198.51.100.250")
    assert (await attempt(fresh, "EMP-TARGET")).status_code == 429
    assert (await attempt(fresh, "EMP-OTHER")).status_code == 200


async def test_trying_many_identifiers_from_one_ip_is_limited(make_client):
    attacker = make_client("192.0.2.66")
    for number in range(settings.LOGIN_MAX_FAILURES_PER_IP):
        assert (await attempt(attacker, f"guess-{number}", "wrong")).status_code == 401
    assert (await attempt(attacker, "guess-new", "wrong")).status_code == 429
    assert (await attempt(attacker, "EMP-0001")).status_code == 429  # whole address waits
    assert (await attempt(make_client("192.0.2.67"), "EMP-0001")).status_code == 200


async def test_a_valid_account_cannot_reset_the_ip_wide_failure_count(make_client, monkeypatch):
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES_PER_IP", 6)
    attacker = make_client("192.0.2.70")
    for number in range(6):
        assert (await attempt(attacker, f"guess-{number}", "wrong")).status_code == 401
        if number == 2:
            # A success in the middle must not clear the address's failures.
            assert (await attempt(attacker, "EMP-ATTACKER")).status_code == 200
    assert (await attempt(attacker, "guess-7", "wrong")).status_code == 429


async def test_blocked_attempts_look_the_same_for_real_and_unknown_accounts(make_client):
    client = make_client()
    for identifier in ("EMP-REAL", "NOBODY"):
        for _ in range(settings.MAX_LOGIN_ATTEMPTS):
            await attempt(client, identifier, "wrong")
    real, unknown = await attempt(client, "EMP-REAL"), await attempt(client, "NOBODY")
    assert real.status_code == unknown.status_code == 429
    assert real.json() == unknown.json()


async def test_request_flood_limit_is_shared_by_both_routes(make_client):
    client = make_client("203.0.113.99")
    limit = settings.LOGIN_MAX_REQUESTS_PER_IP_PER_MINUTE
    for number in range(limit):
        path = "/api/auth/login" if number % 2 else "/api/auth/login/full"
        assert (await attempt(client, f"EMP-{number:04d}", path=path)).status_code == 200, number
    assert (await attempt(client, "EMP-9999")).status_code == 429
    assert (await attempt(client, "EMP-9999", path="/api/auth/login/full")).status_code == 429


async def test_disabling_rate_limits_disables_the_throttle_too(make_client, monkeypatch):
    from core.rate_limiting import limiter
    client = make_client()
    monkeypatch.setattr(limiter, "enabled", False)
    for _ in range(settings.MAX_LOGIN_ATTEMPTS + 3):
        assert (await attempt(client, "EMP-0001", "wrong")).status_code == 401
