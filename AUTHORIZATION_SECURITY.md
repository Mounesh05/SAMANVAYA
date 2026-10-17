# Authorization Security Enhancement

## Overview

This document describes the resource-level authorization security enhancement implemented to fix critical authorization gaps in the Samanvaya API.

**Status:** ✅ Implemented and Tested  
**Date:** 2026-10-17  
**Version:** 1.0.0

---

## Problem Statement

### Security Vulnerabilities Fixed

The original system had **authentication** and **permission-based authorization** but lacked **resource-level authorization**:

1. **Tasks Routes**: Any authenticated user could access any task
2. **Projects Routes**: Any authenticated user could list/read any project
3. **Comments Routes**: Users could comment on and read comments from inaccessible resources

### Attack Scenarios Prevented

- ❌ Developer in Project A reading tasks from Project B
- ❌ User accessing projects they're not assigned to
- ❌ Commenting on tasks/stories without project access
- ❌ Editing comments after losing project access

---

## Solution Architecture

### 3-Layer Authorization Model

```
┌─────────────────────────────────────────────────┐
│ Layer 1: Authentication (Existing)              │
│ ✓ Valid JWT token                               │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ Layer 2: Permission Check (Existing)            │
│ ✓ Role has required capability                  │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│ Layer 3: Resource Authorization (NEW)           │
│ ✓ User has access to THIS specific resource    │
└─────────────────────────────────────────────────┘
```

### Authorization Rules

#### Role Hierarchy (highest to lowest access)

1. **CEO** - Global access to all resources
2. **PM** - Org-wide access to all projects
3. **LEAD** - Team-wide access to team's projects
4. **DEVELOPER/QA/DEVOPS** - Project-level access (only assigned projects)

#### Resource Access Logic

**Projects:**
- CEO: All projects
- PM: All projects in their org
- LEAD: All projects for their team (`team_id` match)
- Others: Only projects in `project_ids` JWT claim

**Tasks:**
- Access granted through parent project
- Task → Project → User's project access

**Stories:**
- Access granted through parent project
- Story → Project → User's project access

**Comments:**
- Dual authorization required:
  1. **Author check** (for edit/delete)
  2. **Parent resource access** (task/story the comment belongs to)

**Teams:**
- CEO/PM: All teams
- Others: Only their own team

---

## Implementation Details

### New Module: `backend/core/authorization.py`

**Helper Functions:**
- `has_global_access(user)` - Check if user is CEO
- `has_org_access(user)` - Check if user is CEO or PM
- `has_team_access(user, team_id)` - Check team membership
- `verify_project_access(user, project_id, require_write=False)` - Verify project access
- `verify_task_access(user, task_id, require_write=False)` - Verify task access (via project)
- `verify_story_access(user, story_id, require_write=False)` - Verify story access (via project)
- `verify_team_access(user, team_id)` - Verify team access
- `verify_can_view_user_tasks(user, target_user_id)` - Verify viewing another user's tasks

### Routes Updated

#### Tasks (`backend/api/routes/tasks.py`)
- ✅ `GET /tasks/{task_id}` - Added `verify_task_access`
- ✅ `GET /tasks/project/{project_id}` - Added `verify_project_access`
- ✅ `GET /tasks/assignee/{assignee_id}` - Added `verify_can_view_user_tasks`
- ✅ `GET /tasks/story/{story_id}` - Added `verify_story_access`
- ✅ `GET /tasks/{task_id}/transitions` - Added `verify_task_access`
- ✅ `GET /tasks/{task_id}/history` - Added `verify_task_access`
- ✅ `PATCH /tasks/{task_id}/status` - Added `verify_task_access(require_write=True)`
- ✅ `PATCH /tasks/{task_id}/transition` - Added `verify_task_access(require_write=True)`

#### Projects (`backend/api/routes/projects.py`)
- ✅ `GET /projects/{project_id}` - Added `verify_project_access`
- ✅ `GET /projects/` - Added filtering by user's `project_ids`
- ✅ `GET /projects/team/{team_id}` - Added `verify_team_access`

#### Comments (`backend/api/routes/comments.py`)
- ✅ `POST /comments/` - Added parent resource verification
- ✅ `GET /comments/{parent_type}/{parent_id}` - Added parent resource verification
- ✅ `PUT /comments/{comment_id}` - Added dual check (author + parent access)
- ✅ `DELETE /comments/{comment_id}` - Added dual check (author + parent access)

---

## Testing

### Test Coverage

**Total Tests:** 67 (all passing ✅)

#### Unit Tests (`test_authorization.py`) - 27 tests
- Role hierarchy checks
- Project access verification
- Task access verification
- Story access verification
- Team access verification
- User task viewing permissions

#### Integration Tests - 40 tests
- `test_tasks_authorization.py` (15 tests)
- `test_projects_authorization.py` (13 tests)
- `test_comments_authorization.py` (12 tests)

### Test Scenarios Covered

✅ **Cross-Project Isolation**
- User in Project A cannot access Project B resources

✅ **Role Override**
- CEO can access all resources
- PM can access all org resources
- LEAD can access team resources

✅ **Ownership Checks**
- Users can edit/delete only their own comments
- Comment author must maintain parent resource access

✅ **Error Responses**
- 404 for missing resources
- 403 for unauthorized access

---

## HTTP Status Codes

### Authorization Responses

| Code | Meaning | When Used |
|------|---------|-----------|
| **200** | OK | Authorized and resource found |
| **403** | Forbidden | User lacks access to existing resource |
| **404** | Not Found | Resource doesn't exist |

### Design Decision: 403 vs 404

**Chosen Approach:** Return `403` for unauthorized access even though it reveals resource existence.

**Rationale:**
- Better user experience with clear error messages
- System already leaks resource IDs through other endpoints
- Prioritizes usability over security through obscurity

---

## API Changes

### Backward Compatibility

✅ **No Breaking Changes**
- All route paths unchanged
- All request/response models unchanged
- All HTTP methods unchanged

### New Behavior

Users will now receive `403 Forbidden` when accessing resources they're not assigned to. This is the intended security fix, not a bug.

**Example:**
```json
// Before: Developer could read any task
GET /api/tasks/TASK-999
200 OK

// After: Developer gets 403 if not assigned to task's project
GET /api/tasks/TASK-999
403 Forbidden
{
  "detail": "You don't have access to this task"
}
```

---

## Deployment Guide

### Pre-Deployment Checklist

- [ ] All 67 authorization tests passing
- [ ] Existing unit tests passing
- [ ] Database backup completed
- [ ] Rollback plan prepared

### Deployment Steps

1. **Deploy Code**
   ```bash
   git pull origin main
   cd backend
   pip install -r requirements.txt  # If dependencies changed
   ```

2. **Restart Services**
   ```bash
   # Stop backend
   pkill -f "uvicorn main:app"
   
   # Start backend
   nohup uvicorn main:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
   ```

3. **Verify Deployment**
   ```bash
   # Check health endpoint
   curl http://localhost:8000/health
   
   # Test authorization (should get 403 if not assigned)
   curl -H "Authorization: Bearer $TOKEN" \
        http://localhost:8000/api/tasks/{unassigned_task_id}
   ```

4. **Monitor Logs**
   ```bash
   tail -f logs/api.log | grep "403\|authorization"
   ```

### Post-Deployment Monitoring

**What to Watch:**
- 403 error rates (expected to increase initially as users hit new boundaries)
- User support tickets about "access denied" errors
- Any 500 errors related to authorization logic

**Success Metrics:**
- No increase in 500 errors
- Users can access their assigned resources
- Users correctly blocked from unassigned resources

---

## Rollback Plan

### If Issues Arise

**Option 1: Quick Rollback (Git)**
```bash
cd backend
git revert HEAD
git push origin main
# Restart services
```

**Option 2: Feature Flag (Future Enhancement)**
Add environment variable to disable authorization:
```python
# In core/authorization.py
if os.getenv("DISABLE_RESOURCE_AUTH") == "true":
    return  # Skip all checks
```

### Rollback Decision Criteria

Roll back if:
- ❌ 500 error rate increases >5%
- ❌ Legitimate users cannot access their own resources
- ❌ Critical business workflows broken
- ❌ Database performance degrades significantly

Do NOT roll back if:
- ✅ 403 errors increase (this is the security fix working)
- ✅ Users complain about not accessing others' resources (expected)
- ✅ Support tickets about "access denied" (provide guidance)

---

## Performance Impact

### Query Overhead

- **Tasks routes**: +1 query to fetch task.project_id
- **Projects routes**: No extra queries (uses JWT `project_ids`)
- **Comments routes**: +1 query to fetch parent resource

### Optimization Done

- Authorization checks use existing repository methods
- JWT `project_ids` cached in token (no DB fetch for user's projects)
- CEO/PM bypass some checks (short-circuit evaluation)

### Performance Monitoring

**Baseline Metrics:**
- Avg response time: ~50ms
- Expected after fix: ~60ms (+20% acceptable)

**Action Needed if:**
- Response time >100ms consistently
- Database CPU >80%
- Query count per request >10

---

## Future Enhancements

### Short Term (Next Sprint)
- [ ] Add field-level authorization (hide sensitive fields by role)
- [ ] Audit logging for all authorization failures
- [ ] Rate limiting per user/role

### Medium Term (Next Quarter)
- [ ] Multi-tenancy with `org_id` in JWT and all resources
- [ ] Fine-grained project permissions (viewer, contributor, admin)
- [ ] Resource-level access control lists (ACLs)

### Long Term (Future)
- [ ] Attribute-based access control (ABAC)
- [ ] Time-based access (temporary project access)
- [ ] Delegation (PM grants permissions)

---

## Team Communication

### Announcement Template

```
🔒 Security Enhancement Deployed

We've deployed resource-level authorization to improve security:

✅ What Changed:
- Users can only access resources in their assigned projects
- Role hierarchy properly enforced (CEO > PM > LEAD > others)
- Comments require parent resource access

⚠️ What You'll Notice:
- You may see "403 Forbidden" errors when accessing unassigned resources
- This is expected security behavior, not a bug

📋 Need Access?
- Contact your Project Manager to be added to projects
- PMs and CEOs have org-wide access

🐛 Issues?
- Report any "403" errors on your OWN resources
- Include: resource ID, your role, expected behavior
```

---

## FAQ

**Q: I'm getting 403 errors. Is this a bug?**  
A: If you're trying to access resources in projects you're not assigned to, this is expected. If you're getting 403 on your own projects, that's a bug—report it.

**Q: Will this affect performance?**  
A: Minimal impact (<20% response time increase). We've optimized queries and use JWT caching.

**Q: Can I still see all projects as PM?**  
A: Yes, PM and CEO roles have org-wide access by design.

**Q: What happens to old comments on resources I no longer have access to?**  
A: You can't edit/delete them anymore (security fix). Comments remain visible to users with project access.

**Q: How do I grant someone access to a project?**  
A: Add their `employee_id` to the project's team or update their `project_ids` list.

---

## Support

**For Questions:**
- Technical: [Your Tech Lead]
- Security: [Your Security Team]
- Product: [Your Product Manager]

**For Bugs:**
- Create ticket with:
  - Resource ID attempted
  - Your role and `project_ids`
  - Expected vs actual behavior
  - Full error message

---

## Compliance Notes

This enhancement addresses:
- ✅ **OWASP A01:2021** - Broken Access Control
- ✅ **CWE-285** - Improper Authorization
- ✅ **SOC 2** - Access Control requirements

**Audit Trail:**
- All authorization decisions logged at INFO level
- Failed authorization attempts logged at WARN level
- Security audit completed: 2026-10-17

---

## Changelog

### v1.0.0 (2026-10-17)
- ✅ Implemented resource-level authorization
- ✅ Fixed tasks, projects, and comments routes
- ✅ Added 67 comprehensive tests
- ✅ Documented rollback procedures
- ✅ Zero breaking API changes

---

## References

- Authorization helper module: `backend/core/authorization.py`
- Test suites: `backend/tests/test_*_authorization.py`
- Design document: `.kiro/specs/authorization-security-fix/design.md`
- Bug requirements: `.kiro/specs/authorization-security-fix/bugfix.md`
