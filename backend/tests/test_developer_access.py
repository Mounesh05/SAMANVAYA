"""
CR-001: shared permission source and Developer access.

Developers work only inside their assigned projects: they create sub-tasks and
draft stories for themselves, report defects, and request their own transfer.
Lead/PM accept drafts. Frontend counterparts: frontend/src/tests/developerAccess.test.jsx.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from core.permissions import ADMIN_PERMISSIONS, OrganizationalRole, Permission, ROLE_PERMISSIONS, get_user_permissions
from domain.models.qa import DefectCreate
from domain.models.story import Story, StoryCreate
from domain.models.task import TaskCreate
from domain.models.transfer import TransferCreate
from domain.services.auth_service import AuthService
from domain.services.qa_service import QAService
from domain.services.sprint_service import SprintService
from domain.services.story_service import StoryService
from domain.services.task_service import TaskService


def make_user(employee_id="DEV-1", role="DEVELOPER", project_ids=None, team_id=None, **extra):
    return {"employee_id": employee_id, "id": employee_id, "name": f"User {employee_id}", "role": role,
            "organizational_role": role, "project_ids": project_ids or [], "team_id": team_id, **extra}


DEV = make_user(project_ids=["PRJ-A"], team_id="TEAM-A")
LEAD = make_user("LEAD-1", "LEAD", team_id="TEAM-A")
PROJECT_A = {"id": "PRJ-A", "team_id": "TEAM-A"}
PROJECT_B = {"id": "PRJ-B", "team_id": "TEAM-B"}


def project_lookup(*projects):
    by_id = {project["id"]: project for project in projects}
    return AsyncMock(side_effect=lambda project_id: by_id.get(project_id))


# ── Permission matrix ───────────────────────────────────────────────────────

class TestPermissionMatrix:
    def test_developer_permissions_match_cr001(self):
        assert ROLE_PERMISSIONS[OrganizationalRole.DEVELOPER] == {
            Permission.VIEW_OWN_DATA, Permission.VIEW_OWN_PERFORMANCE, Permission.VIEW_AI_EVALUATION,
            Permission.TRANSITION_TASK, Permission.CREATE_TASK, Permission.CREATE_BUG,
            Permission.CREATE_STORY, Permission.SYNC_PR, Permission.REQUEST_TRANSFER,
            Permission.CREATE_INCIDENT,  # report only
            Permission.ANALYZE_CICD_LOGS, Permission.ANALYZE_PR_RISK,  # were role-name checks
            Permission.VIEW_DEFECTS, Permission.VIEW_CODE_QUALITY,     # CR-002 page conversions
        }

    def test_developer_cannot_manage_backlog_sprints_or_others(self):
        permissions = ROLE_PERMISSIONS[OrganizationalRole.DEVELOPER]
        for denied in (Permission.ACCEPT_STORY, Permission.MOVE_TASK, Permission.CREATE_SPRINT,
                       Permission.VIEW_TEAM_PERFORMANCE, Permission.VIEW_ORGANIZATION_DATA,
                       Permission.MANAGE_INTEGRATIONS, Permission.VIEW_INCIDENTS):
            assert denied not in permissions, denied

    @pytest.mark.parametrize("role", ["LEAD", "PM", "CEO"])
    def test_backlog_owners_accept_drafts(self, role):
        assert Permission.ACCEPT_STORY in get_user_permissions(role)

    @pytest.mark.parametrize("role", ["QA", "DEVOPS", "HR"])
    def test_other_roles_do_not_accept_drafts(self, role):
        assert Permission.ACCEPT_STORY not in get_user_permissions(role)


class TestProfilePermissions:
    def test_profile_carries_backend_permission_list(self):
        out = AuthService._user_out({"employee_id": "DEV-1", "role": "DEVELOPER", "name": "Dana", "email": "d@example.com"})
        assert out.permissions == sorted(p.value for p in ROLE_PERMISSIONS[OrganizationalRole.DEVELOPER])
        assert out.is_admin is False

    def test_admin_rights_are_in_the_list_not_a_frontend_shortcut(self):
        out = AuthService._user_out({"employee_id": "CEO-1", "role": "CEO", "is_admin": True})
        assert out.is_admin is True
        assert {p.value for p in ADMIN_PERMISSIONS} <= set(out.permissions)

    def test_hr_designation_shapes_the_list(self):
        out = AuthService._user_out({"employee_id": "HR-2", "role": "HR", "designation": "RECRUITER"})
        assert "MANAGE_CANDIDATES" in out.permissions
        assert "VIEW_AUDIT_LOGS" not in out.permissions


# ── Tasks ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestDeveloperTasks:
    async def _create(self, user, task):
        from api.routes.tasks import create_task
        with patch("core.authorization._project_repo") as repo, \
                patch.object(TaskService, "create_task", new=AsyncMock(return_value={"id": "T-1"})) as created:
            repo.find_by_id = project_lookup(PROJECT_A, PROJECT_B)
            result = await create_task(task, user=user)
            return result, created

    async def test_developer_creates_own_task_in_assigned_project(self):
        result, created = await self._create(DEV, TaskCreate(title="Split API", project_id="PRJ-A", assignee_id="DEV-1"))
        assert result == {"id": "T-1"}
        created.assert_awaited_once()

    async def test_developer_cannot_assign_a_task_to_someone_else(self):
        with pytest.raises(HTTPException) as error:
            await self._create(DEV, TaskCreate(title="x", project_id="PRJ-A", assignee_id="DEV-2"))
        assert error.value.status_code == 403

    async def test_developer_cannot_create_in_an_unassigned_project(self):
        with pytest.raises(HTTPException) as error:
            await self._create(DEV, TaskCreate(title="x", project_id="PRJ-B", assignee_id="DEV-1"))
        assert error.value.status_code == 403

    async def test_lead_still_assigns_work_in_team_project(self):
        result, _ = await self._create(LEAD, TaskCreate(title="x", project_id="PRJ-A", assignee_id="DEV-2"))
        assert result == {"id": "T-1"}


# ── Stories ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestDraftStories:
    STORY = StoryCreate(title="Export", sprint_id="SPR-1", project_id="PRJ-A", assignee_id="DEV-1")

    async def test_developer_story_is_a_draft_proposed_by_them(self):
        from api.routes.stories import create_story
        with patch("core.authorization._project_repo") as repo, \
                patch.object(StoryService, "create_story", new=AsyncMock(return_value="ok")) as created:
            repo.find_by_id = project_lookup(PROJECT_A)
            await create_story(self.STORY, user=DEV)
        assert created.await_args.kwargs == {"draft": True, "proposed_by": "DEV-1"}

    async def test_lead_story_goes_straight_to_backlog(self):
        from api.routes.stories import create_story
        story = self.STORY.model_copy(update={"assignee_id": "DEV-2"})
        with patch("core.authorization._project_repo") as repo, \
                patch.object(StoryService, "create_story", new=AsyncMock(return_value="ok")) as created:
            repo.find_by_id = project_lookup(PROJECT_A)
            await create_story(story, user=LEAD)
        assert created.await_args.kwargs == {"draft": False, "proposed_by": None}

    async def test_service_stores_draft_status(self):
        service = StoryService()
        service.story_repo = AsyncMock()
        story = await service.create_story(self.STORY, draft=True, proposed_by="DEV-1")
        assert story.status == "draft" and story.proposed_by == "DEV-1"

    async def _set_status(self, user, story, status):
        from api.routes.stories import update_story_status
        with patch("core.authorization._story_repo") as story_repo, \
                patch("core.authorization._project_repo") as project_repo, \
                patch.object(StoryService, "get_story", new=AsyncMock(return_value=story)), \
                patch.object(StoryService, "update_story_status", new=AsyncMock(return_value=True)) as updated:
            story_repo.find_by_id = AsyncMock(return_value=story.model_dump())
            project_repo.find_by_id = project_lookup(PROJECT_A)
            await update_story_status(story.id, status=status, user=user)
            return updated

    def _story(self, status, assignee="DEV-1"):
        return Story(id="STY-1", title="t", sprint_id="SPR-1", project_id="PRJ-A", assignee_id=assignee, status=status)

    async def test_developer_cannot_accept_own_draft(self):
        with pytest.raises(HTTPException) as error:
            await self._set_status(DEV, self._story("draft"), "todo")
        assert error.value.status_code == 403

    async def test_lead_accepts_draft_into_todo(self):
        updated = await self._set_status(LEAD, self._story("draft"), "todo")
        updated.assert_awaited_once_with("STY-1", "todo")

    async def test_draft_must_be_accepted_before_it_moves(self):
        with pytest.raises(HTTPException) as error:
            await self._set_status(LEAD, self._story("draft"), "in_progress")
        assert error.value.status_code == 409

    async def test_developer_moves_only_own_stories(self):
        with pytest.raises(HTTPException) as error:
            await self._set_status(DEV, self._story("todo", assignee="DEV-2"), "in_progress")
        assert error.value.status_code == 403
        updated = await self._set_status(DEV, self._story("todo"), "in_progress")
        updated.assert_awaited_once_with("STY-1", "in_progress")

    async def test_sprint_health_ignores_drafts(self):
        service = SprintService()
        service.get_sprint = AsyncMock(return_value=type("S", (), {"name": "Sprint 1", "status": "active"})())
        service.story_repo = AsyncMock()
        service.story_repo.find_by_sprint = AsyncMock(return_value=[
            {"id": "1", "status": "done", "points": 3}, {"id": "2", "status": "draft", "points": 8}])
        service.task_repo = AsyncMock()
        service.task_repo.find_by_sprint = AsyncMock(return_value=[])
        health = await service.calculate_sprint_health("SPR-1")
        assert (health["total_stories"], health["total_points"], health["completion_pct"]) == (1, 3, 100.0)


# ── Transfers ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestOwnTransferOnly:
    def _transfer(self, employee_id):
        return TransferCreate(employee_id=employee_id, requested_team_id="TEAM-B", reason="career_growth", justification="Growth path")

    async def test_developer_cannot_open_a_request_for_a_colleague(self):
        from api.routes.transfers import create_transfer
        with pytest.raises(HTTPException) as error:
            await create_transfer(self._transfer("DEV-2"), user=DEV)
        assert error.value.status_code == 403

    @pytest.mark.parametrize("user", [DEV, LEAD, make_user("HR-1", "HR")])
    async def test_own_request_and_managers_pass_the_check(self, user):
        from api.routes.transfers import create_transfer
        target = user["employee_id"] if user is DEV else "DEV-2"
        sentinel = type("T", (), {"id": "TRF-1", "workflow_type": "employee_initiated"})()
        with patch("api.routes.transfers.TransferService") as service, \
                patch("api.routes.transfers.log_audit", new=AsyncMock()):
            service.return_value.create_transfer = AsyncMock(return_value=sentinel)
            assert await create_transfer(self._transfer(target), user=user) is sentinel


def test_every_audit_action_used_by_the_api_exists():
    """Regression: transfers.py logged AuditAction.TRANSFER_* values that did not
    exist, so every transfer action failed with 500 after writing to the DB."""
    import re
    from pathlib import Path
    from core.audit import AuditAction
    api = Path(__file__).resolve().parents[1] / "api"
    used = {name for path in api.rglob("*.py")
            for name in re.findall(r"AuditAction\.([A-Z_]+)", path.read_text(encoding="utf-8"))}
    missing = sorted(name for name in used if not hasattr(AuditAction, name))
    assert missing == [], f"Undefined audit actions: {missing}"


# ── Defects ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestDeveloperDefects:
    def _service(self):
        service = QAService()
        service.accessible_project = AsyncMock(return_value=PROJECT_A)
        service._validate_defect_links = AsyncMock(return_value=(None, None, None, None))
        service.repo = AsyncMock()
        service.repo.insert = AsyncMock(side_effect=lambda _collection, document: document)
        return service

    async def test_developer_reports_a_defect_that_starts_open(self):
        defect = await self._service().create_defect(DEV, DefectCreate(project_id="PRJ-A", title="500 on save", description="Fails"))
        assert defect["status"] == "OPEN" and defect["reporter_id"] == "DEV-1" and defect["assignee_id"] is None

    async def test_roles_without_create_bug_cannot_report(self):
        # CR-003 gave DevOps CREATE_BUG; PM still lacks it.
        with pytest.raises(HTTPException) as error:
            await self._service().create_defect(make_user("PM-1", "PM"), DefectCreate(project_id="PRJ-A", title="t", description="d"))
        assert error.value.status_code == 403

    async def test_developer_sees_defects_they_reported(self):
        service = self._service()
        service.repo.find_one = AsyncMock(return_value={"id": "QAB-1", "project_id": "PRJ-A", "reporter_id": "DEV-1", "assignee_id": None})
        assert (await service.get_defect(DEV, "QAB-1"))["id"] == "QAB-1"
        service.repo.find_one = AsyncMock(return_value={"id": "QAB-2", "project_id": "PRJ-A", "reporter_id": "QA-1", "assignee_id": None})
        with pytest.raises(HTTPException):
            await service.get_defect(DEV, "QAB-2")

    async def test_developer_list_includes_reported_and_assigned(self):
        service = self._service()
        service.repo.list_documents = AsyncMock(return_value=[])
        await service.list_defects(DEV, "PRJ-A")
        query = service.repo.list_documents.await_args.args[1]
        assert query["$or"] == [{"assignee_id": "DEV-1"}, {"reporter_id": "DEV-1"}]


# ── Team directory ──────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_team_directory_exposes_only_id_and_name(mock_db):
    from api.routes import teams as teams_route
    await mock_db["teams"].insert_many([
        {"team_id": "TEAM-B", "name": "Payments", "team_lead_id": "LEAD-9", "project_ids": ["PRJ-B"]},
        {"team_id": "TEAM-Z", "name": "Retired", "is_active": False},
    ])
    with patch.object(teams_route, "col", side_effect=lambda name: mock_db[name]):
        result = await teams_route.team_directory(user=DEV)
    assert [entry.model_dump() for entry in result] == [{"team_id": "TEAM-B", "name": "Payments"}]


# ── Route checks converted from role names to permissions ───────────────────

class TestConvertedRouteGuards:
    """require_roles(...) -> require_permission(...) must keep the same roles."""

    @pytest.mark.parametrize("permission, roles", [
        (Permission.TRANSITION_TASK, {"DEVELOPER", "LEAD", "PM", "QA", "DEVOPS"}),  # board move
        (Permission.ANALYZE_CICD_LOGS, {"DEVELOPER", "LEAD", "QA", "DEVOPS"}),      # CI/CD log analysis
        (Permission.ANALYZE_PR_RISK, {"DEVELOPER", "LEAD", "QA", "DEVOPS"}),        # PR risk analysis
        (Permission.VIEW_INCIDENTS, {"DEVOPS", "LEAD", "CEO"}),                     # former Incidents page roles
        (Permission.CREATE_INCIDENT, {"DEVELOPER", "DEVOPS", "CEO", "QA"}),  # QA added in CR-002
    ])
    def test_permission_holders(self, permission, roles):
        holders = {role.value for role, granted in ROLE_PERMISSIONS.items() if permission in granted}
        assert holders == roles

    def test_no_developer_capability_route_checks_role_names(self):
        import re
        from pathlib import Path
        api = Path(__file__).resolve().parents[1] / "api"
        offenders = []
        for path in api.rglob("*.py"):
            if path.parent.name == "roles":
                continue  # persona dashboards are deliberately role-scoped
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r'require_roles\([^)]*"DEVELOPER"', line):
                    offenders.append(f"{path.name}:{line_no}")
        assert offenders == []


@pytest.mark.asyncio
class TestBoardUsesStoryRules:
    async def _move(self, user, story):
        from api.routes.boards import MoveItemRequest, move_item
        with patch("core.authorization._story_repo") as story_repo, \
                patch("core.authorization._project_repo") as project_repo:
            story_repo.find_by_id = AsyncMock(return_value={"id": "STY-1", "project_id": "PRJ-A", **story})
            project_repo.find_by_id = project_lookup(PROJECT_A)
            return await move_item(MoveItemRequest(item_id="STY-1", item_type="story", target_status="in_progress"), user=user)

    async def test_developer_cannot_drag_someone_elses_story(self):
        with pytest.raises(HTTPException) as error:
            await self._move(DEV, {"status": "todo", "assignee_id": "DEV-2"})
        assert error.value.status_code == 403

    async def test_developer_cannot_drag_a_draft_out_of_review(self):
        with pytest.raises(HTTPException) as error:
            await self._move(DEV, {"status": "draft", "assignee_id": "DEV-1"})
        assert error.value.status_code == 403


@pytest.mark.asyncio
class TestTaskSprintPlanning:
    async def test_developer_cannot_move_a_task_into_a_sprint(self):
        """CREATE_TASK lets developers create their own tasks, not plan sprints."""
        from api.routes.tasks import update_task_sprint
        from domain.models.task import TaskSprintUpdate
        with patch("core.authorization._task_repo") as task_repo, \
                patch("core.authorization._project_repo") as project_repo:
            task_repo.find_by_id = AsyncMock(return_value={"id": "T-1", "project_id": "PRJ-A", "assignee_id": "DEV-1"})
            project_repo.find_by_id = project_lookup(PROJECT_A)
            with pytest.raises(HTTPException) as error:
                await update_task_sprint("T-1", TaskSprintUpdate(sprint_id="SPR-1"), user=DEV)
        assert error.value.status_code == 403


@pytest.mark.asyncio
class TestDefectClosure:
    async def test_developer_cannot_close_or_verify_a_defect(self):
        from domain.models.qa import DefectUpdate
        service = QAService()
        service.accessible_project = AsyncMock(return_value=PROJECT_A)
        service.repo = AsyncMock()
        service.repo.find_one = AsyncMock(return_value={
            "id": "QAB-1", "project_id": "PRJ-A", "status": "READY_FOR_RETEST",
            "assignee_id": "DEV-1", "reporter_id": "QA-1", "history": []})
        with pytest.raises(HTTPException) as error:
            await service.update_defect(DEV, "QAB-1", DefectUpdate(status="CLOSED"))
        assert error.value.status_code in (400, 403)


@pytest.mark.asyncio
class TestPullRequestSync:
    async def _sync(self, user, project):
        from api.routes import github
        sync = AsyncMock(return_value={"pr": {"id": "PR-1", "risk_level": "LOW", "risk_score": 1}})
        projects = AsyncMock()
        projects.find_one = AsyncMock(return_value=project)
        service = type("Sync", (), {"sync_pull_request": sync})()
        with patch.object(github, "col", side_effect=lambda name: projects), \
                patch("core.authorization._project_repo") as repo, \
                patch.object(github, "GitHubSyncService", return_value=service):
            repo.find_by_id = project_lookup(project)
            request = github.PRSyncRequest(owner="o", repo="r", pr_number=7, project_id=project["id"])
            return await github.sync_pull_request(request, user=user), sync

    async def test_developer_syncs_a_pr_in_an_assigned_project(self):
        result, sync = await self._sync({**DEV, "org_id": "O1"}, {**PROJECT_A, "org_id": "O1"})
        assert result["pr_id"] == "PR-1"
        sync.assert_awaited_once()

    async def test_developer_cannot_sync_into_an_unassigned_project(self):
        with pytest.raises(HTTPException) as error:
            await self._sync({**DEV, "org_id": "O1"}, {**PROJECT_B, "org_id": "O1"})
        assert error.value.status_code == 403


# ── Incidents ───────────────────────────────────────────────────────────────

def _incident(incident_id, project_id, reporter_id):
    return {"id": incident_id, "project_id": project_id, "title": "t", "description": "d",
            "severity": "low", "status": "open", "reporter_id": reporter_id}


@pytest.mark.anyio
async def test_developer_reports_in_assigned_project_and_sees_only_own(mock_db):
    from api.routes import incidents
    from domain.models.incident import IncidentCreate
    from repositories import incident_repository
    with patch.object(incident_repository, "col", side_effect=lambda name: mock_db[name]), \
            patch("core.authorization._project_repo") as projects:
        projects.find_by_id = project_lookup(PROJECT_A, PROJECT_B)
        created = await incidents.report_incident(
            IncidentCreate(project_id="PRJ-A", title="Checkout down", description="500s", severity="high"), user=DEV)
        assert created.status == "open" and created.reporter_id == "DEV-1"
        await mock_db["incidents"].insert_one(_incident("INC-X", "PRJ-A", "OPS-1"))
        mine = await incidents.list_incidents(project_id=None, user=DEV)
        assert [incident.id for incident in mine] == [created.id]
        with pytest.raises(HTTPException) as error:
            await incidents.report_incident(IncidentCreate(project_id="PRJ-B", title="t", description="d"), user=DEV)
        assert error.value.status_code == 403


@pytest.mark.anyio
async def test_devops_sees_all_incidents_in_its_projects(mock_db):
    from api.routes import incidents
    from repositories import incident_repository
    await mock_db["incidents"].insert_many([_incident("INC-A", "PRJ-A", "DEV-1"), _incident("INC-B", "PRJ-B", "DEV-9")])
    ops = make_user("OPS-1", "DEVOPS", project_ids=["PRJ-A"])
    with patch.object(incident_repository, "col", side_effect=lambda name: mock_db[name]):
        seen = await incidents.list_incidents(project_id=None, user=ops)
    assert [incident.id for incident in seen] == ["INC-A"]


@pytest.mark.anyio
async def test_roles_without_incident_rights_are_refused():
    from api.routes import incidents
    with pytest.raises(HTTPException) as error:
        await incidents.list_incidents(project_id=None, user=make_user("HR-1", "HR"))
    assert error.value.status_code == 403
    assert Permission.CREATE_INCIDENT not in get_user_permissions("PM")


# ── Performance: own record only ────────────────────────────────────────────

from test_performance_access import records, service as performance_service  # noqa: E402,F401  (fixture reuse)


@pytest.mark.anyio
async def test_developer_cannot_read_a_teammates_performance(records):  # noqa: F811
    """Same project, same org: a developer still cannot open a colleague's record."""
    await records.users.insert_one({"employee_id": "D2", "role": "DEVELOPER", "org_id": "O1",
                                    "is_active": True, "project_ids": ["AUDIT-PROJECT"]})
    for read in ("detail", "trend"):
        with pytest.raises(HTTPException) as error:
            await getattr(performance_service(), read)("AUDIT-DEV", {"employee_id": "D2"})
        assert error.value.status_code == 403


@pytest.mark.anyio
async def test_developer_reads_own_ai_evaluation(records):  # noqa: F811
    result = await performance_service().detail("AUDIT-DEV", {"employee_id": "AUDIT-DEV"})
    assert result.model_dump(mode="json")["ai_evaluation"] is not None
