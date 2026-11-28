"""Phase 1: the compulsory AI interpretation stage of a Code Quality report.

Shared by every path that produces a normal report: repository and selected-file
runs, manual PR comparisons, automatic (webhook) PR comparisons and the AI-only
retry. Static analysis has already finished; this stage only interprets the
measured, bounded evidence and never changes scores or findings.
"""
import hashlib
import json
import time

from fastapi import HTTPException

POLICY_VERSION = "code-quality-advisory-v1"
MAX_AI_ATTEMPTS = 3
MAX_OBSERVATIONS = 20
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def evidence_digest(request):
    """Stable digest of the exact AI input (scope, revision and evidence)."""
    canonical = json.dumps({"package": request["package"], "context": request["context"]},
                           sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def build_request(project_id, commit_sha, evidence, findings, result, comparison=None):
    """Bounded, prioritised AI input built only from server-measured evidence."""
    from intelligence.quality_engine import snapshot_context_diagnostic
    from domain.services.pr_quality_comparison import dependency_audit
    observed = sorted(
        (f for f in findings if not snapshot_context_diagnostic(f.source_tool, f.rule_id)),
        key=lambda f: (SEVERITY_ORDER.get(getattr(f.severity, "value", f.severity), 5), f.file_path or "",
                       f.line_number or 0, f.rule_id or "", f.id))
    observations = [{"id": f.id, "file": f.file_path, "line": f.line_number, "rule_id": f.rule_id,
                     "severity": getattr(f.severity, "value", f.severity), "message": f.message[:500]}
                    for f in observed[:MAX_OBSERVATIONS]]
    complexity = result.get("complexity")
    if complexity is None and comparison is not None and evidence.complexity.is_available:
        complexity = evidence.complexity.model_dump(mode="json")
    package = {"files_analyzed": evidence.files_analyzed, "static_analysis": {"findings": observations},
               "complexity": complexity,
               "tests": {"coverage": {"line_coverage": evidence.testing.coverage_percentage}},
               "dependency_audit": dependency_audit({"tools_skipped": evidence.tools_skipped,
                                                     "tools_executed": evidence.tools_executed}),
               "omitted_findings": max(0, len(observed) - len(observations)),
               "quality_score": result.get("quality_score"), "risk_score": result.get("risk_score")}
    if comparison is not None:
        package["pr_comparison"] = comparison
    return {"package": package,
            "context": {"project_id": project_id, "commit_sha": evidence.commit_sha or commit_sha},
            "evidence_available": result.get("quality_score") is not None,
            "quality_result": {"quality_score": result.get("quality_score"), "quality_grade": result.get("quality_grade")},
            "risk_result": {"risk_score": result.get("risk_score"), "risk_level": result.get("risk_level")}}


async def run_interpretation(authority, request):
    """Call the configured model once. Returns (ai_analysis, request_or_None, latency_ms)."""
    from domain.services import internal_agent_adapter
    started = time.monotonic()
    try:
        ai_analysis = await internal_agent_adapter.interpret_code(
            request["package"], request["context"], authority, evidence_available=request["evidence_available"],
            quality_result=request["quality_result"], risk_result=request["risk_result"])
    except HTTPException:
        ai_analysis = internal_agent_adapter.failed_interpretation("AUTHORIZATION_FAILED")
    except Exception:
        ai_analysis = internal_agent_adapter.failed_interpretation("AGENT_ADAPTER_FAILED")
    latency_ms = int((time.monotonic() - started) * 1000)
    if "MISSING_EVIDENCE" in (ai_analysis.get("errors") or []):
        # Without usable static evidence the interpretation is blocked, not retried.
        return {**ai_analysis, "status": "blocked"}, None, latency_ms
    return ai_analysis, request, latency_ms


def ai_fields(ai_analysis, authority, static_reasons=(), request=None, latency_ms=None, attempts=1):
    """Fields stored on the run.

    ``report_status`` is ``complete`` only with full static evidence and a validated
    interpretation; otherwise ``partial`` (or ``failed`` without static evidence), with
    the reasons. The exact AI input is kept server-side for a bounded AI-only retry.
    """
    from core.config import settings
    from domain.services.quality_advisory import report_state
    state, reasons = report_state(static_reasons, ai_analysis)
    fields = {"ai_required": True, "ai_analysis": ai_analysis, "ai_status": ai_analysis["status"],
              "report_status": state, "report_incomplete_reasons": reasons,
              "ai_authorization_scope": authority.scope if authority is not None else None,
              "ai_provenance": {"schema_version": "ai-internal-observation-v1", "source_status": "SERVER_OBSERVED",
                                "caller_context_status": "UNVERIFIED", "model_interpretation": "ADVISORY",
                                "policy_version": POLICY_VERSION, "model": settings.OLLAMA_MODEL,
                                "latency_ms": latency_ms,
                                "evidence_digest": evidence_digest(request) if request is not None else None}}
    if request is not None:
        fields.update(ai_request={**request, "static_reasons": static_reasons}, ai_attempts=attempts)
    return fields


async def interpret_comparison(summary, head_evidence, authority, project_id, head_sha):
    """The one interpretation of a PR comparison parent (manual or automatic)."""
    from domain.services import internal_agent_adapter
    from domain.services.quality_advisory import static_reasons_for_comparison
    from domain.services.quality_run_results import quality_findings
    reasons = static_reasons_for_comparison(summary)
    if head_evidence is None:  # the head revision was not measured
        blocked = {**internal_agent_adapter.failed_interpretation("MISSING_EVIDENCE"), "status": "blocked"}
        return ai_fields(blocked, None, reasons)
    comparison = {**(summary.get("quality_comparison") or {}), "finding_changes": summary.get("finding_changes") or {}}
    request = build_request(project_id, head_sha, head_evidence, quality_findings(head_evidence), summary, comparison)
    ai_analysis, request, latency_ms = await run_interpretation(authority, request)
    return ai_fields(ai_analysis, authority, reasons, request, latency_ms)
