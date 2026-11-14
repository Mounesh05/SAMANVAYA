"""
Fixes for problems found by the end-to-end role check (real backend, real
logins). Each test reproduces what failed in the running app.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException


def person(employee_id, role, **extra):
    return {"employee_id": employee_id, "id": employee_id, "name": employee_id, "role": role,
            "organizational_role": role, "project_ids": [], "team_id": None, "is_admin": False, **extra}


@pytest.fixture
async def org(mock_db, monkeypatch):
    from api.routes import teams
    monkeypatch.setattr(teams, "col", lambda name: mock_db[name])
    monkeypatch.setattr("repositories.user_repository.col", lambda name: mock_db[name])
    await mock_db.teams.insert_many([{"team_id": "TEAM-A", "name": "Team A", "project_ids": ["P1"], "is_active": True},
                                     {"team_id": "TEAM-B", "name": "Team B", "project_ids": ["P2"], "is_active": True}])
    await mock_db.users.insert_many([person("DEV-1", "DEVELOPER", team_id="TEAM-A"), person("LEAD-1", "LEAD", team_id="TEAM-A")])
    with patch("core.authorization._project_repo") as projects:
        projects.find_all = AsyncMock(side_effect=lambda q: [{"id": "P1", "team_id": "TEAM-A"}]
                                      if q.get("team_id") in (None, "TEAM-A") else [])
        yield mock_db


class TestTeamDetail:
    @pytest.mark.anyio
    async def test_pm_opens_the_team_owning_a_managed_project(self, org):
        """E2E: GET /teams/TEAM-A returned 403 for the PM managing its project."""
        from api.routes.teams import get_team
        result = await get_team("TEAM-A", user=person("PM-1", "PM", project_ids=["P1"]))
        assert result.team_id == "TEAM-A"

    @pytest.mark.anyio
    async def test_pm_still_cannot_open_an_unrelated_team(self, org):
        from api.routes.teams import get_team
        with pytest.raises(HTTPException) as error:
            await get_team("TEAM-B", user=person("PM-1", "PM", project_ids=["P1"]))
        assert error.value.status_code == 403

    @pytest.mark.anyio
    async def test_lead_cannot_open_another_team(self, org):
        from api.routes.teams import get_team
        with pytest.raises(HTTPException) as error:
            await get_team("TEAM-B", user=person("LEAD-1", "LEAD", team_id="TEAM-A"))
        assert error.value.status_code == 403


class TestEmployeeRecord:
    @pytest.mark.anyio
    async def test_admin_opens_an_employee_record(self, org):
        """E2E: an admin could edit and deactivate employees but got 403 opening one."""
        from api.routes.employees import get_employee
        result = await get_employee("DEV-1", user=person("ADM-1", "DEVOPS", is_admin=True))
        assert result.employee_id == "DEV-1"

    @pytest.mark.anyio
    async def test_developer_still_cannot_open_other_records(self, org):
        from api.routes.employees import get_employee
        with pytest.raises(HTTPException) as error:
            await get_employee("LEAD-1", user=person("DEV-1", "DEVELOPER", team_id="TEAM-A"))
        assert error.value.status_code == 403


# ── Organisation (E2E finding: Performance refused everyone) ────────────────

@pytest.fixture
async def users_db(mock_db, monkeypatch):
    from api.routes import employees
    monkeypatch.setattr("repositories.user_repository.col", lambda name: mock_db[name])
    monkeypatch.setattr(employees, "log_audit", AsyncMock())
    yield mock_db


def new_employee(employee_id="NEW-1"):
    from api.routes.employees import EmployeeCreate
    return EmployeeCreate(employee_id=employee_id, name="New", email=f"{employee_id.lower()}@samanvaya.com",
                          role="DEVELOPER", dept="Eng", organisation_password="Org-Passw0rd!x",
                          employee_password="Emp-Passw0rd!y")


class TestOrganisation:
    @pytest.mark.anyio
    async def test_new_employees_join_the_creators_organisation(self, users_db):
        from api.routes.employees import create_employee
        await create_employee(new_employee(), person("ADM-1", "DEVOPS", is_admin=True, org_id="ORG7"))
        assert (await users_db.users.find_one({"employee_id": "NEW-1"}))["org_id"] == "ORG7"

    @pytest.mark.anyio
    async def test_creator_without_an_organisation_uses_the_default(self, users_db):
        from api.routes.employees import create_employee
        from core.config import settings
        await create_employee(new_employee("NEW-2"), person("ADM-1", "DEVOPS", is_admin=True))
        assert (await users_db.users.find_one({"employee_id": "NEW-2"}))["org_id"] == settings.DEFAULT_ORG_ID

    @pytest.mark.anyio
    async def test_performance_accepts_a_user_with_an_organisation(self, users_db, monkeypatch):
        """The check that refused everyone now passes once org_id is set."""
        from domain.services import performance_human_service
        from domain.services.performance_human_service import _current
        monkeypatch.setattr(performance_human_service, "col", lambda name: users_db[name])
        await users_db.users.insert_one({"employee_id": "DEV-1", "is_active": True, "org_id": "ORG001"})
        assert (await _current({"employee_id": "DEV-1"}))["org_id"] == "ORG001"

    @pytest.mark.anyio
    async def test_fix_script_fills_only_missing_organisations(self, mock_db):
        from scripts import assign_org
        await mock_db.users.insert_many([{"employee_id": "A"}, {"employee_id": "B", "org_id": ""},
                                         {"employee_id": "C", "org_id": "ORG9"}])
        people = await assign_org.plan(mock_db)
        assert sorted(p["employee_id"] for p in people) == ["A", "B"]
        assert await assign_org.apply(mock_db, people, "ORG001") == 2
        orgs = {u["employee_id"]: u["org_id"] async for u in mock_db.users.find({})}
        assert orgs == {"A": "ORG001", "B": "ORG001", "C": "ORG9"}
        assert await mock_db.audit_logs.count_documents({"details.field": "org_id"}) == 2
        assert await assign_org.plan(mock_db) == []

    def test_fix_script_validates_the_organisation_id(self):
        from scripts import assign_org
        assert assign_org.parse(["--apply", "--org", "ORG_2"], "ORG001") == (True, "ORG_2")
        with pytest.raises(SystemExit):
            assign_org.parse(["--org", "bad id!"], "ORG001")
