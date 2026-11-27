"""SEC-05: browser sessions in an HttpOnly cookie instead of localStorage.

* ``samanvaya_session`` holds the JWT. It is HttpOnly (page scripts cannot read
  it), SameSite=Strict, and Secure when SECURE_COOKIES is on (required in
  production).
* ``samanvaya_csrf`` is a random value page scripts *can* read. Requests that
  authenticate with the session cookie and change state must echo it in the
  ``X-CSRF-Token`` header (double-submit). A cross-site page cannot read the
  cookie, so it cannot forge that header.

API clients that send ``Authorization: Bearer`` are unchanged and need no CSRF
header, because browsers never attach that header automatically.
"""

import hmac
import secrets

from fastapi import Response

from core.config import settings

SESSION_COOKIE = "samanvaya_session"
CSRF_COOKIE = "samanvaya_csrf"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def set_session_cookies(response: Response, token: str) -> None:
    max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    for name, value, http_only in ((SESSION_COOKIE, token, True), (CSRF_COOKIE, secrets.token_urlsafe(32), False)):
        response.set_cookie(name, value, max_age=max_age, secure=settings.SECURE_COOKIES, httponly=http_only,
                            samesite="strict", path="/")


def clear_session_cookies(response: Response) -> None:
    for name, http_only in ((SESSION_COOKIE, True), (CSRF_COOKIE, False)):
        response.delete_cookie(name, path="/", secure=settings.SECURE_COOKIES, httponly=http_only, samesite="strict")


def csrf_valid(method: str, cookie_value, header_value) -> bool:
    if method.upper() in SAFE_METHODS:
        return True
    if not cookie_value or not header_value:
        return False
    return hmac.compare_digest(str(cookie_value).encode(), str(header_value).encode())
