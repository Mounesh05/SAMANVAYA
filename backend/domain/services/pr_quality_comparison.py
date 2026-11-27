"""Static quality of the two immutable revisions observed by a PR sync."""
import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from core.database import col
from domain.services.code_quality_service import CodeQualityService
from domain.services.quality_run_results import measure_quality, quality_findings, store_findings, expired, run_deadline, RUN_TIMEOUT_SECONDS
from intelligence.algorithms.discovery.service import source_language
from intelligence.analyzers.isolated import source_provenance

logger = logging.getLogger(__name__)


def now():
    return datetime.now(timezone.utc).isoformat()


async def compare_revisions(api, project_id, owner, repo, pr, files, triggered_by, retry_of=None):
    from domain.services.internal_agent_adapter import GitHubAutomation, resolve_code_authority
    repository = owner + "/" + repo
    base, head = pr["base"]["sha"], pr["head"]["sha"]
    if not all(re.fullmatch("[0-9a-f]{40}", sha) for sha in (base, head)):
        raise ValueError("Exact PR revisions required")
    authority = await resolve_code_authority(GitHubAutomation(project_id, repository, head),
        {"project_id": project_id, "repo": repository, "commit_sha": head})
    org = authority.scope["organization_id"]
    identity = [org, project_id, repository, pr["number"], base, head, "pr-quality-v1"]
    parent = "PRQ-" + hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24].upper()
    runs = col("code_quality_runs")
    if retry_of:
        prior = await runs.find_one({"_id": retry_of, "repository_id": project_id, "org_id": org, "pr_number": pr["number"],
                                     "base_sha": base, "head_sha": head, "kind": "pr_quality_comparison"})
        if not prior or (not expired(prior) and prior.get("quality_analysis_status") not in {"failed", "partial", "unsupported"}):
            raise ValueError("A terminal incomplete comparison for this exact revision pair is required")
        parent = "PRQ-" + hashlib.sha256((parent + retry_of).encode()).hexdigest()[:24].upper()
    shared = {"repository_id": project_id, "org_id": org, "pr_number": pr["number"], "repository": repository,
              "triggered_by": triggered_by, "created_at": now(), "work_deadline": run_deadline(), "analysis_scope": "code_quality"}
    old_paths = [f.get("previous_filename", f["filename"]) for f in files if f.get("status") != "added"]
    new_paths = [f["filename"] for f in files if f.get("status") != "removed"]
    child_ids = {side: parent + "-" + side for side in ("base", "head")}
    try:
        await runs.insert_one({**shared, "_id": parent, "run_id": parent, "kind": "pr_quality_comparison",
            "base_sha": base, "head_sha": head, "child_run_ids": child_ids, "reanalysis_of": retry_of, "status": "running"})
    except DuplicateKeyError:
        query = {"org_id": org, "repository_id": project_id, "pr_number": pr["number"], "kind": "pr_quality_comparison",
                 "base_sha": base, "head_sha": head, "repository": repository}
        if retry_of:
            query["_id"] = parent
        existing = await runs.find_one(query, sort=[("created_at", -1)])
        # Replay the measured head for advisory consumers without invoking analyzers twice.
        head_run = await runs.find_one({"_id": existing["child_run_ids"]["head"], "org_id": org,
                                        "repository_id": project_id, "commit_sha": head})
        evidence = None
        if head_run and head_run.get("analyzer_evidence"):
            from intelligence.evidence.models import CodeQualityEvidence
            evidence = CodeQualityEvidence.model_validate({
                **head_run["analyzer_evidence"], "function_discovery": head_run["function_discovery"]})
        return existing, evidence

    service = CodeQualityService()

    async def side_result(side, revision, changed):
        run_id = child_ids[side]
        paths = list(dict.fromkeys(p for p in changed if source_language(p)))
        await runs.insert_one({**shared, "_id": run_id, "run_id": run_id, "parent_run_id": parent,
                               "kind": "pr_quality_" + side, "status": "running", "commit_sha": revision,
                               "changed_files": paths})
        try:
            sources, diagnostics = await api.fetch_analysis_sources(owner, repo, [{"filename": p} for p in paths],
                revision, include_context=True, verified_snapshot=True)
            context = {"project_id": project_id, "organization_id": org, "pr_number": pr["number"], "commit_sha": revision,
                       "source_files": sources, "source_diagnostics": diagnostics,
                       "source_provenance": source_provenance(project_id, repository, revision, sources, org)}
            evidence = await service.analyze_pr(paths, context)
            record = await measure_quality(evidence, paths)
            findings = quality_findings(evidence)
            await store_findings(col("code_quality_findings"), run_id, project_id, org, findings)
            if side == "head":
                record["analyzer_evidence"] = evidence.model_dump(mode="json", exclude={
                    "function_discovery": True, "static_findings": {"__all__": {"code_snippet"}},
                    "security": {"findings": {"__all__": {"code_snippet"}}}})
            record["findings_count"] = min(500, len(findings))
        except Exception:
            logger.exception("Quality snapshot failed for %s", run_id)
            evidence = None
            record = {"status": "failed", "quality_analysis_status": "failed", "quality_unavailable_reason": "Revision analysis failed."}
        await runs.update_one({"_id": run_id}, {"$set": {**record, "completed_at": now()}})
        return record, evidence

    try:
        async with asyncio.timeout(RUN_TIMEOUT_SECONDS):
            async with asyncio.TaskGroup() as group:
                base_task = group.create_task(side_result("base", base, old_paths))
                head_task = group.create_task(side_result("head", head, new_paths))
            before, _ = base_task.result()
            after, head_evidence = head_task.result()
        scores = [r.get("quality_score") for r in (before, after)]
        outcomes = [r["quality_analysis_status"] for r in (before, after)]
        if all(s is not None for s in scores):
            state = "available" if outcomes == ["available", "available"] else "partial"
        elif any(s is not None for s in scores):
            state = "partial"
        else:
            state = "failed" if "failed" in outcomes else "unsupported"
        if pr.get("changed_files", len(files)) > len(files) and state == "available":
            state = "partial"
        summary = {"status": "completed" if state in ("partial", "available") else state,
                   "quality_analysis_status": state, "completed_at": now(), "language": after.get("language"),
                   "quality_comparison": {"base_score": scores[0], "head_score": scores[1],
                       "delta": scores[1] - scores[0] if None not in scores else None,
                       "base_status": outcomes[0], "head_status": outcomes[1]}}
        summary.update({k: after.get(k) for k in ("quality_score", "quality_grade", "risk_score", "risk_level")})
        summary["score_basis"] = child_ids["head"]
        await runs.update_one({"_id": parent}, {"$set": summary})
        return {**summary, "run_id": parent, "child_run_ids": child_ids}, head_evidence
    except (Exception, asyncio.CancelledError):
        await runs.update_one({"_id": parent}, {"$set": {"status": "failed", "quality_analysis_status": "failed",
                              "completed_at": now(), "error": "PR quality comparison interrupted"}})
        raise
