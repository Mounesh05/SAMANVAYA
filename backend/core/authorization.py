"""
Resource-level authorization helpers.

These functions verify that the current user has access to specific resources
(projects, tasks, stories, teams) based on their role and assignments.

Authorization hierarchy (highest to lowest access):
- CEO: Access all resources globally
- PM: Access all resources in their organization
- LEAD: Access all resources for their team
- DEVELOPER/QA/DEVOPS: Access only assigned projects and their resources
"""

from fastapi import HTTPException
from typing import Optional
from repositories.task_repository import TaskRepository
from repositories.project_repository import ProjectRepository
from repositories.story_repository import StoryRepository


# Repository instances
_task_repo = TaskRepository()
_project_repo = ProjectRepository()
_story_repo = StoryRepository()


def has_global_access(user: dict) -> bool:
    """
    Check if user has global access (CEO role).
    
    CEO can access all resources across all organizations and projects.
    
    Args:
        user: Current user from JWT token
    
    Returns:
        True if user is CEO
    """
    role = user.get("role", user.get("organizational_role", "")).upper()
    return role == "CEO"


def has_org_access(user: dict) -> bool:
    """
    Check if user has organization-wide access (CEO or PM role).
    
    These roles can access all projects and resources within their organization.
    
    Args:
        user: Current user from JWT token
    
    Returns:
        True if user is CEO or PM
    """
    role = user.get("role", user.get("organizational_role", "")).upper()
    return role in ("CEO", "PM")


def has_team_access(user: dict, team_id: str) -> bool:
    """
    Check if user has access to a specific team.
    
    Access rules:
    - CEO: Access all teams
    - PM: Access all teams in their org
    - Others: Access only their own team
    
    Args:
        user: Current user from JWT token
        team_id: Team ID to check access for
    
    Returns:
        True if user can access the team
    """
    if has_org_access(user):
        return True
    
    user_team_id = user.get("team_id")
    return user_team_id == team_id


async def verify_project_access(
    user: dict,
    project_id: str,
    *,
    require_write: bool = False
) -> None:
    """
    Verify user has access to a project.
    
    Access rules:
    - CEO: Access all projects
    - PM: Access all projects in their organization
    - LEAD: Access all projects for their team
    - Others: Access only if project_id in user['project_ids']
    
    Args:
        user: Current user from JWT token
        project_id: Project ID to check access for
        require_write: If True, checks write permissions (currently same as read)
    
    Raises:
        HTTPException 404: If project not found
        HTTPException 403: If user lacks access to this project
    """
    # CEO has global access
    if has_global_access(user):
        return
    
    # Fetch project to check ownership
    project = await _project_repo.find_by_id(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # PM can access all projects in their org
    if has_org_access(user):
        # In current single-org deployment, PM sees all projects
        # When multi-tenancy is added, check: project["org_id"] == user["org_id"]
        return
    
    # LEAD can access all projects for their team
    role = user.get("role", user.get("organizational_role", "")).upper()
    if role == "LEAD":
        user_team_id = user.get("team_id")
        project_team_id = project.get("team_id")
        if user_team_id and project_team_id == user_team_id:
            return
    
    # Others: check if project is in their assigned projects
    user_project_ids = user.get("project_ids", [])
    if project_id in user_project_ids:
        return
    
    # Access denied
    raise HTTPException(
        status_code=403,
        detail="You don't have access to this project"
    )


async def verify_task_access(
    user: dict,
    task_id: str,
    *,
    require_write: bool = False
) -> str:
    """
    Verify user has access to a task (via its project).
    
    Tasks are accessed through their parent project. User must have access
    to the project that owns the task.
    
    Args:
        user: Current user from JWT token
        task_id: Task ID to check access for
        require_write: If True, checks write permissions (currently same as read)
    
    Returns:
        The task's project_id (for convenience, avoids re-fetching)
    
    Raises:
        HTTPException 404: If task not found
        HTTPException 403: If user lacks access to the task's project
    """
    # CEO has global access
    if has_global_access(user):
        # Still need to verify task exists
        task = await _task_repo.find_by_id(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task.get("project_id", "")
    
    # Fetch task to get its project
    task = await _task_repo.find_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    project_id = task.get("project_id")
    if not project_id:
        # Task has no project - should not happen in normal flow
        raise HTTPException(status_code=500, detail="Task has no associated project")
    
    # Verify access to the task's project
    await verify_project_access(user, project_id, require_write=require_write)
    
    return project_id


async def verify_story_access(
    user: dict,
    story_id: str,
    *,
    require_write: bool = False
) -> str:
    """
    Verify user has access to a story (via its project).
    
    Stories are accessed through their parent project. User must have access
    to the project that owns the story.
    
    Args:
        user: Current user from JWT token
        story_id: Story ID to check access for
        require_write: If True, checks write permissions (currently same as read)
    
    Returns:
        The story's project_id (for convenience, avoids re-fetching)
    
    Raises:
        HTTPException 404: If story not found
        HTTPException 403: If user lacks access to the story's project
    """
    # CEO has global access
    if has_global_access(user):
        # Still need to verify story exists
        story = await _story_repo.find_by_id(story_id)
        if not story:
            raise HTTPException(status_code=404, detail="Story not found")
        return story.get("project_id", "")
    
    # Fetch story to get its project
    story = await _story_repo.find_by_id(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    
    project_id = story.get("project_id")
    if not project_id:
        # Story has no project - should not happen in normal flow
        raise HTTPException(status_code=500, detail="Story has no associated project")
    
    # Verify access to the story's project
    await verify_project_access(user, project_id, require_write=require_write)
    
    return project_id


async def verify_team_access(user: dict, team_id: str) -> None:
    """
    Verify user has access to team data.
    
    Access rules:
    - CEO: Access all teams
    - PM: Access all teams in their org
    - LEAD: Access their own team
    - Others: Access their own team only
    
    Args:
        user: Current user from JWT token
        team_id: Team ID to check access for
    
    Raises:
        HTTPException 403: If user lacks access to this team
    
    Note: Currently does not verify team exists (no TeamRepository).
          In production, should verify team exists first.
    """
    # Check access
    if not has_team_access(user, team_id):
        raise HTTPException(
            status_code=403,
            detail="You don't have access to this team"
        )


async def verify_can_view_user_tasks(user: dict, target_user_id: str) -> None:
    """
    Verify if current user can view another user's tasks.
    
    Access rules:
    - Users can always view their own tasks
    - CEO and PM can view anyone's tasks
    - Others cannot view other users' tasks
    
    Args:
        user: Current user from JWT token
        target_user_id: Employee ID whose tasks are being accessed
    
    Raises:
        HTTPException 403: If user cannot view target user's tasks
    """
    current_user_id = user.get("employee_id", user.get("id", ""))
    
    # Can always view own tasks
    if target_user_id == current_user_id:
        return
    
    # CEO and PM can view anyone's tasks
    if has_org_access(user):
        return
    
    # Others cannot view other users' tasks
    raise HTTPException(
        status_code=403,
        detail="You can only view your own tasks"
    )
