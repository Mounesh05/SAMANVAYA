"""
CR-002: QA access.

QA owns test management, the defect lifecycle and sign-off (pass/fail work in
Review) inside assigned projects, and sees only their own performance.
Frontend counterparts: frontend/src/tests/qaAccess.test.jsx.
"""

import inspect
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from core.permissions import OrganizationalRole, Permission, ROLE_PERMISSIONS, get_user_permissions
from domain.models.qa import DefectUpdate, TestSuiteCreate
from domain.models.story import Story
from domain.services.qa_service import QAService
from domain.services.workflow_service import WorkflowService


def make_user(employee_id="QA-1", role="QA", project_ids=None, team_id=None, **extra):
    return {"employee_id": employee_id, "id": employee_id, "name": f"User {employee_id}", "role": role,
            "organizational_role": role, "project_ids": project_ids or [], "team_id": team_id, **extra}


QA = make_user(project_ids=["PRJ-A"])
DEV = make_user("DEV-1", "DEVELOPER", project_ids=["PRJ-A"])
PROJECT_A = {"id": "PRJ-A", "team_id": "TEAM-A"}
PROJECT_B = {"id": "PRJ-B", "team_id": "TEAM-B"}


def project_lookup(*projects):
    by_id = {project["id"]: project for project in projects}
    return AsyncMock(side_effect=lambda project_id: by_id.get(project_id))


def holders(permission):
    return {role.value for role, granted in ROLE_PERMISSIONS.items() if permission in granted}


# ── Permission matrix ───────────────────────────────────────────────────────

class TestQaPermissions:
    def test_qa_permission_set_matches_cr002(self):
        assert ROLE_PERMISSIONS[OrganizationalRole.QA] == {
            Permission.VIEW_OWN_DATA, Permission.VIEW_OWN_PERFORMANCE, Permission.VIEW_AI_EVALUATION,
            Permission.VIEW_PROJECT_DATA, Permission.CREATE_BUG, Permission.TRANSITION_TASK,
            Permission.ANALYZE_CICD_LOGS, Permission.ANALYZE_PR_RISK, Permission.TRIGGER_CODE_ANALYSIS,
            Permission.SUBMIT_QA_FEEDBACK, Permission.VIEW_ROLE_FEEDBACK, Permission.REQUEST_TRANSFER,
            Permission.SIGN_OFF_WORK, Permission.MANAGE_TEST_CASES, Permission.VERIFY_DEFECTS,
            Permission.VIEW_DEFECTS, Permission.VIEW_CODE_QUALITY, Permission.MANAGE_TEST_AUTOMATION,
            Permission.CREATE_INCIDENT,
            Permission.VIEW_PIPELINES,  # CR-003 conversion of the Pipelines role list
        }

    def test_qa_sees_only_own_performance(self):
        assert Permission.VIEW_PROJECT_PERFORMANCE not in get_user_permissions("QA")

    @pytest.mark.parametrize("permission, roles", [
        (Permission.SIGN_OFF_WORK, {"QA"}),
        (Permission.MANAGE_TEST_CASES, {"QA"}),
        (Permission.VERIFY_DEFECTS, {"QA"}),
        # Conversions: exactly the roles that had this access before CR-002.
        (Permission.VIEW_DEFECTS, {"QA", "DEVELOPER", "DEVOPS", "LEAD", "PM", "CEO"}),
        (Permission.VIEW_CODE_QUALITY, {"QA", "DEVELOPER", "LEAD", "DEVOPS"}),
        (Permission.MANAGE_TEST_AUTOMATION, {"QA", "PM", "LEAD", "DEVOPS"}),  # DevOps added in CR-003; CEO removed in CR-007
        (Permission.CREATE_INCIDENT, {"QA", "DEVELOPER", "DEVOPS", "CEO"}),
    ])
    def test_permission_holders(self, permission, roles):
        assert holders(permission) == roles

    def test_qa_service_no_longer_checks_the_qa_role_name(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / "domain" / "services" / "qa_service.py").read_text(encoding="utf-8")
        assert '_role_for(user, {"QA"})' not in source
        assert 'elif role == "QA"' not in source


# ── Test management and defects ─────────────────────────────────────────────

@pytest.mark.asyncio
class TestTestManagement:
    def _service(self):
        service = QAService()
        service.accessible_project = AsyncMock(return_value=PROJECT_A)
        service._linked_document = AsyncMock(return_value=None)
        service.repo = AsyncMock()
        service.repo.insert = AsyncMock(side_effect=lambda _collection, document: document)
        return service

    async def test_qa_creates_a_test_suite(self):
        suite = await self._service().create_suite(QA, TestSuiteCreate(project_id="PRJ-A", name="Checkout"))
        assert suite["name"] == "Checkout"

    @pytest.mark.parametrize("role", ["DEVELOPER", "LEAD", "PM", "DEVOPS"])
    async def test_other_roles_cannot_manage_test_cases(self, role):
        with pytest.raises(HTTPException) as error:
            await self._service().create_suite(make_user("X", role), TestSuiteCreate(project_id="PRJ-A", name="x"))
        assert error.value.status_code == 403

    async def test_qa_reopens_a_failed_retest(self):
        service = self._service()
        service.repo.find_one = AsyncMock(return_value={
            "id": "QAB-1", "project_id": "PRJ-A", "status": "READY_FOR_RETEST",
            "assignee_id": "DEV-1", "reporter_id": "QA-1", "history": []})
        service.repo.update = AsyncMock(return_value=True)
        service._validate_assignee = AsyncMock()
        try:
            await service.update_defect(QA, "QAB-1", DefectUpdate(status="REOPENED"))
        except HTTPException as error:  # only an authorization refusal would be a failure here
            assert error.status_code not in (400, 403), error.detail

    async def test_people_without_view_defects_cannot_list_them(self):
        with pytest.raises(HTTPException) as error:
            await self._service().list_defects(make_user("HR-1", "HR"), "PRJ-A")
        assert error.value.status_code == 403


# ── Code analysis and CI automation ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_qa_can_start_code_analysis_in_an_assigned_project():
    """Regression: analysis demanded project write access, which no holder of
    TRIGGER_CODE_ANALYSIS has, so nobody could start one."""
    from api.routes import code_quality
    seen = {}

    async def fake_access(user, project_id, **kwargs):
        seen.update(project_id=project_id, **kwargs)
        raise RuntimeError("stop after the access check")

    with patch.object(code_quality, "verify_project_access", new=fake_access):
        body = code_quality.AnalyzeRequest(repository_id="PRJ-A", changed_files=["app.py"])
        with pytest.raises(RuntimeError):
            await code_quality.start_analysis(body, background_tasks=None, user=QA)
    assert seen == {"project_id": "PRJ-A"}  # read access, no require_write


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["enable_ci_integration", "disable_ci_integration"])
async def test_ci_automation_needs_manage_test_automation(route):
    from api.routes import qa_ci_provisioning
    check = inspect.signature(getattr(qa_ci_provisioning, route)).parameters["user"].default.dependency
    assert await check(user=QA) is QA
    with pytest.raises(HTTPException) as error:
        await check(user=make_user("DEV-9", "DEVELOPER"))
    assert error.value.status_code == 403


# ── Sign-off ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestTaskSignOff:
    async def _check(self, user, status, target):
        from core.authorization import verify_task_status_update_access
        with patch("core.authorization._task_repo") as task_repo, \
                patch("core.authorization._project_repo") as project_repo:
            task_repo.find_by_id = AsyncMock(return_value={
                "id": "T-1", "project_id": "PRJ-A", "assignee_id": "DEV-1", "status": status})
            project_repo.find_by_id = project_lookup(PROJECT_A, PROJECT_B)
            return await verify_task_status_update_access(user, "T-1", target)

    @pytest.mark.parametrize("target", ["done", "in_progress"])
    async def test_qa_passes_or_fails_work_in_review(self, target):
        assert await self._check(QA, "review", target) == "PRJ-A"

    @pytest.mark.parametrize("status, target", [("review", "todo"), ("in_progress", "done"), ("todo", "in_progress")])
    async def test_qa_cannot_make_other_moves(self, status, target):
        with pytest.raises(HTTPException) as error:
            await self._check(QA, status, target)
        assert error.value.status_code == 403

    async def test_developer_still_cannot_sign_off_others_work(self):
        with pytest.raises(HTTPException) as error:
            await self._check(make_user("DEV-2", "DEVELOPER", project_ids=["PRJ-A"]), "review", "done")
        assert error.value.status_code == 403

    async def test_sign_off_is_limited_to_assigned_projects(self):
        with pytest.raises(HTTPException) as error:
            await self._check(make_user("QA-9", "QA", project_ids=["PRJ-B"]), "review", "done")
        assert error.value.status_code == 403


@pytest.mark.asyncio
class TestStorySignOff:
    async def _set(self, user, status, target, assignee="DEV-1"):
        from api.routes.stories import update_story_status
        from domain.services.story_service import StoryService
        story = Story(id="STY-1", title="t", sprint_id="S", project_id="PRJ-A", assignee_id=assignee, status=status)
        with patch("core.authorization._story_repo") as story_repo, \
                patch("core.authorization._project_repo") as project_repo, \
                patch.object(StoryService, "update_story_status", new=AsyncMock(return_value=True)) as updated:
            story_repo.find_by_id = AsyncMock(return_value=story.model_dump())
            project_repo.find_by_id = project_lookup(PROJECT_A)
            await update_story_status("STY-1", status=target, user=user)
            return updated

    async def test_qa_passes_a_story_in_review(self):
        (await self._set(QA, "review", "done")).assert_awaited_once_with("STY-1", "done")

    async def test_qa_can_no_longer_move_stories_anywhere(self):
        with pytest.raises(HTTPException) as error:
            await self._set(QA, "todo", "in_progress")
        assert error.value.status_code == 403

    async def test_board_drag_follows_the_same_rule(self):
        from api.routes.boards import MoveItemRequest, move_item
        story = Story(id="STY-1", title="t", sprint_id="S", project_id="PRJ-A", assignee_id="DEV-1", status="todo")
        with patch("core.authorization._story_repo") as story_repo, \
                patch("core.authorization._project_repo") as project_repo:
            story_repo.find_by_id = AsyncMock(return_value=story.model_dump())
            project_repo.find_by_id = project_lookup(PROJECT_A)
            with pytest.raises(HTTPException) as error:
                await move_item(MoveItemRequest(item_id="STY-1", item_type="story", target_status="done"), user=QA)
        assert error.value.status_code == 403

    async def test_board_drag_lets_qa_pass_a_task_in_review(self):
        from api.routes.boards import MoveItemRequest, move_item
        with patch("core.authorization._task_repo") as task_repo, \
                patch("core.authorization._project_repo") as project_repo, \
                patch.object(WorkflowService, "transition_task", new=AsyncMock(return_value={"id": "T-1"})):
            task_repo.find_by_id = AsyncMock(return_value={"id": "T-1", "project_id": "PRJ-A", "assignee_id": "DEV-1", "status": "review"})
            project_repo.find_by_id = project_lookup(PROJECT_A)
            result = await move_item(MoveItemRequest(item_id="T-1", item_type="task", target_status="done"), user=QA)
        assert result["new_status"] == "done"


# ── Project pull requests ───────────────────────────────────────────────────

@pytest.mark.anyio
async def test_qa_lists_pull_requests_of_assigned_projects_only(mock_db):
    from api.routes import github
    from repositories import pr_repository
    await mock_db["pull_requests"].insert_many([
        {"id": "PR-1", "project_id": "PRJ-A", "title": "a", "updated_at": "2026-11-10"},
        {"id": "PR-2", "project_id": "PRJ-B", "title": "b", "updated_at": "2026-11-11"},
    ])
    with patch.object(pr_repository, "col", side_effect=lambda name: mock_db[name]), \
            patch("core.authorization._project_repo") as projects:
        projects.find_by_id = project_lookup(PROJECT_A, PROJECT_B)
        result = await github.list_project_pull_requests("PRJ-A", user=QA)
        assert [pr["id"] for pr in result["pull_requests"]] == ["PR-1"]
        with pytest.raises(HTTPException) as error:
            await github.list_project_pull_requests("PRJ-B", user=QA)
        assert error.value.status_code == 403


# ── Performance and incidents ───────────────────────────────────────────────

from test_performance_access import records, service as performance_service  # noqa: E402,F401  (fixture reuse)


@pytest.mark.anyio
async def test_qa_cannot_read_a_developers_performance(records):  # noqa: F811
    await records.users.insert_one({"employee_id": "Q1", "role": "QA", "org_id": "O1",
                                    "is_active": True, "project_ids": ["AUDIT-PROJECT"]})
    with pytest.raises(HTTPException) as error:
        await performance_service().detail("AUDIT-DEV", {"employee_id": "Q1"})
    assert error.value.status_code == 403


@pytest.mark.anyio
async def test_qa_reports_an_incident(mock_db):
    from api.routes import incidents
    from domain.models.incident import IncidentCreate
    from repositories import incident_repository
    with patch.object(incident_repository, "col", side_effect=lambda name: mock_db[name]), \
            patch("core.authorization._project_repo") as projects:
        projects.find_by_id = project_lookup(PROJECT_A)
        created = await incidents.report_incident(
            IncidentCreate(project_id="PRJ-A", title="Test env down", description="502s"), user=QA)
    assert created.reporter_id == "QA-1"


# ── Restored CI provisioning endpoints ──────────────────────────────────────

def test_ci_provisioning_routes_are_registered():
    """Regression: the router's model file was missing and the router was never
    registered, so the QA dashboard's Enable CI calls returned 404."""
    from pathlib import Path
    from api.routes.qa_ci_provisioning import router  # import fails if the model is missing
    paths = {(tuple(sorted(route.methods)), route.path) for route in router.routes}
    assert (("POST",), "/projects/{project_id}/enable-ci") in paths
    assert (("GET",), "/projects/{project_id}/ci-config") in paths
    assert (("DELETE",), "/projects/{project_id}/ci-config") in paths
    main_source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
    assert 'app.include_router(qa_ci_provisioning.router, prefix="/api/qa"' in main_source


@pytest.mark.parametrize("repository, branch, valid", [
    ("acme/shop", "main", True),
    ("acme/shop", "release/2026.11", True),
    ("acme", "main", False),
    ("acme/shop/extra", "main", False),
    ("acme/shop", "-rf", False),
    ("acme/shop", "a..b", False),
    ("acme/shop", "has space", False),
])
def test_ci_request_validation(repository, branch, valid):
    from pydantic import ValidationError
    from domain.models.qa_ci_config import CIProvisionRequest
    if valid:
        assert CIProvisionRequest(repository=repository, branch=branch).repository == repository
    else:
        with pytest.raises(ValidationError):
            CIProvisionRequest(repository=repository, branch=branch)


# ── Enable CI: linked repository only, clear errors ─────────────────────────

@pytest.mark.asyncio
class TestEnableCi:
    LINK = {"project_id": "PRJ-A", "repository_owner": "acme", "repository_name": "shop"}

    async def _enable(self, request, *, link=LINK, token="ghp_test", provision=None):
        from api.routes import qa_ci_provisioning as ci
        from domain.models.qa_ci_config import CIProvisionRequest
        links = AsyncMock()
        links.find_one = AsyncMock(return_value=link)
        service = type("Provision", (), {"provision": provision or AsyncMock(return_value={"workflow_url": "https://github.com/acme/shop/actions"})})()
        with patch.object(ci.qa_service, "accessible_project", new=AsyncMock(return_value={"id": "PRJ-A"})), \
                patch.object(ci, "col", side_effect=lambda name: links), \
                patch.object(ci.settings, "GITHUB_TOKEN", token), \
                patch.object(ci, "QAWorkflowProvisioningService", return_value=service), \
                patch.object(ci.qa_repo, "save_ci_config", new=AsyncMock()) as saved:
            result = await ci.enable_ci_integration("PRJ-A", CIProvisionRequest(**request), user=QA)
            return result, service.provision, saved

    async def test_uses_the_projects_linked_repository(self):
        result, provision, saved = await self._enable({"branch": "main"})
        assert provision.await_args.kwargs == {"owner": "acme", "repo": "shop", "project_id": "PRJ-A", "branch": "main"}
        assert result["repository"] == "acme/shop"
        assert saved.await_args.args[0]["repository"] == "acme/shop"

    async def test_refuses_a_repository_other_than_the_linked_one(self):
        with pytest.raises(HTTPException) as error:
            await self._enable({"repository": "someone-else/private-repo", "branch": "main"})
        assert error.value.status_code == 400 and "acme/shop" in error.value.detail

    async def test_needs_a_linked_repository(self):
        with pytest.raises(HTTPException) as error:
            await self._enable({"branch": "main"}, link=None)
        assert error.value.status_code == 400 and "GitHub Sync" in error.value.detail

    async def test_needs_a_github_token(self):
        with pytest.raises(HTTPException) as error:
            await self._enable({"branch": "main"}, token="")
        assert error.value.status_code == 400 and "GITHUB_TOKEN" in error.value.detail

    async def test_github_refusal_is_explained_without_echoing_github(self):
        import httpx
        response = httpx.Response(403, request=httpx.Request("PUT", "https://api.github.com/x"), text="secret-ish details")
        failing = AsyncMock(side_effect=httpx.HTTPStatusError("forbidden", request=response.request, response=response))
        with pytest.raises(HTTPException) as error:
            await self._enable({"branch": "main"}, provision=failing)
        assert error.value.status_code == 502
        assert "GITHUB_TOKEN" in error.value.detail and "secret-ish" not in error.value.detail

    async def test_unexpected_failures_do_not_leak_internals(self):
        failing = AsyncMock(side_effect=RuntimeError("connection string mongodb://user:pass@host"))
        with pytest.raises(HTTPException) as error:
            await self._enable({"branch": "main"}, provision=failing)
        assert error.value.status_code == 502 and "mongodb" not in error.value.detail
