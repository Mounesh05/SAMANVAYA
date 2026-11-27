"""Read-only pre-deployment check for a single reviewed work item."""

import hashlib
import hmac
import re
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from core.config import settings
from core.database import col
from domain.models.release import Digest, ProviderId, ReleaseId
from domain.services.release_decision_service import has_current_release_approval
from domain.services.task_delivery_service import delivery_evidence
from domain.services.task_progress_service import task_ids_in
from repositories.pr_repository import PRRepository


router = APIRouter()
NO_STORE = {"Cache-Control": "no-store"}


class GateScope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project_id: str = Field(min_length=1, max_length=128)
    repository: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
    revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    environment: Literal["production"]


class ReleaseGateCheck(GateScope):
    task_id: str = Field(pattern=r"^TSK-[0-9A-F]{8}$")


class ManifestGateCheck(GateScope):
    release_id: ReleaseId
    artifact_id: ProviderId
    artifact_digest: Digest


def _denied(message):
    return HTTPException(409, message, headers=NO_STORE)


async def _gate_organization(request, token):
    invalid = HTTPException(403, "A current project release-gate credential is required", headers=NO_STORE)
    if not token or len(token) > 512:
        raise invalid
    config = await col("project_release_gates").find_one({"_id": request.project_id})
    digest = hashlib.sha256(token.encode()).hexdigest()
    if (not config or config.get("enabled") is not True
            or config.get("repository") != request.repository.casefold()
            or config.get("environment") != request.environment
            or not isinstance(config.get("token_sha256"), str)
            or not hmac.compare_digest(digest.encode(), config["token_sha256"].encode())):
        raise invalid
    organization = config.get("organization_id")
    if not isinstance(organization, str) or not organization.strip():
        raise invalid
    return organization


async def _single_task_candidate(request, scope, pr_number):
    # The workflow cannot choose an approved sibling task on a multi-task PR.
    rows = await col("pull_requests").find({
        **scope, "repo_id": {"$regex": "^" + re.escape(request.repository) + "$", "$options": "i",
                              "$not": {"$type": "array"}}, "merge_commit_sha": request.revision,
    }, {"id": 1, "pr_number": 1, "title": 1, "branch": 1, "description": 1}).limit(2).to_list(2)
    if len(rows) != 1 or rows[0].get("pr_number") != pr_number:
        return False
    pr = rows[0]
    if not isinstance(pr.get("id"), str) or not pr["id"]:
        return False
    if any(pr.get(key) is not None and not isinstance(pr[key], str) for key in ("title", "branch", "description")):
        return False
    named = set(task_ids_in({"title": pr.get("title"), "head": {"ref": pr.get("branch")}, "body": pr.get("description")}))
    links = col("entity_relationships")
    query = {"source_id": pr["id"], "source_type": "pull_request", "target_type": "task", "relationship_type": "implements"}
    if await links.find_one({**query, "target_id": {"$ne": request.task_id}}, {"_id": 1}):
        return False
    if named:
        return named == {request.task_id}
    return bool(await links.find_one({**query, "target_id": request.task_id}, {"_id": 1}))


@router.post("/check")
async def check_release(request: ReleaseGateCheck | ManifestGateCheck, response: Response,
                        token: str | None = Header(default=None, alias="X-Release-Gate-Token")):
    """Check the supplied task and merge commit against current recorded evidence."""
    organization = await _gate_organization(request, token)
    projects = await col("projects").find({"id": request.project_id},
        {"id": 1, "org_id": 1, "organization_id": 1, "status": 1}).limit(2).to_list(2)
    if (len(projects) != 1 or projects[0].get("id") != request.project_id
            or projects[0].get("org_id") != organization
            or projects[0].get("organization_id", organization) != organization
            or projects[0].get("status", "active") != "active"):
        raise _denied("The project is unavailable for release")
    if isinstance(request, ManifestGateCheck):
        from domain.services.release_management import evaluate, record_gate_receipt
        revision = await evaluate(request, organization)
        await _gate_organization(request, token)
        await record_gate_receipt(revision)
        response.headers.update(NO_STORE)
        return {"allowed": True, **request.model_dump()}
    scope = PRRepository._project_scope([request.project_id], organization)
    tasks = await col("tasks").find({**scope, "id": request.task_id}, {"_id": 0}).limit(2).to_list(2)
    if len(tasks) != 1 or tasks[0].get("id") != request.task_id:
        raise _denied("The task is unavailable in this project")

    status = await delivery_evidence(tasks[0], organization)
    prs = status["implementation"]["pull_requests"]
    if (status["revision_kind"] != "merge_commit" or status["revision"] != request.revision
            or len(prs) != 1 or prs[0]["repository"].casefold() != request.repository.casefold()
            or not await _single_task_candidate(request, scope, prs[0]["number"])):
        raise _denied("This revision must identify one merged pull request for this task and repository")
    if not await has_current_release_approval(status):
        raise _denied("Current passing evidence, QA verification and independent release approval are required")
    from domain.services.release_management import check_legacy_scope, environment
    if settings.RELEASE_MANAGEMENT_ENABLED or (await environment(request.project_id, organization)).get("baseline"):
        await check_legacy_scope(request, organization, prs[0]["number"])
    elif await col("release_candidates").find_one({
        "project_id": request.project_id, "organization_id": organization, "target_sha": request.revision,
    }, {"_id": 1}):
        raise _denied("This revision requires its release manifest.")
    await _gate_organization(request, token)
    response.headers.update(NO_STORE)
    return {"allowed": True, **request.model_dump()}
