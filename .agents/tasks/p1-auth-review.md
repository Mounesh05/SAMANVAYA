# Authorization gap fixes for P1 endpoints

The testing branch adds authorization checks to 17 endpoints across 9 backend files, addressing 11 P1 security gaps identified in the implementation plan. The fixes use existing authorization helpers (`verify_project_access`, `verify_task_access`, `verify_can_view_user_tasks`, `get_accessible_project_ids`) from `core/authorization.py`. Checks are placed before business logic to prevent information disclosure. The changes follow the pattern established in `boards.py` and `stories.py`. All 153 tests pass.

**Watch for:** `require_write` parameter in authorization.py exists but doesn't enforce write restrictions for most roles (confirmed); traceability endpoints verify PR access but don't validate that PRs are actually linked to the claimed project (possible); hitl_workflow_service authorization change breaks existing callers that don't pass `current_user` (confirmed); file history endpoint requires org access instead of project access, blocking developers from their own repositories (confirmed).

**Verdict**: NEEDS_CHANGES

## High-level view

The traceability API requires org access for file history (prevents developers from viewing their own repositories) and doesn't validate PR-to-project mappings before authorization. Performance routes replaced manual role checks with authorization helpers. Code quality and GitHub sync endpoints use `require_write=True`, which is mostly documentary since most roles always have write access. The HITL workflow service's `get_pending_for_user` signature changed to require `current_user`, breaking existing callers.

<details>
<summary>Issues (6)</summary>

1. **require_write doesn't enforce write permissions** — `verify_project_access` in authorization.py accepts `require_write=True` but only enforces it for non-LEAD developers (lines 181-187). CEOs, PMs, and LEADs always have write access regardless of the flag. The authorization model doesn't distinguish between read and write project permissions for most roles, so `require_write=True` is mostly documentary. If write restrictions are intended, the authorization model needs project-level write permission tracking.

2. **Traceability PR-to-project mapping not validated** — The traceability endpoints fetch a PR and extract `project_id` from it, then verify the user has access to that project. If the PR document's `project_id` field is incorrect or maliciously set, a user could access PRs from other projects by claiming they belong to an accessible project. The code should validate that the PR actually belongs to the project or repository, not just trust the stored value.

3. **hitl_workflow_service.get_pending_for_user signature change** — The method signature changed from `get_pending_for_user(self, user_id)` to `get_pending_for_user(self, user_id, current_user)` at line 256. Any existing callers (routes or services) that don't pass `current_user` will break with a TypeError. The codebase should be checked for callers.

4. **File history endpoint uses has_org_access instead of project verification** — The `get_file_history` endpoint in traceability.py (lines 109-116) requires org access instead of verifying that the user has access to the repository's project. A DEVELOPER assigned to project A cannot view file history for repository A, even though they should be able to. The check should map repository to project_id and call `verify_project_access`.

5. **Entity connections endpoint doesn't verify access to all entity types** — The `get_entity_connections` endpoint in traceability.py (lines 138-157) verifies access for TASK and PR entity types, but skips verification for other types with a comment "For other entity types, continue without authorization for now" (line 156). If the traceability system supports entity types beyond TASK and PR (FILE, COMMIT, DEPLOYMENT, etc.), those connections are exposed without authorization.

6. **Recommendations entity endpoint doesn't verify PR access** — The `get_entity_recommendations` endpoint in recommendations.py (lines 73-85) verifies access for task, story, and project entities, but for PRs it only checks `has_org_access` without verifying the PR belongs to an accessible project (lines 82-85). A DEVELOPER could list recommendations for a PR from a project they don't have access to.

</details>

<details>
<summary>Details</summary>

## Traceability API authorization

The `get_file_history` endpoint requires org access instead of project-scoped access, which prevents developers from viewing file history for their own repositories. The authorization checks for PR-related endpoints (`get_pr_relationships`, `get_pr_blast_radius`) trust the `project_id` field stored in the PR document without validating that the PR's repository actually belongs to that project. If the stored project_id is incorrect or malicious, the authorization check passes for the wrong project. The `get_entity_connections` endpoint skips authorization for entity types beyond TASK and PR (FILE, COMMIT, DEPLOYMENT), exposing those connections without access control.

## Performance API authorization

Six feedback endpoints (PM, LEAD, QA, DevOps, CEO, HR) now verify the user can view the target developer's performance before adding feedback, preventing cross-developer feedback submission without permission.

## Recommendations API authorization

The `get_entity_recommendations` endpoint verifies access for task, story, and project entities, but for PRs it only checks `has_org_access` without validating the PR belongs to an accessible project. A DEVELOPER could list recommendations for a PR from an inaccessible project.

## Authorization helper correctness

The `verify_project_access` helper accepts `require_write=True` but only enforces it for non-LEAD developers. CEOs, PMs, and LEADs always pass the write check regardless of the flag. The authorization model doesn't distinguish read and write permissions at the project level for most roles, so `require_write=True` is mostly documentary.

LEADs with team access can write to any project in their team (early return at line 160) but LEADs with assigned projects outside their team hit the write restriction check and are blocked. This asymmetry means a LEAD's write access depends on whether the project is team-owned or individually assigned.

## HITL workflow service authorization

The `get_pending_for_user` method signature changed to require `current_user` (line 256), breaking any existing callers that don't pass it. TypeError will occur at runtime if a route or service calls `get_pending_for_user(user_id)` without the new parameter.

## Test coverage

**Not tested (or not evidenced):**

- Traceability: DEVELOPER accessing PR from inaccessible project (403)
- Traceability: DEVELOPER viewing file history for own repository (should succeed, currently requires org access)
- Performance: DEVELOPER viewing another developer's trend (403)
- Performance: LEAD viewing team performance filtered to accessible projects
- Recommendations: DEVELOPER accessing recommendation for inaccessible entity (403)
- Code quality: DEVELOPER saving project config without write access (403)
- GitHub: DEVELOPER syncing PR for inaccessible project (403)
- HITL: User viewing another user's pending approvals (403)

</details>

<details>
<summary>File map</summary>

- `backend/api/routes/traceability.py` — added authorization to 6 endpoints (PR relationships, blast radius, task PRs, file history, create relationship, entity connections)
- `backend/api/routes/performance.py` — replaced manual role checks in 2 endpoints (performance trend, team performance); added authorization to 6 feedback endpoints
- `backend/api/routes/recommendations.py` — added authorization to 2 endpoints (entity recommendations, get recommendation)
- `backend/api/routes/code_quality.py` — added authorization to 2 config endpoints (save config, get config)
- `backend/api/routes/github.py` — added authorization to 2 endpoints (provision QA workflow, sync PR)
- `backend/api/routes/activity.py` — no changes (already had proper authorization)
- `backend/api/routes/teams.py` — no changes (already had proper authorization)
- `backend/api/routes/ai.py` — no changes (already had proper authorization)
- `backend/domain/services/hitl_workflow_service.py` — added current_user parameter and authorization check to get_pending_for_user method
- `backend/core/authorization.py` — no changes to logic (require_write enforcement verified as existing behavior)

Full diff: `git diff 2546348..HEAD` (9 files changed, 17 endpoints modified)

</details>
