"""
CR-013: PM project membership (existing roles only).

PMs reach only the projects they manage (users.project_ids); organisation-wide
access is CEO only; nobody crosses organisations; CEO and admins assign
members, a PM manages the non-PM members of their own projects (D1-A); the PM
who creates a project manages it (D2-A); a rollout helper proposes PM
assignments from created projects (D3-A).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from core import authorization


def person(employee_id, role, **extra):
    return {"employee_id": employee_id, "id": employee_id, "name": employee_id, "role": role,
            "organizational_role": role, "project_ids": [], "team_id": None, "org_id": "O1",
            "is_admin": False, "is_active": True, **extra}


PM = person("PM-1", "PM", project_ids=["P1"])
OTHER_PM = person("PM-2", "PM")
CEO = person("CEO-1", "CEO")
ADMIN = person("ADM-1", "DEVOPS", is_admin=True)


async def refused(call, status=403):
    with pytest.raises(HTTPException) as error:
        await call
    assert error.value.status_code == status
    return error.value


class TestScope:
    def test_org_wide_access_is_ceo_only(self):
        assert authorization.has_org_access(CEO) and not authorization.has_org_access(PM)

    @pytest.mark.asyncio
    async def test_accessible_projects_are_the_managed_ones(self):
        assert await authorization.get_accessible_project_ids(PM) == ["P1"]

    @pytest.mark.asyncio
    async def test_other_organisations_are_refused_for_everyone(self):
        with patch("core.authorization._project_repo") as projects:
            projects.find_by_id = AsyncMock(return_value={"id": "P1", "org_id": "O2"})
            await refused(authorization.verify_project_access(PM, "P1"))
            await refused(authorization.verify_project_access(CEO, "P1"))
            await refused(authorization.verify_project_access(person("DEV-1", "DEVELOPER", project_ids=["P1"]), "P1"))

    @pytest.mark.asyncio
    async def test_single_organisation_installs_are_unaffected(self):
        with patch("core.authorization._project_repo") as projects:
            projects.find_by_id = AsyncMock(return_value={"id": "P1"})
            assert await authorization.verify_project_access({**PM, "org_id": None}, "P1") is None

    @pytest.mark.asyncio
    async def test_listing_another_organisation_is_refused(self):
        from api.routes.projects import list_projects
        await refused(list_projects("O2", user=PM))


@pytest.fixture
async def org(mock_db, monkeypatch):
    from api.routes import projects
    monkeypatch.setattr(projects, "col", lambda name: mock_db[name])
    monkeypatch.setattr("core.database.col", lambda name: mock_db[name])
    audit = AsyncMock()
    monkeypatch.setattr(projects, "log_audit", audit)
    await mock_db.projects.insert_many([
        {"id": "P1", "name": "Shop", "org_id": "O1", "team_id": "T1"},
        {"id": "P2", "name": "Bank", "org_id": "O1", "team_id": "T2"},
    ])
    await mock_db.users.insert_many([
        person("PM-1", "PM", project_ids=["P1"]), person("PM-2", "PM"),
        person("DEV-1", "DEVELOPER"), person("DEV-T", "DEVELOPER", team_id="T1"),
        person("OLD-1", "DEVELOPER", is_active=False), person("FAR-1", "DEVELOPER", org_id="O9"),
    ])
    yield mock_db, audit


async def projects_of(db, employee_id):
    return (await db.users.find_one({"employee_id": employee_id}))["project_ids"]


class TestMembership:
    @pytest.mark.anyio
    async def test_admin_assigns_a_pm_and_it_is_audited(self, org):
        from api.routes.projects import MemberRequest, add_project_member
        db, audit = org
        await add_project_member("P2", MemberRequest(employee_id="PM-2"), ADMIN)
        assert await projects_of(db, "PM-2") == ["P2"]
        assert audit.await_args.kwargs["details"] == {"field": "project_ids", "old": [], "new": ["P2"], "project_id": "P2"}

    @pytest.mark.anyio
    async def test_pm_adds_and_removes_developers_on_own_project(self, org):
        from api.routes.projects import MemberRequest, add_project_member, remove_project_member
        db, _ = org
        await add_project_member("P1", MemberRequest(employee_id="DEV-1"), PM)
        assert await projects_of(db, "DEV-1") == ["P1"]
        await remove_project_member("P1", "DEV-1", PM)
        assert await projects_of(db, "DEV-1") == []

    @pytest.mark.anyio
    async def test_pm_cannot_add_pms_or_touch_other_projects(self, org):
        from api.routes.projects import MemberRequest, add_project_member
        await refused(add_project_member("P1", MemberRequest(employee_id="PM-2"), PM))
        await refused(add_project_member("P2", MemberRequest(employee_id="DEV-1"), PM))
        await refused(add_project_member("P1", MemberRequest(employee_id="DEV-1"), person("DEV-9", "DEVELOPER")))

    @pytest.mark.anyio
    async def test_inactive_and_other_organisation_people_are_refused(self, org):
        from api.routes.projects import MemberRequest, add_project_member
        await refused(add_project_member("P1", MemberRequest(employee_id="OLD-1"), ADMIN), 422)
        await refused(add_project_member("P1", MemberRequest(employee_id="FAR-1"), ADMIN), 422)

    @pytest.mark.anyio
    async def test_members_list_shows_assignment_and_team(self, org):
        from api.routes.projects import list_project_members
        with patch("core.authorization._project_repo") as repo:
            repo.find_by_id = AsyncMock(return_value={"id": "P1", "org_id": "O1"})
            result = await list_project_members("P1", user=PM)
        links = {m["employee_id"]: m["link"] for m in result["members"]}
        assert links == {"PM-1": "assigned", "DEV-T": "team"} and result["can_manage"] is True


class TestCreatorAndRollout:
    @pytest.mark.anyio
    async def test_the_creating_pm_manages_the_project(self, org):
        from api.routes import projects
        from domain.models.project import ProjectCreate
        db, _ = org
        created = {"id": "P9", "name": "New", "org_id": "O1", "team_id": "T1"}
        with patch.object(projects.project_service, "create_project", AsyncMock(return_value=created)):
            await projects.create_project(ProjectCreate(name="New", org_id="O1", team_id="T1"), user=OTHER_PM)
        assert await projects_of(db, "PM-2") == ["P9"]

    @pytest.mark.anyio
    async def test_rollout_helper_proposes_created_projects_and_applies(self, mock_db):
        from scripts import assign_pm_projects as helper
        await mock_db.users.insert_many([person("PM-1", "PM", project_ids=["P1"]), person("PM-2", "PM"),
                                         person("PM-X", "PM", is_active=False)])
        await mock_db.projects.insert_many([
            {"id": "P1", "created_by": "PM-1", "org_id": "O1"}, {"id": "P2", "created_by": "PM-1", "org_id": "O1"},
            {"id": "P3", "created_by": "PM-2", "org_id": "O1"}, {"id": "P4", "created_by": "PM-2", "org_id": "O9"},
            {"id": "P5", "created_by": "PM-X", "org_id": "O1"},
        ])
        proposal = await helper.plan(mock_db)
        assert proposal == {"PM-1": ["P2"], "PM-2": ["P3"]}
        assert "PM-1: P2" in helper.describe(proposal)
        assert await helper.apply(mock_db, proposal) == 2
        assert await projects_of(mock_db, "PM-1") == ["P1", "P2"]
        assert await mock_db.audit_logs.count_documents({"action": "USER_UPDATED"}) == 2
        assert await helper.plan(mock_db) == {}


class TestOrgWideReads:
    @pytest.mark.parametrize("module", ["api.routes.ai", "api.routes.traceability", "api.routes.webhooks",
                                        "api.routes.approvals", "api.routes.recommendations"])
    def test_org_wide_reads_now_mean_ceo(self, module):
        import importlib
        assert importlib.import_module(module).has_org_access(PM) is False

    def test_pm_acts_on_recommendations_of_managed_projects_only(self):
        from api.routes.recommendations import _may_act
        assert _may_act({"user_id": "x", "project_id": "P1"}, PM)
        assert not _may_act({"user_id": "x", "project_id": "P2"}, PM)
        assert _may_act({"user_id": "PM-1", "project_id": "P2"}, PM)
