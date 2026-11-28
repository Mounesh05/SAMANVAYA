"""Persistence contract shared by manual and GitHub revision analyses."""
import hashlib
import json
from datetime import datetime, timedelta, timezone

from intelligence.algorithms.discovery.service import source_language
from intelligence.quality_engine import QualityEngine, snapshot_context_diagnostic
from intelligence.risk_engine import RiskEngine

RUN_TIMEOUT_SECONDS = 900


def run_deadline():
    return (datetime.now(timezone.utc) + timedelta(seconds=RUN_TIMEOUT_SECONDS)).isoformat()


def policy_digest(quality_policy, risk_policy):
    """Stable identity of the effective quality + risk policy (CQ-02/CQ-04)."""
    if quality_policy is None and risk_policy is None:
        return None
    raw = json.dumps({"quality": quality_policy, "risk": risk_policy}, sort_keys=True, default=str)
    return "policy-" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def expired(run):
    deadline = run.get("work_deadline")
    return (run.get("status") in ("pending", "running") and isinstance(deadline, str)
            and deadline <= datetime.now(timezone.utc).isoformat())


def score_explanation(quality, policy):
    """CQ-15/CQ-17: how the existing engine produced the quality score, from its own outputs.

    Missing dimensions are excluded and the configured weights of the measured ones
    are renormalised; that is shown, not hidden. No new formula is introduced.
    """
    weights = (policy or {}).get("weights") or {}
    penalties = (quality or {}).get("penalties") or {}
    if (quality or {}).get("quality_score") is None or not weights:
        return None
    measured = [dim for dim in weights if penalties.get(dim) is not None]
    total = sum(weights[dim] for dim in measured)
    dimensions = [{"dimension": dim, "configured_weight": weights[dim], "measured": dim in measured,
                   "penalty": penalties.get(dim), "score": (quality.get("dimension_scores") or {}).get(dim),
                   "effective_weight": round(weights[dim] / total, 4) if dim in measured and total else None}
                  for dim in weights]
    weighted = sum(weights[dim] * penalties[dim] for dim in measured) / total if total else None
    return {"formula": "quality = round(100 - sum(effective_weight * penalty)) over measured dimensions, clamped to 0..100",
            "renormalized": len(measured) < len(weights), "weighted_penalty": round(weighted, 2) if weighted is not None else None,
            "dimensions": dimensions}


async def measure_quality(evidence, paths, baseline=None):
    tools = set(evidence.tools_executed) - {"ast-test-discovery"}
    measured = bool(evidence.files_analyzed and tools)
    engine = QualityEngine()
    quality = await engine.calculate(evidence) if measured else {}
    quality_policy = await engine.effective_policy(evidence) if measured else None
    measured = measured and quality.get("quality_score") is not None
    risk_engine = RiskEngine()
    risk = await risk_engine.analyze_evidence(evidence, baseline) if measured else {}
    risk_policy = await risk_engine.effective_policy(evidence, baseline) if measured else None
    supported = any(source_language(path) for path in paths)
    state = ("partial" if evidence.tools_skipped or evidence.analysis_quality.confidence < 1
             else "available") if measured else ("failed" if supported else "unsupported")
    reason = evidence.analysis_quality.reason
    if not supported and not measured:
        reason = "No selected Python, JavaScript or TypeScript file on this revision."
    return {
        "status": "completed" if measured else state, "analysis_scope": "code_quality",
        "quality_analysis_status": state, "quality_unavailable_reason": reason,
        "quality_score": quality.get("quality_score"), "quality_grade": quality.get("quality_grade"),
        "risk_score": risk.get("risk_score"), "risk_level": risk.get("risk_level"),
        "quality_dimensions": quality.get("dimension_scores", {}), "risk_dimensions": risk.get("dimension_scores", {}),
        "risk_factors": risk.get("risk_factors", []), "commit_sha": evidence.commit_sha,
        "quality_policy": quality_policy, "risk_policy": risk_policy,
        "score_explanation": score_explanation(quality, quality_policy),
        "policy_digest": policy_digest(quality_policy, risk_policy),
        "files_analyzed": evidence.files_analyzed, "language": evidence.primary_language,
        "detected_languages": evidence.detected_languages, "tools_executed": evidence.tools_executed,
        "tools_skipped": evidence.tools_skipped, "execution_provenance": evidence.execution_provenance,
        "analysis_quality": evidence.analysis_quality.model_dump(mode="json"),
        "analysis_confidence": evidence.analysis_quality.confidence, "analysis_duration_ms": evidence.analysis_duration_ms,
        "testing": evidence.testing.model_dump(mode="json"),
        "complexity": evidence.complexity.model_dump(mode="json") if measured and evidence.complexity.is_available else None,
        "duplication": evidence.duplication.model_dump(mode="json") if measured else None,
        "function_discovery": evidence.function_discovery.model_dump(mode="json"),
    }


def quality_findings(evidence):
    return list({f.id: f for f in [*evidence.static_findings, *evidence.security.findings]}.values())


async def store_findings(collection, run_id, project_id, org_id, findings):
    if findings:
        await collection.insert_many([
            {**f.model_dump(mode="json", exclude={"code_snippet"}), "run_id": run_id,
             "scope": "project_context" if snapshot_context_diagnostic(f.source_tool, f.rule_id) else "source",
             "repository_id": project_id, **({"org_id": org_id} if org_id else {})} for f in findings[:500]
        ])
