"""
CR-009: HR designation field (new structure).

Admins and HR Managers assign designations (D1-A), nobody changes their own,
only HR employees hold one, leaving HR clears it, and every change is audited.
HR users without a designation keep the base HR set (D2-A).
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from core.permissions import (ADMIN_PERMISSIONS, HR_DESIGNATION_PERMISSIONS, HR_DESIGNATIONS, OrganizationalRole,
                              Permission, ROLE_PERMISSIONS, get_user_permissions)


def person(employee_id, role="HR", designation=None, is_admin=False):
    return {"employee_id": employee_id, "name": employee_id, "email": f"{employee_id.lower()}@example.test",
            "role": role, "dept": "People", "is_admin": is_admin, "is_active": True, "designation": designation}


ADMIN = {"employee_id": "ADM-1", "role": "DEVELOPER", "is_admin": True}
HR_MANAGER = {"employee_id": "HRM-1", "role": "HR", "is_admin": False, "designation": "HR_MANAGER"}
HR_BASE = {"employee_id": "HR-1", "role": "HR", "is_admin": False, "designation": None}
HR_OPS = {"employee_id": "OPS-1", "role": "HR", "is_admin": False, "designation": "HR_OPERATIONS"}


@pytest.fixture
async def staff(mock_db, monkeypatch):
    from api.routes import employees
    monkeypatch.setattr("repositories.user_repository.col", lambda name: mock_db[name])
    audit = AsyncMock()
    monkeypatch.setattr(employees, "log_audit", audit)
    await mock_db.users.insert_many([
        person("ADM-1", "DEVELOPER", is_admin=True), person("HRM-1", designation="HR_MANAGER"),
        person("HR-1"), person("HR-2"), person("OPS-1", designation="HR_OPERATIONS"), person("DEV-1", "DEVELOPER"),
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


# ── Permission sets ─────────────────────────────────────────────────────────

class TestSets:
    def test_assigners_are_admins_and_hr_managers(self):
        assert Permission.MANAGE_HR_DESIGNATIONS in ADMIN_PERMISSIONS
        holders = {d for d, s in HR_DESIGNATION_PERMISSIONS.items() if Permission.MANAGE_HR_DESIGNATIONS in s}
        assert holders == {"HR_MANAGER"}
        assert Permission.MANAGE_HR_DESIGNATIONS not in ROLE_PERMISSIONS[OrganizationalRole.HR]

    @pytest.mark.parametrize("designation", HR_DESIGNATIONS)
    def test_every_designation_can_request_its_own_transfer(self, designation):
        assert Permission.REQUEST_TRANSFER in get_user_permissions("HR", False, designation)

    @pytest.mark.parametrize("designation", HR_DESIGNATIONS)
    def test_a_designation_replaces_the_base_set(self, designation):
        assert get_user_permissions("HR", False, designation) == HR_DESIGNATION_PERMISSIONS[designation]

    def test_no_designation_keeps_the_base_set(self):
        assert get_user_permissions("HR", False, None) == ROLE_PERMISSIONS[OrganizationalRole.HR]

    def test_designation_on_another_role_is_ignored(self):
        assert get_user_permissions("DEVELOPER", False, "HR_MANAGER") == ROLE_PERMISSIONS[OrganizationalRole.DEVELOPER]


# ── Assigning ───────────────────────────────────────────────────────────────

class TestAssigning:
    @pytest.mark.anyio
    @pytest.mark.parametrize("actor", [ADMIN, HR_MANAGER])
    async def test_admins_and_hr_managers_assign(self, staff, actor):
        result = await update("HR-1", actor, designation="recruiter")
        assert result.designation == "RECRUITER"
        audit = staff[1].await_args.kwargs
        assert audit["details"] == {"field": "designation", "old": None, "new": "RECRUITER"}

    @pytest.mark.anyio
    @pytest.mark.parametrize("actor", [HR_BASE, HR_OPS])
    async def test_other_hr_staff_cannot_assign(self, staff, actor):
        await refused(update("HR-2", actor, designation="HR_MANAGER"), 403)

    @pytest.mark.anyio
    async def test_nobody_changes_their_own(self, staff):
        await refused(update("HRM-1", HR_MANAGER, designation="COMPENSATION_BENEFITS"), 403)

    @pytest.mark.anyio
    async def test_unknown_code_and_non_hr_roles_are_refused(self, staff):
        await refused(update("HR-1", ADMIN, designation="CHIEF_PEOPLE"), 422)
        await refused(update("DEV-1", ADMIN, designation="RECRUITER"), 422)

    @pytest.mark.anyio
    async def test_clearing_returns_to_generalist(self, staff):
        result = await update("OPS-1", ADMIN, designation=None)
        assert result.designation is None

    @pytest.mark.anyio
    async def test_leaving_hr_clears_the_designation(self, staff):
        result = await update("OPS-1", ADMIN, role="PM")
        assert result.role == "PM" and result.designation is None
        assert staff[1].await_args_list[0].kwargs["details"]["old"] == "HR_OPERATIONS"

    @pytest.mark.anyio
    async def test_edits_without_designation_leave_it_alone(self, staff):
        result = await update("OPS-1", HR_OPS | {"employee_id": "HR-1"}, dept="Ops")
        assert result.designation == "HR_OPERATIONS"


# ── Creating ────────────────────────────────────────────────────────────────

def new_employee(**overrides):
    from api.routes.employees import EmployeeCreate
    values = dict(employee_id="HR-9", name="New", email="new.hire@samanvaya.com", role="HR", dept="People",
                  organisation_password="Org-Passw0rd!x", employee_password="Emp-Passw0rd!y")
    values.update(overrides)
    return EmployeeCreate(**values)


class TestCreating:
    @pytest.mark.anyio
    async def test_admin_creates_a_designated_hr_employee(self, staff):
        from api.routes.employees import create_employee
        result = await create_employee(new_employee(designation="HRBP"), ADMIN)
        assert result.designation == "HRBP"
        assert (await staff[0].users.find_one({"employee_id": "HR-9"}))["designation"] == "HRBP"

    @pytest.mark.anyio
    async def test_base_hr_cannot_create_with_a_designation(self, staff):
        from api.routes.employees import create_employee
        await refused(create_employee(new_employee(designation="HR_MANAGER"), HR_BASE), 403)
        assert await staff[0].users.count_documents({"employee_id": "HR-9"}) == 0

    @pytest.mark.anyio
    async def test_base_hr_still_creates_without_one(self, staff):
        from api.routes.employees import create_employee
        await create_employee(new_employee(), HR_BASE)
        assert (await staff[0].users.find_one({"employee_id": "HR-9"}))["designation"] is None
