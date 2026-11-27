"""Release candidate ledger and deterministic approval checks."""
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from core.authorization import get_accessible_project_ids
from core.config import settings
from core.database import col
from core.permissions import Permission
from domain.models.performance_evidence import canonical_digest
from domain.services.ai_evidence_service import _repository
from domain.services.release_decision_service import _permissions
from domain.services.release_discovery import discover
from domain.services.release_test_evidence import release_tests
from integrations.github.client import GitHubClient
from repositories.pr_repository import PRRepository


async def ensure_indexes():
    await col("release_candidates").create_index([("organization_id", 1), ("project_id", 1), ("created_at", -1)])
    await col("release_candidates").create_index([("organization_id", 1), ("repository_id", 1), ("target_sha", 1), ("environment", 1)])
    await col("release_revisions").create_index([("release_id", 1), ("version", -1)], unique=True)
    await col("release_revisions").create_index([("release_id", 1), ("manifest_digest", 1)])
    await col("release_gate_receipts").create_index([("release_id", 1), ("manifest_digest", 1), ("checked_at", 1)])
    await col("webhook_events").create_index([("project_id", 1), ("event_type", 1),
                                             ("production.observed_at", -1), ("production.status_id", -1)])


def enabled():
    if not settings.RELEASE_MANAGEMENT_ENABLED:
        raise HTTPException(404, "Release management is disabled.")


def role(user, name, permission):
    return user.get("role") == name and permission in _permissions(user)


def can_manage(user):
    return role(user, "DEVOPS", Permission.RECORD_RELEASE_DECISION)


def can_verify(user):
    return role(user, "QA", Permission.SIGN_OFF_WORK)


def error(code, message, status=409):
    return HTTPException(status, {"code": code, "message": message}, headers={"Cache-Control": "no-store"})


def now():
    return datetime.now(timezone.utc).isoformat()


async def authorize(project_id, user):
    enabled()
    if user.get("role") not in {"DEVOPS", "QA", "PM", "LEAD", "DEVELOPER"}:
        raise error("RELEASE_ACCESS_DENIED", "Release access is restricted to assigned engineering and management roles.", 403)
    org = user.get("org_id")
    if not org or user.get("organization_id", org) != org or project_id not in await get_accessible_project_ids(user):
        raise error("RELEASE_ACCESS_DENIED", "Project access required.", 403)
    return org


def environment_key(project, org):
    return canonical_digest([org, project, "production"])


async def environment(project, org):
    return await col("release_environments").find_one({"_id": environment_key(project, org)}) or {}


async def deployment_rows(project, org, repository, repository_id, extra=None):
    return await col("webhook_events").find({
        "source": "github", "event_type": "deployment_status", "project_id": project,
        "production.org_id": org, "production.repository": repository.casefold(),
        "payload.repository.id": repository_id, "payload.deployment.environment": "production",
        **(extra or {}),
    }, {"_id": 0, "production": 1, "payload.deployment.payload": 1}).sort(
        [("production.observed_at", -1), ("production.status_id", -1)]
    ).limit(1).to_list(1)


async def baseline(project, org, repository, repository_id):
    # A successful status records the most recent deployed revision even if a
    # later candidate fails. A GitHub deployment cannot move this backwards by redelivery.
    observed = await deployment_rows(project, org, repository, repository_id, {"production.state": "success"})
    if observed:
        row = observed[0]["production"]
        return {"revision": row["revision"], "source": "github_deployment", "deployment_id": row["deployment_id"]}
    initial = (await environment(project, org)).get("baseline")
    return initial if initial and initial["repository_id"] == repository_id else None


async def repository_identity(project, org):
    owner, name = await _repository(project, org)
    try:
        details = await GitHubClient().get_repository(owner, name)
        identifier = details.get("id")
        repository = f"{owner}/{name}"
        if type(identifier) is not int or identifier <= 0 or str(details.get("full_name")).casefold() != repository.casefold():
            raise ValueError("Repository identity differs")
        return repository, identifier
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise error("REPOSITORY_UNVERIFIED", "GitHub repository identity could not be verified.") from exc


async def initialize(project, org, user, request):
    repository, identifier = await repository_identity(project, org)
    if await baseline(project, org, repository, identifier):
        raise error("BASELINE_EXISTS", "A production baseline has already been established.")
    try:
        commit = await GitHubClient().get_commit(*repository.split("/"), request.revision)
        if commit.get("sha") != request.revision:
            raise ValueError("Commit differs")
    except (httpx.HTTPError, ValueError, AttributeError) as exc:
        raise error("BASELINE_UNVERIFIED", "The initialization revision is unavailable in the linked repository.") from exc
    entry = {"revision": request.revision, "source": "devops_initialization", "repository_id": identifier,
             "reason": request.reason, "actor_id": user["employee_id"], "recorded_at": now()}
    try:
        result = await col("release_environments").update_one(
            {"_id": environment_key(project, org), "baseline": {"$exists": False}},
            {"$set": {"baseline": entry}}, upsert=True)
    except DuplicateKeyError:
        result = None
    if not result or not (result.matched_count or result.upserted_id):
        raise error("BASELINE_EXISTS", "Another reviewer initialized the baseline.")
    return entry


async def manifest_for(project, org, inputs):
    repository, identifier = await repository_identity(project, org)
    current = await baseline(project, org, repository, identifier)
    if not current or inputs["baseline_sha"] != current["revision"]:
        raise error("BASELINE_CHANGED", "Select the current verified production baseline.")
    if inputs["target_sha"] == current["revision"]:
        raise error("NO_RELEASE_CHANGES", "The target and baseline must differ.")
    if inputs["kind"] == "rollback":
        discovered = {"complete": False, "pull_requests": [], "tasks": [], "unmapped_commits": [], "reverts": [],
                      "artifact": None, "blockers": ["Rollback execution requires a separate deployment policy."]}
    else:
        discovered = await discover(project, org, inputs["baseline_sha"], inputs["target_sha"],
                                    inputs["run_id"], inputs["artifact_id"])
        if discovered.get("repository_id") != identifier:
            discovered["complete"] = False
            discovered.setdefault("blockers", []).append("GitHub repository identity changed during discovery.")
    return {**discovered, **inputs, "repository": repository, "repository_id": identifier,
            "project_id": project, "organization_id": org,
            "baseline_source": current["source"], "environment": "production", "schema_version": "release-manifest-v1"}


def manifest_digest(manifest):
    return canonical_digest(manifest)


async def latest(release_id):
    return await col("release_revisions").find_one({"release_id": release_id}, {"_id": 0}, sort=[("version", -1)])


async def candidate(project, org, release_id):
    row = await col("release_candidates").find_one({"_id": release_id, "organization_id": org, "project_id": project})
    revision = await latest(release_id) if row else None
    if not revision:
        raise error("RELEASE_UNAVAILABLE", "Release candidate unavailable.", 404)
    return row, revision


async def create(project, org, user, request):
    inputs = request.model_dump()
    manifest = await manifest_for(project, org, inputs)
    digest = manifest_digest(manifest)
    release_id = "RL-" + canonical_digest([org, project, manifest["repository_id"], inputs])[:32]
    index = {"_id": release_id, "organization_id": org, "project_id": project,
             "repository_id": manifest["repository_id"], "environment": "production", "target_sha": inputs["target_sha"],
             "created_by": user["employee_id"], "created_at": now(), "inputs": inputs}
    await col("release_candidates").update_one({"_id": release_id}, {"$setOnInsert": index}, upsert=True)
    initial = {"_id": f"{release_id}:1", "release_id": release_id, "version": 1, "manifest": manifest,
               "manifest_digest": digest, "record": {"action": "create", "actor_id": user["employee_id"], "recorded_at": now()},
               "submitted": False, "superseded": False, "qa_verification": None, "release_decision": None}
    await col("release_revisions").update_one({"_id": initial["_id"]}, {"$setOnInsert": initial}, upsert=True)
    return await candidate(project, org, release_id)


async def _assigned_authority(project, org, record, permission):
    if not record:
        return False
    actors = await col("users").find({"employee_id": record["actor_id"]}).limit(2).to_list(2)
    return bool(len(actors) == 1 and actors[0].get("is_active") is True
                and actors[0].get("org_id") == org and permission(actors[0])
                and project in await get_accessible_project_ids(actors[0]))


async def live_tasks(project, org, manifest):
    expected = {task["id"]: task for task in manifest.get("tasks", [])}
    records = await col("tasks").find({**PRRepository._project_scope([project], org), "id": {"$in": list(expected)}},
        {"_id": 0, "id": 1, "status": 1, "last_transition_id": 1, "story_id": 1, "title": 1, "assignee_id": 1}
    ).limit(len(expected) + 1).to_list(len(expected) + 1)
    return sorted(records, key=lambda task: task["id"])


async def deployment(candidate_row, revision):
    m, artifact = revision["manifest"], revision["manifest"].get("artifact")
    decision = revision["release_decision"]
    if not artifact or not decision or decision["action"] != "approve" or decision["manifest_digest"] != revision["manifest_digest"]:
        return {"status": "unknown"}
    receipt = await col("release_gate_receipts").find_one(
        {"release_id": candidate_row["_id"], "manifest_digest": revision["manifest_digest"],
         "decision_id": canonical_digest(decision)}, sort=[("checked_at", 1)])
    if not receipt:
        return {"status": "unknown"}
    extra = {"production.revision": m["target_sha"], "payload.deployment.payload.samanvaya_release_id": candidate_row["_id"],
             "payload.deployment.payload.artifact_id": artifact["id"],
             "payload.deployment.payload.artifact_digest": artifact["digest"],
             "payload.deployment.payload.manifest_digest": revision["manifest_digest"],
             "production.observed_at": {"$gte": receipt["checked_at"]}}
    rows = await deployment_rows(candidate_row["project_id"], candidate_row["organization_id"],
                                 m["repository"], m["repository_id"], extra)
    if not rows:
        return {"status": "unknown"}
    observation = rows[0]["production"]
    return {**observation, "status": {"success": "deployed", "error": "failed", "failure": "failed"}.get(
        observation["state"], "unknown")}


async def detail(row, revision, user=None, include_history=True):
    project, org, release_id = row["project_id"], row["organization_id"], row["_id"]
    m = revision["manifest"]
    blockers = list(m.get("blockers", []))
    if manifest_digest(m) != revision["manifest_digest"]:
        raise error("MANIFEST_INTEGRITY", "The stored release manifest could not be verified.")
    observed = await deployment(row, revision)
    current = await baseline(project, org, m["repository"], m["repository_id"])
    if not current or current["revision"] != m["baseline_sha"]:
        blockers.append("The current production baseline differs from this candidate.")
    try:
        repo = await _repository(project, org)
    except HTTPException as exc:
        if exc.status_code != 409:
            raise
        repo = ()
    if "/".join(repo).casefold() != m["repository"].casefold():
        blockers.append("The repository mapping changed.")
    tasks = await live_tasks(project, org, m)
    expected_ids = {task["id"] for task in m.get("tasks", [])}
    if ({t["id"] for t in tasks} != expected_ids or len(tasks) != len(expected_ids)
            or any(t.get("status") in {None, "blocked"} for t in tasks)):
        blockers.append("One or more required tasks are blocked or unavailable.")
    if m["complete"] and not revision["superseded"]:
        evidence = await release_tests(m)
    else:
        evidence = {"qa": {"status": "unknown", "reason": "Release manifest is incomplete or superseded.", "runs": []},
                    "coverage_status": "missing", "coverage": None}
    if evidence["qa"]["status"] != "passed":
        blockers.append(evidence["qa"]["reason"])
    evidence_id = canonical_digest([revision["manifest_digest"], current, tasks, evidence])
    verification = revision["qa_verification"]
    decision = revision["release_decision"]
    verified = bool(verification and verification["evidence_id"] == evidence_id
                    and await _assigned_authority(project, org, verification, can_verify))
    approved = bool(decision and decision["action"] == "approve" and verified and decision["evidence_id"] == evidence_id
                    and verification["actor_id"] != decision["actor_id"]
                    and await _assigned_authority(project, org, decision, can_manage))
    held = bool(decision and decision["action"] == "hold")
    active = (await environment(project, org)).get("active_release") == release_id
    submitted = revision["submitted"] and active
    if revision["superseded"]:
        state = "superseded"
    elif observed["status"] in {"deployed", "failed"}:
        state = "deployed" if observed["status"] == "deployed" else "deployment_failed"
    elif held:
        state = "on_hold"
    elif not m["complete"] or blockers:
        state = "invalidated" if verification or decision else "evidence_incomplete"
    elif not submitted:
        state = "draft"
    elif approved:
        state = "approved"
    elif verified:
        state = "awaiting_devops"
    else:
        state = "awaiting_qa"
    ready = not blockers and m["complete"] and not revision["superseded"] and observed["status"] == "unknown"
    manage = bool(user and can_manage(user))
    actor = user.get("employee_id") if user else None
    history = []
    if include_history:
        history = await col("release_revisions").find({"release_id": release_id},
            {"_id": 0, "version": 1, "record": 1, "manifest_digest": 1}
        ).sort("version", -1).limit(25).to_list(25)
    return {"id": release_id, "version": revision["version"], "manifest": m, "state": state,
            "manifest_digest": revision["manifest_digest"], "evidence_digest": evidence_id, "evidence": evidence,
            "blockers": blockers, "deployment": observed, "history": history,
            "qa_verification": {**verification, "is_current": verified} if verification else None,
            "release_decision": {**decision, "is_current": held or approved} if decision else None,
            "eligible": bool(submitted and ready and approved and not held),
            "can": {"submit": manage and ready and not submitted, "refresh": manage and not revision["superseded"]
                    and observed["status"] == "unknown", "supersede": manage and not revision["superseded"],
                    "verify_qa": bool(user and can_verify(user) and submitted and ready and not verified),
                    "approve": bool(manage and submitted and ready and verified and not approved
                                    and verification["actor_id"] != actor),
                    "hold": manage and not revision["superseded"] and observed["status"] == "unknown"}}


async def action(row, revision, user, request):
    view = await detail(row, revision, user, include_history=False)
    release_id = row["_id"]
    project, org = row["project_id"], row["organization_id"]
    event_key = canonical_digest([user["employee_id"], request.model_dump()])
    if revision.get("event_key") == event_key:
        return row, revision
    if request.version != revision["version"]:
        raise error("RELEASE_VERSION_CHANGED", "The candidate changed. Review the current evidence.")
    if not view["can"].get(request.action):
        raise error("RELEASE_TRANSITION_DENIED", "The current evidence or role does not permit this action.")
    if request.action in {"submit", "verify_qa", "approve"} and request.evidence_digest != view["evidence_digest"]:
        raise error("RELEASE_EVIDENCE_CHANGED", "The release evidence changed. Review it again.")
    if request.action in {"submit", "verify_qa", "approve"}:
        await assert_current_scope(project, org, revision["manifest"])
    if request.action == "verify_qa":
        required = sorted(task["id"] for task in revision["manifest"]["tasks"])
        if not required or sorted(request.verified_task_ids) != required:
            raise error("QA_TASKS_INCOMPLETE", "QA must review every included task before verifying the release.")
        if (any(revert.get("status") == "review_required" for revert in revision["manifest"]["reverts"])
                and not request.reviewed_uncertain_reverts):
            raise error("QA_REVERT_REVIEW_REQUIRED", "QA must explicitly review uncertain revert effects.")
    successor = dict(revision)
    record = {"action": request.action, "decision": request.action, "reason": request.reason,
              "actor_id": user["employee_id"], "actor_name": user.get("name") or user["employee_id"],
              "recorded_at": now(), "evidence_id": view["evidence_digest"], "manifest_digest": view["manifest_digest"],
              "target_sha": view["manifest"]["target_sha"], "artifact": view["manifest"].get("artifact")}
    if request.action == "refresh":
        update = await manifest_for(project, org, row["inputs"])
        successor.update(manifest=update, manifest_digest=manifest_digest(update))
        if successor["manifest_digest"] != revision["manifest_digest"]:
            successor.update(submitted=False, qa_verification=None)
    elif request.action == "submit":
        environments = col("release_environments")
        selected = (await environment(project, org)).get("active_release")
        permitted = [None, release_id]
        if selected and selected != release_id:
            prior_row, prior = await candidate(project, org, selected)
            if prior["superseded"] or (await deployment(prior_row, prior))["status"] == "deployed":
                permitted.append(selected)
        try:
            await environments.update_one({"_id": environment_key(project, org), "active_release": {"$in": permitted}},
                {"$set": {"active_release": release_id}}, upsert=True)
        except DuplicateKeyError:
            raise error("ACTIVE_RELEASE_EXISTS", "Settle or supersede the current production candidate first.") from None
        successor["submitted"] = True
    elif request.action == "supersede":
        successor["superseded"] = True
    elif request.action == "verify_qa":
        record["verified_task_ids"] = required
        record["reviewed_uncertain_reverts"] = request.reviewed_uncertain_reverts
        successor["qa_verification"] = record
    else:
        successor["release_decision"] = record
    version = request.version + 1
    successor.update(_id=f"{release_id}:{version}", version=version, record=record, event_key=event_key)
    try:
        await col("release_revisions").insert_one(successor)
    except DuplicateKeyError:
        winner = await latest(release_id)
        if winner.get("event_key") == event_key:
            return row, winner
        raise error("RELEASE_VERSION_CHANGED", "Another reviewer changed the candidate. Refresh and review.") from None
    if request.action == "supersede":
        await col("release_environments").update_one({"_id": environment_key(project, org), "active_release": release_id},
                                                    {"$unset": {"active_release": ""}})
    successor.pop("_id")
    return row, successor


async def evaluate(request, org):
    enabled()
    row, revision = await candidate(request.project_id, org, request.release_id)
    m = revision["manifest"]
    artifact = m.get("artifact") or {}
    if (m["repository"].casefold() != request.repository.casefold() or m["target_sha"] != request.revision
            or artifact.get("id") != request.artifact_id or artifact.get("digest") != request.artifact_digest):
        raise error("RELEASE_IDENTITY_MISMATCH", "The deployment commit or artifact differs from the reviewed release.")
    decision = revision["release_decision"]
    if revision["superseded"] or not revision["submitted"] or not decision or decision["action"] != "approve":
        raise error("RELEASE_GATE_DENIED", "Current complete evidence and independent approval are required.")
    await assert_current_scope(request.project_id, org, m)
    view = await detail(row, revision, include_history=False)
    if not view["eligible"]:
        raise error("RELEASE_GATE_DENIED", "Current complete evidence and independent approval are required.")
    if (await latest(request.release_id))["version"] != revision["version"]:
        raise error("RELEASE_VERSION_CHANGED", "The release decision changed during the check.")
    active = await environment(request.project_id, org)
    current = await baseline(request.project_id, org, m["repository"], m["repository_id"])
    if active.get("active_release") != request.release_id or not current or current["revision"] != m["baseline_sha"]:
        raise error("RELEASE_SUPERSEDED", "The production candidate changed.")
    if not (await _assigned_authority(request.project_id, org, revision["qa_verification"], can_verify)
            and await _assigned_authority(request.project_id, org, revision["release_decision"], can_manage)):
        raise error("RELEASE_REVIEWER_REVOKED", "Current reviewer authority is required.")
    return revision


async def record_gate_receipt(revision):
    decision = revision["release_decision"]
    identifier = canonical_digest(decision)
    receipt_id = canonical_digest([revision["release_id"], revision["manifest_digest"], identifier])
    await col("release_gate_receipts").update_one({"_id": receipt_id}, {"$setOnInsert": {
        "release_id": revision["release_id"], "manifest_digest": revision["manifest_digest"],
        "decision_id": identifier, "checked_at": now(),
    }}, upsert=True)


async def assert_current_scope(project, org, manifest):
    discovered = await discover(project, org, manifest["baseline_sha"], manifest["target_sha"])
    fields = ("repository_id", "commits", "unmapped_commits", "reverts")
    # The task workflow state is compared separately on every read.
    tasks = ("id", "story", "acceptance_criteria", "pr_numbers")
    def snapshot(results):
        prs = [{k: value for k, value in pr.items() if k != "local_pr_id"} for pr in results["pull_requests"]]
        return prs, [{key: row.get(key) for key in tasks} for row in results.get("tasks", [])]
    if (not discovered["scope_complete"] or any(discovered.get(key) != manifest.get(key) for key in fields)
            or snapshot(discovered) != snapshot(manifest)):
        raise error("RELEASE_SCOPE_CHANGED", "The included changes or requirements changed. Refresh the manifest and review it.")


async def check_legacy_scope(request, org, pr_number):
    """Under release management, legacy requests also prove the deployment delta."""
    repository, repository_id = await repository_identity(request.project_id, org)
    current = await baseline(request.project_id, org, repository, repository_id)
    if await col("release_candidates").find_one({
        "project_id": request.project_id, "organization_id": org, "repository_id": repository_id,
        "target_sha": request.revision,
    }, {"_id": 1}):
        raise error("MANIFEST_REQUIRED", "This revision has a release candidate. Use its manifest-aware check.")
    if not current:
        raise error("BASELINE_REQUIRED", "Initialize the production baseline before using the legacy checker.")
    discovered = await discover(request.project_id, org, current["revision"], request.revision)
    if (not discovered["scope_complete"] or discovered.get("repository_id") != repository_id
            or [pr["number"] for pr in discovered["pull_requests"]] != [pr_number]
            or [task["id"] for task in discovered["tasks"]] != [request.task_id]
            or await baseline(request.project_id, org, repository, repository_id) != current):
        raise error("MANIFEST_REQUIRED", "The deployment delta is not exactly the reviewed single PR and task.")
