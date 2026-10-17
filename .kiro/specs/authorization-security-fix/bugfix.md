# Authorization Security Fix - Bug Requirements

## Context
Security audit revealed resource-level authorization gaps. Users can access/modify resources they don't own because routes only check authentication (valid token) and permissions (role-based), but never verify the user has access to the specific resource.

## Scope
Fix authorization in:
1. **tasks.py** - Task resource access
2. **projects.py** - Project resource access  
3. **comments.py** - Comment resource access

## Current Architecture Constraints
- Single-organization deployment (no multi-tenancy yet)
- Users have `project_ids: List[str]` in JWT token
- Projects have `org_id` field
- Tasks have `project_id` field
- Comments have `parent_type` and `parent_id` (task/story/PR)

---

## DEFECT - What is broken

### D1. Task Routes Allow Unauthorized Access
**Route:** `GET /tasks/{task_id}`  
**Current:** Any authenticated user can read any task  
**Expected:** Only users assigned to the task's project can read it

**Route:** `GET /tasks/project/{project_id}`  
**Current:** Any authenticated user can list any project's tasks  
**Expected:** Only users assigned to that project can list its tasks

**Route:** `PATCH /tasks/{task_id}/status`  
**Current:** Any user with MOVE_TASK permission can modify any task  
**Expected:** Only users assigned to the task's project can modify it

**Route:** `PATCH /tasks/{task_id}/transition`  
**Current:** Any user with TRANSITION_TASK permission can transition any task  
**Expected:** Only users assigned to the task's project can transition it

**Route:** `GET /tasks/assignee/{assignee_id}`  
**Current:** Any authenticated user can see any user's tasks  
**Expected:** Users can only see their own tasks (or all if they're PM/LEAD)

**Route:** `GET /tasks/story/{story_id}`  
**Current:** Any authenticated user can see any story's tasks  
**Expected:** Only users assigned to the story's project can see its tasks

### D2. Project Routes Allow Unauthorized Access
**Route:** `GET /projects/{project_id}`  
**Current:** Any authenticated user can read any project  
**Expected:** Only users assigned to that project can read it

**Route:** `GET /projects/?org_id=X`  
**Current:** Any authenticated user can list any org's projects  
**Expected:** Users can only list projects they're assigned to

**Route:** `GET /projects/team/{team_id}`  
**Current:** Any authenticated user can list any team's projects  
**Expected:** Only users on that team (or PM/CEO) can list team projects

### D3. Comment Routes Allow Unauthorized Access
**Route:** `POST /comments/`  
**Current:** Any authenticated user can comment on any task/story/PR  
**Expected:** Only users with access to the parent resource can comment

**Route:** `GET /comments/{parent_type}/{parent_id}`  
**Current:** Any authenticated user can read any comments  
**Expected:** Only users with access to the parent resource can read comments

**Route:** `PUT /comments/{comment_id}`  
**Current:** Only author check, no parent resource check  
**Expected:** User must be author AND have access to parent resource

**Route:** `DELETE /comments/{comment_id}`  
**Current:** Only author check, no parent resource check  
**Expected:** User must be author AND have access to parent resource

---

## CORRECT - What works and must not break

### C1. Authentication System
✅ JWT token validation works correctly  
✅ Token includes `employee_id`, `role`, `project_ids`, `team_id`  
✅ `get_current_user` dependency correctly decodes tokens

### C2. Permission System
✅ Role-based permissions work correctly (CEO, PM, LEAD, etc.)  
✅ `require_permission()` correctly checks role permissions  
✅ Permission enum defines appropriate permissions per role

### C3. Create Operations
✅ `POST /tasks/` requires CREATE_TASK permission - keep this  
✅ `POST /projects/` requires CREATE_PROJECT permission - keep this  
✅ New resources are created with proper ownership

### C4. Business Logic
✅ Task workflow transitions work correctly  
✅ Activity logging for comments works  
✅ Task/project data models are correct

### C5. Admin Overrides
✅ CEO role can access all resources (global visibility)  
✅ PM role can access all projects in their org  
✅ LEAD role can access all resources in their team

---

## PRESERVE - What must stay unchanged

### P1. API Contract
- Route paths and methods stay the same
- Request/response models stay the same
- HTTP status codes stay the same

### P2. Role Hierarchy
- CEO has global access (across all orgs/projects)
- PM has org-wide access (all projects in their org)
- LEAD has team-wide access (all projects for their team)
- DEVELOPER/QA/DEVOPS have project-level access (only assigned projects)

### P3. Backward Compatibility
- Existing clients must work without changes
- Frontend doesn't need updates
- Existing tests for business logic stay passing

### P4. Performance
- Don't add N+1 queries
- Use existing indexes where possible
- Keep response times reasonable

---

## Solution Strategy

### Authorization Helper Functions
Create `backend/core/authorization.py` with:
- `verify_project_access(user, project_id)` - Check if user can access project
- `verify_task_access(user, task_id)` - Check if user can access task
- `verify_story_access(user, story_id)` - Check if user can access story
- `verify_team_access(user, team_id)` - Check if user can access team

### Authorization Rules
1. **CEO role:** Access everything (no checks needed)
2. **PM role:** Access all projects in their org
3. **LEAD role:** Access all projects for their team
4. **Other roles:** Access only projects in their `project_ids` list

### Implementation Order
1. Create authorization helper module
2. Fix tasks.py routes (most critical - handles work items)
3. Fix projects.py routes (second priority)
4. Fix comments.py routes (depends on parent resource access)
5. Add integration tests for each route

---

## Verification Criteria

### Security Tests Pass
- ✅ User in Project A cannot read tasks from Project B
- ✅ User in Project A cannot modify tasks in Project B
- ✅ User in Team A cannot read projects from Team B
- ✅ User cannot comment on tasks they don't have access to
- ✅ User cannot read comments on tasks they don't have access to

### Role Override Tests Pass
- ✅ CEO can access all resources
- ✅ PM can access all projects in their org
- ✅ LEAD can access all projects for their team

### Existing Functionality Preserved
- ✅ All existing unit tests still pass
- ✅ Workflow transitions still work
- ✅ Activity logging still works
- ✅ Comment edit/delete still checks author

---

## Out of Scope
- Multi-tenancy architecture (org_id in users/JWT)
- Adding org_id to resources that don't have it
- Changing data models or database schema
- Adding new API endpoints
- Rate limiting or API throttling
