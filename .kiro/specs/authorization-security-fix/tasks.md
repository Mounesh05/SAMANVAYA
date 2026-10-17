# Authorization Security Fix - Implementation Tasks

## Task 1: Create Authorization Helper Module ✅
**File:** `backend/core/authorization.py`

Create authorization helper functions:
- `verify_project_access(user, project_id, require_write=False)`
- `verify_task_access(user, task_id, require_write=False)`
- `verify_story_access(user, story_id, require_write=False)`
- `verify_team_access(user, team_id)`
- `has_global_access(user)` - Check if CEO
- `has_org_access(user)` - Check if CEO/PM
- `has_team_access(user, team_id)` - Check if user can access team

**Acceptance Criteria:**
- [ ] Module created with all helper functions
- [ ] Functions raise HTTPException 403 for unauthorized access
- [ ] Functions raise HTTPException 404 for missing resources
- [ ] CEO role bypasses all checks (global access)
- [ ] PM role accesses all projects in org
- [ ] LEAD role accesses all projects for team
- [ ] Other roles access only assigned projects

---

## Task 2: Add Unit Tests for Authorization Helpers ✅
**File:** `backend/tests/test_authorization.py`

Test all authorization scenarios:
- CEO can access everything
- PM can access org resources
- LEAD can access team resources  
- DEVELOPER can access assigned projects only
- Users cannot access unassigned projects

**Acceptance Criteria:**
- [ ] Test file created with comprehensive coverage
- [ ] All role hierarchy tests pass
- [ ] Project access boundary tests pass
- [ ] Task access boundary tests pass
- [ ] Error handling tests pass (404 vs 403)

---

## Task 3: Fix Tasks Routes - Read Operations ✅
**File:** `backend/api/routes/tasks.py`

Add authorization checks to read routes:
- `GET /tasks/{task_id}` - Add `verify_task_access`
- `GET /tasks/project/{project_id}` - Add `verify_project_access`
- `GET /tasks/assignee/{assignee_id}` - Add self-or-manager check
- `GET /tasks/story/{story_id}` - Add `verify_story_access`
- `GET /tasks/{task_id}/transitions` - Add `verify_task_access`
- `GET /tasks/{task_id}/history` - Add `verify_task_access`

**Acceptance Criteria:**
- [ ] All read routes have authorization checks
- [ ] Users can only access their assigned projects
- [ ] Users can only see their own tasks (or all if PM/LEAD)
- [ ] Existing tests still pass

---

## Task 4: Fix Tasks Routes - Write Operations ✅
**File:** `backend/api/routes/tasks.py`

Add authorization checks to write routes:
- `PATCH /tasks/{task_id}/status` - Add `verify_task_access(require_write=True)`
- `PATCH /tasks/{task_id}/transition` - Add `verify_task_access(require_write=True)`

**Acceptance Criteria:**
- [ ] All write routes have authorization checks
- [ ] Write checks use `require_write=True` flag
- [ ] Users cannot modify tasks in unassigned projects
- [ ] Workflow transitions still work correctly

---

## Task 5: Add Integration Tests for Tasks Routes ⏳
**File:** `backend/tests/test_tasks_authorization.py`

Test task route authorization:
- User A cannot access User B's project tasks
- PM can access all project tasks
- CEO can access all tasks
- Users can only see their own task lists

**Acceptance Criteria:**
- [ ] Test file created with task-specific scenarios
- [ ] Cross-project access denial tests pass
- [ ] Role override tests pass (PM/CEO access)
- [ ] Self-access tests pass

---

## Task 6: Fix Projects Routes ⏳
**File:** `backend/api/routes/projects.py`

Add authorization checks:
- `GET /projects/{project_id}` - Add `verify_project_access`
- `GET /projects/` - Filter by user's project_ids
- `GET /projects/team/{team_id}` - Add `verify_team_access`

**Acceptance Criteria:**
- [ ] All project routes have authorization checks
- [ ] List endpoint filters to user's assigned projects
- [ ] Team project listing checks team membership
- [ ] Existing tests still pass

---

## Task 7: Add Integration Tests for Projects Routes ⏳
**File:** `backend/tests/test_projects_authorization.py`

Test project route authorization:
- User cannot access unassigned projects
- Project list filtered by assignment
- Team project access requires team membership
- PM/CEO see all projects

**Acceptance Criteria:**
- [ ] Test file created with project-specific scenarios
- [ ] Project isolation tests pass
- [ ] List filtering tests pass
- [ ] Team boundary tests pass

---

## Task 8: Fix Comments Routes - Add/List ⏳
**File:** `backend/api/routes/comments.py`

Add parent resource authorization:
- `POST /comments/` - Verify parent resource access before creating
- `GET /comments/{parent_type}/{parent_id}` - Verify parent resource access

**Acceptance Criteria:**
- [ ] Cannot comment on inaccessible tasks/stories
- [ ] Cannot read comments on inaccessible tasks/stories
- [ ] Parent resource verification works for task/story types
- [ ] Existing comment functionality preserved

---

## Task 9: Fix Comments Routes - Edit/Delete ⏳
**File:** `backend/api/routes/comments.py`

Add dual authorization (author AND parent resource):
- `PUT /comments/{comment_id}` - Check author AND parent access
- `DELETE /comments/{comment_id}` - Check author AND parent access

**Acceptance Criteria:**
- [ ] Author check preserved (only owner can edit/delete)
- [ ] Parent resource check added (must have access to parent)
- [ ] Both checks enforced together (AND logic)
- [ ] Error messages clear about which check failed

---

## Task 10: Add Integration Tests for Comments Routes ⏳
**File:** `backend/tests/test_comments_authorization.py`

Test comment authorization:
- Cannot comment on unassigned tasks
- Cannot read comments on unassigned tasks
- Can edit own comments (if parent access maintained)
- Cannot edit others' comments

**Acceptance Criteria:**
- [ ] Test file created with comment-specific scenarios
- [ ] Parent resource boundary tests pass
- [ ] Author + resource dual-check tests pass
- [ ] Cross-project comment isolation verified

---

## Task 11: End-to-End Security Testing ✅

## Task 12: Documentation and Deployment ✅

---

## Progress Tracker

- [x] Task 1: Authorization helper module
- [x] Task 2: Authorization helper tests
- [x] Task 3: Tasks read routes
- [x] Task 4: Tasks write routes
- [x] Task 5: Tasks authorization tests
- [x] Task 6: Projects routes
- [x] Task 7: Projects authorization tests
- [x] Task 8: Comments add/list routes
- [x] Task 9: Comments edit/delete routes
- [x] Task 10: Comments authorization tests
- [x] Task 11: End-to-end security testing
- [x] Task 12: Documentation and deployment

**Total:** 12 tasks (**ALL COMPLETE ✅**)
