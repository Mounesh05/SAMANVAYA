"""Audit records require immutable tenant provenance before scoped disclosure."""
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import FastAPI

from api.routes import audit
from core import database
from core.audit import AuditAction, audit_logger, log_audit
from core.dependencies import get_current_user

pytestmark = pytest.mark.anyio


@pytest.fixture
async def audit_api(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    monkeypatch.setattr(audit_logger, "collection", mock_db.audit_logs)
    actor = {"employee_id": "CEO-A", "role": "CEO", "org_id": "A"}
    app = FastAPI()
    app.include_router(audit.router, prefix="/audit")
    app.dependency_overrides[get_current_user] = lambda: actor
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base = {"actor_id": "shared-actor", "resource_type": "employee", "resource_id": "shared-resource",
            "action": AuditAction.USER_UPDATED.value, "date": date, "timestamp": date, "details": {"marker": "OWN"}}
    await mock_db.audit_logs.insert_many([
        {**base, "org_id": "A"},
        {**base, "org_id": "B", "timestamp": date + "Z", "details": {"marker": "FOREIGN"}},
        {**base, "timestamp": date + "Z", "details": {"marker": "LEGACY"}},
        {**base, "org_id": ["A", "B"], "details": {"marker": "ARRAY"}},
        {**base, "org_id": "A", "organization_id": "B", "details": {"marker": "CONFLICT"}},
    ])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, mock_db, actor


@pytest.mark.parametrize("role", ["CEO", "HR"])
@pytest.mark.parametrize("path", ["/logs?limit=1", "/logs/user/shared-actor/activity", "/logs/resource/employee/shared-resource?limit=1"])
async def test_audit_reads_scope_before_limits_and_counts(audit_api, role, path):
    client, _, actor = audit_api
    actor["role"] = role
    response = await client.get("/audit" + path)
    assert response.status_code == 200
    assert "OWN" in response.text
    for marker in ("FOREIGN", "LEGACY", "ARRAY", "CONFLICT"):
        assert marker not in response.text


@pytest.mark.parametrize("org", [None, "", ["A"], 1])
async def test_audit_principal_without_scalar_tenant_is_denied(audit_api, org):
    client, _, actor = audit_api
    actor["org_id"] = org
    assert (await client.get("/audit/logs")).status_code == 403


async def test_audit_write_preserves_verified_actor_tenant(audit_api):
    _, db, actor = audit_api
    await log_audit(AuditAction.USER_UPDATED, actor, resource_id="new-local-record")
    record = await db.audit_logs.find_one({"resource_id": "new-local-record"})
    assert record["org_id"] == "A"


async def test_hr_allowed_actions_are_filtered_before_limit(audit_api):
    client, db, actor = audit_api
    actor["role"] = "HR"
    await db.audit_logs.insert_one({"org_id": "A", "action": AuditAction.ADMIN_REVOKED.value, "timestamp": "9999", "details": {"marker": "RESTRICTED"}})
    response = await client.get("/audit/logs?limit=1")
    assert response.status_code == 200
    assert "OWN" in response.text and "RESTRICTED" not in response.text
