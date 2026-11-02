"""
Integration tests for task routes authorization.

Tests that task API endpoints correctly enforce resource-level authorization,
ensuring users can only access tasks in their assigned projects.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from domain.services.task_service import TaskService
from domain.services.workflow_service import WorkflowService


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


# ── GET /tasks/{task_id} Tests ────────────────────────────────────────────


@pytest.mark.asyncio
class TestGetTask:
    """Test GET /tasks/{task_id} authorization."""

    async def test_user_can_access_task_in_assigned_project(self):
        """User can read tasks in their assigned project."""
        user = create_user(project_ids=["PRJ-A"])
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                with patch.object(TaskService, "get_task") as mock_get:
                    mock_task_repo.find_by_id = AsyncMock(return_value={
                        "id": "TASK-1", "project_id": "PRJ-A"
                    })
                    mock_project_repo.find_by_id = AsyncMock(return_value={
                        "id": "PRJ-A"
                    })
                    mock_get.return_value = {
                        "id": "TASK-1",
                        "title": "Test Task",
                        "project_id": "PRJ-A"
                    }
                    
                    # Import after patching to get the patched version
                    from api.routes.tasks import get_task
                    
                    result = await get_task("TASK-1", user=user)
                    assert result["id"] == "TASK-1"

    async def test_user_cannot_access_task_in_unassigned_project(self):
        """User cannot read tasks in unassigned projects."""
        user = create_user(project_ids=["PRJ-A"])
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                mock_task_repo.find_by_id = AsyncMock(return_value={
                    "id": "TASK-2", "project_id": "PRJ-B"
                })
                mock_project_repo.find_by_id = AsyncMock(return_value={
                    "id": "PRJ-B"
                })
                
                from api.routes.tasks import get_task
                
                with pytest.raises(HTTPException) as exc_info:
                    await get_task("TASK-2", user=user)
                
                assert exc_info.value.status_code == 403

    async def test_ceo_can_access_any_task(self):
        """CEO can read any task regardless of assignment."""
        user = create_user(role="CEO", project_ids=[])
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch.object(TaskService, "get_task") as mock_get:
                mock_task_repo.find_by_id = AsyncMock(return_value={
                    "id": "TASK-999", "project_id": "PRJ-Z"
                })
                mock_get.return_value = {
                    "id": "TASK-999",
                    "title": "Any Task",
                    "project_id": "PRJ-Z"
                }
                
                from api.routes.tasks import get_task
                
                result = await get_task("TASK-999", user=user)
                assert result["id"] == "TASK-999"


# ── GET /tasks/project/{project_id} Tests ─────────────────────────────────


@pytest.mark.asyncio
class TestListProjectTasks:
    """Test GET /tasks/project/{project_id} authorization."""

    async def test_user_can_list_tasks_in_assigned_project(self):
        """User can list tasks in their assigned project."""
        user = create_user(project_ids=["PRJ-A"])
        
        with patch("core.authorization._project_repo") as mock_project_repo:
            with patch.object(TaskService, "get_project_tasks") as mock_get:
                mock_project_repo.find_by_id = AsyncMock(return_value={
                    "id": "PRJ-A"
                })
                mock_get.return_value = [
                    {"id": "TASK-1", "project_id": "PRJ-A"},
                    {"id": "TASK-2", "project_id": "PRJ-A"}
                ]
                
                from api.routes.tasks import list_project_tasks
                
                result = await list_project_tasks("PRJ-A", user=user)
                assert len(result) == 2

    async def test_user_cannot_list_tasks_in_unassigned_project(self):
        """User cannot list tasks in unassigned projects."""
        user = create_user(project_ids=["PRJ-A"])
        
        with patch("core.authorization._project_repo") as mock_project_repo:
            mock_project_repo.find_by_id = AsyncMock(return_value={
                "id": "PRJ-B"
            })
            
            from api.routes.tasks import list_project_tasks
            
            with pytest.raises(HTTPException) as exc_info:
                await list_project_tasks("PRJ-B", user=user)
            
            assert exc_info.value.status_code == 403


# ── GET /tasks/assignee/{assignee_id} Tests ───────────────────────────────


@pytest.mark.asyncio
class TestListAssigneeTasks:
    """Test GET /tasks/assignee/{assignee_id} authorization."""

    async def test_user_can_view_own_tasks(self):
        """User can view their own tasks."""
        user = create_user(employee_id="E001", project_ids=["PRJ-A"])
        
        with patch.object(TaskService, "get_assignee_tasks") as mock_get:
            mock_get.return_value = [
                {"id": "TASK-1", "assignee_id": "E001"}
            ]
            
            from api.routes.tasks import list_assignee_tasks
            
            result = await list_assignee_tasks("E001", user=user)
            assert len(result) == 1

    async def test_developer_cannot_view_others_tasks(self):
        """Developer cannot view other users' tasks."""
        user = create_user(employee_id="E001", role="DEVELOPER")
        
        from api.routes.tasks import list_assignee_tasks
        
        with pytest.raises(HTTPException) as exc_info:
            await list_assignee_tasks("E002", user=user)
        
        assert exc_info.value.status_code == 403
        assert "own tasks" in str(exc_info.value.detail)

    async def test_pm_can_view_any_users_tasks(self):
        """PM can view any user's tasks."""
        user = create_user(employee_id="E001", role="PM")
        
        with patch.object(TaskService, "get_assignee_tasks") as mock_get:
            mock_get.return_value = [
                {"id": "TASK-5", "assignee_id": "E002"}
            ]
            
            from api.routes.tasks import list_assignee_tasks
            
            result = await list_assignee_tasks("E002", user=user)
            assert len(result) == 1


# ── PATCH /tasks/{task_id}/status Tests ───────────────────────────────────


@pytest.mark.asyncio
class TestUpdateTaskStatus:
    """Test PATCH /tasks/{task_id}/status authorization."""

    async def test_user_can_update_task_in_assigned_project(self):
        """User with MOVE_TASK permission can update tasks in assigned project."""
        user = create_user(role="LEAD", project_ids=["PRJ-A"])
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                with patch.object(WorkflowService, "transition_task") as mock_update:
                    mock_task_repo.find_by_id = AsyncMock(return_value={
                        "id": "TASK-1", "project_id": "PRJ-A"
                    })
                    mock_project_repo.find_by_id = AsyncMock(return_value={
                        "id": "PRJ-A"
                    })
                    mock_update.return_value = {"id": "TASK-1", "status": "in_progress"}
                    
                    from api.routes.tasks import update_task_status
                    
                    result = await update_task_status("TASK-1", "in_progress", user=user)
                    assert result["message"] == "Status updated"

    async def test_user_cannot_update_task_in_unassigned_project(self):
        """User cannot update tasks in unassigned projects."""
        user = create_user(role="LEAD", project_ids=["PRJ-A"])
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                mock_task_repo.find_by_id = AsyncMock(return_value={
                    "id": "TASK-2", "project_id": "PRJ-B"
                })
                mock_project_repo.find_by_id = AsyncMock(return_value={
                    "id": "PRJ-B"
                })
                
                from api.routes.tasks import update_task_status
                
                with pytest.raises(HTTPException) as exc_info:
                    await update_task_status("TASK-2", "done", user=user)
                
                assert exc_info.value.status_code == 403

    async def test_developer_can_update_own_task(self):
        user = create_user(
            employee_id="E001",
            role="DEVELOPER",
            team_id="TEAM-A",
        )
        with patch("core.authorization._task_repo") as task_repo:
            with patch("core.authorization._project_repo") as project_repo:
                with patch.object(WorkflowService, "transition_task") as update:
                    task_repo.find_by_id = AsyncMock(return_value={
                        "id": "TASK-1",
                        "project_id": "PRJ-A",
                        "assignee_id": "E001",
                    })
                    project_repo.find_by_id = AsyncMock(return_value={
                        "id": "PRJ-A",
                        "team_id": "TEAM-A",
                    })
                    update.return_value = {"id": "TASK-1", "status": "in_progress"}
                    from api.routes.tasks import update_task_status
                    result = await update_task_status("TASK-1", "in_progress", user=user)
                    assert result["status"] == "in_progress"

    async def test_developer_cannot_update_another_developers_task(self):
        user = create_user(employee_id="E001", role="DEVELOPER", team_id="TEAM-A")
        with patch("core.authorization._task_repo") as task_repo:
            task_repo.find_by_id = AsyncMock(return_value={
                "id": "TASK-2",
                "project_id": "PRJ-A",
                "assignee_id": "E002",
            })
            from api.routes.tasks import update_task_status
            with pytest.raises(HTTPException) as exc_info:
                await update_task_status("TASK-2", "in_progress", user=user)
            assert exc_info.value.status_code == 403

    async def test_sprint_assignment_rejects_cross_project_sprint(self):
        user = create_user(role="PM")
        with patch("api.routes.tasks.verify_task_access", new=AsyncMock()):
            with patch("api.routes.tasks.sprint_repo") as sprint_repo:
                with patch.object(TaskService, "get_task", new=AsyncMock(return_value={
                    "id": "TASK-1",
                    "project_id": "PRJ-A",
                })):
                    sprint_repo.find_by_id = AsyncMock(return_value={
                        "id": "SPR-B",
                        "project_id": "PRJ-B",
                    })
                    from api.routes.tasks import update_task_sprint
                    from domain.models.task import TaskSprintUpdate
                    with pytest.raises(HTTPException) as exc_info:
                        await update_task_sprint(
                            "TASK-1",
                            TaskSprintUpdate(sprint_id="SPR-B"),
                            user=user,
                        )
                    assert exc_info.value.status_code == 400


# ── PATCH /tasks/{task_id}/transition Tests ───────────────────────────────


@pytest.mark.asyncio
class TestTransitionTask:
    """Test PATCH /tasks/{task_id}/transition authorization."""

    async def test_user_can_transition_task_in_assigned_project(self):
        """User can transition tasks in assigned projects."""
        user = create_user(role="LEAD", project_ids=["PRJ-A"])
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                with patch.object(WorkflowService, "transition_task") as mock_transition:
                    mock_task_repo.find_by_id = AsyncMock(return_value={
                        "id": "TASK-1", "project_id": "PRJ-A"
                    })
                    mock_project_repo.find_by_id = AsyncMock(return_value={
                        "id": "PRJ-A"
                    })
                    mock_transition.return_value = {
                        "id": "TASK-1",
                        "status": "in_progress"
                    }
                    
                    from api.routes.tasks import transition_task
                    from domain.models.workflow import TransitionRequest
                    
                    body = TransitionRequest(status="in_progress")
                    result = await transition_task("TASK-1", body, user=user)
                    assert result["status"] == "in_progress"

    async def test_user_cannot_transition_task_in_unassigned_project(self):
        """User cannot transition tasks in unassigned projects."""
        user = create_user(role="LEAD", project_ids=["PRJ-A"])
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                mock_task_repo.find_by_id = AsyncMock(return_value={
                    "id": "TASK-2", "project_id": "PRJ-B"
                })
                mock_project_repo.find_by_id = AsyncMock(return_value={
                    "id": "PRJ-B"
                })
                
                from api.routes.tasks import transition_task
                from domain.models.workflow import TransitionRequest
                
                body = TransitionRequest(status="done")
                
                with pytest.raises(HTTPException) as exc_info:
                    await transition_task("TASK-2", body, user=user)
                
                assert exc_info.value.status_code == 403


# ── Role Hierarchy Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
class TestTaskRouteRoleHierarchy:
    """Test role hierarchy in task routes."""

    async def test_lead_can_access_team_project_tasks(self):
        """LEAD can access tasks in their team's projects."""
        user = create_user(role="LEAD", project_ids=[], team_id="TEAM-A")
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                with patch.object(TaskService, "get_task") as mock_get:
                    mock_task_repo.find_by_id = AsyncMock(return_value={
                        "id": "TASK-1", "project_id": "PRJ-TEAM-A"
                    })
                    mock_project_repo.find_by_id = AsyncMock(return_value={
                        "id": "PRJ-TEAM-A",
                        "team_id": "TEAM-A"
                    })
                    mock_get.return_value = {
                        "id": "TASK-1",
                        "project_id": "PRJ-TEAM-A"
                    }
                    
                    from api.routes.tasks import get_task
                    
                    result = await get_task("TASK-1", user=user)
                    assert result["id"] == "TASK-1"

    async def test_pm_can_access_all_tasks(self):
        """PM can access tasks in any project."""
        user = create_user(role="PM", project_ids=[])
        
        with patch("core.authorization._task_repo") as mock_task_repo:
            with patch("core.authorization._project_repo") as mock_project_repo:
                with patch.object(TaskService, "get_task") as mock_get:
                    mock_task_repo.find_by_id = AsyncMock(return_value={
                        "id": "TASK-999", "project_id": "PRJ-ANY"
                    })
                    mock_project_repo.find_by_id = AsyncMock(return_value={
                        "id": "PRJ-ANY"
                    })
                    mock_get.return_value = {
                        "id": "TASK-999",
                        "project_id": "PRJ-ANY"
                    }
                    
                    from api.routes.tasks import get_task
                    
                    result = await get_task("TASK-999", user=user)
                    assert result["id"] == "TASK-999"
