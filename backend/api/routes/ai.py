"""
AI Agent API Routes
Invoke specialized agents to interpret Intelligence Engine evidence
"""

import asyncio

from core.config import settings
from typing import Dict, Any, Literal
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from datetime import datetime, timezone

from agents.supervisor import invoke_agent
from agents.llm_provider import check_ollama_connection
from core.dependencies import get_current_user
from core.authorization import has_org_access as has_org_access
from core.permissions import get_user_permissions, Permission
from domain.models.ai_run import AIRun
from domain.models.ai_evidence import GitHubFileEvidenceV1
from domain.services.ai_run_access import invocation_scope, read_filter
from domain.services.ai_evidence_service import prepare_evidence
from repositories.ai_run_repository import AIRunRepository

router = APIRouter(tags=["AI Agents"])


class AgentRequest(BaseModel):
    """Request to invoke an AI agent."""
    task_type: Literal["code_review", "qa_analysis", "devops_risk", "meeting_insights", "cicd_analysis", "hr_assistant"]
    evidence: Dict[str, Any] = Field(..., description="Caller-supplied unverified evidence")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    save_run: bool = Field(default=True, description="Save run to database")
    evidence_sources_v1: list[GitHubFileEvidenceV1] = Field(default_factory=list, max_length=4,
        description="Optional exact-revision GitHub file references for scoped code_review")


class AgentResponse(BaseModel):
    """AI agent execution result."""
    run_id: str | None
    task_type: str
    analysis: str | None
    recommendations: list[str] | None
    risk_level: str | None
    confidence: float | None
    agent_history: list[str]
    errors: list[str]
    execution_time_ms: float


@router.get("/health")
async def ai_health_check():
    """Check AI agent system health (Ollama connection)."""
    ollama_ok = await asyncio.to_thread(check_ollama_connection)

    return {
        "status": "healthy" if ollama_ok else "degraded",
        "ollama_connected": ollama_ok,
        "message": "AI agents ready" if ollama_ok else "Ollama not reachable - check OLLAMA_BASE_URL",
    }


@router.post("/invoke", response_model=AgentResponse)
async def invoke_agent_endpoint(
    request: AgentRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Invoke AI agent to interpret Intelligence Engine evidence.
    """
    # Check permission to trigger AI evaluation
    user_permissions = get_user_permissions(
        current_user.get('role', '').upper(),
        current_user.get('is_admin', False),
        current_user.get('designation')
    )
    hr_assistance = (request.task_type == 'hr_assistant' and current_user.get('role', '').upper() == 'HR'
                     and Permission.VIEW_EMPLOYEE_DIRECTORY in user_permissions)
    if Permission.TRIGGER_AI_EVALUATION not in user_permissions and not hr_assistance:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    if hr_assistance and (request.context.get('project_id') is not None or request.evidence_sources_v1):
        raise HTTPException(403, 'HR assistance is private and cannot access engineering source evidence')
    
    start_time = datetime.now(timezone.utc)

    scope = await invocation_scope(current_user, request.context)
    evidence, stored_inputs, provenance = await prepare_evidence(
        current_user, scope, request.task_type, request.evidence, request.context, request.evidence_sources_v1)
    context = {**request.context, "project_id": scope["project_id"], "organization_id": scope["organization_id"]}

    if not await asyncio.to_thread(check_ollama_connection):
        raise HTTPException(
            status_code=503,
            detail="Ollama service not available. Ensure Ollama is running at OLLAMA_BASE_URL."
        )

    try:
        # Add user context to agent state
        initial_state = {
            "task_type": request.task_type,
            "evidence": evidence,
            "context": context,
            "user_context": {
                "employee_id": current_user.get('employee_id', current_user.get('id')),
                "role": current_user.get('role', '').upper(),
                "designation": current_user.get('designation'),
                "permissions": [p.value for p in user_permissions],
                "accessible_project_ids": [scope["project_id"]] if scope["project_id"] else [],
            },
            "agent_history": [],
            "errors": [],
            "analysis": None,
            "recommendations": None,
            "risk_level": None,
            "confidence": None,
        }

        result = await asyncio.to_thread(invoke_agent, request.task_type, initial_state)

        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        run_id = None
        if request.save_run:
            ai_run_repo = AIRunRepository()
            ai_run = AIRun(
                agent_type=request.task_type,
                **scope,
                provenance=provenance,
                input_data=stored_inputs,
                output_data={
                    "analysis": result.get("analysis"),
                    "recommendations": result.get("recommendations"),
                    "risk_level": result.get("risk_level"),
                    "confidence": result.get("confidence"),
                },
                status="completed" if not result.get("errors") else "failed",
                error_message="; ".join(result.get("errors", [])) if result.get("errors") else None,
                execution_time_ms=execution_time,
                model_name=f"ollama/{settings.OLLAMA_MODEL}",  # AI-03: record the actual model
                triggered_by=current_user["email"],
            )
            run_id = await ai_run_repo.create(ai_run)

        return AgentResponse(
            run_id=run_id,
            task_type=request.task_type,
            analysis=result.get("analysis"),
            recommendations=result.get("recommendations"),
            risk_level=result.get("risk_level"),
            confidence=result.get("confidence"),
            agent_history=result.get("agent_history", []),
            errors=result.get("errors", []),
            execution_time_ms=execution_time,
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Agent execution failed")


@router.get("/runs", response_model=list[AIRun])
async def list_ai_runs(
    limit: int = Query(default=50, ge=1, le=500),
    agent_type: str | None = None,
    current_user: dict = Depends(get_current_user),
    skip: int = Query(default=0, ge=0),
):
    """Authorize in MongoDB before counting and paginating the matching runs."""
    ai_run_repo = AIRunRepository()

    filters = await read_filter(current_user)
    if agent_type:
        filters["agent_type"] = agent_type

    runs = await ai_run_repo.list(limit=limit, skip=skip, filters=filters)
    if current_user.get("role", "").upper() == "HR":
        return [filter_ai_run_for_hr(run.model_dump()) for run in runs]
    return runs


@router.get("/runs/{run_id}", response_model=AIRun)
async def get_ai_run(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Read an authorized run, concealing unavailable or unauthorized identities."""
    ai_run_repo = AIRunRepository()
    run = await ai_run_repo.get_by_id(run_id, filters=await read_filter(current_user))

    if not run:
        raise HTTPException(status_code=404, detail="AI run not found")

    if current_user.get("role", "").upper() == "HR":
        return filter_ai_run_for_hr(run.model_dump())

    return run


def filter_ai_run_for_hr(run: Dict[str, Any]) -> Dict[str, Any]:
    """Expose lifecycle metadata only. Generic model prose has no HR-safe approval."""
    fields = ("id", "agent_type", "status", "created_at", "updated_at", "access_version",
              "owner_id", "project_id", "organization_id")
    filtered = {key: run[key] for key in fields if key in run}
    # AIRun retains its public fields, with sensitive values deliberately empty.
    filtered.update(input_data={}, output_data={}, provenance={}, triggered_by="redacted",
                    model_name=None, error_message=None, execution_time_ms=None)
    return filtered
