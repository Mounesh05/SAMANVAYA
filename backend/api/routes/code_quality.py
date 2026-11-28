"""
Unified Code Quality API endpoints.
Language-agnostic — the frontend never needs to know if a project is Java or C++.

Endpoints:
  POST   /api/code-quality/analyze                → start async run
  GET    /api/code-quality/runs/{run_id}          → status + results
  GET    /api/code-quality/runs/{run_id}/findings → paginated findings
  GET    /api/code-quality/repositories/{repo_id}/latest
  GET    /api/code-quality/repositories/{repo_id}/history
  POST   /api/code-quality/projects/{project_id}/config
  GET    /api/code-quality/projects/{project_id}/config
"""

import asyncio
import hashlib
import json
import re
import uuid
from pymongo.errors import DuplicateKeyError
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.config import settings
from core.database import col
from core.dependencies import get_current_user, require_permission
from core.permissions import Permission
from core.authorization import code_quality_tenant_filter, verify_code_quality_access, verify_project_access
from domain.models.project_code_config import ProjectCodeConfig
from domain.services.code_quality_service import CodeQualityService
from domain.services import code_quality_jobs as jobs
from domain.services.quality_run_results import expired, run_deadline, RUN_TIMEOUT_SECONDS
from domain.services.ai_run_access import invocation_scope, permissions, ACCESS_VERSION
from intelligence.algorithms.discovery.service import MAX_FILES
from intelligence.analyzers.language_detector import LanguageDetector
from intelligence.analyzers.registry import list_runtime_verified_languages, list_supported_languages

router = APIRouter()
cq_service = CodeQualityService()
lang_detector = LanguageDetector()
RUNS_COLLECTION = "code_quality_runs"
FINDINGS_COLLECTION = "code_quality_findings"
CONFIGS_COLLECTION = "project_configs"


# ── Request / Response models ─────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    repository_id: str
    pr_number: Optional[int] = Field(default=None, ge=1)
    changed_files: List[str] = []
    pr_context: Dict[str, Any] = {}
    analysis_level: Literal["quick", "standard", "deep", "purpose_discovery"] = "standard"   # "quick" | "standard" | "deep"
    use_ai: bool = True
    reanalysis_of: Optional[str] = None
    file_scope: Optional[Literal["repository", "selected_files", "pr_comparison"]] = None
    repository_ref: Optional[str] = Field(default=None, max_length=200, pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


class RunStatus(BaseModel):
    run_id: str
    status: str         # "pending" | "running" | "completed" | "failed"
    language: Optional[str] = None
    quality_score: Optional[int] = None
    quality_grade: Optional[str] = None
    risk_score: Optional[int] = None
    risk_level: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


MAX_PR_ANALYSIS_PATHS = 100


async def _pull_request_paths(project_id: str, org_id: Optional[str], pr_number: int) -> List[str]:
    """Changed (non-deleted) paths of one PR in the project's connected repository."""
    from domain.services.ai_evidence_service import _repository
    from domain.services.github_api_service import GitHubAPIService
    owner, repo = await _repository(project_id, org_id)
    try:
        files = await GitHubAPIService().client.get_pr_files(owner, repo, pr_number)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Pull request files are unavailable from GitHub") from None
    paths = list(dict.fromkeys(
        item["filename"] for item in files or []
        if isinstance(item, dict) and isinstance(item.get("filename"), str)
        and item.get("status") != "removed" and 0 < len(item["filename"]) <= 500
    ))[:MAX_PR_ANALYSIS_PATHS]
    if not paths:
        raise HTTPException(422, "The pull request has no analysable changed files")
    return paths


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/analyze", status_code=202)
async def start_analysis(
    body: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_permission(Permission.TRIGGER_CODE_ANALYSIS)),
):
    """
    Start an async code quality analysis run.
    Returns run_id immediately — poll /runs/{run_id} for results.
    Requires TRIGGER_CODE_ANALYSIS permission (QA, DEVOPS roles by default).
    """
    repository_id = body.repository_id.strip()
    changed_files = list(dict.fromkeys(path.strip() for path in body.changed_files if path.strip()))
    if len(changed_files) > 100 or any(len(path) > 500 for path in changed_files):
        raise HTTPException(422, "Select at most 100 repository paths of up to 500 characters each")
    if not repository_id:
        raise HTTPException(status_code=422, detail="A real repository or project ID is required")
    if body.file_scope == "repository" and (changed_files or body.pr_number):
        raise HTTPException(422, "Whole repository analysis requires a branch or commit without file or PR inputs")
    if body.file_scope == "pr_comparison" and (not body.pr_number or changed_files or body.reanalysis_of):
        raise HTTPException(422, "Select a pull request to compare its base and head revisions")
    if body.file_scope == "pr_comparison" and body.analysis_level == "purpose_discovery":
        raise HTTPException(422, "Function discovery requires repository or selected files scope")
    if not changed_files and not body.pr_number and body.file_scope != "repository":
        raise HTTPException(status_code=422, detail="At least one real changed file is required")
    # CR-002: TRIGGER_CODE_ANALYSIS holders (QA, DevOps) analyse projects they
    # are assigned to. Requiring project *write* access made this unusable:
    # no role holding the permission ever has write access.
    await verify_project_access(user, repository_id)
    changed_files_source = "explicit"
    if not changed_files and body.file_scope in (None, "selected_files") and body.pr_number:
        # CQ-01: a PR request without paths analyses the PR's own changed files,
        # resolved server-side from the connected repository (never client paths).
        changed_files = await _pull_request_paths(repository_id, user.get("org_id"), body.pr_number)
        changed_files_source = "pull_request"
    # Public callers select a project and files, never host filesystem roots or
    # supposedly verified source bytes/revisions. Connected snapshots are
    # resolved by the server in _run_analysis; internal adapters retain their
    # separately supplied trusted context.
    server_source_fields = {"repo_path", "source_files", "commit_sha", "source_revision",
                            "source_diagnostics", "source_provenance", "isolated_quality_worker",
                            "project_id", "org_id", "organization_id"}
    if server_source_fields.intersection(body.pr_context):
        raise HTTPException(status_code=422, detail="Source location and revision must be resolved by the server")
    if body.repository_ref and (body.pr_number or body.reanalysis_of or ".." in body.repository_ref or "//" in body.repository_ref):
        raise HTTPException(422, "Select one repository revision, PR or prior run")
    normalized_body = body.model_copy(
        update={"repository_id": repository_id, "changed_files": changed_files}
    )

    # CQ-05: bounded intake per organisation; waiting work is never unbounded.
    if await col(RUNS_COLLECTION).count_documents(jobs.active_filter(user.get("org_id"))) >= settings.CODE_QUALITY_MAX_PENDING_PER_ORG:
        raise HTTPException(429, "Too many analyses are already waiting or running for your organisation. Retry shortly.")

    run_id = f"RUN-{uuid.uuid4().hex[:12].upper()}"
    pinned_revision = None
    if body.reanalysis_of:
        original = await col(RUNS_COLLECTION).find_one({"run_id": body.reanalysis_of, "repository_id": repository_id,
                                                         **code_quality_tenant_filter(user)})
        if not original:
            raise HTTPException(404, "Original run unavailable")
        await verify_code_quality_access(user, repository_id, original)
        if original.get("status") in ("pending", "running", "analyzing") and not expired(original):
            raise HTTPException(409, "The original analysis is still active")
        pinned_revision = original.get("commit_sha")
        if not re.fullmatch(r"[a-f0-9]{40}", pinned_revision or "") or body.pr_number != original.get("pr_number"):
            raise HTTPException(422, "Reanalysis requires the original revision and PR identity")
        from domain.services.ai_evidence_service import _repository
        owner, repo = await _repository(repository_id, user.get("org_id"))
        recorded_repo = (original.get("execution_provenance") or {}).get("repository") or original.get("repository")
        if recorded_repo and recorded_repo.casefold() != (owner + "/" + repo).casefold():
            raise HTTPException(409, "Original repository mapping has changed")
        if body.file_scope == "repository" and original.get("file_scope") != "repository":
            raise HTTPException(422, "Whole repository reanalysis requires an original whole repository run")
        key = [repository_id, user.get("org_id"), body.reanalysis_of, sorted(set(changed_files)), body.analysis_level, body.use_ai]
        run_id = "RUN-" + hashlib.sha256(json.dumps(key).encode()).hexdigest()[:24].upper()
    if body.file_scope == "repository":
        changed_files_source = "repository_tree"
    elif body.file_scope == "pr_comparison":
        changed_files_source = "pull_request_comparison"
    now = datetime.now(timezone.utc).isoformat()

    # Detect language immediately (fast — no tools needed)
    profile = lang_detector.detect_from_files(changed_files)

    # Create the run record in PENDING state
    run_doc = {
        "run_id": run_id,
        "repository_id": repository_id,
        "pr_number": body.pr_number,
        "language": profile.primary_language,
        "detected_languages": profile.detected_languages,
        "analysis_level": body.analysis_level,
        "use_ai": body.use_ai,
        "repository_ref": body.repository_ref,
        "status": "pending",
        "triggered_by": user.get("employee_id", user.get("id", "")),
        "org_id": user.get("org_id"),
        "changed_files": changed_files,
        "changed_files_source": changed_files_source,
        **({"file_scope": body.file_scope} if body.file_scope else {}),
        **({"selected_scope": changed_files} if body.file_scope == "selected_files" else {}),
        "triggered_by_name": user.get("name", ""),
        "created_at": now,
        "work_deadline": run_deadline(),
        "completed_at": None,
        "quality_score": None,
        "quality_grade": None,
        "risk_score": None,
        "risk_level": None,
        "risk_factors": [],
        "tools_executed": [],
        "tools_skipped": [],
        "analysis_duration_ms": None,
        "error": None,
        # CQ-05: durable intake; recovery restarts a run that no process claimed.
        "request": jobs.stored_request(normalized_body, user.get("employee_id"), pinned_revision, user.get("org_id")),
    }

    collection = col(RUNS_COLLECTION)
    if body.reanalysis_of:
        run_doc.update(_id=run_id, reanalysis_of=body.reanalysis_of, commit_sha=pinned_revision)
    try:
        await collection.insert_one(run_doc)
    except DuplicateKeyError:
        existing = await collection.find_one({"_id": run_id, "repository_id": repository_id, **code_quality_tenant_filter(user)})
        if not existing:
            raise
        return {"run_id": run_id, "status": existing["status"], "duplicate": True}

    # Queue the heavy analysis in the background
    jobs.mark_queued(run_id)
    background_tasks.add_task(
        _run_analysis,
        run_id=run_id,
        body=normalized_body,
        profile=profile,
        actor_id=user.get("employee_id"),
        pinned_revision=pinned_revision, expected_org=user.get("org_id"),
    )

    return {
        "run_id": run_id,
        "status": "pending",
        "language": profile.primary_language,
        "detected_languages": profile.detected_languages,
        "message": f"Analysis started. Poll GET /api/code-quality/runs/{run_id} for results.",
    }


@router.get("/runs/{run_id}")
async def get_run(run_id: str, user: dict = Depends(get_current_user)):
    """Get the current status and results of a code quality run."""
    collection = col(RUNS_COLLECTION)
    # v4 BASE-04: scope the lookup to the caller's tenant first, so another
    # organisation's run is indistinguishable from a missing one.
    run = await collection.find_one({"run_id": run_id, **code_quality_tenant_filter(user)}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Authorization: verify user has access to the run's repository
    await verify_code_quality_access(user, run.get("repository_id"), run)
    
    return await _visible_ai_result(run, user)


@router.get("/runs/{run_id}/findings")
async def get_run_findings(
    run_id: str,
    severity: Optional[str] = Query(None, description="Filter: critical|high|medium|low"),
    category: Optional[str] = Query(None, description="Filter: security|syntax|type|maintainability"),
    limit: int = Query(50, ge=1, le=500),
    skip: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """Get paginated findings for a completed analysis run."""
    # First verify user has access to this run
    runs_collection = col(RUNS_COLLECTION)
    run = await runs_collection.find_one({"run_id": run_id, **code_quality_tenant_filter(user)},
                                         {"repository_id": 1, "org_id": 1, "organization_id": 1})
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Authorization: verify user has access to the run's repository
    await verify_code_quality_access(user, run.get("repository_id"), run)
    
    query: dict = {"run_id": {"$eq": run_id, "$not": {"$type": "array"}}, **code_quality_tenant_filter(user),
                   "$or": [{"repository_id": {"$exists": False}},
                           {"repository_id": {"$eq": run["repository_id"], "$not": {"$type": "array"}}}]}
    if severity:
        query["severity"] = severity
    if category:
        query["category"] = category

    collection = col(FINDINGS_COLLECTION)
    findings = await collection.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    total = await collection.count_documents(query)

    return {
        "run_id": run_id,
        "findings": findings,
        "total": total,
        "returned": len(findings),
    }


@router.get("/runs/{run_id}/functions")
async def get_discovered_functions(
    run_id: str, limit: int = Query(50, ge=1, le=256), skip: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
):
    """Read preserved function evidence with the same authorization as the run."""
    run = await get_run(run_id, user)
    from intelligence.evidence.function_purpose import FunctionDiscovery
    report = run.get("function_discovery") or FunctionDiscovery().model_dump()
    functions = report.get("functions", [])
    return {**report, "run_id": run_id, "functions": functions[skip:skip + limit],
            "total": len(functions), "returned": len(functions[skip:skip + limit])}


@router.get("/repositories/{repository_id}/latest")
async def get_latest_run(
    repository_id: str,
    user: dict = Depends(get_current_user),
):
    """Get the most recent completed analysis run for a repository."""
    # Authorization: verify user has access to this repository
    await verify_code_quality_access(user, repository_id)
    
    collection = col(RUNS_COLLECTION)
    run = await collection.find_one(
        {"repository_id": {"$eq": repository_id, "$not": {"$type": "array"}}, "status": "completed", **code_quality_tenant_filter(user)},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not run:
        raise HTTPException(status_code=404, detail="No completed runs for this repository")
    return await _visible_ai_result(run, user)


@router.get("/repositories/{repository_id}/history")
async def get_run_history(
    repository_id: str,
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """Get historical quality/risk trend for a repository."""
    # Authorization: verify user has access to this repository
    await verify_code_quality_access(user, repository_id)
    
    collection = col(RUNS_COLLECTION)
    runs = (
        await collection.find(
            {"repository_id": {"$eq": repository_id, "$not": {"$type": "array"}}, **code_quality_tenant_filter(user)},
            {"_id": 0, "run_id": 1, "created_at": 1, "language": 1,
             "quality_score": 1, "quality_grade": 1, "risk_score": 1,
             "risk_level": 1, "status": 1, "pr_number": 1,
             "analysis_level": 1, "analysis_scope": 1, "quality_analysis_status": 1,
             "file_scope": 1, "repository_ref": 1, "commit_sha": 1, "is_truncated": 1,
             "changed_files": 1, "source_selection_count": 1, "files_analyzed": 1, "file_counts": 1,
             "kind": 1, "work_deadline": 1, "source_provenance.method": 1, "reason": 1, "quality_unavailable_reason": 1, "tools_executed": 1, "tools_skipped": 1},
        )
        .sort("created_at", -1)
        .limit(limit)
        .to_list(limit)
    )
    return {"repository_id": repository_id, "history": [analysis_scope(run) for run in runs], "count": len(runs)}


@router.get("/repositories/{repository_id}/branches")
async def list_repository_branches(
    repository_id: str,
    user: dict = Depends(get_current_user),
):
    """List branches for a connected project's GitHub repository."""
    await verify_code_quality_access(user, repository_id)
    config = await col("github_project_configs").find_one({"project_id": repository_id}, {"_id": 0})
    if not config:
        raise HTTPException(status_code=404, detail="No GitHub repository is connected to this project")
    from domain.services.ai_evidence_service import _repository
    owner, repo = await _repository(repository_id, user.get("org_id"))
    default_branch = config.get("default_branch") or "main"
    try:
        from domain.services.github_api_service import GitHubAPIService
        raw_branches = await GitHubAPIService().client.list_branches(owner, repo)
        branches = [
            {
                "name": b["name"],
                "commit_sha": (b.get("commit") or {}).get("sha"),
                "protected": bool(b.get("protected", False)),
            }
            for b in (raw_branches or [])
            if isinstance(b, dict) and isinstance(b.get("name"), str)
        ]
        if default_branch and not any(b["name"] == default_branch for b in branches):
            branches.insert(0, {"name": default_branch, "commit_sha": None, "protected": False})
        return {
            "repository_id": repository_id,
            "repository": f"{owner}/{repo}",
            "default_branch": default_branch,
            "branches": branches,
            "branches_available": True,
        }
    except Exception:
        return {
            "repository_id": repository_id,
            "repository": f"{owner}/{repo}",
            "default_branch": default_branch,
            "branches": [{"name": default_branch, "commit_sha": None, "protected": False}],
            "branches_available": False,
        }


@router.get("/repositories/{repository_id}/files")
async def list_repository_files(
    repository_id: str,
    ref: Optional[str] = Query(default=None, max_length=200),
    user: dict = Depends(get_current_user),
):
    """Browse supported source files and directories at a specific branch or commit."""
    await verify_code_quality_access(user, repository_id)
    if ref and (".." in ref or "//" in ref or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", ref)):
        raise HTTPException(status_code=422, detail="Invalid branch or commit reference")
    config = await col("github_project_configs").find_one({"project_id": repository_id}, {"_id": 0})
    if not config:
        raise HTTPException(status_code=404, detail="No GitHub repository is connected to this project")
    cfg_doc = await col(CONFIGS_COLLECTION).find_one({"project_id": repository_id}, {"_id": 0})
    project_config = ProjectCodeConfig(**cfg_doc) if cfg_doc else ProjectCodeConfig(project_id=repository_id)
    from domain.services.ai_evidence_service import _repository
    owner, repo = await _repository(repository_id, user.get("org_id"))
    target_ref = ref or config.get("default_branch") or "main"
    try:
        from domain.services.github_api_service import GitHubAPIService
        github = GitHubAPIService()
        commit = await github.client.get_commit(owner, repo, target_ref)
        revision = commit.get("sha")
        summary = await github.list_repository_tree_summary(
            owner, repo, revision, excluded_paths=project_config.excluded_paths
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail="Could not retrieve repository source tree from GitHub") from error

    return {
        "repository_id": repository_id,
        "repository": f"{owner}/{repo}",
        "ref": target_ref,
        "commit_sha": revision,
        "files": summary["files"],
        "directories": summary["directories"],
        "total_supported_files": len(summary["files"]),
        "excluded_files_count": summary["excluded_files_count"],
        "unsupported_files_count": summary["unsupported_files_count"],
        "unsupported_extensions": summary["unsupported_extensions"],
        "max_files_per_run": MAX_FILES,
    }


@router.get("/repositories/{repository_id}/pull-requests")
async def list_repository_pull_requests(
    repository_id: str,
    state: str = Query(default="all", pattern="^(open|closed|all)$"),
    user: dict = Depends(get_current_user),
):
    """List pull requests for a connected repository so users can choose a PR without typing paths."""
    await verify_code_quality_access(user, repository_id)
    config = await col("github_project_configs").find_one({"project_id": repository_id}, {"_id": 0})
    if not config:
        raise HTTPException(status_code=404, detail="No GitHub repository is connected to this project")
    from domain.services.ai_evidence_service import _repository
    owner, repo = await _repository(repository_id, user.get("org_id"))
    try:
        from domain.services.github_api_service import GitHubAPIService
        raw_prs = await GitHubAPIService().list_pull_requests(owner, repo, state=state, per_page=30)
        pull_requests = [
            {
                "number": pr.get("number"),
                "title": pr.get("title", ""),
                "state": pr.get("state", "open"),
                "base_ref": (pr.get("base") or {}).get("ref"),
                "head_ref": (pr.get("head") or {}).get("ref"),
                "base_sha": (pr.get("base") or {}).get("sha"),
                "head_sha": (pr.get("head") or {}).get("sha"),
                "author": (pr.get("user") or {}).get("login"),
                "updated_at": pr.get("updated_at"),
            }
            for pr in (raw_prs or [])
            if isinstance(pr, dict) and isinstance(pr.get("number"), int)
        ]
        return {
            "repository_id": repository_id,
            "repository": f"{owner}/{repo}",
            "pull_requests": pull_requests,
            "source": "github",
        }
    except Exception as error:
        raise HTTPException(502, "Could not retrieve pull requests from GitHub") from error


@router.post("/projects/{project_id}/config")
async def save_project_config(
    project_id: str,
    config: ProjectCodeConfig,
    user: dict = Depends(get_current_user),
):
    """Save per-project code quality configuration."""
    # Authorization: verify user has write access to this project
    await verify_project_access(user, project_id, require_write=True)
    
    config.project_id = project_id
    collection = col(CONFIGS_COLLECTION)
    await collection.update_one(
        {"project_id": project_id},
        {"$set": config.model_dump(exclude={"algorithm_requirement_source_ids"})},
        upsert=True,
    )
    return {"message": "Project config saved", "project_id": project_id}


@router.get("/projects/{project_id}/config")
async def get_project_config(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """Get per-project code quality configuration."""
    # Authorization: verify user has access to this project
    await verify_code_quality_access(user, project_id)
    
    collection = col(CONFIGS_COLLECTION)
    doc = await collection.find_one({"project_id": {"$eq": project_id, "$not": {"$type": "array"}}}, {"_id": 0})
    if not doc:
        # Return defaults if not configured
        return ProjectCodeConfig(project_id=project_id).model_dump()
    await verify_code_quality_access(user, project_id, doc)
    return doc


@router.get("/languages")
async def supported_languages():
    """Languages analyzed with a proven toolchain, and registered adapters that are not yet verified."""
    verified = list_runtime_verified_languages()
    return {"supported_languages": verified,
            "experimental_languages": [lang for lang in list_supported_languages() if lang not in verified]}


# ── Background task ───────────────────────────────────────────────────────────

async def _visible_ai_result(run, user):
    """Apply the AI tenant/permission boundary to optional interpretation fields."""
    run = analysis_scope(run)
    if "ai_analysis" not in run:
        return run
    if run.get("ai_status") == "skipped":
        return {**run, "ai_analysis": {"status": "skipped", "errors": []},
                "ai_provenance": {}, "ai_authorization_scope": None}
    scope = run.get("ai_authorization_scope") or {}
    if not isinstance(scope, dict):
        scope = {}
    if (user.get("role", "").upper() != "HR" and Permission.VIEW_AI_EVALUATION in permissions(user)
            and scope.get("access_version") == ACCESS_VERSION and scope.get("owner_id")
            and scope.get("project_id") == run.get("repository_id")):
        try:
            current = await invocation_scope(user, {"project_id": scope["project_id"]})
            if current["organization_id"] == scope.get("organization_id"):
                return run
        except HTTPException:
            pass
    return {**run, "ai_analysis": {"status": "unavailable", "analysis": None, "errors": ["AI_RESULT_ACCESS_DENIED"]},
            "ai_status": "unavailable", "ai_provenance": {}, "ai_authorization_scope": None}


def analysis_scope(run):
    """Read-time metadata for historical discovery snapshots; never rewrite them."""
    result = dict(run)
    result.pop("analyzer_evidence", None)
    if expired(run):
        result.update(status="failed", quality_analysis_status="failed", error="Worker deadline expired before a result was recorded.")
        return result
    if run.get("kind") == "pr_algorithm_intelligence":
        result["analysis_scope"] = "pr_algorithm_intelligence"
        return result
    if run.get("tools_skipped") and run.get("quality_score") is None and run.get("status") == "completed":
        result.update(status="failed", quality_analysis_status="failed", analysis_scope="code_quality")
        return result
    if run.get("analysis_level") == "purpose_discovery" or (run.get("source_provenance") or {}).get("method") == "github-exact-revision" or (
        run.get("function_discovery") and not run.get("tools_executed")
        and run.get("quality_score") is None and run.get("risk_score") is None
    ):
        result.setdefault("analysis_scope", "purpose_discovery")
        result.setdefault("quality_analysis_status", "not_run")
        result.setdefault("quality_unavailable_reason", "This snapshot contains static function discovery only. Quality and risk tools were not run.")
    return result


async def _run_analysis(run_id: str, body: AnalyzeRequest, profile: Any, actor_id: Optional[str] = None,
                        pinned_revision: Optional[str] = None, expected_org: Optional[str] = None) -> None:
    # CQ-05: bounded concurrency, then an atomic claim. A run another process
    # (or recovery) already took is left alone.
    try:
        async with jobs.slots():
            collection = col(RUNS_COLLECTION)
            if not await jobs.claim(collection, run_id):
                return
            try:
                async with asyncio.timeout(RUN_TIMEOUT_SECONDS):
                    await jobs.run_with_lease(collection, run_id, lambda: _execute_analysis(
                        run_id, body, actor_id, pinned_revision, expected_org))
            except (TimeoutError, asyncio.CancelledError) as exc:
                await collection.update_one(jobs.owned(run_id),
                    {"$set": {"status": "failed", "quality_analysis_status": "failed", "error": "Quality worker interrupted or timed out",
                              "completed_at": datetime.now(timezone.utc).isoformat()}})
                if isinstance(exc, asyncio.CancelledError):
                    raise
    finally:
        jobs.mark_done(run_id)


def _dispatch_recovered(run: dict) -> None:
    """Start a stored run that no process claimed (CQ-05 recovery)."""
    stored = run["request"]
    body = AnalyzeRequest.model_validate(stored["body"])
    profile = lang_detector.detect_from_files(body.changed_files)
    jobs.mark_queued(run["run_id"])
    task = asyncio.create_task(_run_analysis(run["run_id"], body, profile, actor_id=stored.get("actor_id"),
                                             pinned_revision=stored.get("pinned_revision"),
                                             expected_org=stored.get("expected_org")))
    _recovered_tasks.add(task)
    task.add_done_callback(_recovered_tasks.discard)


_recovered_tasks: set = set()
recovery = jobs.RecoveryLoop(lambda: col(RUNS_COLLECTION), _dispatch_recovered)


async def _execute_analysis(run_id, body, actor_id, pinned_revision, expected_org):
    """
    Heavy analysis executed in the background.
    Updates the run document with results when complete.
    """
    collection = col(RUNS_COLLECTION)
    findings_col = col(FINDINGS_COLLECTION)

    owned = jobs.owned(run_id)  # CQ-05: every write is fenced on this process's claim

    try:
        # Load project config
        cfg_col = col(CONFIGS_COLLECTION)
        cfg_doc = await cfg_col.find_one({"project_id": body.repository_id})
        project_config = (
            ProjectCodeConfig(**cfg_doc) if cfg_doc
            else ProjectCodeConfig(project_id=body.repository_id)
        )

        # Run analysis via CodeQualityService
        deep = body.analysis_level == "deep"
        paths = body.changed_files
        scope_details = {}
        if body.file_scope == "pr_comparison":
            from domain.services.ai_evidence_service import _repository
            from domain.services.github_api_service import GitHubAPIService
            from domain.services.pr_quality_comparison import compare_revisions

            owner, repo = await _repository(body.repository_id, expected_org)
            github = GitHubAPIService()
            pr = await github.client.get_pull_request(owner, repo, body.pr_number)
            files = await github.client.get_pr_files(owner, repo, body.pr_number)
            current = await github.client.get_pull_request(owner, repo, body.pr_number)
            if pr.get("number") != body.pr_number or any(
                pr[side]["sha"] != current[side]["sha"] for side in ("base", "head")
            ):
                raise ValueError("Pull request revisions changed during source selection. Start a new comparison.")
            await compare_revisions(
                github, body.repository_id, owner, repo, pr, files, actor_id,
                claimed_run=owned, expected_org=expected_org, deep_analysis=deep,
            )
            return
        context = {**body.pr_context, "project_id": body.repository_id, "pr_number": body.pr_number}
        project_record = await col("projects").find_one({"id": body.repository_id}, {"org_id": 1})
        context["organization_id"] = project_record.get("org_id") if project_record else None
        if expected_org and context["organization_id"] != expected_org:
            raise ValueError("The project organization has changed")
        if not context.get("repo_path") and "source_files" not in context:
            # The UI submits a project, not host paths. Use the already-configured
            # GitHub repository and freeze all discovery reads to one revision.
            config = await col("github_project_configs").find_one({"project_id": body.repository_id})
            if not config and body.file_scope in ("repository", "selected_files"):
                raise ValueError("Connect a GitHub repository to analyze selected files or a whole revision")
            if config:
                try:
                    from domain.services.github_api_service import GitHubAPIService
                    github = GitHubAPIService()
                    owner, repo = config["repository_owner"], config["repository_name"]
                    if expected_org:
                        from domain.services.ai_evidence_service import _repository
                        verified_owner, verified_repo = await _repository(body.repository_id, expected_org)
                        if (verified_owner, verified_repo) != (owner, repo):
                            raise ValueError("Repository mapping changed")
                    if pinned_revision:
                        revision = pinned_revision
                    elif body.pr_number:
                        pr = await github.client.get_pull_request(owner, repo, body.pr_number)
                        revision = pr.get("head", {}).get("sha")
                    else:
                        commit = await github.client.get_commit(
                            owner, repo, body.repository_ref or config.get("default_branch") or "main",
                        )
                        revision = commit.get("sha")
                    await collection.update_one(owned, {"$set": {"commit_sha": revision, "repository": owner + "/" + repo}})
                    if body.file_scope == "repository":
                        paths = await github.list_repository_analysis_paths(
                            owner, repo, revision, excluded_paths=project_config.excluded_paths,
                        )
                    elif body.file_scope == "selected_files":
                        paths = await github.expand_selected_paths(
                            owner, repo, revision, paths, excluded_paths=project_config.excluded_paths,
                        )
                    if body.file_scope:
                        if not paths:
                            await collection.update_one(owned, {"$set": {
                                "status": "unsupported",
                                "quality_analysis_status": "unsupported",
                                "quality_unavailable_reason": "No supported source files found in the selected scope.",
                                "source_selection_count": 0,
                                "changed_files": [],
                                "completed_at": datetime.now(timezone.utc).isoformat(),
                            }})
                            return
                        scope_details = {
                            "source_selection_count": len(paths),
                            "is_truncated": len(paths) > MAX_FILES,
                        }
                        paths = paths[:MAX_FILES]
                        await collection.update_one(owned, {"$set": {"changed_files": paths, **scope_details}})
                    sources, diagnostics = await github.fetch_analysis_sources(
                        owner, repo, [{"filename": p} for p in paths], revision, include_context=True, verified_snapshot=True,
                    )
                    context.update(source_files=sources, source_diagnostics=diagnostics, commit_sha=revision)
                    from intelligence.analyzers.isolated import source_provenance
                    context["source_provenance"] = source_provenance(body.repository_id, owner + "/" + repo, revision, sources,
                                                                    context["organization_id"])
                except Exception:
                    if body.file_scope in ("repository", "selected_files") or any(path.endswith("/") for path in body.changed_files):
                        raise ValueError("Could not resolve the selected source scope from GitHub") from None
                    context.update(source_files={}, source_diagnostics=[{"kind": "connected_source_unavailable"}])
        if body.analysis_level == "purpose_discovery":
            discovery = await cq_service.discover_functions(paths, context)
            await collection.update_one(owned, {"$set": {
                "status": "failed" if discovery.status == "unavailable" else "completed",
                "analysis_scope": "purpose_discovery", "quality_analysis_status": "not_run",
                "function_discovery": discovery.model_dump(mode="json"), "commit_sha": context.get("commit_sha"),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }})
            return
        evidence = await cq_service.analyze_pr(
            changed_files=paths,
            pr_context=context,
            project_config=project_config,
            deep_analysis=deep,
        )

        from domain.services.quality_run_results import measure_quality, quality_findings, store_findings
        from intelligence.baselines.repository_baseline import RepositoryBaseline
        baseline = None if body.file_scope == "repository" else RepositoryBaseline()
        result = await measure_quality(evidence, paths, baseline)
        if scope_details.get("is_truncated"):
            result["quality_analysis_status"] = "partial" if result.get("quality_score") is not None else result["quality_analysis_status"]
        findings = quality_findings(evidence)

        # AI Code Agent (if requested and not quick)
        from domain.services.internal_agent_adapter import resolve_code_authority, interpret_code, failed_interpretation
        ai_analysis = {"status": "skipped", "errors": []}
        authority = None
        if body.use_ai and body.analysis_level != "quick":
            try:
                authority = await resolve_code_authority({"employee_id": actor_id}, context, operation="code_quality")
                from intelligence.quality_engine import snapshot_context_diagnostic
                observed_findings = [f for f in findings if not snapshot_context_diagnostic(f.source_tool, f.rule_id)]
                observations = [{"file": f.file_path, "line": f.line_number, "rule_id": f.rule_id,
                                 "message": f.message[:500]} for f in observed_findings[:20]]
                ai_analysis = await interpret_code(
                    {"files_analyzed": evidence.files_analyzed, "static_analysis": {"findings": observations},
                     "complexity": result["complexity"], "tests": {"coverage": {"line_coverage": evidence.testing.coverage_percentage}}},
                    {"project_id": body.repository_id, "commit_sha": evidence.commit_sha}, authority,
                    evidence_available=result["quality_score"] is not None,
                    quality_result={"quality_score": result["quality_score"], "quality_grade": result["quality_grade"]},
                    risk_result={"risk_score": result["risk_score"], "risk_level": result["risk_level"]})
            except HTTPException:
                ai_analysis = failed_interpretation("AUTHORIZATION_FAILED")
            except Exception:
                ai_analysis = failed_interpretation("AGENT_ADAPTER_FAILED")

        # Persist findings to their own collection
        if not await jobs.renew(collection, run_id):
            return  # CQ-05: claim lost (recovered elsewhere); store nothing
        await store_findings(findings_col, run_id, body.repository_id, context["organization_id"], findings)

        # Update baseline with this run's metrics
        if baseline is not None and result["quality_score"] is not None and not scope_details.get("is_truncated"):
            metrics = {
                "files_changed": float(evidence.files_analyzed),
                "lines_added": float(evidence.lines_added),
                "lines_deleted": float(evidence.lines_deleted),
                "lines_changed": float(evidence.lines_added + evidence.lines_deleted),  # Combined metric for Z-score
            }
            if evidence.execution_provenance.get("method") == "quality-snapshot-v1":
                # A source snapshot alone has no diff line counts.
                metrics = {"files_changed": float(evidence.files_analyzed)}
            if evidence.complexity.average_complexity is not None:
                metrics["complexity_avg"] = float(evidence.complexity.average_complexity)
            if evidence.testing.coverage_percentage is not None:
                metrics["test_coverage"] = evidence.testing.coverage_percentage
            await baseline.update_baseline(body.repository_id, metrics)

        # Update run document with final results
        now = datetime.now(timezone.utc).isoformat()
        await collection.update_one(
            owned,
            {
                "$set": {
                    **result,
                    "completed_at": now,
                    "findings_count": min(500, len(findings)),
                    "ai_analysis": ai_analysis,
                    "ai_status": ai_analysis["status"],
                    "ai_authorization_scope": authority.scope if authority is not None else None,
                    "ai_provenance": {"schema_version": "ai-internal-observation-v1", "source_status": "SERVER_OBSERVED",
                                      "caller_context_status": "UNVERIFIED", "model_interpretation": "ADVISORY"},
                }
            },
        )

    except Exception as e:
        await collection.update_one(
            owned,
            {
                "$set": {
                    "status": "failed",
                    "error": str(e)[:500],
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
