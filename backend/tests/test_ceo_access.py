"""
CR-007: CEO (executive) access (access and rules only, no new backend structure).

The CEO keeps executive oversight, approvals and organisation design (D2-A).
Hands-on delivery rights move to the people accountable for them (D1-A), and
the CEO reads defects without editing, assigning or closing them (D3-A).
The first-run CEO is also a system admin; that split is CR-008, so these tests
use a CEO without admin rights.
"""

import inspect
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from core.permissions import ADMIN_PERMISSIONS, OrganizationalRole, Permission, ROLE_PERMISSIONS, get_user_permissions

CEO = {"employee_id": "CEO-1", "id": "CEO-1", "name": "Chief", "role": "CEO", "organizational_role": "CEO",
       "project_ids": [], "team_id": None, "org_id": "O1", "is_admin": False}
PROJECT = {"id": "PRJ-A", "team_id": "TEAM-A", "org_id": "O1"}

REMOVED = [Permission.MANAGE_REPOSITORY_LINK, Permission.MANAGE_TEST_AUTOMATION, Permission.ACCEPT_STORY,
           Permission.CLEAR_RISK_CACHE, Permission.MANAGE_RISK_CONFIG]
KEPT = [Permission.VIEW_ALL_DATA, Permission.VIEW_ORGANIZATION_DATA, Permission.VIEW_ORGANIZATION_PERFORMANCE,
        Permission.VIEW_AUDIT_LOGS, Permission.VIEW_DEFECTS, Permission.APPROVE_TRANSFER_AS_MANAGEMENT,
        Permission.MANAGE_EVALUATION_POLICY, Permission.TRIGGER_BULK_EVALUATION]
# CR-015 (larger-company model): set-up, record-keeping and engineering tools
# move to admins, HR and engineering; replaces CR-007 D2-A.
MOVED_BY_CR015 = [Permission.CREATE_TEAM, Permission.MANAGE_TEAMS, Permission.ASSIGN_TEAM_LEAD, Permission.ASSIGN_PROJECT,
                  Permission.EXECUTE_TRANSFER, Permission.TRIGGER_AI_EVALUATION, Permission.APPROVE_ENGINEERING_CONTRACTS,
                  Permission.USE_ENGINEERING_INTELLIGENCE, Permission.MANAGE_GLOBAL_RISK_CONFIG]


def dependency_of(endpoint):
    return inspect.signature(endpoint).parameters["user"].default.dependency


class TestCEOPermissions:
    @pytest.mark.parametrize("permission", REMOVED)
    def test_hands_on_delivery_rights_are_removed(self, permission):
        assert permission not in ROLE_PERMISSIONS[OrganizationalRole.CEO]

    @pytest.mark.parametrize("permission", KEPT)
    def test_executive_rights_are_kept(self, permission):
        assert permission in get_user_permissions("CEO")

    @pytest.mark.parametrize("permission", MOVED_BY_CR015)
    def test_operating_rights_moved_away_from_the_ceo(self, permission):
        assert permission not in get_user_permissions("CEO")

    @pytest.mark.parametrize("permission", REMOVED)
    def test_the_accountable_roles_still_hold_them(self, permission):
        holders = {role.value for role, granted in ROLE_PERMISSIONS.items() if permission in granted}
        assert holders and "CEO" not in holders

    def test_admin_set_is_unchanged_until_cr008(self):
        # The first-run CEO account is also admin and keeps these through ADMIN_PERMISSIONS.
        assert {Permission.MANAGE_TEAMS, Permission.CREATE_TEAM, Permission.EXPORT_DATA} <= ADMIN_PERMISSIONS


class TestCEOGuards:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("module, name", [
        ("api.routes.github", "save_project_github_config"),
        ("api.routes.github", "provision_qa_workflow"),
        ("api.routes.qa_ci_provisioning", "enable_ci_integration"),
        ("api.routes.qa_ci_provisioning", "disable_ci_integration"),
    ])
    async def test_ceo_is_refused_delivery_endpoints(self, module, name):
        import importlib
        check = dependency_of(getattr(importlib.import_module(module), name))
        with pytest.raises(HTTPException) as error:
            await check(user=CEO)
        assert error.value.status_code == 403

    @pytest.mark.asyncio
    async def test_ceo_changes_no_risk_weights(self):
        # CR-015 D2-A: global defaults are a platform setting (admins).
        from api.routes.risk_configurations import _authorize_risk_change
        with patch("core.authorization._project_repo") as projects:
            projects.find_by_id = AsyncMock(return_value=PROJECT)
            for project_id in ("PRJ-A", None):
                with pytest.raises(HTTPException) as error:
                    await _authorize_risk_change(CEO, project_id)
                assert error.value.status_code == 403
            assert await _authorize_risk_change({**CEO, "role": "DEVOPS", "is_admin": True}, None) is None

    @pytest.mark.asyncio
    async def test_ceo_cannot_accept_a_draft_story(self):
        from core import authorization
        with patch.object(authorization, "verify_story_access", AsyncMock(return_value="PRJ-A")), \
                patch.object(authorization, "_story_repo") as stories:
            stories.find_by_id = AsyncMock(return_value={"id": "S-1", "status": "draft", "project_id": "PRJ-A"})
            with pytest.raises(HTTPException) as error:
                await authorization.verify_story_status_update_access(CEO, "S-1", "todo")
        assert error.value.status_code == 403


class TestCEODefects:
    def _service(self):
        from domain.services.qa_service import QAService
        service = QAService()
        service.repo = AsyncMock()
        service.repo.projects = "projects"
        service.repo.find_one = AsyncMock(return_value=PROJECT)
        return service

    @pytest.mark.asyncio
    async def test_ceo_still_reads_any_project(self):
        assert (await self._service().accessible_project(CEO, "PRJ-A"))["id"] == "PRJ-A"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("current, update", [
        ("OPEN", {"assignee_id": "DEV-A"}),
        ("OPEN", {"description": "Changed by the CEO"}),
        ("OPEN", {"status": "ASSIGNED"}),
        ("READY_FOR_RETEST", {"status": "CLOSED"}),
    ])
    async def test_ceo_cannot_assign_edit_or_change_status(self, current, update):
        from domain.models.qa import DefectUpdate
        service = self._service()
        service.accessible_project = AsyncMock(return_value=PROJECT)
        service.repo.find_one = AsyncMock(return_value={
            "id": "QAB-1", "project_id": "PRJ-A", "status": current,
            "assignee_id": "DEV-A", "reporter_id": "QA-1", "history": []})
        with pytest.raises(HTTPException) as error:
            await service.update_defect(CEO, "QAB-1", DefectUpdate(**update))
        assert error.value.status_code == 403
