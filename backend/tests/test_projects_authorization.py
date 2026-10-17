"""
Integration tests for project routes authorization.

Tests that project API endpoints correctly enforce resource-level authorization.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from domain.services.project_service import ProjectService


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
        "name": "Test User",
        "role": role,
        "organizational_role": role,
        "project_ids": project_ids or [],
        "team_id": team_id,
    }


# ── GET /projects/{project_id} Tests ──────────────────────────────────────


@pytest.mark.asyncio
class TestGetProject:
    """Test GET /projects/{project_id} authorization."""

    async def test_user_can_access_assigned_project(self):
        """User can read projects they're assigned to."""
        user = create_user(project_ids=["PRJ-A"])
        
        with patch("core.authorization._project_repo") as mock_repo:
            with patch.object(ProjectService, "get_project") as mock_get:
                mock_repo.find_by_id = AsyncMock(return_value={"id": "PRJ-A"})
                mock_get.return_value = {
                    "id": "PRJ-A",
                    "name": "Project A"
                }
                
                from api.routes.projects import get_project
                
                result = await get_project("PRJ-A", user=user)
                assert result["id"] == "PRJ-A"

    async def test_user_cannot_access_unassigned_project(self):
        """User cannot read projects they're not assigned to."""
        user = create_user(project_ids=["PRJ-A"])
        
        with patch("core.authorization._project_repo") as mock_repo:
            mock_repo.find_by_id = AsyncMock(return_value={"id": "PRJ-B"})
            
            from api.routes.projects import get_project
            
            with pytest.raises(HTTPException) as exc_info:
                await get_project("PRJ-B", user=user)
            
            assert exc_info.value.status_code == 403

    async def test_pm_can_access_any_project(self):
        """PM can read any project."""
        user = create_user(role="PM", project_ids=[])
        
        with patch("core.authorization._project_repo") as mock_repo:
            with patch.object(ProjectService, "get_project") as mock_get:
                mock_repo.find_by_id = AsyncMock(return_value={"id": "PRJ-Z"})
                mock_get.return_value = {
                    "id": "PRJ-Z",
                    "name": "Project Z"
                }
                
                from api.routes.projects import get_project
                
                result = await get_project("PRJ-Z", user=user)
                assert result["id"] == "PRJ-Z"

    async def test_lead_can_access_team_project(self):
        """LEAD can access projects for their team."""
        user = create_user(role="LEAD", project_ids=[], team_id="TEAM-A")
        
        with patch("core.authorization._project_repo") as mock_repo:
            with patch.object(ProjectService, "get_project") as mock_get:
                mock_repo.find_by_id = AsyncMock(return_value={
                    "id": "PRJ-TEAM-A",
                    "team_id": "TEAM-A"
                })
                mock_get.return_value = {
                    "id": "PRJ-TEAM-A",
                    "name": "Team A Project",
                    "team_id": "TEAM-A"
                }
                
                from api.routes.projects import get_project
                
                result = await get_project("PRJ-TEAM-A", user=user)
                assert result["id"] == "PRJ-TEAM-A"


# ── GET /projects/ Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
class TestListProjects:
    """Test GET /projects/ authorization and filtering."""

    async def test_developer_sees_only_assigned_projects(self):
        """Developer sees only their assigned projects."""
        user = create_user(role="DEVELOPER", project_ids=["PRJ-A", "PRJ-B"])
        
        with patch.object(ProjectService, "get_active_projects") as mock_get:
            # Service returns all projects in org
            mock_get.return_value = [
                {"id": "PRJ-A", "name": "Project A"},
                {"id": "PRJ-B", "name": "Project B"},
                {"id": "PRJ-C", "name": "Project C"},  # Not assigned
            ]
            
            from api.routes.projects import list_projects
            
            result = await list_projects("ORG-1", user=user)
            
            # Should only see assigned projects
            assert len(result) == 2
            result_ids = [p["id"] for p in result]
            assert "PRJ-A" in result_ids
            assert "PRJ-B" in result_ids
            assert "PRJ-C" not in result_ids

    async def test_pm_sees_all_projects(self):
        """PM sees all projects in their org."""
        user = create_user(role="PM", project_ids=[])
        
        with patch.object(ProjectService, "get_active_projects") as mock_get:
            mock_get.return_value = [
                {"id": "PRJ-A", "name": "Project A"},
                {"id": "PRJ-B", "name": "Project B"},
                {"id": "PRJ-C", "name": "Project C"},
            ]
            
            from api.routes.projects import list_projects
            
            result = await list_projects("ORG-1", user=user)
            
            # Should see all projects
            assert len(result) == 3

    async def test_ceo_sees_all_projects(self):
        """CEO sees all projects globally."""
        user = create_user(role="CEO", project_ids=[])
        
        with patch.object(ProjectService, "get_active_projects") as mock_get:
            mock_get.return_value = [
                {"id": "PRJ-1", "name": "Project 1"},
                {"id": "PRJ-2", "name": "Project 2"},
            ]
            
            from api.routes.projects import list_projects
            
            result = await list_projects("ORG-ANY", user=user)
            
            # Should see all projects
            assert len(result) == 2

    async def test_unassigned_developer_sees_empty_list(self):
        """Developer with no projects sees empty list."""
        user = create_user(role="DEVELOPER", project_ids=[])
        
        with patch.object(ProjectService, "get_active_projects") as mock_get:
            mock_get.return_value = [
                {"id": "PRJ-A", "name": "Project A"},
                {"id": "PRJ-B", "name": "Project B"},
            ]
            
            from api.routes.projects import list_projects
            
            result = await list_projects("ORG-1", user=user)
            
            # Should see nothing
            assert len(result) == 0


# ── GET /projects/team/{team_id} Tests ────────────────────────────────────


@pytest.mark.asyncio
class TestListTeamProjects:
    """Test GET /projects/team/{team_id} authorization."""

    async def test_team_member_can_list_team_projects(self):
        """Team member can list their team's projects."""
        user = create_user(role="DEVELOPER", team_id="TEAM-A")
        
        with patch.object(ProjectService, "get_team_projects") as mock_get:
            mock_get.return_value = [
                {"id": "PRJ-1", "team_id": "TEAM-A"},
                {"id": "PRJ-2", "team_id": "TEAM-A"},
            ]
            
            from api.routes.projects import list_team_projects
            
            result = await list_team_projects("TEAM-A", user=user)
            assert len(result) == 2

    async def test_non_member_cannot_list_team_projects(self):
        """Non-member cannot list other team's projects."""
        user = create_user(role="DEVELOPER", team_id="TEAM-A")
        
        from api.routes.projects import list_team_projects
        
        with pytest.raises(HTTPException) as exc_info:
            await list_team_projects("TEAM-B", user=user)
        
        assert exc_info.value.status_code == 403

    async def test_pm_can_list_any_team_projects(self):
        """PM can list any team's projects."""
        user = create_user(role="PM", team_id="TEAM-A")
        
        with patch.object(ProjectService, "get_team_projects") as mock_get:
            mock_get.return_value = [
                {"id": "PRJ-X", "team_id": "TEAM-B"},
            ]
            
            from api.routes.projects import list_team_projects
            
            result = await list_team_projects("TEAM-B", user=user)
            assert len(result) == 1

    async def test_lead_can_list_own_team_projects(self):
        """LEAD can list their own team's projects."""
        user = create_user(role="LEAD", team_id="TEAM-A")
        
        with patch.object(ProjectService, "get_team_projects") as mock_get:
            mock_get.return_value = [
                {"id": "PRJ-1", "team_id": "TEAM-A"},
            ]
            
            from api.routes.projects import list_team_projects
            
            result = await list_team_projects("TEAM-A", user=user)
            assert len(result) == 1


# ── Project Not Found Tests ───────────────────────────────────────────────


@pytest.mark.asyncio
class TestProjectNotFound:
    """Test 404 handling for missing projects."""

    async def test_missing_project_returns_404_not_403(self):
        """Non-existent project returns 404, not 403."""
        user = create_user(role="DEVELOPER", project_ids=["PRJ-A"])
        
        with patch("core.authorization._project_repo") as mock_repo:
            mock_repo.find_by_id = AsyncMock(return_value=None)
            
            from api.routes.projects import get_project
            
            with pytest.raises(HTTPException) as exc_info:
                await get_project("PRJ-MISSING", user=user)
            
            # Should be 404, not 403
            assert exc_info.value.status_code == 404
            assert "not found" in str(exc_info.value.detail).lower()
