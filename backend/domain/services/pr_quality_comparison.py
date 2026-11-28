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


# Skips the isolated static worker reports on every snapshot by design (no tests,
# no network, no project config). They are the same on both revisions, so they do
# not make a comparison partial. Any other skip (a tool that failed) still does.
ENVIRONMENT_SKIPS = frozenset({"dependency-advisories-offline", "pytest", "coverage",
                               "tsc:configuration-unavailable", "npm-audit:package-manifest-unavailable"})


def _fully_observed(record):
    status, skipped = record.get("quality_analysis_status"), set(record.get("tools_skipped") or [])
    # A partial side with no recorded skip is partial for an unknown reason: not comparable.
    return status == "available" or (status == "partial" and bool(skipped) and skipped <= ENVIRONMENT_SKIPS)


def comparable_sides(before, after, truncated=False):
    """v4 CQ-13/CQ-14: None when both revisions were measured alike, else the reason they are not.

    Both sides must be scored, complete apart from the worker's fixed environment
    skips, and have run and skipped exactly the same tools under the same policy.
    """
    if None in (before.get("quality_score"), after.get("quality_score")):
        return "score_unavailable"
    if truncated or not (_fully_observed(before) and _fully_observed(after)):
        return "partial_evidence"
    if before.get("policy_digest") != after.get("policy_digest"):
        return "policy_changed"
    if (set(before.get("tools_executed") or []) != set(after.get("tools_executed") or [])
            or set(before.get("tools_skipped") or []) != set(after.get("tools_skipped") or [])):
        return "tools_differ"
    if ({k for k, v in (before.get("quality_dimensions") or {}).items() if v is not None}
            != {k for k, v in (after.get("quality_dimensions") or {}).items() if v is not None}):
        return "dimensions_differ"
    return None


def comparable_delta(before, after, truncated=False):
    """CQ-02: a delta only between fully measured sides under the same policy, tools and dimensions."""
    reason = comparable_sides(before, after, truncated)
    if reason:
        return {"delta": None, "delta_withheld_reason": reason}
    return {"delta": after["quality_score"] - before["quality_score"], "delta_withheld_reason": None,
            "policy_digest": after.get("policy_digest")}


FINDING_IDENTITY_VERSION = "finding-identity-v1"
MAX_LISTED_CHANGES = 100
_DIGITS = re.compile(r"\d+")
_SPACE = re.compile(r"\s+")


def rename_map(files):
    """Old path -> new path for renamed PR files, so moved code keeps its findings."""
    return {f["previous_filename"]: f["filename"] for f in files
            if f.get("status") == "renamed" and f.get("previous_filename") and f.get("filename")}


def finding_fingerprints(findings, renames=None):
    """CQ-03: stable identity per finding, independent of line numbers.

    Identity = tool + rule + file (after rename) + message with numbers removed
    + the flagged code with whitespace collapsed. Line moves and renames keep
    the same identity; identical repeats in one file are numbered in order.
    Returns {finding.id: fingerprint}.
    """
    from intelligence.quality_engine import snapshot_context_diagnostic
    renames = renames or {}
    counts, result = {}, {}
    ordered = sorted(findings, key=lambda f: (f.file_path, f.line_number or 0, f.rule_id, f.id))
    for finding in ordered:
        if snapshot_context_diagnostic(finding.source_tool, finding.rule_id):
            continue  # project-context diagnostics are not source findings
        message = _SPACE.sub(" ", _DIGITS.sub("#", finding.message or "")).strip().casefold()[:300]
        snippet = _SPACE.sub(" ", finding.code_snippet or "").strip()[:500]
        base = json.dumps([FINDING_IDENTITY_VERSION, finding.source_tool, finding.rule_id,
                           renames.get(finding.file_path, finding.file_path), message, snippet])
        counts[base] = counts.get(base, 0) + 1
        result[finding.id] = hashlib.sha256(json.dumps([base, counts[base]]).encode()).hexdigest()[:32]
    return result


def _listed(finding, fingerprint, path=None):
    return {"fingerprint": fingerprint, "rule_id": finding.rule_id,
            "severity": getattr(finding.severity, "value", finding.severity),
            "category": finding.category, "source_tool": finding.source_tool, "file_path": path or finding.file_path,
            "line_number": finding.line_number, "message": (finding.message or "")[:300]}


def classify_findings(base_findings, head_findings, renames, base_available=True, head_available=True):
    """CQ-03: new / existing / resolved between the PR's base and head revisions.

    Withheld unless both revisions were fully analysed: a partial side would
    report findings as resolved (or new) only because they were not measured.
    Returns (public summary, fingerprints for marking stored findings).
    """
    if not (base_available and head_available):
        return {"status": "unavailable", "reason": "partial_evidence", "identity_version": FINDING_IDENTITY_VERSION}, None
    before = finding_fingerprints(base_findings, renames)
    after = finding_fingerprints(head_findings, {})
    base_by_fp = {before[f.id]: f for f in base_findings if f.id in before}
    head_by_fp = {after[f.id]: f for f in head_findings if f.id in after}
    new = [fp for fp in head_by_fp if fp not in base_by_fp]
    resolved = [fp for fp in base_by_fp if fp not in head_by_fp]
    existing = [fp for fp in head_by_fp if fp in base_by_fp]
    summary = {
        "status": "available", "identity_version": FINDING_IDENTITY_VERSION,
        "counts": {"new": len(new), "existing": len(existing), "resolved": len(resolved)},
        "new": [_listed(head_by_fp[fp], fp) for fp in new[:MAX_LISTED_CHANGES]],
        "resolved": [_listed(base_by_fp[fp], fp, renames.get(base_by_fp[fp].file_path))
                     for fp in resolved[:MAX_LISTED_CHANGES]],
        "truncated": max(len(new), len(resolved)) > MAX_LISTED_CHANGES,
    }
    return summary, {"base": before, "head": after, "new": set(new), "resolved": set(resolved)}


async def _mark_findings(collection, run_id, fingerprints, changed, changed_status):
    """Store identity and classification on the persisted findings of one revision."""
    from pymongo import UpdateOne
    operations = [UpdateOne({"run_id": run_id, "id": finding_id}, {"$set": {
        "fingerprint": fingerprint, "comparison_status": changed_status if fingerprint in changed else "existing"}})
        for finding_id, fingerprint in fingerprints.items()]
    if operations:
        await collection.bulk_write(operations, ordered=False)


_DEPENDENCY_AUDITORS = frozenset({"pip-audit", "safety", "npm-audit"})


def dependency_audit(record):
    """How a revision's dependencies were audited. Never reported as passing unless a tool ran."""
    skipped = set(record.get("tools_skipped") or [])
    if "dependency-advisories-offline" in skipped:
        return "not_checked_offline"
    if _DEPENDENCY_AUDITORS & set(record.get("tools_executed") or []):
        return "checked"
    return "not_checked"


def now():
    return datetime.now(timezone.utc).isoformat()


async def compare_revisions(api, project_id, owner, repo, pr, files, triggered_by, retry_of=None, *,
                            claimed_run=None, expected_org=None, deep_analysis=False, interpret=None):
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
    if claimed_run is not None:
        if not expected_org or org != expected_org:
            raise ValueError("The project organization has changed")
        parent = claimed_run["run_id"]
    parent_filter = claimed_run if claimed_run is not None else {"_id": parent}
    child_ids = {side: parent + "-" + side for side in ("base", "head")}
    try:
        if claimed_run is None:
            await runs.insert_one({**shared, "_id": parent, "run_id": parent, "kind": "pr_quality_comparison",
                "base_sha": base, "head_sha": head, "child_run_ids": child_ids, "reanalysis_of": retry_of, "status": "running"})
    except DuplicateKeyError:
        query = {"org_id": org, "repository_id": project_id, "pr_number": pr["number"], "kind": "pr_quality_comparison",
                 "base_sha": base, "head_sha": head, "repository": repository, "file_scope": {"$ne": "pr_comparison"}}
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
            if deep_analysis:
                evidence = await service.analyze_pr(paths, context, deep_analysis=True)
            else:
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
            evidence, findings = None, []
            record = {"status": "failed", "quality_analysis_status": "failed", "quality_unavailable_reason": "Revision analysis failed."}
        await runs.update_one({"_id": run_id}, {"$set": {**record, "completed_at": now()}})
        return record, evidence, findings

    try:
        async with asyncio.timeout(RUN_TIMEOUT_SECONDS):
            async with asyncio.TaskGroup() as group:
                base_task = group.create_task(side_result("base", base, old_paths))
                head_task = group.create_task(side_result("head", head, new_paths))
            before, _, base_findings = base_task.result()
            after, head_evidence, head_findings = head_task.result()
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
                       **comparable_delta(before, after, truncated=pr.get("changed_files", len(files)) > len(files)),
                       "base_status": outcomes[0], "head_status": outcomes[1]}}
        summary.update({k: after.get(k) for k in ("quality_score", "quality_grade", "risk_score", "risk_level")})
        # CQ-03: new / existing / resolved findings across the two revisions.
        renames = rename_map(files)
        # v4 CQ-14: classify only when both revisions were measured alike (same tools run and skipped).
        comparable = comparable_sides(before, after, truncated=pr.get("changed_files", len(files)) > len(files)) is None
        finding_changes, identities = classify_findings(
            base_findings, head_findings, renames, base_available=comparable, head_available=comparable)
        summary["finding_changes"] = finding_changes
        summary["dependency_audit"] = {"base": dependency_audit(before), "head": dependency_audit(after)}
        if identities:
            stored = col("code_quality_findings")
            await _mark_findings(stored, child_ids["head"], identities["head"], identities["new"], "new")
            await _mark_findings(stored, child_ids["base"], identities["base"], identities["resolved"], "resolved")
        summary["score_basis"] = child_ids["head"]
        if claimed_run is not None:
            summary.update(kind="pr_quality_comparison", file_scope="pr_comparison", base_sha=base, head_sha=head,
                           repository=repository, child_run_ids=child_ids, analysis_scope="code_quality")
        if interpret is not None:
            # Optional advisory interpretation, stored with the final result in one write.
            # It reads the measured summary and never changes it.
            try:
                summary.update(await interpret(dict(summary), head_evidence))
            except Exception:
                logger.exception("PR comparison interpretation could not be stored for %s", parent)
        await runs.update_one(parent_filter, {"$set": summary})
        return {**summary, "run_id": parent, "child_run_ids": child_ids}, head_evidence
    except (Exception, asyncio.CancelledError):
        await runs.update_one(parent_filter, {"$set": {"status": "failed", "quality_analysis_status": "failed",
                              "completed_at": now(), "error": "PR quality comparison interrupted"}})
        raise
