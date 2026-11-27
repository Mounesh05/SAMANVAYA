"""Delivery evidence for one authorized task, as observed in synchronized records."""

import re
from datetime import datetime

from fastapi import HTTPException

from core.authorization import verify_project_access
from core.database import col
from core.permissions import Permission, get_user_permissions
from domain.services.ai_evidence_service import _repository
from domain.services.production_evidence import production_evidence
from repositories.pr_repository import PRRepository


MAX_LINKS = 50
MAX_REPORTS = 100
TEST_FIELDS = ("id", "workflow_run_id", "run_attempt", "test_suite", "status",
               "tests_run", "tests_passed", "tests_failed", "tests_skipped", "received_at")


def _org_matches(record, organization):
    return all(record.get(key, organization) == organization for key in ("org_id", "organization_id"))


def _sha(value):
    return value if isinstance(value, str) and re.fullmatch(r"[a-f0-9]{40}", value) else None


async def _task_context(task_id, user):
    role = user.get("role") or user.get("organizational_role") or ""
    if Permission.TRANSITION_TASK not in get_user_permissions(role, user.get("is_admin", False), user.get("designation")):
        raise HTTPException(403, "Delivery workspace access required")
    organization = user.get("org_id")
    if not isinstance(organization, str) or not organization.strip() or not _org_matches(user, organization):
        raise HTTPException(403, "Current organization required")
    task = await col("tasks").find_one({"id": task_id}, {"_id": 0})
    if not task or task.get("id") != task_id or not _org_matches(task, organization):
        raise HTTPException(404, "Task unavailable")
    project_id = task.get("project_id")
    if not isinstance(project_id, str) or not project_id:
        raise HTTPException(404, "Task project unavailable")
    project = await col("projects").find_one({"id": project_id, "org_id": organization}, {"id": 1, "org_id": 1, "organization_id": 1})
    if not project or project["id"] != project_id or not _org_matches(project, organization):
        raise HTTPException(404, "Task project unavailable")
    await verify_project_access(user, project_id)
    return task, organization


async def _linked_prs(task_id, scope, repository):
    edges = await col("entity_relationships").find({
        "target_type": "task", "target_id": task_id, "source_type": "pull_request", "relationship_type": "implements",
    }, {"source_id": 1}).limit(MAX_LINKS + 1).to_list(MAX_LINKS + 1)
    if len(edges) > MAX_LINKS:
        return [], True
    ids = [edge["source_id"] for edge in edges if isinstance(edge.get("source_id"), str)]
    # Older PR syncs retain the named task in normalized title, branch, or description.
    mention = {"$regex": r"\b" + re.escape(task_id) + r"\b", "$options": "i"}
    query = {**scope, "repo_id": {"$regex": "^" + re.escape(repository) + "$", "$options": "i", "$not": {"$type": "array"}},
             "$or": [{"id": {"$in": ids}}, {"title": mention}, {"branch": mention}, {"description": mention}]}
    fields = ("id", "title", "pr_number", "status", "merged_at", "head_sha", "merge_commit_sha", "ci_status")
    rows = await col("pull_requests").find(query, {key: 1 for key in fields}).sort("pr_number", 1).limit(MAX_LINKS + 1).to_list(MAX_LINKS + 1)
    return rows[:MAX_LINKS], len(rows) > MAX_LINKS


def _pr_summary(pr, repository):
    status = "merged" if pr.get("merged_at") else pr.get("status")
    return {"number": pr.get("pr_number") if type(pr.get("pr_number")) is int else None,
            "title": pr.get("title") if isinstance(pr.get("title"), str) else None, "repository": repository,
            "status": status if status in ("open", "merged", "closed") else "unknown",
            "head_sha": _sha(pr.get("head_sha")), "merge_commit_sha": _sha(pr.get("merge_commit_sha"))}


def _valid_report(row):
    counts = [row.get(key) for key in ("tests_run", "tests_passed", "tests_failed", "tests_skipped")]
    try:
        received = datetime.fromisoformat(row.get("received_at", ""))
    except (ValueError, TypeError):
        return False
    return (received.utcoffset() is not None and isinstance(row.get("id"), str) and bool(row["id"])
            and isinstance(row.get("workflow_run_id"), str)
            and re.fullmatch(r"[1-9][0-9]{0,18}", row["workflow_run_id"])
            and int(row["workflow_run_id"]) < 2**63
            and type(row.get("run_attempt")) is int and row["run_attempt"] > 0
            and isinstance(row.get("test_suite"), str) and bool(row["test_suite"])
            and all(type(n) is int and n >= 0 for n in counts) and sum(counts[1:]) == counts[0]
            and row.get("status") in ("passed", "failed", "error", "cancelled"))


def _report_evidence(row, repository):
    report = {key: row[key] for key in TEST_FIELDS}
    report["provenance"] = "legacy_submission"
    if row.get("ingestion_provenance") == "project_ci_token":
        report["provenance"] = "project_ci_token"
    artifact = row.get("artifact_provenance")
    if (isinstance(artifact, dict) and artifact.get("verification_scope") == "GITHUB_ARTIFACT_BYTES_AT_RUN"
            and isinstance(artifact.get("repository"), str) and artifact["repository"].casefold() == repository.casefold()
            and artifact.get("commit_sha") == row["commit_sha"] and artifact.get("run_attempt") == row["run_attempt"]
            and str(artifact.get("workflow_run_id")) == row["workflow_run_id"]
            and type(artifact.get("artifact_id")) is int and artifact["artifact_id"] > 0
            and isinstance(artifact.get("artifact_sha256"), str)
            and re.fullmatch(r"[a-f0-9]{64}", artifact["artifact_sha256"])):
        report.update(provenance="github_artifact", artifact_id=artifact["artifact_id"],
                      artifact_sha256=artifact["artifact_sha256"],
                      workflow_conclusion=artifact.get("workflow_conclusion"))
    return report


async def _workflow_blocker(scope, repo_match, revision, reported_attempts):
    """A newer observed GitHub attempt supersedes an earlier suite report."""
    pipeline = [
        {"$match": {**scope, "source": "github", "event_type": "workflow_run",
                    "payload.repository.full_name": repo_match, "payload.workflow_run.head_sha": revision,
                    "payload.workflow_run.id": {"$in": list(reported_attempts)}}},
        # GitHub timestamps come from the provider. Redelivery order is immaterial.
        {"$sort": {"payload.workflow_run.run_attempt": -1, "payload.workflow_run.updated_at": -1,
                   "payload.workflow_run.status": 1}},
        {"$group": {"_id": "$payload.workflow_run.id", "attempt": {"$first": "$payload.workflow_run.run_attempt"},
                    "status": {"$first": "$payload.workflow_run.status"},
                    "conclusion": {"$first": "$payload.workflow_run.conclusion"}}},
        {"$sort": {"_id": 1}},
    ]
    unknown = None
    async for run in col("webhook_events").aggregate(pipeline):
        run_id, attempt = run["_id"], run.get("attempt")
        if type(run_id) is not int or type(attempt) is not int or attempt < 1:
            unknown = "A workflow update is missing its attempt identity."
            continue
        if attempt < reported_attempts[run_id]:
            continue
        source = f"GitHub Actions run {run_id}, attempt {attempt}"
        if run.get("conclusion") in ("failure", "timed_out", "startup_failure", "action_required"):
            return "failed", f"{source} reported {run['conclusion']}."
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            unknown = f"{source} has no successful completion."
        elif attempt > reported_attempts[run_id]:
            unknown = f"No test report has arrived for {source}."
    return ("unknown", unknown) if unknown else None


async def _qa(scope, repository, revision, pr_number):
    repo_match = {"$regex": "^" + re.escape(repository) + "$", "$options": "i", "$not": {"$type": "array"}}
    source = await col("qa_ci_configs").find_one({**scope, "repository": repo_match, "enabled": True}, {"_id": 1})
    if not source:
        return {"status": "unknown", "runs": [], "reason": "No active QA reporting source for this repository."}
    query = {**scope, "repository": repo_match, "commit_sha": revision, "source": "github_actions",
             "pr_number": {"$in": [pr_number, None], "$not": {"$type": "array"}}}
    docs = await col("test_runs").find(query, {**dict.fromkeys(TEST_FIELDS, 1), "commit_sha": 1, "source": 1,
                                              "ingestion_provenance": 1, "artifact_provenance": 1}
        ).sort([("workflow_run_id", 1), ("run_attempt", 1), ("test_suite", 1), ("id", 1)]).limit(MAX_REPORTS + 1).to_list(MAX_REPORTS + 1)
    if len(docs) > MAX_REPORTS:
        return {"status": "unknown", "runs": [], "reason": "Too many reports to establish complete revision evidence."}
    if not docs:
        return {"status": "unknown", "runs": [], "reason": "No test report was recorded for this exact commit."}
    valid = [doc for doc in docs if _valid_report(doc) and doc["commit_sha"] == revision and doc["source"] == "github_actions"]
    runs = [_report_evidence(row, repository) for row in valid]
    # Each suite keeps its latest observed attempt. A partial rerun must never clear
    # a different suite's failure, and receiving an older attempt late cannot erase a rerun.
    groups = {}
    reported_attempts = {}
    for row in runs:
        run_id = int(row["workflow_run_id"])
        reported_attempts[run_id] = max(row["run_attempt"], reported_attempts.get(run_id, 0))
        key = (row["workflow_run_id"], row["test_suite"])
        if key not in groups or row["run_attempt"] > groups[key][0]["run_attempt"]:
            groups[key] = [row]
        elif row["run_attempt"] == groups[key][0]["run_attempt"]:
            groups[key].append(row)
    current = [row for group in groups.values() for row in group]
    if any(row.get("workflow_conclusion") == "failure" for row in current):
        return {"status": "failed", "runs": runs, "reason": "GitHub reported a failed workflow for a published test report on this commit."}
    if any(row["status"] in ("failed", "error") or row["tests_failed"] > 0 for row in current):
        return {"status": "failed", "runs": runs, "reason": "A recorded suite failed on this commit."}
    if (len(valid) != len(docs)
            or any(row["status"] != "passed" or not row["tests_passed"] or row["tests_skipped"] for row in current)):
        return {"status": "unknown", "runs": runs, "reason": "Recorded suites contain incomplete, skipped, or conflicting results."}
    blocker = await _workflow_blocker(scope, repo_match, revision, reported_attempts)
    if blocker:
        return {"status": blocker[0], "runs": runs, "reason": blocker[1]}
    for row in current:
        attempt = reported_attempts[int(row["workflow_run_id"])]
        if row["run_attempt"] < attempt:
            return {"status": "unknown", "runs": runs,
                    "reason": f"No report for {row['test_suite']} on run {row['workflow_run_id']}, attempt {attempt}."}
    if any(row["provenance"] == "github_artifact" and row.get("workflow_conclusion") != "success" for row in current):
        return {"status": "unknown", "runs": runs, "reason": "A published test report has no verified successful workflow conclusion. Import a current workflow attempt."}
    # An old uploader can duplicate an authenticated submission. Attribute
    # coverage only when suite, run, attempt, commit and outcome agree.
    for group in groups.values():
        trusted = [row for row in group if row["provenance"] != "legacy_submission"]
        if not trusted:
            return {"status": "unknown", "runs": runs,
                    "reason": "A suite has only a legacy CI report. Reprovision project CI and rerun, or import its published GitHub artifact."}
        if len(trusted) != 1 or any(row["tests_run"] != trusted[0]["tests_run"] for row in group):
            return {"status": "unknown", "runs": runs, "reason": "Multiple reports disagree or have ambiguous provenance for a test suite."}
    return {"status": "passed", "runs": runs, "reason": "Recorded suites passed. QA must confirm required check coverage."}


async def build_delivery_status(task_id: str, user: dict) -> dict:
    task, organization = await _task_context(task_id, user)
    return await delivery_evidence(task, organization)


async def delivery_evidence(task: dict, organization: str) -> dict:
    """Assemble observations after the caller has authorized this task and tenant."""
    task_id = task["id"]
    project_id = task["project_id"]
    scope = PRRepository._project_scope([project_id], organization)
    requirement = {"title": task.get("title"), "story": None}
    transition_id = task.get("last_transition_id")
    if not transition_id:
        # Older task records keep reopen history in project-scoped activity.
        reopened = await col("activities").find_one({
            **scope, "item_id": {"$eq": task_id, "$not": {"$type": "array"}}, "item_type": "task",
            "event_type": "status_changed", "details.from_status": "done", "details.to_status": "in_progress",
        }, {"_id": 1}, sort=[("created_at", -1), ("_id", -1)])
        if reopened:
            transition_id = str(reopened["_id"])
    # Preserve the original evidence fingerprint for unchanged, completed legacy work.
    if transition_id or task.get("status") != "done":
        requirement["task_workflow"] = {"status": task.get("status", "todo"), "last_transition_id": transition_id}
    if isinstance(task.get("story_id"), str):
        requirement["story"] = await col("stories").find_one(
            {**scope, "id": task["story_id"]}, {"_id": 0, "id": 1, "title": 1, "description": 1})
    readout = {
        "task_id": task_id, "organization_id": organization, "project_id": project_id, "requirement": requirement,
        "revision": None, "revision_kind": None,
        "implementation": {"status": "unknown", "pull_requests": [], "reason": "No linked pull request was found."},
        "qa": {"status": "unknown", "runs": [], "reason": "A single linked pull request with an exact revision is required."},
        "production": {"status": "unknown", "reason": "No unambiguous release commit was identified."},
        "readiness": {"status": "unknown", "reason": "A merged change and exact release-commit test results are required."},
    }
    try:
        owner, name = await _repository(project_id, organization)
    except HTTPException as error:
        if error.status_code != 409:
            raise
        readout["implementation"]["reason"] = "A unique project repository connection is required."
        return readout
    repository = f"{owner}/{name}"
    rows, truncated = await _linked_prs(task_id, scope, repository)
    prs = [_pr_summary(row, repository) for row in rows]
    if truncated or len(prs) > 1:
        readout["implementation"] = {"status": "multiple", "pull_requests": prs,
                                     "reason": "The linked changes do not identify a single release candidate."}
        return readout
    if not prs:
        return readout
    pr = prs[0]
    readout["implementation"] = {"status": pr["status"], "pull_requests": prs, "reason": "Latest synchronized pull request state."}
    merged = pr["status"] == "merged"
    merge_sha = pr["merge_commit_sha"] if merged else None
    revision = merge_sha or pr["head_sha"]
    if not revision or not pr["number"] or pr["number"] < 1:
        return readout
    readout.update(revision=revision, revision_kind="merge_commit" if merge_sha else "pr_head")
    qa = await _qa(scope, repository, revision, pr["number"])
    readout["qa"] = qa
    if merge_sha:
        readout["production"] = await production_evidence(project_id, repository, revision, organization)
    if task.get("status") == "blocked":
        readout["readiness"] = {"status": "blocked", "reason": "The task is marked blocked. Review the blocker before release."}
    elif qa["status"] == "failed":
        readout["readiness"] = {"status": "blocked", "reason": "A recorded test failure needs resolution."}
    elif merged and not merge_sha:
        readout["readiness"]["reason"] = "Only the pull request head is known. Synchronize the merged revision before release review."
    elif revision == pr["head_sha"] and rows[0].get("ci_status") in ("failing", "pending"):
        readout["readiness"] = {"status": "blocked", "reason": "Synchronized CI checks are failing or pending for this commit."}
    elif merge_sha and qa["status"] == "passed":
        readout["readiness"] = {"status": "awaiting_review", "reason": "QA must confirm required checks for the release commit before DevOps decides."}
    return readout
