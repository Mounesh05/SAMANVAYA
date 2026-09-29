"""
AI Evaluation API.
Requires authentication for all endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
from core.dependencies import get_current_user, require_roles
import asyncio
import json
import time
import uuid

router = APIRouter()


class SimpleEvalRequest(BaseModel):
    """Simple evaluation request."""
    github_username: str                    # e.g., "torvalds"
    repo_owner: str                        # e.g., "microsoft" 
    repo_name: str                         # e.g., "vscode"
    pr_number: Optional[int] = None        # e.g., 200000 (optional)
    human_score: Optional[float] = None    # Optional human feedback (1-10)
    evaluation_focus: str = "code_quality" # Focus area


class EvaluationResult(BaseModel):
    """AI evaluation result."""
    evaluation_id: str
    github_username: str
    repo_info: Dict[str, Any]
    human_score: Optional[float]  # Optional human feedback (not manufactured)
    ai_analysis: Dict[str, Any]
    overall_score: float
    recommendations: list
    timestamp: str


@router.post("/evaluate", response_model=EvaluationResult)
async def evaluate_developer_ai(request: SimpleEvalRequest, user: dict = Depends(require_roles("CEO", "HR", "LEAD"))):
    """
    AI-powered developer evaluation for a specific repository.
    
    Required roles: CEO, HR, or LEAD per RBAC spec.
    """
    try:
        evaluation_id = f"EVAL-{uuid.uuid4().hex[:8].upper()}"
        
        # Step 1: Get repository info
        from domain.services.github_api_service import GitHubAPIService
        github_service = GitHubAPIService()
        
        repo_info = await github_service.get_repository_info(
            request.repo_owner, 
            request.repo_name
        )
        
        # Step 2: If PR specified, analyze specific PR
        pr_analysis = None
        if request.pr_number:
            try:
                pr_result = await github_service.sync_pull_request(
                    owner=request.repo_owner,
                    repo=request.repo_name,
                    pr_number=request.pr_number,
                    project_id=f"eval-{evaluation_id}",
                    use_ai=True,
                    use_deep_analysis=False,
                    triggered_by=f"evaluation-{request.github_username}"
                )
                pr_analysis = pr_result.get("ai_analysis")
            except Exception as e:
                pr_analysis = {"error": f"Could not analyze PR: {str(e)}"}
        
        # Step 3: Ask AI to score each dimension using only the collected evidence.
        ai_evaluation = await _run_ai_evaluation(
            github_username=request.github_username,
            repo_info=repo_info,
            pr_analysis=pr_analysis,
            focus=request.evaluation_focus
        )
        
        # Step 4: Aggregate validated AI dimension scores. The weights total 90%;
        # the optional human score is a separate 10% calibration signal.
        evidence_score = _calculate_ai_evidence_score(ai_evaluation["dimensions"])
        if request.human_score is not None:
            overall_score = (evidence_score * 0.9 + request.human_score * 0.1)
        else:
            overall_score = evidence_score
        
        recommendations = ai_evaluation["recommendations"]
        
        return EvaluationResult(
            evaluation_id=evaluation_id,
            github_username=request.github_username,
            repo_info={
                "name": repo_info.get("name"),
                "owner": repo_info.get("owner"),
                "language": repo_info.get("language"),
                "description": repo_info.get("description"),
                "stars": repo_info.get("github_url", "").split("/")[-1] if repo_info.get("github_url") else "N/A"
            },
            human_score=request.human_score,
            ai_analysis={
                "evidence_score": evidence_score,
                "dimensions": ai_evaluation["dimensions"],
                "analysis": ai_evaluation["analysis"],
                "strengths": ai_evaluation["strengths"],
                "improvements": ai_evaluation["improvements"],
                "confidence": ai_evaluation["confidence"],
            },
            overall_score=round(overall_score, 2),
            recommendations=recommendations,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {str(e)}"
        )


AI_DIMENSION_WEIGHTS = {
    "code_quality": 25,
    "delivery": 20,
    "collaboration": 15,
    "reliability": 15,
    "engineering_impact": 10,
    "engineering_judgment": 5,
}


def _calculate_ai_evidence_score(dimensions: Dict[str, Any]) -> float:
    """Aggregate validated 0-10 AI dimension scores into a 0-10 score."""
    weighted_points = sum(
        float(dimensions[name]["score"]) * weight
        for name, weight in AI_DIMENSION_WEIGHTS.items()
    )
    return round(weighted_points / 90, 2)


async def _run_ai_evaluation(
    github_username: str,
    repo_info: Dict[str, Any],
    pr_analysis: Optional[Dict[str, Any]],
    focus: str
) -> Dict[str, Any]:
    """
    Score the developer from the supplied evidence and return structured reasoning.
    """
    try:
        from agents.llm_provider import get_ollama_llm, check_ollama_connection

        if not check_ollama_connection():
            raise RuntimeError("Ollama is not available")

        prompt = f"""
Evaluate GitHub user '{github_username}' using only the evidence below.
Do not invent activity, code changes, or outcomes. If evidence is missing, score
that dimension conservatively and explain what is missing.

Repository Context:
- Repository: {repo_info.get('name', 'N/A')}
- Owner: {repo_info.get('owner', 'N/A')}
- Primary Language: {repo_info.get('language', 'N/A')}
- Description: {repo_info.get('description', 'N/A')}

Pull Request Analysis:
{pr_analysis if pr_analysis else 'No specific PR analyzed'}

Focus Area: {focus}

Score each dimension from 0 to 10 based on the evidence:
code_quality, delivery, collaboration, reliability, engineering_impact,
engineering_judgment.

Return JSON only:
{{
  "dimensions": {{
    "code_quality": {{"score": 0, "reasoning": "Evidence-based reasoning"}},
    "delivery": {{"score": 0, "reasoning": "Evidence-based reasoning"}},
    "collaboration": {{"score": 0, "reasoning": "Evidence-based reasoning"}},
    "reliability": {{"score": 0, "reasoning": "Evidence-based reasoning"}},
    "engineering_impact": {{"score": 0, "reasoning": "Evidence-based reasoning"}},
    "engineering_judgment": {{"score": 0, "reasoning": "Evidence-based reasoning"}}
  }},
  "analysis": "Overall evidence-based assessment",
  "strengths": ["Evidence-backed strength"],
  "improvements": ["Evidence-backed improvement"],
  "recommendations": ["Specific actionable recommendation"],
  "confidence": 0.0
}}
"""

        llm = get_ollama_llm(temperature=0.3)
        response = await asyncio.to_thread(llm.invoke, prompt)

        start_idx = response.find("{")
        end_idx = response.rfind("}") + 1
        if start_idx < 0 or end_idx <= start_idx:
            raise ValueError("AI response did not contain JSON")
        ai_data = json.loads(response[start_idx:end_idx])
        dimensions = ai_data.get("dimensions")
        if not isinstance(dimensions, dict):
            raise ValueError("AI response did not contain dimensions")
        for name in AI_DIMENSION_WEIGHTS:
            dimension = dimensions.get(name)
            if not isinstance(dimension, dict):
                raise ValueError(f"AI response missing dimension: {name}")
            score = dimension.get("score")
            if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 10:
                raise ValueError(f"AI score for {name} must be between 0 and 10")
            if not isinstance(dimension.get("reasoning"), str) or not dimension["reasoning"].strip():
                raise ValueError(f"AI reasoning missing for {name}")
        if not isinstance(ai_data.get("recommendations"), list):
            raise ValueError("AI response missing recommendations")
        ai_data["confidence"] = max(0.0, min(1.0, float(ai_data.get("confidence", 0.0))))
        return ai_data
    except Exception as e:
        raise RuntimeError(f"AI evaluation failed: {e}") from e


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
        "evaluation_ready": check_ollama_connection() and github_status in ["configured", "not_configured"]
    }
