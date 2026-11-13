"""
CR-003: DevOps access (access and rules only, no new backend structure).

DevOps own pipelines, deployments, repository links and CI in their projects;
pipeline/deployment data, repository links and risk weights are project-scoped.
"""

import inspect
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from core.permissions import OrganizationalRole, Permission, ROLE_PERMISSIONS, get_user_permissions


def make_user(employee_id="OPS-1", role="DEVOPS", project_ids=None, team_id=None, **extra):
    return {"employee_id": employee_id, "id": employee_id, "name": f"User {employee_id}", "role": role,
            "organizational_role": role, "project_ids": project_ids or [], "team_id": team_id, **extra}


OPS = make_user(project_ids=["PRJ-A"])
CEO = make_user("CEO-1", "CEO")
PROJECT_A = {"id": "PRJ-A", "team_id": "TEAM-A"}
PROJECT_B = {"id": "PRJ-B", "team_id": "TEAM-B"}


def project_lookup(*projects):
    by_id = {project["id"]: project for project in projects}
    return AsyncMock(side_effect=lambda project_id: by_id.get(project_id))


def holders(permission):
    return {role.value for role, granted in ROLE_PERMISSIONS.items() if permission in granted}


def dependency_of(endpoint):
    return inspect.signature(endpoint).parameters["user"].default.dependency


# ── Permission matrix ───────────────────────────────────────────────────────

class TestDevOpsPermissions:
    def test_devops_permission_set_matches_cr003(self):
        assert ROLE_PERMISSIONS[OrganizationalRole.DEVOPS] == {
            Permission.VIEW_OWN_DATA, Permission.VIEW_OWN_PERFORMANCE, Permission.VIEW_AI_EVALUATION,
            Permission.VIEW_PROJECT_DATA, Permission.TRANSITION_TASK, Permission.ANALYZE_CICD_LOGS,
            Permission.ANALYZE_PR_RISK, Permission.TRIGGER_CODE_ANALYSIS, Permission.VIEW_CODE_QUALITY,
            Permission.VIEW_DEFECTS, Permission.VIEW_INCIDENTS, Permission.CREATE_INCIDENT,
            Permission.SUBMIT_DEVOPS_FEEDBACK, Permission.VIEW_ROLE_FEEDBACK, Permission.REQUEST_TRANSFER,
            Permission.MANAGE_REPOSITORY_LINK, Permission.VIEW_PIPELINES, Permission.VIEW_DEPLOYMENTS,
            Permission.ANALYZE_DEPLOYMENT_RISK, Permission.MANAGE_RISK_CONFIG, Permission.CLEAR_RISK_CACHE,
            Permission.MANAGE_TEST_AUTOMATION, Permission.CREATE_BUG,
            Permission.TRIAGE_INCIDENT,  # CR-014
            Permission.USE_ENGINEERING_INTELLIGENCE,  # was the engineering role list
        }

    def test_devops_sees_only_own_performance(self):
        assert Permission.VIEW_PROJECT_PERFORMANCE not in get_user_permissions("DEVOPS")

    @pytest.mark.parametrize("permission, roles", [
        # Conversions keep today's roles (DevOps added where CR-003 says so).
        # CR-007 later removed the CEO from the hands-on delivery permissions.
        (Permission.MANAGE_REPOSITORY_LINK, {"PM", "LEAD", "DEVOPS"}),
        (Permission.VIEW_PIPELINES, {"DEVOPS", "QA", "LEAD"}),
        (Permission.VIEW_DEPLOYMENTS, {"DEVOPS", "LEAD"}),
        (Permission.ANALYZE_DEPLOYMENT_RISK, {"DEVOPS", "LEAD"}),
        (Permission.MANAGE_RISK_CONFIG, {"LEAD", "PM", "DEVOPS"}),
        (Permission.MANAGE_GLOBAL_RISK_CONFIG, {"CEO"}),
        (Permission.CLEAR_RISK_CACHE, {"DEVOPS"}),
        (Permission.MANAGE_TEST_AUTOMATION, {"QA", "PM", "LEAD", "DEVOPS"}),
        (Permission.CREATE_BUG, {"QA", "DEVELOPER", "LEAD", "DEVOPS"}),
    ])
    def test_permission_holders(self, permission, roles):
        assert holders(permission) == roles

    def test_no_devops_capability_route_checks_role_names(self):
        import re
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "api"
        offenders = []
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), 1):
                if re.search(r'require_roles\([^)]*"DEVOPS"', line) and "async def devops_dashboard" not in line:
                    offenders.append(f"{path.name}:{line_no}")
            if path.name == "risk_configurations.py":
                assert "allowed_roles" not in text and '["DEVOPS", "CEO"]' not in text
        assert offenders == []  # the DevOps dashboard is a persona view, checked separately

    def test_devops_dashboard_stays_a_persona_view(self):
        from pathlib import Path
        text = (Path(__file__).resolve().parents[1] / "api" / "roles" / "devops.py").read_text(encoding="utf-8")
        assert 'async def devops_dashboard(user: dict = Depends(require_roles("DEVOPS")))' in text


# ── Route guards ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestRouteGuards:
    async def _allowed(self, endpoint, role):
        try:
            await dependency_of(endpoint)(user=make_user("X", role))
            return True
        except HTTPException as error:
            assert error.status_code == 403
            return False

    async def test_pipelines_and_deployments(self):
        from api.roles import devops
        assert {r for r in ["DEVOPS", "QA", "LEAD", "DEVELOPER", "PM", "HR", "CEO"] if await self._allowed(devops.pipelines, r)} == {"DEVOPS", "QA", "LEAD"}
        assert {r for r in ["DEVOPS", "QA", "LEAD", "DEVELOPER", "PM", "HR", "CEO"] if await self._allowed(devops.deployments, r)} == {"DEVOPS", "LEAD"}

    async def test_deployment_risk_analysis(self):
        from api.routes import intelligence
        allowed = {r for r in ["DEVOPS", "LEAD", "QA", "DEVELOPER", "PM", "CEO"] if await self._allowed(intelligence.analyze_deployment, r)}
        assert allowed == {"DEVOPS", "LEAD"}

    async def test_repository_link_and_legacy_ci(self):
        from api.routes import github
        link = {r for r in ["CEO", "PM", "LEAD", "DEVOPS", "QA", "DEVELOPER", "HR"] if await self._allowed(github.save_project_github_config, r)}
        assert link == {"PM", "LEAD", "DEVOPS"}  # CR-007: not the CEO
        ci = {r for r in ["CEO", "PM", "LEAD", "DEVOPS", "QA", "DEVELOPER", "HR"] if await self._allowed(github.provision_qa_workflow, r)}
        assert ci == {"PM", "LEAD", "DEVOPS", "QA"}  # CR-007: not the CEO. HR removed; it never passed the old write check


# ── Project scope for pipelines and deployments ─────────────────────────────

@pytest.mark.anyio
async def test_pipelines_show_only_the_callers_projects(mock_db):
    from api.roles import devops
    await mock_db["github_project_configs"].insert_many([
        {"project_id": "PRJ-A", "repository_owner": "acme", "repository_name": "shop"},
        {"project_id": "PRJ-B", "repository_owner": "acme", "repository_name": "bank"},
    ])
    await mock_db["webhook_events"].insert_many([
        {"event_type": "workflow_run", "created_at": "2026-11-12T10:00:00",
         "payload": {"repository": {"full_name": "acme/shop"}, "workflow_run": {"conclusion": "success"}}},
        {"event_type": "workflow_run", "created_at": "2026-11-12T11:00:00",
         "payload": {"repository": {"full_name": "acme/bank"}, "workflow_run": {"conclusion": "failure"}}},
    ])
    with patch.object(devops, "col", side_effect=lambda name: mock_db[name]), \
            patch("api.roles.devops.get_accessible_project_ids", new=AsyncMock(return_value=["PRJ-A"])):
        mine = await devops.pipelines(user=OPS)
    assert [e["payload"]["repository"]["full_name"] for e in mine["pipelines"]] == ["acme/shop"]

    with patch.object(devops, "col", side_effect=lambda name: mock_db[name]):
        everything = await devops.pipelines(user=CEO)
    assert everything["total"] == 2


@pytest.mark.anyio
async def test_projects_without_a_linked_repository_show_no_pipelines(mock_db):
    from api.roles import devops
    await mock_db["webhook_events"].insert_one(
        {"event_type": "workflow_run", "payload": {"repository": {"full_name": "acme/shop"}}})
    with patch.object(devops, "col", side_effect=lambda name: mock_db[name]), \
            patch("api.roles.devops.get_accessible_project_ids", new=AsyncMock(return_value=["PRJ-A"])):
        assert (await devops.pipelines(user=OPS))["total"] == 0


# ── Repository link and legacy CI endpoint ──────────────────────────────────

@pytest.mark.asyncio
async def test_devops_link_check_is_project_access_not_write_access():
    from api.routes import github
    from domain.models.github_project_config import GitHubProjectConfig
    seen = {}

    async def fake_access(user, project_id, **kwargs):
        seen.update(project_id=project_id, **kwargs)
        raise RuntimeError("stop after the access check")

    config = GitHubProjectConfig(project_id="PRJ-A", repository_owner="acme", repository_name="shop",
                                 repository_url="https://github.com/acme/shop", default_branch="main")
    with patch.object(github, "verify_project_access", new=fake_access):
        with pytest.raises(RuntimeError):
            await github.save_project_github_config("PRJ-A", config, user=OPS)
    assert seen == {"project_id": "PRJ-A"}


@pytest.mark.asyncio
async def test_legacy_ci_endpoint_only_writes_to_the_linked_repository():
    from api.routes import github, qa_ci_provisioning
    links = AsyncMock()
    links.find_one = AsyncMock(return_value={"project_id": "PRJ-A", "repository_owner": "acme", "repository_name": "shop"})
    request = github.QAWorkflowProvisionRequest(owner="someone-else", repo="private", project_id="PRJ-A")
    with patch.object(github, "verify_project_access", new=AsyncMock()), \
            patch.object(qa_ci_provisioning, "col", side_effect=lambda name: links):
        with pytest.raises(HTTPException) as error:
            await github.provision_qa_workflow(request, user=OPS)
    assert error.value.status_code == 400 and "acme/shop" in error.value.detail


# ── Risk configurations ─────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestRiskConfigScope:
    async def _authorize(self, user, project_id):
        from api.routes.risk_configurations import _authorize_risk_change
        with patch("core.authorization._project_repo") as projects:
            projects.find_by_id = project_lookup(PROJECT_A, PROJECT_B)
            return await _authorize_risk_change(user, project_id)

    async def test_devops_changes_weights_of_their_project(self):
        assert await self._authorize(OPS, "PRJ-A") is None

    async def test_devops_cannot_change_another_projects_weights(self):
        with pytest.raises(HTTPException) as error:
            await self._authorize(OPS, "PRJ-B")
        assert error.value.status_code == 403

    @pytest.mark.parametrize("role", ["DEVOPS", "LEAD", "PM"])
    async def test_only_the_ceo_changes_global_defaults(self, role):
        with pytest.raises(HTTPException) as error:
            await self._authorize(make_user("X", role), None)
        assert error.value.status_code == 403
        assert await self._authorize(CEO, None) is None

    async def test_people_without_the_permission_are_refused(self):
        with pytest.raises(HTTPException) as error:
            await self._authorize(make_user("Q", "QA", project_ids=["PRJ-A"]), "PRJ-A")
        assert error.value.status_code == 403


@pytest.mark.asyncio
# CR-007: the CEO no longer clears the risk cache (DevOps only).
@pytest.mark.parametrize("role, allowed", [("DEVOPS", True), ("CEO", False), ("LEAD", False), ("PM", False)])
async def test_clearing_the_risk_cache(role, allowed):
    from api.routes import risk_configurations
    service = type("S", (), {"clear_cache": lambda self, project_id=None: None})()
    with patch.object(risk_configurations, "get_risk_config_service", return_value=service):
        if allowed:
            await risk_configurations.clear_cache(project_id=None, current_user=make_user("X", role))
        else:
            with pytest.raises(HTTPException) as error:
                await risk_configurations.clear_cache(project_id=None, current_user=make_user("X", role))
            assert error.value.status_code == 403


# ── Stories and defects ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_devops_moves_only_their_own_stories():
    from api.routes.stories import update_story_status
    from domain.models.story import Story
    from domain.services.story_service import StoryService
    story = Story(id="STY-1", title="t", sprint_id="S", project_id="PRJ-A", assignee_id="DEV-1", status="todo")
    with patch("core.authorization._story_repo") as story_repo, \
            patch("core.authorization._project_repo") as project_repo, \
            patch.object(StoryService, "update_story_status", new=AsyncMock(return_value=True)):
        story_repo.find_by_id = AsyncMock(return_value=story.model_dump())
        project_repo.find_by_id = project_lookup(PROJECT_A)
        with pytest.raises(HTTPException) as error:
            await update_story_status("STY-1", status="in_progress", user=OPS)
        assert error.value.status_code == 403
        story_repo.find_by_id = AsyncMock(return_value=story.model_copy(update={"assignee_id": "OPS-1"}).model_dump())
        await update_story_status("STY-1", status="in_progress", user=OPS)


@pytest.mark.asyncio
async def test_devops_reports_and_sees_their_own_defects():
    from domain.models.qa import DefectCreate
    from domain.services.qa_service import QAService
    service = QAService()
    service.accessible_project = AsyncMock(return_value=PROJECT_A)
    service._validate_defect_links = AsyncMock(return_value=(None, None, None, None))
    service.repo = AsyncMock()
    service.repo.insert = AsyncMock(side_effect=lambda _collection, document: document)
    defect = await service.create_defect(OPS, DefectCreate(project_id="PRJ-A", title="Deploy step flaky", description="d"))
    assert defect["reporter_id"] == "OPS-1"
    service.repo.find_one = AsyncMock(return_value={**defect, "assignee_id": None})
    assert (await service.get_defect(OPS, defect["id"]))["id"] == defect["id"]
    service.repo.list_documents = AsyncMock(return_value=[])
    await service.list_defects(OPS, "PRJ-A")
    assert service.repo.list_documents.await_args.args[1]["$or"] == [{"assignee_id": "OPS-1"}, {"reporter_id": "OPS-1"}]
