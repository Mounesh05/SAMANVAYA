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
from core.permissions import Permission, get_user_permissions
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
    - CEO/PM/HR/admin: Access all teams
    - Others: Access only their own team
    
    Args:
        user: Current user from JWT token
        team_id: Team ID to check access for
    
    Returns:
        True if user can access the team
    """
    role = user.get("role", user.get("organizational_role", "")).upper()
    if has_org_access(user) or role == "HR" or user.get("is_admin", False):
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
    - CEO: Access all projects (read and write)
    - PM: Access all projects in their organization (read and write)
    - LEAD: Access all projects for their team (read and write)
    - Others: Access only if project_id in user['project_ids']
    
    Args:
        user: Current user from JWT token
        project_id: Project ID to check access for
        require_write: If True, blocks non-LEAD developers from write operations.
                      CEO/PM/LEAD roles have implicit write access to their scope.
                      Note: The authorization model does not track granular write
                      permissions; this flag enforces the baseline policy that only
                      LEADs and above can modify projects.
    
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
        if require_write:
            # CEOs and PMs always have write access
            return
        return
    
    # LEAD can access all projects for their team
    role = user.get("role", user.get("organizational_role", "")).upper()
    if role == "LEAD":
        user_team_id = user.get("team_id")
        project_team_id = project.get("team_id")
        if user_team_id and project_team_id == user_team_id:
            if require_write:
                # LEADs have write access to their team's projects
                return
            return
    
    # Team members can read projects assigned to their team. This keeps
    # project visibility aligned with the team membership used elsewhere.
    if (
        not require_write
        and user.get("team_id")
        and project.get("team_id") == user.get("team_id")
    ):
        return

    # Others: check if project is in their assigned projects
    user_project_ids = user.get("project_ids", [])
    if project_id in user_project_ids:
        if require_write:
            # LEAD role has write access to assigned projects
            # Non-lead roles don't have write access
            if role != "LEAD":
                raise HTTPException(
                    status_code=403,
                    detail="You don't have write access to this project"
                )
        return
    
    # Access denied
    raise HTTPException(
        status_code=403,
        detail="You don't have access to this project"
    )


async def verify_work_item_creation(user: dict, project_id: str, assignee_id: str | None) -> bool:
    """
    Authorize creating a task or story in a project.

    Returns True for project managers (write access to the project), who may
    assign the item to anyone. Contributors (read access to an assigned or team
    project, e.g. DEVELOPER) may create items only for themselves; the caller
    decides what a contributor-created item looks like (e.g. a draft story).

    Raises:
        HTTPException 403: outside the project, or assigning to someone else
        HTTPException 404: project not found
    """
    try:
        await verify_project_access(user, project_id, require_write=True)
        return True
    except HTTPException as error:
        if error.status_code != 403:
            raise
    # Contributor path: read access is required (assigned or team project).
    await verify_project_access(user, project_id)
    if assignee_id != user.get("employee_id"):
        raise HTTPException(
            status_code=403,
            detail="You can only create work items assigned to yourself",
        )
    return False


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


async def verify_task_status_update_access(user: dict, task_id: str) -> str:
    """Allow management roles or an assignee in an engineering role to update it."""
    role = user.get("role", user.get("organizational_role", "")).upper()
    task = await _task_repo.find_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    employee_id = user.get("employee_id", user.get("id"))
    if role in {"DEVELOPER", "QA", "DEVOPS"}:
        if task.get("assignee_id") != employee_id:
            raise HTTPException(
                status_code=403,
                detail="You can only update tasks assigned to you",
            )
        return await verify_task_access(user, task_id)

    if role not in {"CEO", "PM", "LEAD"}:
        raise HTTPException(status_code=403, detail="Insufficient task update permissions")
    return await verify_task_access(user, task_id, require_write=True)


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


async def verify_story_status_update_access(user: dict, story_id: str, new_status: str) -> dict:
    """
    Authorize changing a story's status (Stories page and board drag-and-drop).

    - A DRAFT story can only be accepted into "todo", and only by a backlog
      owner: ACCEPT_STORY permission plus write access to the project.
    - Developers can move only stories assigned to them.
    - Everyone else keeps project-level access, as before.

    Returns the story document.
    """
    project_id = await verify_story_access(user, story_id)
    story = await _story_repo.find_by_id(story_id)
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    if story.get("status") == "draft":
        permissions = get_user_permissions(
            user.get("role", user.get("organizational_role", "")),
            user.get("is_admin", False),
            user.get("designation"),
        )
        if Permission.ACCEPT_STORY not in permissions:
            raise HTTPException(status_code=403, detail="Only a Lead or PM can accept a draft story")
        await verify_project_access(user, project_id, require_write=True)
        if new_status != "todo":
            raise HTTPException(status_code=409, detail="A draft story must be accepted into todo first")
    elif (
        (user.get("role") or user.get("organizational_role") or "").upper() == "DEVELOPER"
        and story.get("assignee_id") != user.get("employee_id")
    ):
        raise HTTPException(status_code=403, detail="You can only update stories assigned to you")
    return story


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


async def get_accessible_project_ids(user: dict) -> list[str]:
    """
    Get list of project IDs that the user can access.
    
    Access rules:
    - CEO: All projects in database
    - PM: All projects in their organization (currently all projects)
    - LEAD: All projects for their team
    - Others: Only projects they're assigned to
    
    Args:
        user: Current user from JWT token
    
    Returns:
        List of project IDs the user can access
    """
    # CEO has global access - fetch all projects
    if has_global_access(user):
        all_projects = await _project_repo.find_all({})
        return [p.get("id", p.get("_id", "")) for p in all_projects]
    
    # PM can access all projects in their org
    # In current single-org deployment, PM sees all projects
    role = user.get("role", user.get("organizational_role", "")).upper()
    if has_org_access(user):
        all_projects = await _project_repo.find_all({})
        return [p.get("id", p.get("_id", "")) for p in all_projects]
    
    # LEAD can access all projects for their team
    if role == "LEAD":
        user_team_id = user.get("team_id")
        if user_team_id:
            team_projects = await _project_repo.find_all({"team_id": user_team_id})
            return [p.get("id", p.get("_id", "")) for p in team_projects]
    
    # Others: return only assigned projects
    return user.get("project_ids", [])
