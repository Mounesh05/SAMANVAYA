# Authorization fixes for five high-priority security bugs

Five authorization vulnerabilities fixed across approval workflow, code quality, recommendations, teams/employees, and sprint creation. BUG-1 migrates the approval workflow from in-memory dict to MongoDB. BUG-2 through BUG-5 add missing authorization checks using existing helpers. All changes use documented patterns, no new abstractions introduced. Test suite passes (153/153).

**Watch for:** MongoDB migration in BUG-1 changes behavior around expired approvals (confirmed); error message sanitization in employees/teams/sprints was added but wasn't part of the authorization fixes (confirmed); recommendations authorization checks instantiate the repository inline rather than using dependency injection (confirmed).

**Verdict**: NEEDS_CHANGES

## High-level view

The approval workflow now persists to MongoDB instead of an in-memory dict, which means approvals survive server restarts but the expired-approval cleanup changes from immediate mutation to database queries. The code quality API gates all four GET endpoints by verifying the user has access to the repository via `get_accessible_project_ids`. Recommendations now verify ownership or org access before accept/reject, and filter role-based recommendations by accessible projects. Teams and employees routes call `verify_team_access` for GET operations, and employees list is filtered to own-team when the requester is a LEAD. Sprint creation now requires write access to the project. Several error messages were sanitized from detailed exceptions to "Internal server error" — this wasn't in the bug descriptions but shipped in the same commits.

<details>
<summary>Issues (4)</summary>

1. **Expired approval cleanup behavior change** — BUG-1 changed cleanup from in-memory mutation to a MongoDB update_many query, which means `cleanup_expired()` now issues a database write for every expired approval. If this runs on a schedule with many expired approvals, consider adding a limit or batch size.

2. **Inline repository instantiation in recommendations** — BUG-3 instantiates `RecommendationRepository()` inside the accept/reject endpoints to fetch the recommendation for authorization. The rest of the codebase uses the `RecommendationEngine` service. Either pass the repository through dependency injection or call `engine.get_recommendation(id)` if the engine exposes it.

3. **Error message sanitization bundled with authorization fixes** — Commits for BUG-4 and BUG-5 include unrelated changes that replace detailed error messages with "Internal server error". These should have been separate commits (not blocking, but breaks single-responsibility).

4. **MongoDB collection helper usage in BUG-1** — The migration uses `col("approvals")` from `core.database` correctly, matching the documented pattern, but the indexes are created in `_ensure_indexes()` which is defined but never called. The indexes won't be created unless this method is invoked during service initialization.

</details>

<details>
<summary>Details</summary>

## Approval workflow MongoDB migration

BUG-1 replaces the in-memory `self.pending_approvals` dict with a MongoDB collection accessed via `col("approvals")`. The service now calls `insert_one`, `find_one_and_update`, and `update_many` for all approval operations.

The `_ensure_indexes()` method creates a unique index on `id` and a compound index on `status + approvers`, but the method is never called. Indexes won't be created automatically. The service initialization should call `await self._ensure_indexes()` or the indexes should be provisioned separately.

The `cleanup_expired()` method changed from iterating an in-memory dict to issuing a `update_many` query that sets `status` to `EXPIRED` for all pending approvals past their expiration timestamp. If thousands of approvals expire, the query updates them all in one transaction. Consider adding a limit if cleanup runs on a tight schedule.

The `approve_approval` and `reject_approval` methods reconstruct an `ApprovalRequest` object from the MongoDB document to call `_notify_agent_approved` and `_notify_agent_rejected`. This is brittle: if the dataclass schema changes, the reconstruction could fail. Consider storing the full serialized object or calling the notification directly with the dict.

## Code quality API authorization

BUG-2 adds authorization to four GET endpoints in `backend/api/routes/code_quality.py`:

- `GET /runs/{run_id}`: fetches the run, extracts `repository_id`, checks if it's in `get_accessible_project_ids(user)`, raises 403 if not.
- `GET /runs/{run_id}/findings`: same pattern, fetches the run first to get the repository ID.
- `GET /repositories/{repo_id}/latest`: checks if `repository_id` is in accessible projects before querying.
- `GET /repositories/{repo_id}/history`: same check.

The `/runs/{run_id}/findings` endpoint fetches the run twice: once for authorization (projecting only `repository_id`) and again inside the pagination logic. Could be optimized by passing the repository_id down or caching the first fetch.

## Recommendations API authorization

BUG-3 adds four checks:

- `GET /user/{user_id}`: calls `verify_can_view_user_tasks(current_user, user_id)` before fetching recommendations.
- `GET /role/{role}`: fetches recommendations, then filters the list by `get_accessible_project_ids(current_user)`.
- `POST /{recommendation_id}/accept`: instantiates `RecommendationRepository()`, fetches the recommendation, verifies the requester is the owner or has org access, raises 403 otherwise.
- `POST /{recommendation_id}/reject`: same pattern as accept.

The accept/reject pattern is unusual: instead of using dependency injection or the existing `RecommendationEngine`, it creates a new repository instance inline (`repo = RecommendationRepository()`). The rest of the codebase uses `engine` (already imported) to interact with recommendations. This introduces a second path to the data layer.

The role-based endpoint filters recommendations in-memory after fetching them from the engine. If the result set is large, this is inefficient; the query should filter by project IDs at the database level. The current implementation fetches all recommendations for the role, then discards inaccessible ones.

## Teams and employees authorization

BUG-4 adds `verify_team_access(user, team_id)` calls to two endpoints:

- `GET /teams/{team_id}`: added at the start of the handler.
- `GET /teams/{team_id}/members`: added at the start, replacing a longer inline check that verified `VIEW_TEAM_DATA` and `VIEW_ORGANIZATION_DATA` permissions.

The `GET /employees/` list endpoint adds a filter for LEAD role:

```python
if user.get("role", "").upper() == "LEAD":
    filter_query["team_id"] = user["team_id"]
```

This restricts LEADs to see only employees in their own team.

The commit also replaces detailed error messages (`f"Failed to create employee: {str(e)}"`) with generic "Internal server error" across six exception handlers. This wasn't part of the bug description (authorization) and should have been a separate commit.

## Sprint creation authorization

BUG-5 adds a single check to `POST /sprints/`:

```python
await verify_project_access(user, sprint_data.project_id, require_write=True)
```

The commit also sanitizes the error message from `f"Failed to create sprint: {str(e)}"` to "Internal server error". Same issue as BUG-4: should have been a separate commit.

The `require_write=True` parameter is passed but the current implementation of `verify_project_access` in `core/authorization.py` doesn't differentiate between read and write permissions (the parameter is accepted but ignored).

## Test coverage

The verification note reports 153 tests passing. The note doesn't specify which tests cover the new authorization checks.

**Not tested (or not evidenced):**

- BUG-1: approval retrieval by unauthorized user (403), MongoDB persistence across service restarts, expired approval cleanup.
- BUG-2: code quality endpoint access with inaccessible repository (403).
- BUG-3: recommendation accept/reject by non-owner without org access (403), role recommendations filtered by accessible projects.
- BUG-4: team access by non-member (403), employee list filtered for LEAD.
- BUG-5: sprint creation without write access (403).

</details>

<details>
<summary>File map</summary>

- `backend/api/routes/approvals.py` — added authorization check to GET `/{approval_id}` (approver or org access)
- `backend/api/routes/code_quality.py` — added authorization to four GET endpoints (run, findings, latest, history)
- `backend/api/routes/employees.py` — filtered employee list for LEAD role; sanitized error messages
- `backend/api/routes/recommendations.py` — added authorization to user/role/accept/reject endpoints
- `backend/api/routes/sprints.py` — added project write access check to sprint creation; sanitized error
- `backend/api/routes/teams.py` — added `verify_team_access` to two GET endpoints; sanitized errors
- `backend/domain/services/hitl_workflow_service.py` — migrated approval storage from dict to MongoDB collection

Full diff: `git diff 388ce0d..HEAD` (7 files changed)

</details>
