"""
Unit tests for resource-level authorization helpers.

Tests authorization rules for projects, tasks, stories, and teams based on
user roles and assignments.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from core.authorization import (
    has_global_access,
    has_org_access,
    has_team_access,
    verify_project_access,
    verify_task_access,
    verify_story_access,
    verify_team_access as verify_team_access_func,
    verify_can_view_user_tasks,
)


# ── Helper Functions ──────────────────────────────────────────────────────


def create_user(
    employee_id: str = "E001",
    role: str = "DEVELOPER",
    project_ids: list = None,
    team_id: str = None,
) -> dict:
    """Create a mock user dict (simulates JWT payload)."""
    return {
        "employee_id": employee_id,
        "id": employee_id,
        "role": role,
        "organizational_role": role,
        "project_ids": project_ids or [],
        "team_id": team_id,
    }


# ── Role Access Tests ─────────────────────────────────────────────────────


class TestRoleAccess:
    """Test role hierarchy access checks."""

    def test_ceo_has_global_access(self):
        """CEO role has global access."""
        user = create_user(role="CEO")
        assert has_global_access(user) is True
        assert has_org_access(user) is True

    def test_pm_has_org_access(self):
        """PM role has org-wide access."""
        user = create_user(role="PM")
        assert has_global_access(user) is False
        assert has_org_access(user) is True

    def test_lead_has_no_org_access(self):
        """LEAD role does not have org-wide access."""
        user = create_user(role="LEAD")
        assert has_global_access(user) is False
        assert has_org_access(user) is False

    def test_developer_has_no_org_access(self):
        """DEVELOPER role has no special access."""
        user = create_user(role="DEVELOPER")
        assert has_global_access(user) is False
        assert has_org_access(user) is False

    def test_team_access_own_team(self):
        """User can access their own team."""
        user = create_user(role="DEVELOPER", team_id="TEAM-A")
        assert has_team_access(user, "TEAM-A") is True

    def test_team_access_other_team(self):
        """User cannot access other teams."""
        user = create_user(role="DEVELOPER", team_id="TEAM-A")
        assert has_team_access(user, "TEAM-B") is False

    def test_pm_has_all_team_access(self):
        """PM can access any team."""
        user = create_user(role="PM", team_id="TEAM-A")
        assert has_team_access(user, "TEAM-B") is True


# ── Project Access Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
class TestProjectAccess:
    """Test project access verification."""

    async def test_ceo_can_access_any_project(self):
        """CEO can access any project without fetching it."""
        user = create_user(role="CEO", project_ids=[])
        
        # Should not raise - CEO has global access
        await verify_project_access(user, "PRJ-999")

    async def test_pm_can_access_any_project(self):
        """PM can access any project in their org."""
        user = create_user(role="PM", project_ids=[])
        
        with patch("core.authorization._project_repo") as mock_repo:
            mock_repo.find_by_id = AsyncMock(return_value={"id": "PRJ-999", "name": "Test"})
            
            # Should not raise - PM has org access
            await verify_project_access(user, "PRJ-999")

    async def test_developer_can_access_assigned_project(self):
        """Developer can access projects they're assigned to."""
        user = create_user(role="DEVELOPER", project_ids=["PRJ-A", "PRJ-B"])
        
        with patch("core.authorization._project_repo") as mock_repo:
            mock_repo.find_by_id = AsyncMock(return_value={"id": "PRJ-A", "name": "Test"})
            
            # Should not raise - user is assigned to PRJ-A
            await verify_project_access(user, "PRJ-A")

    async def test_developer_cannot_access_unassigned_project(self):
        """Developer cannot access projects they're not assigned to."""
        user = create_user(role="DEVELOPER", project_ids=["PRJ-A"])
        
        with patch("core.authorization._project_repo") as mock_repo:
            mock_repo.find_by_id = AsyncMock(return_value={"id": "PRJ-B", "name": "Test"})
            
            # Should raise 403
            with pytest.raises(HTTPException) as exc_info:
                await verify_project_access(user, "PRJ-B")
            
            assert exc_info.value.status_code == 403
            assert "don't have access" in str(exc_info.value.detail)

    async def test_project_not_found_returns_404(self):
        """Non-existent project returns 404."""
        user = create_user(role="DEVELOPER", project_ids=["PRJ-A"])
        
        with patch("core.authorization._project_repo") as mock_repo:
            mock_repo.find_by_id = AsyncMock(return_value=None)
            
            # Should raise 404
            with pytest.raises(HTTPException) as exc_info:
                await verify_project_access(user, "PRJ-999")
            
            assert exc_info.value.status_code == 404
            assert "not found" in str(exc_info.value.detail).lower()

    async def test_lead_can_access_team_project(self):
        """LEAD can access projects for their team."""
        user = create_user(role="LEAD", project_ids=[], team_id="TEAM-A")
        
        with patch("core.authorization._project_repo") as mock_repo:
            mock_repo.find_by_id = AsyncMock(return_value={"id": "PRJ-TEAM-A", "team_id": "TEAM-A"})
            
            # Should not raise - LEAD can access their team's projects
            await verify_project_access(user, "PRJ-TEAM-A")

    async def test_lead_cannot_access_other_team_project(self):
        """LEAD cannot access projects from other teams."""
        user = create_user(role="LEAD", project_ids=[], team_id="TEAM-A")
        
        with patch("core.authorization._project_repo") as mock_repo:
            mock_repo.find_by_id = AsyncMock(return_value={"id": "PRJ-TEAM-B", "team_id": "TEAM-B"})
            
            # Should raise 403
            with pytest.raises(HTTPException) as exc_info:
                await verify_project_access(user, "PRJ-TEAM-B")
            
            assert exc_info.value.status_code == 403

    async def test_developer_can_read_their_team_project(self):
        """Developers can read projects assigned to their team."""
        user = create_user(role="DEVELOPER", team_id="TEAM-A")

        with patch("core.authorization._project_repo") as mock_repo:
            mock_repo.find_by_id = AsyncMock(return_value={
                "id": "PRJ-TEAM-A",
                "team_id": "TEAM-A",
            })

            await verify_project_access(user, "PRJ-TEAM-A")


# ── Task Access Tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestTaskAccess:
    """Test task access verification."""

    async def test_ceo_can_access_any_task(self):
        """CEO can access any task."""
        user = create_user(role="CEO", project_ids=[])
        
        with patch("core.authorization._task_repo") as mock_repo:
            mock_repo.find_by_id = AsyncMock(return_value={"id": "TASK-999", "project_id": "PRJ-999"})
            
            # Should not raise and return project_id
            project_id = await verify_task_access(user, "TASK-999")
            assert project_id == "PRJ-999"

    async def test_developer_can_access_task_in_assigned_project(self):
        """Developer can access tasks in their assigned projects."""
        user = create_user(role="DEVELOPER", project_ids=["PRJ-A"])
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                mock_task_repo.find_by_id = AsyncMock(return_value={"id": "TASK-1", "project_id": "PRJ-A"})
                mock_project_repo.find_by_id = AsyncMock(return_value={"id": "PRJ-A"})
                
                # Should not raise
                project_id = await verify_task_access(user, "TASK-1")
                assert project_id == "PRJ-A"

    async def test_developer_cannot_access_task_in_unassigned_project(self):
        """Developer cannot access tasks in unassigned projects."""
        user = create_user(role="DEVELOPER", project_ids=["PRJ-A"])
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                mock_task_repo.find_by_id = AsyncMock(return_value={"id": "TASK-1", "project_id": "PRJ-B"})
                mock_project_repo.find_by_id = AsyncMock(return_value={"id": "PRJ-B"})
                
                # Should raise 403
                with pytest.raises(HTTPException) as exc_info:
                    await verify_task_access(user, "TASK-1")
                
                assert exc_info.value.status_code == 403

    async def test_task_not_found_returns_404(self):
        """Non-existent task returns 404."""
        user = create_user(role="DEVELOPER", project_ids=["PRJ-A"])
        
        with patch("core.authorization._task_repo") as mock_repo:
            mock_repo.find_by_id = AsyncMock(return_value=None)
            
            # Should raise 404
            with pytest.raises(HTTPException) as exc_info:
                await verify_task_access(user, "TASK-999")
            
            assert exc_info.value.status_code == 404
            assert "not found" in str(exc_info.value.detail).lower()


# ── Story Access Tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestStoryAccess:
    """Test story access verification."""

    async def test_developer_can_access_story_in_assigned_project(self):
        """Developer can access stories in their assigned projects."""
        user = create_user(role="DEVELOPER", project_ids=["PRJ-A"])
        
        with patch("core.authorization._story_repo") as mock_story_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                mock_story_repo.find_by_id = AsyncMock(return_value={"id": "STORY-1", "project_id": "PRJ-A"})
                mock_project_repo.find_by_id = AsyncMock(return_value={"id": "PRJ-A"})
                
                # Should not raise
                project_id = await verify_story_access(user, "STORY-1")
                assert project_id == "PRJ-A"

    async def test_developer_cannot_access_story_in_unassigned_project(self):
        """Developer cannot access stories in unassigned projects."""
        user = create_user(role="DEVELOPER", project_ids=["PRJ-A"])
        
        with patch("core.authorization._story_repo") as mock_story_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                mock_story_repo.find_by_id = AsyncMock(return_value={"id": "STORY-1", "project_id": "PRJ-B"})
                mock_project_repo.find_by_id = AsyncMock(return_value={"id": "PRJ-B"})
                
                # Should raise 403
                with pytest.raises(HTTPException) as exc_info:
                    await verify_story_access(user, "STORY-1")
                
                assert exc_info.value.status_code == 403


# ── Team Access Tests ─────────────────────────────────────────────────────


@pytest.mark.asyncio
class TestTeamAccessVerification:
    """Test team access verification."""

    async def test_user_can_access_own_team(self):
        """User can access their own team."""
        user = create_user(role="DEVELOPER", team_id="TEAM-A")
        
        # Should not raise
        await verify_team_access_func(user, "TEAM-A")

    async def test_user_cannot_access_other_team(self):
        """User cannot access other teams."""
        user = create_user(role="DEVELOPER", team_id="TEAM-A")
        
        # Should raise 403
        with pytest.raises(HTTPException) as exc_info:
            await verify_team_access_func(user, "TEAM-B")
        
        assert exc_info.value.status_code == 403

    async def test_pm_can_access_any_team(self):
        """PM can access any team."""
        user = create_user(role="PM", team_id="TEAM-A")
        
        # Should not raise
        await verify_team_access_func(user, "TEAM-B")


# ── User Task Viewing Tests ───────────────────────────────────────────────


@pytest.mark.asyncio
class TestUserTaskViewing:
    """Test viewing other users' tasks."""

    async def test_user_can_view_own_tasks(self):
        """User can view their own tasks."""
        user = create_user(employee_id="E001", role="DEVELOPER")
        
        # Should not raise
        await verify_can_view_user_tasks(user, "E001")

    async def test_developer_cannot_view_other_users_tasks(self):
        """Developer cannot view other users' tasks."""
        user = create_user(employee_id="E001", role="DEVELOPER")
        
        # Should raise 403
        with pytest.raises(HTTPException) as exc_info:
            await verify_can_view_user_tasks(user, "E002")
        
        assert exc_info.value.status_code == 403
        assert "own tasks" in str(exc_info.value.detail)

    async def test_pm_can_view_any_users_tasks(self):
        """PM can view any user's tasks."""
        user = create_user(employee_id="E001", role="PM")
        
        # Should not raise
        await verify_can_view_user_tasks(user, "E002")

    async def test_ceo_can_view_any_users_tasks(self):
        """CEO can view any user's tasks."""
        user = create_user(employee_id="E001", role="CEO")
        
        # Should not raise
        await verify_can_view_user_tasks(user, "E002")
