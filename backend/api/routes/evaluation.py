"""
AI Evaluation API — Endpoints for multi-agent employee evaluation.
Protected with authentication and RBAC.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
from bson import ObjectId
from core.dependencies import get_current_user
from core.database import col
from agents.supervisor import evaluate_employee
import time
import uuid
import logging
import traceback as _traceback

logger = logging.getLogger("samanvaya.evaluation")


def _serialize(obj):
    """Recursively convert MongoDB docs to JSON-safe types."""
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    try:
        # Catch NaN/Inf floats that JSON can't encode
        import math
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
    except Exception:
        pass
    # Handle Pydantic BaseModel objects
    try:
        from pydantic import BaseModel as _BaseModel
        if isinstance(obj, _BaseModel):
            return _serialize(obj.model_dump())
    except Exception:
        pass
    # Handle sets, tuples
    if isinstance(obj, (set, tuple, frozenset)):
        return [_serialize(i) for i in obj]
    # Last resort: convert to string
    try:
        import json
        json.dumps(obj)  # test if already serializable
        return obj
    except (TypeError, ValueError):
        return str(obj)


router = APIRouter()


class EmployeeEvaluationRequest(BaseModel):
    """Multi-agent employee evaluation request."""
    employee_id: str = Field(..., description="Employee ID (e.g. 'EMP-001')")
    start_date: str = Field(default="2026-09-01", description="Period start YYYY-MM-DD")
    end_date: str = Field(default="2026-09-30", description="Period end YYYY-MM-DD")
    period_label: Optional[str] = Field(default="2026-09", description="Label for period (e.g. '2026-09' or '2026-Q3')")
    company_id: Optional[str] = Field(default="ORG-001", description="Company isolation ID")
    skip_llm: bool = Field(default=False, description="Skip LLM calls and use deterministic scoring (fast mode for CI/CD testing)")
    verbose: bool = Field(default=True, description="Include per-agent metrics, reasoning, confidence, and evidence summary in response")


class SimpleEvalRequest(BaseModel):
    """Simple repo-based evaluation request (compat)."""
    github_username: str
    repo_owner: str
    repo_name: str
    pr_number: Optional[int] = None
    human_score: float = 5.0
    evaluation_focus: str = "code_quality"


@router.post("/run")
async def run_employee_evaluation(
    request: EmployeeEvaluationRequest,
    user: dict = Depends(get_current_user),
):
    """
    Triggers multi-agent specialist scoring for an employee across an evaluation period.

    Executes in parallel:
    - Code Agent: Code Quality ONLY
    - QA Agent: Testing & Reliability ONLY
    - DevOps Agent: Deployment & Infrastructure ONLY
    - CI/CD Agent: CI/CD Performance ONLY
    - Meeting Agent: Agile & Collaboration ONLY
    Followed by Performance Aggregator and Report Agent presentation.
    """
    company_id = user.get("company_id") or user.get("org_id") or request.company_id or "ORG-001"
    evaluator_id = user.get("employee_id") or user.get("id") or "system"

    try:
        result = await evaluate_employee(
            employee_id=request.employee_id,
            start_date=request.start_date,
            end_date=request.end_date,
            company_id=company_id,
            evaluator_id=evaluator_id,
            period_label=request.period_label,
            skip_llm=request.skip_llm,
            verbose=request.verbose,
        )
        return JSONResponse(content=_serialize(result))
    except Exception as exc:
        logger.error("[EVAL] /run failed for %s: %s", request.employee_id, exc)
        logger.error(_traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Employee evaluation failed: {exc}")


@router.get("")
@router.get("/all")
async def list_all_evaluations(
    period_label: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    """
    List latest multi-agent evaluations for all employees in the organization.
    """
    company_id = user.get("company_id") or user.get("org_id") or "ORG-001"
    query = {"company_id": company_id} if company_id else {}
    if period_label:
        query["period.label"] = period_label

    try:
        cursor = col("employee_evaluations").find(query).sort("period.end", -1)
        docs = await cursor.to_list(100)
        return JSONResponse(content=_serialize(docs))
    except Exception as exc:
        logger.error("[EVAL] list_all_evaluations failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{employee_id}")
async def get_latest_employee_evaluation(
    employee_id: str,
    period_label: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    """
    Fetch the latest multi-agent evaluation for an employee.
    If no evaluation exists yet, automatically calculates an evaluation for September 2026.
    """
    company_id = user.get("company_id") or user.get("org_id") or "ORG-001"

    query = {"employee_id": employee_id}
    if period_label:
        query["period.label"] = period_label

    doc = await col("employee_evaluations").find_one(
        query,
        sort=[("period.end", -1), ("_id", -1)],
    )

    if not doc:
        # Generate dynamically on first request
        try:
            doc = await evaluate_employee(
                employee_id=employee_id,
                start_date="2026-09-01",
                end_date="2026-09-30",
                company_id=company_id,
                evaluator_id="system",
                period_label="2026-09",
            )
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"No evaluation found for {employee_id}: {e}")

    # Remove mongo ObjectId if present
    if "_id" in doc and not isinstance(doc["_id"], str):
        doc["_id"] = str(doc["_id"])

    return doc


@router.get("/{employee_id}/report.pdf")
async def download_evaluation_pdf(
    employee_id: str,
    period_label: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    """
    Generate and download a professional PDF evaluation scorecard.
    """
    from fastapi.responses import Response
    from agents.report_agent import EmployeeReportGenerator

    query = {"employee_id": employee_id}
    if period_label:
        query["period.label"] = period_label

    doc = await col("employee_evaluations").find_one(
        query,
        sort=[("period.end", -1), ("_id", -1)],
    )

    if not doc:
        # Generate on demand
        company_id = user.get("company_id") or user.get("org_id") or "ORG-001"
        try:
            doc = await evaluate_employee(
                employee_id=employee_id,
                start_date="2026-09-01",
                end_date="2026-09-30",
                company_id=company_id,
                period_label="2026-09",
            )
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"No evaluation to generate PDF for {employee_id}: {e}")

    pdf_bytes = EmployeeReportGenerator.generate_pdf_report_from_doc(doc)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="evaluation_{employee_id}.pdf"'},
    )


@router.get("/{employee_id}/history")
async def get_employee_evaluation_history(
    employee_id: str,
    limit: int = Query(10, ge=1, le=50),
    user: dict = Depends(get_current_user),
):
    """
    Retrieve historical evaluations for an employee across past periods.
    """
    cursor = col("employee_evaluations").find(
        {"employee_id": employee_id},
        sort=[("period.end", -1)],
    ).limit(limit)

    results = await cursor.to_list(limit)
    for r in results:
        if "_id" in r and not isinstance(r["_id"], str):
            r["_id"] = str(r["_id"])

    return {"employee_id": employee_id, "history": results}


@router.get("/status/{task_id}")
async def get_evaluation_status(task_id: str, user: dict = Depends(get_current_user)):
    """Status check for long-running evaluation tasks."""
    doc = await col("employee_evaluations").find_one({"evaluation_id": task_id})
    if doc:
        return {"status": "completed", "evaluation_id": task_id, "result": doc}
    return {"status": "processing", "evaluation_id": task_id}


# ── Backward compatibility endpoint ──
@router.post("/evaluate")
async def evaluate_developer_ai_compat(
    request: SimpleEvalRequest,
    user: dict = Depends(get_current_user),
):
    """Legacy evaluate endpoint preserved for backward compatibility."""
    return await run_employee_evaluation(
        EmployeeEvaluationRequest(
            employee_id=request.github_username,
            start_date="2026-09-01",
            end_date="2026-09-30",
            period_label="2026-09",
        ),
        user=user,
    )


@router.get("/health")
async def evaluation_health():
    """Check evaluation system health."""
    from agents.llm_provider import check_ollama_connection
    from integrations.github.client import GitHubClient

    github_status = "not_configured"
    try:
        client = GitHubClient()
        github_status = "configured" if await client.check_token_validity() else "invalid"
    except Exception:
        github_status = "error"

    return {
        "status": "operational",
        "ai_available": check_ollama_connection(),
        "github_available": github_status,
        "specialist_agents": [
            "code_agent (Code Quality)",
            "qa_agent (Testing & Reliability)",
            "devops_agent (DevOps & Infrastructure)",
            "cicd_agent (CI/CD Performance)",
            "meeting_agent (Agile & Collaboration)",
        ],
        "aggregator": "performance_agent",
        "reporter": "report_agent",
    }
