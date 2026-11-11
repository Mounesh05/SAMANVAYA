"""Authentication boundaries use current accounts and durable logout state."""

from datetime import datetime, timezone

import pytest
from fastapi import Depends, FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pymongo.errors import ConnectionFailure

from core import database, security
from core.dependencies import get_current_user, get_current_user_optional, require_admin
from domain.services.auth_service import AuthService

pytestmark = pytest.mark.anyio

@pytest.fixture
async def session_store(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    await mock_db.users.insert_one({
        "employee_id": "SESSION-USER", "role": "HR", "is_admin": True,
        "is_active": True, "org_id": "ORG", "team_id": "OLD", "project_ids": ["P1"],
        "designation": "HR Manager",
    })
    return mock_db


def token():
    return security.create_access_token(AuthService._token_payload({
        "employee_id": "SESSION-USER", "role": "HR", "is_admin": True,
        "team_id": "OLD", "project_ids": ["P1"], "org_id": "ORG",
    }))


@pytest.mark.parametrize("scheme", ["Bearer", "bearer", "bEaReR"])
async def test_logout_rejects_same_token_on_required_and_optional_routes(session_store, scheme):
    from api.routes.auth import logout
    app = FastAPI()
    app.post("/logout")(logout)

    @app.get("/required")
    async def required(user=Depends(get_current_user)):
        return user["employee_id"]

    @app.get("/optional")
    async def optional(user=Depends(get_current_user_optional)):
        return {"authenticated": user is not None}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = {"Authorization": f"{scheme} {token()}"}
        assert (await client.get("/required", headers=headers)).status_code == 200
        assert (await client.post("/logout", headers=headers)).status_code == 200
        assert (await client.get("/required", headers=headers)).status_code == 401
        assert (await client.get("/optional", headers=headers)).json() == {"authenticated": False}


async def test_authorization_uses_current_record_and_clears_removed_claims(session_store):
    encoded = token()
    await session_store.users.update_one({"employee_id": "SESSION-USER"}, {
        "$set": {"role": "DEVELOPER", "is_admin": False, "team_id": "NEW", "org_id": "NEW-ORG"},
        "$unset": {"project_ids": "", "designation": ""},
    })
    user = await get_current_user(f"Bearer {encoded}")
    assert user["role"] == "DEVELOPER" and user["is_admin"] is False
    assert user["team_id"] == "NEW" and user["org_id"] == "NEW-ORG"
    assert user["project_ids"] == [] and user.get("designation") is None
    with pytest.raises(HTTPException) as denied:
        await require_admin()(user)
    assert denied.value.status_code == 403


@pytest.mark.parametrize("change", ["deactivate", "delete"])
async def test_removed_account_cannot_keep_old_session(session_store, change):
    encoded = token()
    if change == "delete":
        await session_store.users.delete_one({"employee_id": "SESSION-USER"})
    else:
        await session_store.users.update_one({"employee_id": "SESSION-USER"}, {"$set": {"is_active": False}})
    with pytest.raises(HTTPException) as denied:
        await get_current_user(f"Bearer {encoded}")
    assert denied.value.status_code == 401
    assert await get_current_user_optional(f"Bearer {encoded}") is None


async def test_durable_revocation_survives_fresh_security_module(session_store):
    import importlib.util
    encoded = token()
    claims = security.decode_token(encoded)
    from api.routes.auth import logout
    await logout(authorization=f"Bearer {encoded}", user=claims)
    spec = importlib.util.spec_from_file_location("core.fresh_security", security.__file__)
    fresh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh)
    assert await fresh.is_token_revoked(claims["jti"])
    stored = await session_store.revoked_tokens.find_one({"_id": claims["jti"]})
    assert stored["expires_at"].replace(tzinfo=timezone.utc) == datetime.fromtimestamp(claims["exp"], timezone.utc)


async def test_storage_outage_never_falls_back_to_signed_claims(session_store, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: (_ for _ in ()).throw(ConnectionFailure("offline")))
    for dependency in [get_current_user, get_current_user_optional]:
        with pytest.raises(HTTPException) as denied:
            await dependency(f"Bearer {token()}")
        assert denied.value.status_code == 503


@pytest.mark.parametrize("authorization", [None, "Bearer malformed", "Basic abc"])
async def test_optional_unauthenticated_contract(session_store, authorization):
    assert await get_current_user_optional(authorization) is None


@pytest.mark.parametrize("changes", [{"jti": None}, {"sub": "different"}, {"employee_id": None},
                                    {"exp": None}, {"session_version": None}, {"session_version": 0}])
async def test_incomplete_or_mismatched_session_identity_is_rejected(session_store, changes):
    import jwt
    claims = security.decode_token(token())
    for field, value in changes.items():
        if value is None:
            claims.pop(field, None)
        else:
            claims[field] = value
    encoded = jwt.encode(claims, security.settings.SECRET_KEY, algorithm=security.settings.ALGORITHM)
    with pytest.raises(HTTPException) as denied:
        await get_current_user(f"Bearer {encoded}")
    assert denied.value.status_code == 401
    assert await get_current_user_optional(f"Bearer {encoded}") is None


async def test_failed_logout_write_does_not_report_success(session_store, monkeypatch):
    from api.routes import auth
    from unittest.mock import AsyncMock
    claims = security.decode_token(token())
    monkeypatch.setattr(auth, "revoke_token", AsyncMock(side_effect=ConnectionFailure("offline")))
    with pytest.raises(HTTPException) as denied:
        await auth.logout(authorization="unused", user=claims)
    assert denied.value.status_code == 503
