"""
CR-008: Platform Admin (access and rules only, no new backend structure).

Activating or deactivating an account is admin-only everywhere, the last
active admin is protected, admins run the platform but don't make people
decisions (D2-A), and admin-right changes are audited. "Lead/PM and admin"
for performance claims stays as it is (D3-A).
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from core.permissions import ADMIN_PERMISSIONS, Permission, get_user_permissions


def person(employee_id, role="DEVELOPER", is_admin=False, is_active=True):
    return {"employee_id": employee_id, "name": employee_id, "email": f"{employee_id.lower()}@example.test",
            "role": role, "dept": "Engineering", "is_admin": is_admin, "is_active": is_active}


ADMIN = {"employee_id": "ADM-1", "role": "DEVELOPER", "is_admin": True}
HR = {"employee_id": "HR-1", "role": "HR", "is_admin": False}


@pytest.fixture
async def staff(mock_db, monkeypatch):
    from api.routes import employees
    monkeypatch.setattr("repositories.user_repository.col", lambda name: mock_db[name])
    audit = AsyncMock()
    monkeypatch.setattr(employees, "log_audit", audit)
    await mock_db.users.insert_many([
        person("ADM-1", is_admin=True), person("CEO-1", "CEO", is_admin=True),
        person("DEV-1"), person("HR-1", "HR"),
    ])
    yield mock_db, audit


async def update(employee_id, user, **fields):
    from api.routes.employees import EmployeeUpdate, update_employee
    return await update_employee(employee_id, EmployeeUpdate(**fields), user)


async def refused(call, status):
    with pytest.raises(HTTPException) as error:
        await call
    assert error.value.status_code == status
    return error.value


# ── Active status ───────────────────────────────────────────────────────────

class TestActiveStatus:
    @pytest.mark.anyio
    async def test_hr_can_no_longer_deactivate_through_edit(self, staff):
        await refused(update("DEV-1", HR, is_active=False), 403)
        assert (await staff[0].users.find_one({"employee_id": "DEV-1"}))["is_active"] is True

    @pytest.mark.anyio
    async def test_admin_deactivates_and_it_is_audited(self, staff):
        result = await update("DEV-1", ADMIN, is_active=False)
        assert result.is_active is False
        assert staff[1].await_args.kwargs["action"].value == "USER_DEACTIVATED"

    @pytest.mark.anyio
    async def test_ceo_account_and_self_are_refused(self, staff):
        await refused(update("CEO-1", ADMIN, is_active=False), 403)
        await refused(update("ADM-1", ADMIN, is_active=False), 400)

    @pytest.mark.anyio
    async def test_unchanged_active_flag_is_not_an_admin_action(self, staff):
        result = await update("DEV-1", HR, is_active=True, dept="Platform")
        assert result.dept == "Platform"


# ── Last active admin ───────────────────────────────────────────────────────

class TestLastAdmin:
    @pytest.mark.anyio
    async def test_admin_rights_move_from_the_ceo_to_a_platform_admin(self, staff):
        await update("DEV-1", ADMIN, is_admin=True)
        await update("CEO-1", ADMIN, is_admin=False)
        assert (await staff[0].users.find_one({"employee_id": "CEO-1"}))["is_admin"] is False
        actions = [c.kwargs["action"].value for c in staff[1].await_args_list]
        assert actions == ["ADMIN_GRANTED", "ADMIN_REVOKED"]

    @pytest.mark.anyio
    async def test_the_last_admin_cannot_lose_admin_rights(self, staff):
        await update("CEO-1", ADMIN, is_admin=False)
        error = await refused(update("ADM-1", {**ADMIN, "employee_id": "OTHER"}, is_admin=False), 409)
        assert "last active admin" in error.detail

    @pytest.mark.anyio
    async def test_the_last_admin_cannot_be_deactivated(self, staff):
        from api.routes.employees import delete_employee
        await staff[0].users.update_one({"employee_id": "CEO-1"}, {"$set": {"is_admin": False}})
        await staff[0].users.insert_one(person("ADM-2", is_admin=True, is_active=False))
        await refused(delete_employee("ADM-1", {"employee_id": "SOMEONE", "is_admin": True}), 409)

    @pytest.mark.anyio
    async def test_only_admins_change_admin_rights(self, staff):
        await refused(update("DEV-1", HR, is_admin=True), 403)


# ── Admin rights are platform rights ────────────────────────────────────────

PEOPLE_DECISIONS = [Permission.TRIGGER_AI_EVALUATION, Permission.TRIGGER_BULK_EVALUATION,
                    Permission.MANAGE_EVALUATION_POLICY, Permission.REVIEW_HUMAN_EVALUATION_COMPLETENESS]


class TestAdminPermissions:
    @pytest.mark.parametrize("permission", PEOPLE_DECISIONS)
    def test_people_decisions_are_not_admin_rights(self, permission):
        assert permission not in ADMIN_PERMISSIONS
        assert permission not in get_user_permissions("DEVELOPER", True)

    @pytest.mark.parametrize("permission", PEOPLE_DECISIONS[:3])
    def test_the_ceo_keeps_them_through_the_role(self, permission):
        assert permission in get_user_permissions("CEO", False)

    def test_platform_rights_stay(self):
        assert {Permission.MANAGE_EMPLOYEES, Permission.MANAGE_TEAMS, Permission.CREATE_TEAM,
                Permission.ASSIGN_TEAM_LEAD, Permission.ASSIGN_PROJECT, Permission.VIEW_AUDIT_LOGS} <= ADMIN_PERMISSIONS


class TestNoAdminBypass:
    DEV_ADMIN = {"employee_id": "ADM-1", "role": "DEVELOPER", "is_admin": True, "org_id": "O1"}

    @pytest.mark.asyncio
    async def test_admin_cannot_approve_function_contracts_without_the_role(self):
        from domain.services.function_contract_service import FunctionContractService
        service = FunctionContractService.__new__(FunctionContractService)
        with pytest.raises(PermissionError):
            await service.approve({"proposed_by": "DEV-9"}, {}, self.DEV_ADMIN)

    @pytest.mark.asyncio
    async def test_admin_cannot_approve_requirements_without_the_role(self):
        from domain.services.requirement_discovery_service import RequirementDiscoveryService
        service = RequirementDiscoveryService.__new__(RequirementDiscoveryService)
        body = {"expected_fingerprint": "x", "source_reference": "spec.md", "rationale": "ok", "scope_reviewed": True}
        with pytest.raises(PermissionError):
            await service.approve({"proposed_by": "DEV-9", "organization_id": "O1"}, body, self.DEV_ADMIN)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("name", ["save_hr_assessment_draft", "submit_hr_assessment", "configure_human_evaluation_policy"])
    async def test_admin_without_the_permission_is_refused_on_hr_and_policy_routes(self, name):
        from api.routes import performance
        endpoint = getattr(performance, name, None)
        if endpoint is None:
            pytest.skip(f"{name} not present")
        with pytest.raises(HTTPException) as error:
            await endpoint(**_minimal_args(endpoint, self.DEV_ADMIN))
        assert error.value.status_code == 403


def _minimal_args(endpoint, user):
    import inspect
    args = {}
    for param in inspect.signature(endpoint).parameters.values():
        if param.name == "user":
            args["user"] = user
        elif param.default is inspect.Parameter.empty:
            args[param.name] = None
    return args
