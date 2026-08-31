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

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel

from core.database import col
from core.dependencies import get_current_user, require_roles
from domain.models.project_code_config import ProjectCodeConfig
from domain.services.code_quality_service import CodeQualityService
from intelligence.analyzers.language_detector import LanguageDetector
from intelligence.analyzers.registry import get_analyzer, list_supported_languages

router = APIRouter()
cq_service = CodeQualityService()
lang_detector = LanguageDetector()
RUNS_COLLECTION = "code_quality_runs"
FINDINGS_COLLECTION = "code_quality_findings"
CONFIGS_COLLECTION = "project_configs"


# ── Request / Response models ─────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    repository_id: str
    pr_number: Optional[int] = None
    changed_files: List[str] = []
    pr_context: Dict[str, Any] = {}
    analysis_level: str = "standard"   # "quick" | "standard" | "deep"
    use_ai: bool = True


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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/analyze", status_code=202)
async def start_analysis(
    body: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_roles("DEVELOPER", "LEAD", "QA", "DEVOPS")),
):
    """
    Start an async code quality analysis run.
    Returns run_id immediately — poll /runs/{run_id} for results.
    """
    run_id = f"RUN-{uuid.uuid4().hex[:12].upper()}"
    now = datetime.now(timezone.utc).isoformat()

    # Detect language immediately (fast — no tools needed)
    profile = lang_detector.detect_from_files(body.changed_files)

    # Create the run record in PENDING state
    run_doc = {
        "run_id": run_id,
        "repository_id": body.repository_id,
        "pr_number": body.pr_number,
        "language": profile.primary_language,
        "detected_languages": profile.detected_languages,
        "analysis_level": body.analysis_level,
        "use_ai": body.use_ai,
        "status": "pending",
        "triggered_by": user.get("employee_id", user.get("id", "")),
        "triggered_by_name": user.get("name", ""),
        "created_at": now,
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
    }

    collection = col(RUNS_COLLECTION)
    await collection.insert_one(run_doc)

    # Queue the heavy analysis in the background
    background_tasks.add_task(
        _run_analysis,
        run_id=run_id,
        body=body,
        profile=profile,
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
    run = await collection.find_one({"run_id": run_id}, {"_id": 0})
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


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
    query: dict = {"run_id": run_id}
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


@router.get("/repositories/{repository_id}/latest")
async def get_latest_run(
    repository_id: str,
    user: dict = Depends(get_current_user),
):
    """Get the most recent completed analysis run for a repository."""
    collection = col(RUNS_COLLECTION)
    run = await collection.find_one(
        {"repository_id": repository_id, "status": "completed"},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not run:
        raise HTTPException(status_code=404, detail="No completed runs for this repository")
    return run


@router.get("/repositories/{repository_id}/history")
async def get_run_history(
    repository_id: str,
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    """Get historical quality/risk trend for a repository."""
    collection = col(RUNS_COLLECTION)
    runs = (
        await collection.find(
            {"repository_id": repository_id},
            {"_id": 0, "run_id": 1, "created_at": 1, "language": 1,
             "quality_score": 1, "quality_grade": 1, "risk_score": 1,
             "risk_level": 1, "status": 1, "pr_number": 1},
        )
        .sort("created_at", -1)
        .limit(limit)
        .to_list(limit)
    )
    return {"repository_id": repository_id, "history": runs, "count": len(runs)}


@router.post("/projects/{project_id}/config")
async def save_project_config(
    project_id: str,
    config: ProjectCodeConfig,
    user: dict = Depends(get_current_user),
):
    """Save per-project code quality configuration."""
    config.project_id = project_id
    collection = col(CONFIGS_COLLECTION)
    await collection.replace_one(
        {"project_id": project_id},
        config.model_dump(),
        upsert=True,
    )
    return {"message": "Project config saved", "project_id": project_id}


@router.get("/projects/{project_id}/config")
async def get_project_config(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """Get per-project code quality configuration."""
    collection = col(CONFIGS_COLLECTION)
    doc = await collection.find_one({"project_id": project_id}, {"_id": 0})
    if not doc:
        # Return defaults if not configured
        return ProjectCodeConfig(project_id=project_id).model_dump()
    return doc


@router.get("/languages")
async def supported_languages():
    """List all languages supported by the analyzer registry."""
    return {"supported_languages": list_supported_languages()}


# ── Background task ───────────────────────────────────────────────────────────

async def _run_analysis(run_id: str, body: AnalyzeRequest, profile: Any) -> None:
    """
    Heavy analysis executed in the background.
    Updates the run document with results when complete.
    """
    import time
    collection = col(RUNS_COLLECTION)
    findings_col = col(FINDINGS_COLLECTION)

    try:
        await collection.update_one(
            {"run_id": run_id}, {"$set": {"status": "running"}}
        )

        # Load project config
        cfg_col = col(CONFIGS_COLLECTION)
        cfg_doc = await cfg_col.find_one({"project_id": body.repository_id})
        project_config = (
            ProjectCodeConfig(**cfg_doc) if cfg_doc
            else ProjectCodeConfig(project_id=body.repository_id)
        )

        # Run analysis via CodeQualityService
        deep = body.analysis_level == "deep"
        evidence = await cq_service.analyze_pr(
            changed_files=body.changed_files,
            pr_context={**body.pr_context, "project_id": body.repository_id,
                        "pr_number": body.pr_number},
            project_config=project_config,
            deep_analysis=deep,
        )

        # Calculate quality score
        from intelligence.quality_engine import QualityEngine
        quality_result = QualityEngine().calculate(evidence)

        # Calculate risk score
        from intelligence.risk_engine import RiskEngine
        from intelligence.baselines.repository_baseline import RepositoryBaseline
        baseline = RepositoryBaseline()
        risk_result = await RiskEngine().analyze_evidence(evidence, baseline)

        # AI Code Agent (if requested and not quick)
        ai_analysis = {}
        if body.use_ai and body.analysis_level != "quick":
            try:
                from agents.code_agent import code_analysis_node
                from intelligence.evidence_builder import EvidenceBuilder
                # Build a summary string for the agent
                summary = (
                    f"Language: {evidence.primary_language}\n"
                    f"Files: {evidence.files_analyzed} | "
                    f"Lines: +{evidence.lines_added}/-{evidence.lines_deleted}\n"
                    f"Quality: {quality_result['quality_score']}/100 ({quality_result['quality_grade']})\n"
                    f"Risk: {risk_result['risk_score']}/100 ({risk_result['risk_level']})\n"
                    f"Critical findings: {evidence.total_critical_findings}\n"
                    f"High findings: {evidence.total_high_findings}\n"
                    f"Coverage: {evidence.testing.coverage_percentage or 'N/A'}%\n"
                    f"Complexity avg: {evidence.complexity.average_complexity}\n"
                    f"Duplication: {evidence.duplication.duplication_percentage}%\n"
                    f"Risk factors: {', '.join(risk_result['risk_factors'][:5])}\n"
                    f"{evidence.analysis_quality.prompt_note()}"
                )
                agent_state = {
                    "evidence": {"evidence_summary": summary},
                    "context": body.pr_context,
                    "agent_history": [],
                    "errors": [],
                }
                agent_result = code_analysis_node(agent_state)
                ai_analysis = {
                    "analysis": agent_result.get("analysis", ""),
                    "recommendations": agent_result.get("recommendations", []),
                    "critical_issues": agent_result.get("critical_issues", []),
                    "review_focus": agent_result.get("review_focus", ""),
                }
            except Exception as e:
                ai_analysis = {"error": str(e)[:200]}

        # Persist findings to their own collection
        if evidence.static_findings:
            finding_docs = [
                {
                    "run_id": run_id,
                    "repository_id": body.repository_id,
                    **f.model_dump(),
                }
                for f in evidence.static_findings[:500]  # Cap at 500 per run
            ]
            await findings_col.insert_many(finding_docs)

        # Update baseline with this run's metrics
        await baseline.update_baseline(
            body.repository_id,
            {
                "files_changed": float(evidence.files_analyzed),
                "lines_added": float(evidence.lines_added),
                "lines_deleted": float(evidence.lines_deleted),
                "complexity_avg": evidence.complexity.average_complexity,
                "test_coverage": evidence.testing.coverage_percentage or 0.0,
            },
        )

        # Update run document with final results
        now = datetime.now(timezone.utc).isoformat()
        await collection.update_one(
            {"run_id": run_id},
            {
                "$set": {
                    "status": "completed",
                    "completed_at": now,
                    "language": evidence.primary_language,
                    "quality_score": quality_result["quality_score"],
                    "quality_grade": quality_result["quality_grade"],
                    "quality_dimensions": quality_result["dimension_scores"],
                    "risk_score": risk_result["risk_score"],
                    "risk_level": risk_result["risk_level"],
                    "risk_factors": risk_result["risk_factors"],
                    "risk_dimensions": risk_result["dimension_scores"],
                    "tools_executed": evidence.tools_executed,
                    "tools_skipped": evidence.tools_skipped,
                    "analysis_confidence": evidence.analysis_quality.confidence,
                    "analysis_duration_ms": evidence.analysis_duration_ms,
                    "findings_count": len(evidence.static_findings),
                    "ai_analysis": ai_analysis,
                }
            },
        )

    except Exception as e:
        await collection.update_one(
            {"run_id": run_id},
            {
                "$set": {
                    "status": "failed",
                    "error": str(e)[:500],
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
