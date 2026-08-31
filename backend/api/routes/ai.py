"""
AI Agent API Routes
Invoke specialized agents to interpret Intelligence Engine evidence
"""

from typing import Dict, Any, Literal
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import datetime

from agents.supervisor import invoke_agent
from agents.llm_provider import check_ollama_connection
from core.dependencies import get_current_user
from domain.models.ai_run import AIRun
from repositories.ai_run_repository import AIRunRepository
from core.database import db

router = APIRouter(prefix="/ai", tags=["AI Agents"])


class AgentRequest(BaseModel):
    """Request to invoke an AI agent."""
    task_type: Literal["code_review", "qa_analysis", "devops_risk", "meeting_insights", "cicd_analysis"]
    evidence: Dict[str, Any] = Field(..., description="Evidence from Intelligence Engine")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    save_run: bool = Field(default=True, description="Save run to database")


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
    ollama_ok = check_ollama_connection()

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
    start_time = datetime.utcnow()

    if not check_ollama_connection():
        raise HTTPException(
            status_code=503,
            detail="Ollama service not available. Ensure Ollama is running at OLLAMA_BASE_URL."
        )

    try:
        initial_state = {
            "task_type": request.task_type,
            "evidence": request.evidence,
            "context": request.context,
            "agent_history": [],
            "errors": [],
            "analysis": None,
            "recommendations": None,
            "risk_level": None,
            "confidence": None,
        }

        result = invoke_agent(request.task_type, initial_state)

        execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        run_id = None
        if request.save_run:
            ai_run_repo = AIRunRepository(db)
            ai_run = AIRun(
                agent_type=request.task_type,
                input_data={"evidence": request.evidence, "context": request.context},
                output_data={
                    "analysis": result.get("analysis"),
                    "recommendations": result.get("recommendations"),
                    "risk_level": result.get("risk_level"),
                    "confidence": result.get("confidence"),
                },
                status="completed" if not result.get("errors") else "failed",
                error_message="; ".join(result.get("errors", [])) if result.get("errors") else None,
                execution_time_ms=execution_time,
                model_name="ollama",
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
    limit: int = 50,
    agent_type: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    """List recent AI agent runs with optional filtering."""
    ai_run_repo = AIRunRepository(db)

    filters = {}
    if agent_type:
        filters["agent_type"] = agent_type

    runs = await ai_run_repo.list(limit=limit, filters=filters)
    return runs


@router.get("/runs/{run_id}", response_model=AIRun)
async def get_ai_run(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get specific AI run by ID."""
    ai_run_repo = AIRunRepository(db)
    run = await ai_run_repo.get_by_id(run_id)

    if not run:
        raise HTTPException(status_code=404, detail="AI run not found")

    return run
