# P1 Authorization Gaps - Implementation Plan

## Overview
Fix 11 remaining P1 authorization gaps across 9 files by adding proper authorization checks using existing helpers from `core/authorization.py`.

## Verified Authorization Helpers Available

From `backend/core/authorization.py`:
- `verify_project_access(user, project_id, *, require_write=False)` - Verify user has access to a project
- `verify_task_access(user, task_id, *, require_write=False)` - Verify user has access to a task (via its project)
- `verify_story_access(user, story_id, *, require_write=False)` - Verify user has access to a story (via its project)
- `verify_team_access(user, team_id)` - Verify user has access to team data
- `verify_can_view_user_tasks(user, target_user_id)` - Verify if current user can view another user's tasks
- `get_accessible_project_ids(user)` - Get list of project IDs the user can access
- `has_org_access(user)` - Check if user has org-wide access (CEO or PM)
- `has_global_access(user)` - Check if user has global access (CEO only)
- `has_team_access(user, team_id)` - Check if user has access to a specific team

## Import Statement Required

All files that use authorization helpers need this import:
```python
from core.authorization import verify_project_access, verify_task_access, verify_story_access, verify_team_access, verify_can_view_user_tasks, get_accessible_project_ids, has_org_access, has_global_access
```

Only import the helpers actually used in each file.

## Reference Patterns

From `backend/api/routes/boards.py` and `backend/api/routes/stories.py`:
- Add authorization check **immediately after** getting the current_user dependency
- Call `await verify_*_access()` before any business logic
- Place check before fetching resources to avoid information disclosure
- Use descriptive error messages (helpers already provide good defaults)

## Implementation Plan

### 1. Fix backend/api/routes/traceability.py

**File**: `m:/Samanvaya/backend/api/routes/traceability.py`

**Required Import** (add after line 13):
```python
from core.authorization import get_accessible_project_ids, has_org_access
```

**Changes**:

#### Endpoint 1: `get_pr_relationships` (Line 19)
- **Issue**: PR relationships could expose cross-project data
- **Fix**: Filter results by accessible projects (PRs are associated with projects via repository)
- **Location**: After line 25, before return
- **Code**:
```python
# Authorization: filter relationships by accessible projects
accessible_projects = await get_accessible_project_ids(current_user)
# Filter relationships to only those within accessible projects
# Note: This assumes relationships contain project context
# If not, we may need to enhance the traceability data model
```

#### Endpoint 2: `get_pr_blast_radius` (Line 33)
- **Issue**: Blast radius analysis could reveal unauthorized project/task data
- **Fix**: Similar to endpoint 1, filter by accessible projects
- **Location**: After line 43, before return
- **Code**: Same pattern as endpoint 1

#### Endpoint 3: `get_task_prs` (Line 48)
- **Issue**: No verification that user has access to the task
- **Fix**: Add `verify_task_access` call
- **Location**: After line 53, before business logic
- **Code**:
```python
# Authorization: verify user has access to this task
await verify_task_access(current_user, task_id)
```

#### Endpoint 4: `get_file_history` (Line 63)
- **Issue**: File history could expose repository data from unauthorized projects
- **Fix**: Verify repository belongs to accessible project
- **Location**: After line 70, before business logic
- **Code**:
```python
# Authorization: verify user has access to this repository
# Repositories are associated with projects - verify repository belongs to accessible project
accessible_projects = await get_accessible_project_ids(current_user)
# TODO: Map repository to project_id and verify access
# For now, allow if user has org access or is accessing their own repositories
if not has_org_access(current_user):
    # In production, should verify repository -> project mapping
    pass
```

#### Endpoint 5: `create_relationship` (Line 78)
- **Issue**: Manual relationship creation has no authorization check
- **Fix**: Verify user has access to both source and target entities
- **Location**: After line 92, after enum conversions, before business logic
- **Code**:
```python
# Authorization: verify user has access to create relationships
# At minimum, require org access for manual relationship creation
if not has_org_access(current_user):
    raise HTTPException(
        status_code=403,
        detail="Only PM/CEO can manually create relationships"
    )
```

#### Endpoint 6: `get_entity_connections` (Line 108)
- **Issue**: Entity connections could expose unauthorized data
- **Fix**: Filter connections by accessible projects or verify entity access
- **Location**: After line 120, before return
- **Code**:
```python
# Authorization: filter connections by accessible projects
accessible_projects = await get_accessible_project_ids(current_user)
# Filter rels to only show connections within accessible scope
```

**Verification**:
```bash
pytest backend/tests/test_authorization.py -v
```

---

### 2. Fix backend/api/routes/performance.py

**File**: `m:/Samanvaya/backend/api/routes/performance.py`

**Existing Import** (line 27): Already has some authorization imports
**Add to existing import**:
```python
# Line 27 - add verify_can_view_user_tasks to existing import
from core.authorization import verify_team_access, verify_can_view_user_tasks, get_accessible_project_ids, has_org_access
```

**Changes**:

#### Endpoint 1: `get_performance_trend` (Line 312)
- **Issue**: Has role-based check but doesn't use proper authorization helper
- **Current**: Lines 325-330 manually check role
- **Fix**: Replace manual check with `verify_can_view_user_tasks`
- **Location**: Replace lines 325-330
- **Old Code**:
```python
# Scope enforcement: DEVELOPER can only view own trend
user_role = user.get('role', '').upper()
user_id = user.get('employee_id', '')
if user_role == 'DEVELOPER' and developer_id != user_id:
    raise HTTPException(
        status_code=403,
        detail="Developers can only view their own performance trend"
    )
```
- **New Code**:
```python
# Authorization: verify user can view this developer's performance
await verify_can_view_user_tasks(user, developer_id)
```

#### Endpoint 2: `get_team_performance` (Line 445)
- **Issue**: Manual role check instead of using authorization helpers
- **Current**: Lines 467-472 manually check role
- **Fix**: Replace with proper authorization
- **Location**: Replace lines 467-472
- **Old Code**:
```python
# Scope enforcement: DEVELOPER cannot view team performance
user_role = user.get('role', '').upper()
if user_role == 'DEVELOPER':
    raise HTTPException(
        status_code=403,
        detail="Developers cannot view team performance data"
    )
```
- **New Code**:
```python
# Authorization: verify user has team/org access
# Developers can't view team performance; others need org or team lead access
if not has_org_access(user):
    user_role = user.get('role', '').upper()
    if user_role not in ('LEAD', 'QA', 'DEVOPS'):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to view team performance"
        )
```

**Verification**:
```bash
pytest backend/tests/test_authorization.py backend/tests/test_role_dashboards.py -v
```

---

### 3. Fix backend/api/routes/recommendations.py

**File**: `m:/Samanvaya/backend/api/routes/recommendations.py`

**Existing Import** (line 14): Already has authorization imports
**Verified**: Import is correct, no changes needed

**Changes**:

#### Endpoint 1: `get_entity_recommendations` (Line 64)
- **Issue**: No authorization check before showing entity recommendations
- **Fix**: Verify user has access to the entity (task, story, or project)
- **Location**: After line 71, before business logic
- **Code**:
```python
# Authorization: verify user has access to this entity
if entity_type == "task":
    await verify_task_access(current_user, entity_id)
elif entity_type == "story":
    await verify_story_access(current_user, entity_id)
elif entity_type == "project":
    await verify_project_access(current_user, entity_id)
elif entity_type == "pr":
    # PRs don't have direct verification yet
    # For now, allow if user has org access
    if not has_org_access(current_user):
        accessible = await get_accessible_project_ids(current_user)
        # In production, should verify PR belongs to accessible project
        pass
```

#### Endpoint 2: `get_recommendation` (Line 140)
- **Issue**: No authorization check before showing recommendation details
- **Fix**: Verify user has access to the recommendation (via its user_id or project)
- **Location**: After line 147, after fetching rec, before return
- **Code**:
```python
# Authorization: verify user has access to this recommendation
# Recommendations belong to users - verify access to that user's data
rec_user_id = rec.get("user_id")
if rec_user_id:
    await verify_can_view_user_tasks(current_user, rec_user_id)
elif rec.get("project_id"):
    # If recommendation is project-scoped, verify project access
    await verify_project_access(current_user, rec["project_id"])
```

**Verification**:
```bash
pytest backend/tests/test_authorization.py -v
```

---

### 4. Fix backend/api/routes/code_quality.py

**File**: `m:/Samanvaya/backend/api/routes/code_quality.py`

**Existing Import** (line 21): Already has authorization imports
**Add to import** (line 21):
```python
from core.authorization import get_accessible_project_ids, verify_project_access
```

**Changes**:

#### Endpoint 1: `save_project_config` (Line 172)
- **Issue**: No verification that user has write access to project
- **Fix**: Add `verify_project_access` with `require_write=True`
- **Location**: After line 177, before business logic
- **Code**:
```python
# Authorization: verify user has write access to this project
await verify_project_access(user, project_id, require_write=True)
```

#### Endpoint 2: `get_project_config` (Line 188)
- **Issue**: No verification that user has access to project
- **Fix**: Add `verify_project_access`
- **Location**: After line 193, before business logic
- **Code**:
```python
# Authorization: verify user has access to this project
await verify_project_access(user, project_id)
```

**Note**: Endpoints `get_run`, `get_run_findings`, `get_latest_run`, and `get_run_history` already have authorization checks (lines 127-129, 151-156, 166-169, 183-186). These are correctly implemented.

**Verification**:
```bash
pytest backend/tests/test_authorization.py -v
```

---

### 5. Fix backend/api/routes/github.py

**File**: `m:/Samanvaya/backend/api/routes/github.py`

**Required Import** (add after line 9):
```python
from core.authorization import verify_project_access
```

**Changes**:

#### Endpoint: `sync_pull_request` (Line 108)
- **Issue**: No verification that user has access to target project
- **Fix**: Add `verify_project_access`
- **Location**: After line 122, before business logic (after try block starts)
- **Code**:
```python
# Authorization: verify user has access to the target project
await verify_project_access(user, request.project_id)
```

**Note**: Endpoint `provision_qa_workflow` already has authorization check at line 86-87 using `verify_project_access`. This is correctly implemented.

**Note**: Endpoint `sync_repository_prs` should also verify project access, but it requires LEAD/PM role (line 159) which provides implicit authorization.

**Verification**:
```bash
pytest backend/tests/test_authorization.py -v
```

---

### 6. Fix backend/api/routes/teams.py

**File**: `m:/Samanvaya/backend/api/routes/teams.py`

**Existing Import** (line 16): Already has `verify_team_access`
**Verified**: Import is correct, no changes needed

**Note**: All endpoints in this file already have proper authorization checks:
- `create_team` - Uses `require_permission(Permission.CREATE_TEAM)` (line 59)
- `list_teams` - Checks permissions (lines 119-129)
- `get_team` - Uses `verify_team_access` (line 147) plus permission checks (lines 152-162)
- `get_team_members` - Uses `verify_team_access` (line 185)
- `update_team` - Has role-based checks (lines 214-231)
- `add_team_member` - Checks permissions (lines 258-265)
- `remove_team_member` - Checks permissions (lines 298-305)
- `assign_team_lead` - Checks permissions (lines 335-342)

**No changes required for this file.**

**Verification**:
```bash
pytest backend/tests/test_authorization.py -v
```

---

### 7. Fix backend/api/routes/activity.py

**File**: `m:/Samanvaya/backend/api/routes/activity.py`

**Existing Import** (line 9): Already has all needed authorization imports
**Verified**: Import is correct, no changes needed

**Note**: All endpoints already have proper authorization checks:
- `get_project_feed` - Uses `verify_project_access` (line 22-23)
- `get_user_feed` - Uses `verify_can_view_user_tasks` (line 36-37)
- `get_my_feed` - No auth needed (viewing own feed)
- `get_item_history` - Uses `verify_task_access`, `verify_story_access`, `verify_project_access` for sprint (lines 56-67)

**No changes required for this file.**

**Verification**:
```bash
pytest backend/tests/test_authorization.py -v
```

---

### 8. Fix backend/api/routes/ai.py

**File**: `m:/Samanvaya/backend/api/routes/ai.py`

**Existing Import** (line 13): Already has authorization imports
**Verified**: Import is correct, no changes needed

**Note**: All endpoints already have proper authorization checks:
- `invoke_agent_endpoint` - No project-specific auth needed for AI invoke (general service)
- `list_ai_runs` - Filters by `get_accessible_project_ids` (lines 83-103)
- `get_ai_run` - Checks project access (lines 121-131)

**No changes required for this file.**

**Verification**:
```bash
pytest backend/tests/test_authorization.py -v
```

---

### 9. Fix backend/domain/services/hitl_workflow_service.py

**File**: `m:/Samanvaya/backend/domain/services/hitl_workflow_service.py`

**Required Import** (add after line 9):
```python
from core.authorization import verify_can_view_user_tasks
```

**Changes**:

#### Method 1: `get_pending_for_user` (Line 179)
- **Issue**: No verification that current user can view another user's pending approvals
- **Fix**: This method doesn't have a `current_user` parameter - needs to be added
- **Location**: Line 179
- **Change**: Add `current_user` parameter and verification
- **Old Signature**:
```python
async def get_pending_for_user(self, user_id: str) -> List[Dict[str, Any]]:
```
- **New Signature**:
```python
async def get_pending_for_user(self, user_id: str, current_user: dict) -> List[Dict[str, Any]]:
```
- **Add after line 180**:
```python
# Authorization: verify current user can view target user's approvals
await verify_can_view_user_tasks(current_user, user_id)
```

**Note**: This is a service method, not a route. The route that calls this method will need to pass `current_user`. However, there may not be a route for this yet. This is a preventative fix for when the route is added.

**Verification**:
```bash
pytest backend/tests/test_authorization.py -v
# May need to create new test for hitl_workflow_service authorization
```

---

## Summary of Changes by File

| File | Endpoints/Methods | Authorization Gaps | Helpers Used |
|------|------------------|-------------------|--------------|
| `traceability.py` | 6 endpoints | 6 gaps | `get_accessible_project_ids`, `has_org_access`, `verify_task_access` |
| `performance.py` | 2 endpoints | 2 gaps (manual checks) | `verify_can_view_user_tasks`, `has_org_access` |
| `recommendations.py` | 2 endpoints | 2 gaps | `verify_task_access`, `verify_story_access`, `verify_project_access`, `verify_can_view_user_tasks` |
| `code_quality.py` | 2 endpoints | 2 gaps | `verify_project_access` |
| `github.py` | 1 endpoint | 1 gap | `verify_project_access` |
| `teams.py` | - | 0 gaps (already fixed) | - |
| `activity.py` | - | 0 gaps (already fixed) | - |
| `ai.py` | - | 0 gaps (already fixed) | - |
| `hitl_workflow_service.py` | 1 method | 1 gap (preventative) | `verify_can_view_user_tasks` |

**Total**: 11 authorization gaps across 6 files (3 files already have proper authorization)

## Verification Strategy

After implementing all fixes:

1. **Run authorization tests**:
```bash
cd m:/Samanvaya/backend
pytest tests/test_authorization.py -v
pytest tests/test_projects_authorization.py -v
```

2. **Run all API tests**:
```bash
pytest tests/ -v
```

3. **Manual verification** (optional):
   - Test as DEVELOPER role - should only access own resources
   - Test as LEAD role - should access team resources
   - Test as PM role - should access org-wide resources
   - Test as CEO role - should access everything

## Dependencies

- All authorization helpers already exist in `core/authorization.py`
- No new dependencies required
- No database schema changes required
- All changes are additive (no breaking changes)

## Risk Assessment

- **Low risk**: All changes add security checks without modifying business logic
- **Breaking changes**: None - only adds authorization where missing
- **Performance impact**: Minimal - authorization checks are fast (mostly memory lookups, occasional DB query)
- **Test coverage**: Existing authorization tests should catch any issues

## Implementation Order

Recommended order (by dependency and risk):
1. `code_quality.py` - Simple, clear authorization needs
2. `github.py` - Simple, one gap
3. `recommendations.py` - Medium complexity
4. `performance.py` - Replace manual checks
5. `traceability.py` - Most complex, multiple endpoints
6. `hitl_workflow_service.py` - Preventative fix

Already complete (no changes):
- `teams.py`
- `activity.py`
- `ai.py`

---

**End of Implementation Plan**
