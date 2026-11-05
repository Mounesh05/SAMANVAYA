"""
AI Agent API Routes
Invoke specialized agents to interpret Intelligence Engine evidence
"""

from typing import Dict, Any, Literal
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import datetime, timezone

from agents.supervisor import invoke_agent
from agents.llm_provider import check_ollama_connection
from core.dependencies import get_current_user
from core.authorization import get_accessible_project_ids, has_org_access
from core.permissions import get_user_permissions, Permission
from domain.models.ai_run import AIRun
from repositories.ai_run_repository import AIRunRepository

router = APIRouter(tags=["AI Agents"])


class AgentRequest(BaseModel):
    """Request to invoke an AI agent."""
    task_type: Literal["code_review", "qa_analysis", "devops_risk", "meeting_insights", "cicd_analysis", "hr_assistant"]
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
    # Check permission to trigger AI evaluation
    user_permissions = get_user_permissions(
        current_user.get('role', '').upper(),
        current_user.get('is_admin', False),
        current_user.get('designation')
    )
    if Permission.TRIGGER_AI_EVALUATION not in user_permissions:
        raise HTTPException(status_code=403, detail='Insufficient permissions')
    
    start_time = datetime.now(timezone.utc)

    if not check_ollama_connection():
        raise HTTPException(
            status_code=503,
            detail="Ollama service not available. Ensure Ollama is running at OLLAMA_BASE_URL."
        )

    try:
        # Add user context to agent state
        accessible_project_ids = await get_accessible_project_ids(current_user)
        
        initial_state = {
            "task_type": request.task_type,
            "evidence": request.evidence,
            "context": request.context,
            "user_context": {
                "employee_id": current_user.get('employee_id', current_user.get('id')),
                "role": current_user.get('role', '').upper(),
                "designation": current_user.get('designation'),
                "permissions": [p.value for p in user_permissions],
                "accessible_project_ids": accessible_project_ids,
            },
            "agent_history": [],
            "errors": [],
            "analysis": None,
            "recommendations": None,
            "risk_level": None,
            "confidence": None,
        }

        import asyncio
        result = await asyncio.to_thread(invoke_agent, request.task_type, initial_state)

        execution_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        run_id = None
        if request.save_run:
            ai_run_repo = AIRunRepository()
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
    """List recent AI agent runs with optional filtering. Only returns runs for accessible projects.
    
    **HR users receive filtered runs without technical evidence.**
    """
    ai_run_repo = AIRunRepository()

    filters = {}
    if agent_type:
        filters["agent_type"] = agent_type

    runs = await ai_run_repo.list(limit=limit, filters=filters)
    
    # Filter runs by accessible projects
    # AI runs store project_id in context if available
    accessible_project_ids = await get_accessible_project_ids(current_user)
    is_hr_user = current_user.get('role', '').upper() == 'HR'
    
    filtered_runs = []
    for run in runs:
        # If user has org-wide access, include all runs
        if has_org_access(current_user):
            # Filter technical details for HR
            if is_hr_user:
                run_dict = run if isinstance(run, dict) else run.dict() if hasattr(run, 'dict') else {}
                filtered_runs.append(filter_ai_run_for_hr(run_dict))
            else:
                filtered_runs.append(run)
            continue
            
        # Check if run has a project_id in context
        run_dict = run if isinstance(run, dict) else run.dict() if hasattr(run, 'dict') else {}
        input_data = run_dict.get("input_data", {})
        context = input_data.get("context", {}) if isinstance(input_data, dict) else {}
        project_id = context.get("project_id") if isinstance(context, dict) else None
        
        # Include run if it has no project_id (ad-hoc) or if user has access
        if not project_id or project_id in accessible_project_ids:
            # Filter technical details for HR
            if is_hr_user:
                filtered_runs.append(filter_ai_run_for_hr(run_dict))
            else:
                filtered_runs.append(run)
    
    return filtered_runs


@router.get("/runs/{run_id}", response_model=AIRun)
async def get_ai_run(
    run_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get specific AI run by ID. User must have access to the run's project if applicable.
    
    **HR users receive filtered run without technical evidence.**
    """
    ai_run_repo = AIRunRepository()
    run = await ai_run_repo.get_by_id(run_id)

    if not run:
        raise HTTPException(status_code=404, detail="AI run not found")

    is_hr_user = current_user.get('role', '').upper() == 'HR'

    # Check project access if run has a project_id
    if not has_org_access(current_user):
        run_dict = run if isinstance(run, dict) else run.dict() if hasattr(run, 'dict') else {}
        input_data = run_dict.get("input_data", {})
        context = input_data.get("context", {}) if isinstance(input_data, dict) else {}
        project_id = context.get("project_id") if isinstance(context, dict) else None
        
        if project_id:
            accessible_project_ids = await get_accessible_project_ids(current_user)
            if project_id not in accessible_project_ids:
                raise HTTPException(status_code=403, detail="You don't have access to this AI run")

    # Filter technical details for HR
    if is_hr_user:
        run_dict = run if isinstance(run, dict) else run.dict() if hasattr(run, 'dict') else {}
        return filter_ai_run_for_hr(run_dict)

    return run


def filter_ai_run_for_hr(run: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove technical evidence from AI run results for HR users.
    HR sees summary, scores, recommendations - NO raw technical data.
    
    Args:
        run: Full AI run data
        
    Returns:
        Filtered run data safe for HR viewing
    """
    filtered = run.copy()
    
    # Remove technical evidence from output_data
    if 'output_data' in filtered and filtered['output_data']:
        output = filtered['output_data'].copy()
        
        # Remove raw technical details
        output.pop('raw_evidence', None)
        output.pop('github_data', None)
        output.pop('pr_diffs', None)
        output.pop('commit_details', None)
        output.pop('cicd_logs', None)
        output.pop('code_review_comments', None)
        output.pop('test_failures', None)
        output.pop('technical_details', None)
        
        # Remove system internals and debugging info
        output.pop('agent_history', None)
        output.pop('errors', None)
        
        # Keep only HR-appropriate summaries
        # Keep: summary, scores, recommendations, risk_level, analysis, confidence
        filtered['output_data'] = output
    
    # Remove raw evidence from input_data completely
    if 'input_data' in filtered and filtered['input_data']:
        input_data = filtered['input_data'].copy()
        input_data.pop('evidence', None)  # Remove full evidence dict completely
        filtered['input_data'] = input_data
    
    return filtered
