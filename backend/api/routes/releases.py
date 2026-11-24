"""Project-scoped release management API."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response

from core.database import col
from core.dependencies import get_current_user
from domain.models.release import BaselineRequest, CandidateRequest, ReleaseAction, ReleaseId
from domain.services import release_management as releases

router = APIRouter()


async def visible_to(row, revision, user):
    if user.get("role") != "DEVELOPER":
        return True
    tasks = await releases.live_tasks(row["project_id"], row["organization_id"], revision["manifest"])
    return any(task.get("assignee_id") == user["employee_id"] for task in tasks)


async def visible_candidate(project_id, org, release_id, user):
    row, revision = await releases.candidate(project_id, org, release_id)
    if not await visible_to(row, revision, user):
        raise releases.error("RELEASE_UNAVAILABLE", "Release candidate unavailable.", 404)
    return row, revision


@router.get("/{project_id}/releases")
async def list_releases(project_id: str, response: Response, offset: int = Query(0, ge=0, le=10000),
                        limit: int = Query(20, ge=1, le=50), user=Depends(get_current_user)):
    org = await releases.authorize(project_id, user)
    response.headers["Cache-Control"] = "no-store"
    unavailable = False
    try:
        repository, repository_id = await releases.repository_identity(project_id, org)
        baseline = await releases.baseline(project_id, org, repository, repository_id)
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        unavailable = True
        baseline = None
    candidates = await col("release_candidates").find({"project_id": project_id, "organization_id": org}).sort(
        [("created_at", -1), ("_id", -1)]).skip(offset).limit(limit + 1).to_list(limit + 1)
    items = []
    for row in candidates[:limit]:
        revision = await releases.latest(row["_id"])
        if not revision or not await visible_to(row, revision, user):
            continue
        manifest = revision["manifest"]
        decision = revision["release_decision"]
        observed = await releases.deployment(row, revision)
        state = {"deployed": "deployed", "failed": "deployment_failed"}.get(observed["status"], "review_required")
        if revision["superseded"]:
            state = "superseded"
        elif state == "review_required" and decision and decision["action"] == "hold":
            state = "on_hold"
        elif state == "review_required" and not manifest["complete"]:
            state = "evidence_incomplete"
        elif state == "review_required" and not revision["submitted"]:
            state = "draft"
        items.append({"id": row["_id"], "created_at": row["created_at"], "state": state,
                      "manifest": {k: manifest.get(k) for k in ("target_sha", "baseline_sha", "repository", "kind", "complete")},
                      "pr_count": len(manifest.get("pull_requests", [])), "task_count": len(manifest.get("tasks", []))})
    manage = releases.can_manage(user) and not unavailable
    return {"enabled": True, "releases": items, "has_more": len(candidates) > limit,
            "can_create": manage, "can_initialize_baseline": manage and not baseline, "baseline": baseline,
            "baseline_unavailable": unavailable}


@router.post("/{project_id}/releases/baseline", status_code=201)
async def initialize_baseline(project_id: str, body: BaselineRequest, user=Depends(get_current_user)):
    org = await releases.authorize(project_id, user)
    if not releases.can_manage(user):
        raise releases.error("RELEASE_ACCESS_DENIED", "DevOps authority is required to initialize a baseline.", 403)
    return await releases.initialize(project_id, org, user, body)


@router.post("/{project_id}/releases", status_code=201)
async def create_release(project_id: str, body: CandidateRequest, user=Depends(get_current_user)):
    org = await releases.authorize(project_id, user)
    if not releases.can_manage(user):
        raise releases.error("RELEASE_ACCESS_DENIED", "DevOps authority is required to create a candidate.", 403)
    row, revision = await releases.create(project_id, org, user, body)
    return await releases.detail(row, revision, user)


@router.get("/{project_id}/releases/{release_id}/history")
async def release_history(project_id: str, release_id: ReleaseId, offset: int = Query(0, ge=0, le=10000),
                          limit: int = Query(25, ge=1, le=50), user=Depends(get_current_user)):
    org = await releases.authorize(project_id, user)
    await visible_candidate(project_id, org, release_id, user)
    entries = await col("release_revisions").find({"release_id": release_id},
        {"_id": 0, "manifest_digest": 1, "record": 1, "version": 1}
    ).sort("version", -1).skip(offset).limit(limit + 1).to_list(limit + 1)
    return {"history": entries[:limit], "has_more": len(entries) > limit}


@router.get("/{project_id}/releases/{release_id}")
async def release_detail(project_id: str, release_id: ReleaseId, response: Response, user=Depends(get_current_user)):
    org = await releases.authorize(project_id, user)
    response.headers["Cache-Control"] = "no-store"
    row, revision = await visible_candidate(project_id, org, release_id, user)
    return await releases.detail(row, revision, user)


@router.post("/{project_id}/releases/{release_id}/actions")
async def release_action(project_id: str, release_id: ReleaseId, body: ReleaseAction, user=Depends(get_current_user)):
    org = await releases.authorize(project_id, user)
    manager_action = body.action != "verify_qa"
    if not (releases.can_manage(user) if manager_action else releases.can_verify(user)):
        raise releases.error("RELEASE_ACCESS_DENIED", "Your release role does not permit this action.", 403)
    row, revision = await releases.candidate(project_id, org, release_id)
    row, revision = await releases.action(row, revision, user, body)
    return await releases.detail(row, revision, user)
