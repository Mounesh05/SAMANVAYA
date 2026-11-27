"""Sign-in abuse protection for /api/auth/login and /api/auth/login/full.

Why not "5 requests per minute per IP": that counted *successful* sign-ins,
so an office (or a proxy) sharing one IP address locked everyone out after
five ordinary logins. Successful sign-ins now never count against anyone.

Failed sign-ins are counted in three buckets over a moving window
(LOGIN_FAILURE_WINDOW_MINUTES, default 15):

====================  ==================================  ===================
bucket                stops                               default threshold
====================  ==================================  ===================
account + IP          guessing one account's password     MAX_LOGIN_ATTEMPTS
                      from one address                    (5)
account (any IP)      guessing one account's password     20
                      from many addresses
IP (any account)      trying many identifiers from one    50
                      address (credential stuffing)
====================  ==================================  ===================

Thresholds: 5 keeps the existing per-person allowance for typos. 20 is four
times that, so a single attacking address cannot by itself lock a person
out, while distributed guessing on one account is still capped at about 80
guesses an hour. 50 lets a busy shared office absorb ordinary typos
(dozens of people mistyping once) while stopping one address from testing
many accounts.

A separate request-flood limit (LOGIN_MAX_REQUESTS_PER_IP_PER_MINUTE,
default 60, all attempts) is applied by SlowAPI and shared by both routes.

When any bucket is full the attempt is refused with 429 *before* the
password is checked, with the same message for existing and unknown
accounts. A successful sign-in clears that account's buckets, but never
the IP bucket: otherwise one valid account could reset it between guesses.

Counters use the SlowAPI limiter's storage (in memory by default; shared
when SlowAPI is configured with a shared store). Identifiers are hashed.
"""

import hashlib
import time

from fastapi import HTTPException, Request
from limits import parse
from slowapi.util import get_remote_address

from core.config import settings
from core.rate_limiting import limiter

NAMESPACE = "login-failures"
TOO_MANY_ATTEMPTS = "Too many sign-in attempts. Wait a few minutes and try again."


def _rules():
    window = settings.LOGIN_FAILURE_WINDOW_MINUTES
    return (
        ("account-ip", parse(f"{settings.MAX_LOGIN_ATTEMPTS} per {window} minutes")),
        ("account", parse(f"{settings.LOGIN_MAX_FAILURES_PER_ACCOUNT} per {window} minutes")),
        ("ip", parse(f"{settings.LOGIN_MAX_FAILURES_PER_IP} per {window} minutes")),
    )


def _keys(request: Request, login_id: str) -> dict:
    account = hashlib.sha256((login_id or "").strip().lower().encode()).hexdigest()[:32]
    ip = get_remote_address(request) or "unknown"
    return {"account-ip": (account, ip), "account": (account,), "ip": (ip,)}


def _enabled() -> bool:
    # The same switch as every other limit (RATE_LIMIT_ENABLED sets it).
    return bool(limiter.enabled)


def check(request: Request, login_id: str) -> None:
    """Raise 429 when any failure bucket for this attempt is full."""
    if not _enabled():
        return
    keys = _keys(request, login_id)
    for scope, item in _rules():
        if not limiter.limiter.test(item, NAMESPACE, scope, *keys[scope]):
            reset = limiter.limiter.get_window_stats(item, NAMESPACE, scope, *keys[scope]).reset_time
            retry_after = max(1, int(reset - time.time()))
            raise HTTPException(status_code=429, detail=TOO_MANY_ATTEMPTS, headers={"Retry-After": str(retry_after)})


def record_failure(request: Request, login_id: str) -> None:
    if not _enabled():
        return
    keys = _keys(request, login_id)
    for scope, item in _rules():
        limiter.limiter.hit(item, NAMESPACE, scope, *keys[scope])


def record_success(request: Request, login_id: str) -> None:
    """Forget this account's failures; the IP-wide bucket is kept on purpose."""
    if not _enabled():
        return
    keys = _keys(request, login_id)
    for scope, item in _rules():
        if scope != "ip":
            limiter.limiter.clear(item, NAMESPACE, scope, *keys[scope])
