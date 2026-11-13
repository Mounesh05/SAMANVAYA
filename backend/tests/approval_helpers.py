"""Shared helpers for CR-010 two-person approval tests."""

import json
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException


def wire(mock_db, monkeypatch):
    """Point users, approvals and audit at the in-memory database; returns the audit mock."""
    from api.routes import approvals, employees
    from domain.services import employee_change_service
    from domain.services.hitl_workflow_service import hitl_service
    monkeypatch.setattr("repositories.user_repository.col", lambda name: mock_db[name])
    monkeypatch.setattr(hitl_service, "collection", mock_db["approvals"])
    monkeypatch.setattr(hitl_service.notification_service, "notify", AsyncMock())
    audit = AsyncMock()
    for module in (employees, employee_change_service, approvals):
        monkeypatch.setattr(module, "log_audit", audit)
    return audit


def body(response):
    """Payload of a 202 JSONResponse (or a plain model / dict)."""
    if hasattr(response, "body"):
        return json.loads(response.body)
    return response if isinstance(response, dict) else response.model_dump()


async def update(employee_id, user, **fields):
    from api.routes.employees import EmployeeUpdate, update_employee
    return await update_employee(employee_id, EmployeeUpdate(**fields), user)


async def approve(approval_id, user, comment=None):
    from api.routes.approvals import ApproveRequest, approve_request
    return await approve_request(approval_id, ApproveRequest(comment=comment), user)


async def reject(approval_id, user, reason="no"):
    from api.routes.approvals import RejectRequest, reject_request
    return await reject_request(approval_id, RejectRequest(reason=reason), user)


async def refused(call, status):
    with pytest.raises(HTTPException) as error:
        await call
    assert error.value.status_code == status
    return error.value
