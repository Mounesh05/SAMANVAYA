"""
CR-016: one sign-in rule (larger-company model).

Every sign-in names an employee ID or a work email and gives both the
organisation and the employee password. Every failure gets the same message,
and every attempt is recorded in the audit log without any password.
"""

from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from core.security import hash_password

ORG, EMP = "Org-Pass-1234!", "Emp-Pass-5678!"


@pytest.fixture
async def api(mock_db, monkeypatch):
    from api.routes import auth
    from core import audit
    from core.rate_limiting import limiter
    from repositories.user_repository import UserRepository

    monkeypatch.setattr("repositories.user_repository.col", lambda name: mock_db[name])
    monkeypatch.setattr(auth.auth_service, "user_repo", UserRepository())
    monkeypatch.setattr(limiter, "enabled", False)
    recorded = AsyncMock()
    monkeypatch.setattr(audit, "log_audit", recorded)

    base = dict(organisation_password=hash_password(ORG), employee_password=hash_password(EMP),
                role="DEVELOPER", dept="Engineering", org_id="O1")
    await mock_db.users.insert_many([
        dict(base, employee_id="EMP-1001", name="Asha Rao", email="asha.rao@company.com", is_active=True),
        dict(base, employee_id="EMP-1002", name="Former Employee", email="left@company.com", is_active=False),
    ])

    app = FastAPI()
    app.include_router(auth.router, prefix="/api/auth")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, recorded


def body(identifier, org=ORG, emp=EMP):
    return {"identifier": identifier, "organisation_password": org, "employee_password": emp}


@pytest.mark.anyio
@pytest.mark.parametrize("identifier", ["EMP-1001", "emp-1001", " EMP-1001 ", "asha.rao@company.com", "Asha.Rao@Company.com"])
async def test_employee_id_or_work_email_with_both_passwords(api, identifier):
    client, _ = api
    response = await client.post("/api/auth/login", json=body(identifier))
    assert response.status_code == 200
    assert response.json()["user"]["employee_id"] == "EMP-1001"
    assert response.json()["token"]


@pytest.mark.anyio
@pytest.mark.parametrize("attempt", [
    body("EMP-1001", org="wrong"),             # wrong organisation password
    body("EMP-1001", emp="wrong"),             # wrong employee password
    body("EMP-1001", org=EMP, emp=EMP),        # the employee password alone, twice
    body("EMP-9999"),                          # no such account
    body("EMP-1002"),                          # inactive account, right passwords
    body("nobody@company.com"),
])
async def test_every_failure_gets_the_same_answer(api, attempt):
    from api.routes.auth import SIGN_IN_FAILED
    client, _ = api
    response = await client.post("/api/auth/login", json=attempt)
    assert response.status_code == 401
    assert response.json()["detail"] == SIGN_IN_FAILED


@pytest.mark.anyio
async def test_the_old_email_and_one_password_form_is_gone(api):
    client, _ = api
    response = await client.post("/api/auth/login", json={"email": "asha.rao@company.com", "password": EMP})
    assert response.status_code == 422


@pytest.mark.anyio
async def test_login_full_keeps_working_with_the_same_rule(api):
    client, _ = api
    ok = await client.post("/api/auth/login/full", json={"employee_id": "EMP-1001", "organisation_password": ORG,
                                                          "employee_password": EMP})
    assert ok.status_code == 200
    refused = await client.post("/api/auth/login/full", json={"employee_id": "EMP-1001", "organisation_password": "x",
                                                               "employee_password": EMP})
    assert refused.status_code == 401


@pytest.mark.anyio
async def test_attempts_are_audited_without_passwords(api):
    from core.audit import AuditAction
    client, recorded = api
    await client.post("/api/auth/login", json=body("EMP-1001"))
    await client.post("/api/auth/login", json=body("EMP-1001", emp="Not-The-Password-1!"))
    (ok_args, ok_kwargs), (bad_args, bad_kwargs) = [(c.args, c.kwargs) for c in recorded.await_args_list]
    assert ok_args[0] == AuditAction.LOGIN and ok_args[1]["employee_id"] == "EMP-1001" and ok_kwargs["success"]
    assert bad_args[0] == AuditAction.LOGIN_FAILED and bad_args[1]["employee_id"] == "anonymous"
    assert bad_kwargs["success"] is False and bad_kwargs["details"]["login_id"] == "EMP-1001"
    logged = str(recorded.await_args_list)
    for secret in (ORG, EMP, "Not-The-Password-1!"):
        assert secret not in logged


@pytest.mark.anyio
async def test_audit_trouble_never_blocks_sign_in(api, monkeypatch):
    from core import audit
    client, _ = api
    monkeypatch.setattr(audit, "log_audit", AsyncMock(side_effect=RuntimeError("audit store down")))
    assert (await client.post("/api/auth/login", json=body("EMP-1001"))).status_code == 200


@pytest.mark.anyio
async def test_unknown_accounts_still_check_a_password_hash(api, monkeypatch):
    """Timing: a missing account costs the same bcrypt checks as a real one."""
    from domain.services import auth_service as service_module
    client, _ = api
    checks = []
    real = service_module.verify_password
    monkeypatch.setattr(service_module, "verify_password", lambda plain, hashed: checks.append(hashed) or real(plain, hashed))
    await client.post("/api/auth/login", json=body("EMP-9999"))
    assert len(checks) == 2 and all(h == service_module._UNUSED_HASH for h in checks)
