# Authorization Security Fix - Technical Design

## Root Cause Analysis

### Current Implementation
Routes perform 2-layer authorization:
1. **Authentication** - Valid JWT token (`get_current_user`)
2. **Permission** - Role has required permission (`require_permission`)

**Missing layer:** Resource ownership verification

```python
# Example vulnerability in tasks.py:
@router.get("/{task_id}")
async def get_task(task_id: str, user: dict = Depends(get_current_user)):
    task = await task_service.get_task(task_id)
    return task  # ❌ No check if user has access to this task's project
```

### Why This Happened
- Permission system focuses on **role capabilities** (what actions a role can do)
- Missing **resource boundaries** (which specific resources a user can access)
- Token has `project_ids` but routes never check it

---

## Solution Architecture

### 3-Layer Authorization Model

```
┌─────────────────────────────────────────────────┐
│ Layer 1: Authentication                         │
│ ✓ Valid JWT token (get_current_user)           │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ Layer 2: Permission Check                       │
│ ✓ Role has required capability                  │
│   (require_permission / require_roles)          │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ Layer 3: Resource Authorization (NEW)           │
│ ✓ User has access to THIS specific resource    │
│   (verify_project_access / verify_task_access)  │
└─────────────────────────────────────────────────┘
```

### Authorization Helper Module

**File:** `backend/core/authorization.py`

```python
from fastapi import HTTPException
from typing import Optional

# Role hierarchy (from highest to lowest access):
# CEO > PM > LEAD > DEVELOPER/QA/DEVOPS

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
    - PM: Access all projects in their org (requires fetching project.org_id)
    - LEAD: Access all projects for their team (requires fetching project.team_id)
    - Others: Access only if project_id in user['project_ids']
    
    Args:
        user: Current user from JWT token
        project_id: Project to check access for
        require_write: If True, checks write permissions (not just read)
    
    Raises:
        HTTPException 403: If user lacks access
        HTTPException 404: If project not found
    """
    pass

async def verify_task_access(
    user: dict,
    task_id: str,
    *,
    require_write: bool = False
) -> str:
    """
    Verify user has access to a task (via its project).
    
    Returns the task's project_id for convenience.
    
    Raises:
        HTTPException 403: If user lacks access
        HTTPException 404: If task not found
    """
    pass

async def verify_story_access(
    user: dict,
    story_id: str,
    *,
    require_write: bool = False
) -> str:
    """
    Verify user has access to a story (via its project).
    
    Returns the story's project_id.
    """
    pass

async def verify_team_access(user: dict, team_id: str) -> None:
    """
    Verify user has access to team data.
    
    Access rules:
    - CEO: Access all teams
    - PM: Access all teams in their org
    - LEAD: Access their own team
    - Others: Access their own team only
    """
    pass

def has_global_access(user: dict) -> bool:
    """Check if user has global access (CEO role)."""
    return user.get("role", "").upper() == "CEO"

def has_org_access(user: dict) -> bool:
    """Check if user has org-wide access (CEO or PM role)."""
    role = user.get("role", "").upper()
    return role in ("CEO", "PM")

def has_team_access(user: dict, team_id: str) -> bool:
    """Check if user has access to a specific team."""
    if has_org_access(user):
        return True
    return user.get("team_id") == team_id
```

---

## Route-Specific Fixes

### 1. Tasks Routes (`backend/api/routes/tasks.py`)

#### `GET /tasks/{task_id}`
```python
# Before:
async def get_task(task_id: str, user: dict = Depends(get_current_user)):
    task = await task_service.get_task(task_id)
    return task

# After:
async def get_task(task_id: str, user: dict = Depends(get_current_user)):
    await verify_task_access(user, task_id)  # ← ADD THIS
    task = await task_service.get_task(task_id)
    return task
```

#### `GET /tasks/project/{project_id}`
```python
# Before:
async def list_project_tasks(project_id: str, user: dict = Depends(get_current_user)):
    tasks = await task_service.get_project_tasks(project_id)
    return tasks

# After:
async def list_project_tasks(project_id: str, user: dict = Depends(get_current_user)):
    await verify_project_access(user, project_id)  # ← ADD THIS
    tasks = await task_service.get_project_tasks(project_id)
    return tasks
```

#### `GET /tasks/assignee/{assignee_id}`
```python
# Before:
async def list_assignee_tasks(assignee_id: str, user: dict = Depends(get_current_user)):
    tasks = await task_service.get_assignee_tasks(assignee_id)
    return tasks

# After:
async def list_assignee_tasks(assignee_id: str, user: dict = Depends(get_current_user)):
    # Users can only see their own tasks unless they're PM/LEAD
    user_id = user.get("employee_id", user.get("id", ""))
    if not has_org_access(user) and assignee_id != user_id:  # ← ADD THIS
        raise HTTPException(status_code=403, detail="Can only view your own tasks")
    
    tasks = await task_service.get_assignee_tasks(assignee_id)
    return tasks
```

#### `PATCH /tasks/{task_id}/status`
```python
# Before:
async def update_task_status(
    task_id: str,
    status: str,
    user: dict = Depends(require_permission(Permission.MOVE_TASK)),
):
    success = await task_service.update_task_status(task_id, status)
    return {"message": "Status updated"}

# After:
async def update_task_status(
    task_id: str,
    status: str,
    user: dict = Depends(require_permission(Permission.MOVE_TASK)),
):
    await verify_task_access(user, task_id, require_write=True)  # ← ADD THIS
    success = await task_service.update_task_status(task_id, status)
    return {"message": "Status updated"}
```

#### `PATCH /tasks/{task_id}/transition`
```python
# Similar pattern - add verify_task_access before transition
```

### 2. Projects Routes (`backend/api/routes/projects.py`)

#### `GET /projects/{project_id}`
```python
# Before:
async def get_project(project_id: str, user: dict = Depends(get_current_user)):
    project = await project_service.get_project(project_id)
    return project

# After:
async def get_project(project_id: str, user: dict = Depends(get_current_user)):
    await verify_project_access(user, project_id)  # ← ADD THIS
    project = await project_service.get_project(project_id)
    return project
```

#### `GET /projects/?org_id=X`
```python
# Before:
async def list_projects(org_id: str, user: dict = Depends(get_current_user)):
    projects = await project_service.get_active_projects(org_id)
    return projects

# After:
async def list_projects(org_id: str, user: dict = Depends(get_current_user)):
    # Don't trust org_id param - filter by user's actual project access
    if has_global_access(user):  # ← ADD THIS
        # CEO sees all
        projects = await project_service.get_active_projects(org_id)
    elif has_org_access(user):
        # PM sees all in their org
        projects = await project_service.get_active_projects(org_id)
    else:
        # Others see only their assigned projects
        all_projects = await project_service.get_active_projects(org_id)
        user_project_ids = set(user.get("project_ids", []))
        projects = [p for p in all_projects if p.get("id") in user_project_ids]
    
    return projects
```

#### `GET /projects/team/{team_id}`
```python
# Before:
async def list_team_projects(team_id: str, user: dict = Depends(get_current_user)):
    projects = await project_service.get_team_projects(team_id)
    return projects

# After:
async def list_team_projects(team_id: str, user: dict = Depends(get_current_user)):
    await verify_team_access(user, team_id)  # ← ADD THIS
    projects = await project_service.get_team_projects(team_id)
    return projects
```

### 3. Comments Routes (`backend/api/routes/comments.py`)

Comments are trickier because they reference parent resources (task/story/PR).

#### `POST /comments/`
```python
# Before:
async def add_comment(body: CommentCreate, user: dict = Depends(get_current_user)):
    comment = {
        "parent_type": body.parent_type,
        "parent_id": body.parent_id,
        # ... create comment
    }
    await comment_repo.insert(comment)
    return comment

# After:
async def add_comment(body: CommentCreate, user: dict = Depends(get_current_user)):
    # Verify access to parent resource
    if body.parent_type == "task":  # ← ADD THIS
        await verify_task_access(user, body.parent_id)
    elif body.parent_type == "story":
        await verify_story_access(user, body.parent_id)
    # PR access check would go here if implemented
    
    comment = {
        "parent_type": body.parent_type,
        "parent_id": body.parent_id,
        # ... create comment
    }
    await comment_repo.insert(comment)
    return comment
```

#### `GET /comments/{parent_type}/{parent_id}`
```python
# Similar - verify parent resource access before returning comments
```

#### `PUT /comments/{comment_id}` and `DELETE /comments/{comment_id}`
```python
# Before:
async def edit_comment(comment_id: str, body: CommentUpdate, user: dict = Depends(get_current_user)):
    comment = await comment_repo.find_by_id(comment_id)
    if comment["author_id"] != user_id:  # Only checks author
        raise HTTPException(status_code=403)
    # ... update comment

# After:
async def edit_comment(comment_id: str, body: CommentUpdate, user: dict = Depends(get_current_user)):
    comment = await comment_repo.find_by_id(comment_id)
    
    # Check author (existing)
    user_id = user.get("employee_id", user.get("id", ""))
    if comment["author_id"] != user_id:
        raise HTTPException(status_code=403, detail="You can only edit your own comments")
    
    # Check parent resource access (NEW)
    if comment["parent_type"] == "task":  # ← ADD THIS
        await verify_task_access(user, comment["parent_id"])
    elif comment["parent_type"] == "story":
        await verify_story_access(user, comment["parent_id"])
    
    # ... update comment
```

---

## Data Access Patterns

### Fetching Related Resources

Authorization helpers need to fetch related data:

```python
# verify_task_access needs to:
# 1. Fetch task by ID
# 2. Get task.project_id
# 3. Check if user has access to that project

# This requires accessing repositories:
from repositories.task_repository import TaskRepository
from repositories.project_repository import ProjectRepository
```

### Caching Considerations

For performance, consider caching project access checks within a request:
- User's project_ids is already in JWT (no fetch needed)
- Project details might need caching if checked multiple times per request
- For MVP, direct DB lookups are acceptable

---

## Error Handling Strategy

### HTTP Status Codes
- **404 Not Found**: Resource doesn't exist
- **403 Forbidden**: Resource exists but user lacks access

### Security Consideration
Returning 403 instead of 404 reveals that a resource exists. Two approaches:

**Approach A (More Secure):**
```python
# Always return 404 for unauthorized access
# Attacker can't enumerate resource IDs
raise HTTPException(status_code=404, detail="Task not found")
```

**Approach B (More User-Friendly):**
```python
# Return 403 with clear message
# Users understand why they can't access
raise HTTPException(status_code=403, detail="You don't have access to this task")
```

**Decision:** Use Approach B - the system already leaks resource existence through other routes, and clear error messages improve UX.

---

## Testing Strategy

### Unit Tests
Test each authorization helper function:
- CEO can access everything
- PM can access org resources
- LEAD can access team resources
- DEVELOPER can only access assigned projects
- Users cannot access other projects

### Integration Tests
Test each route with different user roles:
- User in Project A tries to access Project B task (should fail)
- PM tries to access any project (should succeed)
- CEO tries to access any resource (should succeed)

### Security Test Cases
```python
def test_task_access_isolation():
    """Users in different projects cannot see each other's tasks."""
    user_a = create_user(project_ids=["PRJ-A"])
    user_b = create_user(project_ids=["PRJ-B"])
    task_a = create_task(project_id="PRJ-A")
    
    # User A can access their own task
    response = get_task(task_a.id, user=user_a)
    assert response.status_code == 200
    
    # User B cannot access User A's task
    response = get_task(task_a.id, user=user_b)
    assert response.status_code == 403
```

---

## Rollback Plan

If issues arise after deployment:

1. **Feature flag**: Add `ENABLE_RESOURCE_AUTHORIZATION=true` env var
2. **Gradual rollout**: Enable per route type (tasks first, then projects, then comments)
3. **Monitoring**: Track 403 errors to detect over-blocking
4. **Quick revert**: Remove authorization checks, deploy previous version

---

## Performance Impact

### Estimated Query Overhead
- **Tasks routes**: +1 query to fetch task.project_id
- **Projects routes**: No extra queries (checks user.project_ids from JWT)
- **Comments routes**: +1 query to fetch parent resource

### Optimization Opportunities (Future)
- Add indexes on `tasks.project_id` (likely already exists)
- Cache project membership within request context
- Denormalize frequently-checked fields

---

## Migration Path

No database migration needed! This is purely application-level authorization logic.

**Deployment steps:**
1. Deploy authorization.py helper module
2. Deploy updated routes (no downtime, backward compatible)
3. Monitor 403 error rates
4. Document new authorization behavior for team

---

## Future Enhancements

After this fix is stable, consider:

1. **Multi-tenancy**: Add org_id to users and all resources
2. **Fine-grained permissions**: Per-project roles (viewer, contributor, admin)
3. **Audit logging**: Log all authorization failures for security monitoring
4. **Rate limiting**: Add per-user API rate limits
5. **Field-level authorization**: Hide sensitive fields based on role
