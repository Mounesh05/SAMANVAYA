"""
CR-004: Lead access (access and rules only, no new backend structure).

A Lead manages one team: people data (AI evaluations) is team-scoped, the QA
module is limited to team and assigned projects, QA verifies defects, and Leads
can run team sprints.
"""

import inspect
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from core import database
from core.permissions import Permission, ROLE_PERMISSIONS


def make_user(employee_id="LEAD-1", role="LEAD", project_ids=None, team_id="TEAM-A", **extra):
    return {"employee_id": employee_id, "id": employee_id, "name": f"User {employee_id}", "role": role,
            "organizational_role": role, "project_ids": project_ids or [], "team_id": team_id, **extra}


LEAD = make_user()
CEO = make_user("CEO-1", "CEO", team_id=None)
PROJECT_A = {"id": "PRJ-A", "team_id": "TEAM-A", "org_id": "O1"}
PROJECT_B = {"id": "PRJ-B", "team_id": "TEAM-B", "org_id": "O1"}


def holders(permission):
    return {role.value for role, granted in ROLE_PERMISSIONS.items() if permission in granted}


@pytest.fixture
async def people(mock_db, monkeypatch):
    """TEAM-A: LEAD-1, DEV-A. TEAM-B: DEV-B. DEV-P is on TEAM-B but assigned to PRJ-A."""
    monkeypatch.setattr(database, "col", lambda name: mock_db[name])
    await mock_db.users.insert_many([
        {"employee_id": "LEAD-1", "team_id": "TEAM-A"},
        {"employee_id": "DEV-A", "team_id": "TEAM-A"},
        {"employee_id": "DEV-B", "team_id": "TEAM-B"},
        {"employee_id": "DEV-P", "team_id": "TEAM-B", "project_ids": ["PRJ-A"]},
    ])
    projects = AsyncMock()
    projects.find_all = AsyncMock(side_effect=lambda query: [p for p in (PROJECT_A, PROJECT_B)
                                                             if all(p.get(k) == v for k, v in query.items())])
    projects.find_by_id = AsyncMock(side_effect=lambda pid: {"PRJ-A": PROJECT_A, "PRJ-B": PROJECT_B}.get(pid))
    with patch("core.authorization._project_repo", projects):
        yield mock_db


# ── Permission matrix ───────────────────────────────────────────────────────

@pytest.mark.parametrize("permission, roles", [
    (Permission.SYNC_REPOSITORY_PRS, {"LEAD"}),  # CR-015: not PM
    (Permission.ANALYZE_SPRINT_RISK, {"LEAD", "PM"}),
    (Permission.CREATE_SPRINT, {"LEAD", "PM"}),  # Lead added (Decision 1)
])
def test_permission_holders(permission, roles):
    assert holders(permission) == roles


@pytest.mark.asyncio
@pytest.mark.parametrize("module, name, allowed", [
    ("api.routes.github", "sync_repository_prs", ("LEAD",)),  # CR-015: PR syncing is engineering's, not the PM's
    ("api.routes.intelligence", "analyze_sprint", ("LEAD", "PM"))])
async def test_converted_guards_keep_lead_and_pm(module, name, allowed):
    import importlib
    check = inspect.signature(getattr(importlib.import_module(module), name)).parameters["user"].default.dependency
    for role in allowed:
        assert (await check(user=make_user("X", role)))["role"] == role
    for role in {"LEAD", "PM", "DEVELOPER", "QA", "DEVOPS", "HR", "CEO"} - set(allowed):
        with pytest.raises(HTTPException):
            await check(user=make_user("X", role))


# ── Team scope for AI evaluations ───────────────────────────────────────────

@pytest.mark.anyio
class TestEvaluationScope:
    async def test_team_members_include_team_and_project_assignees(self, people):
        from core.authorization import team_member_ids
        assert await team_member_ids(LEAD) == {"LEAD-1", "DEV-A", "DEV-P"}

    @pytest.mark.parametrize("target", ["LEAD-1", "DEV-A", "DEV-P"])
    async def test_lead_sees_own_team(self, people, target):
        from core.authorization import verify_can_view_person_evaluations
        assert await verify_can_view_person_evaluations(LEAD, target) is None

    async def test_lead_cannot_see_another_team(self, people):
        from core.authorization import verify_can_view_person_evaluations
        with pytest.raises(HTTPException) as error:
            await verify_can_view_person_evaluations(LEAD, "DEV-B")
        assert error.value.status_code == 403

    async def test_ceo_sees_everyone_and_others_only_themselves(self, people):
        from core.authorization import verify_can_view_person_evaluations
        assert await verify_can_view_person_evaluations(CEO, "DEV-B") is None
        dev = make_user("DEV-A", "DEVELOPER")
        assert await verify_can_view_person_evaluations(dev, "DEV-A") is None
        with pytest.raises(HTTPException):
            await verify_can_view_person_evaluations(dev, "LEAD-1")

    async def test_lead_cannot_run_an_evaluation_outside_the_team(self, people):
        from api.routes import evaluation
        request = evaluation.SimpleEvalRequest(employee_id="DEV-B", github_username="b", repo_owner="o", repo_name="r", pr_number=1)
        with patch.object(evaluation, "GitHubAPIService") as github:
            with pytest.raises(HTTPException) as error:
                await evaluation.evaluate_developer_ai(request, user=LEAD)
        assert error.value.status_code == 403
        github.assert_not_called()  # refused before any GitHub call

    async def test_latest_evaluation_is_limited_to_the_team(self, people):
        from api.routes import evaluation
        with patch.object(evaluation.EvaluationRepository, "latest", new=AsyncMock(return_value=None)) as latest:
            await evaluation.get_latest_evaluation(user=LEAD)
            assert latest.await_args.args[0] == {"employee_id": {"$in": ["DEV-A", "DEV-P", "LEAD-1"]}}
            await evaluation.get_latest_evaluation(user=CEO)
            assert latest.await_args.args[0] == {}

    async def test_employee_evaluation_list_is_scoped(self, people):
        from api.routes import evaluation
        with patch.object(evaluation.EvaluationRepository, "list", new=AsyncMock(return_value=[])):
            assert await evaluation.list_employee_evaluations("DEV-A", user=LEAD) == []
            with pytest.raises(HTTPException):
                await evaluation.list_employee_evaluations("DEV-B", user=LEAD)

    async def test_pr_evaluations_only_for_linked_repositories(self, people):
        from api.routes import evaluation
        await people["github_project_configs"].insert_many([
            {"project_id": "PRJ-A", "repository_owner": "acme", "repository_name": "shop"},
            {"project_id": "PRJ-B", "repository_owner": "acme", "repository_name": "bank"},
        ])
        with patch.object(evaluation.EvaluationRepository, "list", new=AsyncMock(return_value=[])):
            assert await evaluation.list_pr_evaluations("ACME", "Shop", 7, user=LEAD) == []
            with pytest.raises(HTTPException) as error:
                await evaluation.list_pr_evaluations("acme", "bank", 7, user=LEAD)
            assert error.value.status_code == 403
            assert await evaluation.list_pr_evaluations("acme", "bank", 7, user=CEO) == []

    async def test_deprecated_evaluate_endpoint_is_scoped_too(self, people):
        from api.routes import performance
        with pytest.raises(HTTPException) as error:
            await performance.evaluate_developer_performance(
                developer_id="DEV-B", developer_name="B", period="2026-Q4", developer_email=None,
                project_id="PRJ-B", period_type="quarter", repo_owner=None, repo_name=None,
                evaluated_by="api", user=LEAD)
        assert error.value.status_code == 403


# ── QA module scope and defect closing ──────────────────────────────────────

@pytest.mark.asyncio
class TestQaModuleForLeads:
    def _service(self, project):
        from domain.services.qa_service import QAService
        service = QAService()
        service.repo = AsyncMock()
        service.repo.projects = "projects"
        service.repo.find_one = AsyncMock(return_value=project)
        return service

    async def test_lead_reaches_own_team_projects(self):
        assert (await self._service(PROJECT_A).accessible_project({**LEAD, "org_id": "O1"}, "PRJ-A"))["id"] == "PRJ-A"

    async def test_lead_no_longer_reaches_every_org_project(self):
        with pytest.raises(HTTPException) as error:
            await self._service(PROJECT_B).accessible_project({**LEAD, "org_id": "O1"}, "PRJ-B")
        assert error.value.status_code == 403

    async def test_pm_qa_access_follows_managed_projects(self):
        # CR-013: PMs reach QA data only for projects they manage.
        pm = make_user("PM-1", "PM", team_id=None, org_id="O1", project_ids=["PRJ-B"])
        assert (await self._service(PROJECT_B).accessible_project(pm, "PRJ-B"))["id"] == "PRJ-B"
        with pytest.raises(HTTPException):
            await self._service(PROJECT_B).accessible_project(make_user("PM-2", "PM", team_id=None, org_id="O1"), "PRJ-B")

    @pytest.mark.parametrize("target", ["CLOSED", "REOPENED"])
    async def test_lead_cannot_verify_or_close(self, target):
        from domain.models.qa import DefectUpdate
        service = self._service(PROJECT_A)
        service.accessible_project = AsyncMock(return_value=PROJECT_A)
        service.repo.find_one = AsyncMock(return_value={
            "id": "QAB-1", "project_id": "PRJ-A", "status": "READY_FOR_RETEST",
            "assignee_id": "DEV-A", "reporter_id": "QA-1", "history": []})
        with pytest.raises(HTTPException) as error:
            await service.update_defect(LEAD, "QAB-1", DefectUpdate(status=target))
        assert error.value.status_code == 403


# ── Sprints ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_lead_creates_sprints_in_team_projects_only():
    from api.routes import sprints
    from domain.models.sprint import SprintCreate
    check = inspect.signature(sprints.create_sprint).parameters["user"].default.dependency
    assert await check(user=LEAD) is LEAD
    fields = SprintCreate.model_fields
    payload = {"project_id": "PRJ-B", "name": "S1", "start_date": "2026-11-16", "end_date": "2026-11-27"}
    payload.update({name: "x" for name, field in fields.items() if field.is_required() and name not in payload})
    with patch("core.authorization._project_repo") as projects:
        projects.find_by_id = AsyncMock(return_value=PROJECT_B)
        with pytest.raises(HTTPException) as error:
            await sprints.create_sprint(SprintCreate(**payload), user=LEAD)
    assert error.value.status_code == 403
