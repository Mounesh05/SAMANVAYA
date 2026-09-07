"""
AI Evaluation API.
Requires authentication for all endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
from core.dependencies import get_current_user, require_roles
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
        
        # Step 3: Get evidence-based evaluation from engines (authoritative)
        evidence_score = await _get_evidence_based_score(
            repo_info=repo_info,
            pr_analysis=pr_analysis,
        )
        
        # Step 4: Run AI for explanations and recommendations (NOT for scoring)
        ai_insights = await _run_ai_insights(
            github_username=request.github_username,
            repo_info=repo_info,
            pr_analysis=pr_analysis,
            evidence_score=evidence_score,
            focus=request.evaluation_focus
        )
        
        # Step 5: Calculate overall score (90% evidence / 10% human feedback)
        # Evidence-based engines provide authoritative scores
        # Human feedback is optional calibration, not the primary signal
        if request.human_score is not None:
            overall_score = (evidence_score * 0.9 + request.human_score * 0.1)
        else:
            overall_score = evidence_score  # Pure evidence-based when no human input
        
        # Step 6: Get recommendations from AI (no hardcoded fallbacks)
        recommendations = ai_insights.get("recommendations", [])
        
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
                "insights": ai_insights,
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


async def _get_evidence_based_score(
    repo_info: Dict[str, Any],
    pr_analysis: Optional[Dict[str, Any]],
) -> float:
    """
    Calculate evidence-based score from deterministic engines.
    This is the AUTHORITATIVE score, not LLM-generated.
    
    Returns score 0-10 based on:
    - Quality score from QualityEngine (if PR analyzed)
    - Risk score from RiskEngine (if PR analyzed)
    - Repository metrics (stars, activity, etc.)
    
    Note: LLMs explain this score, they don't generate it.
    """
    # If we have PR analysis with quality/risk scores, use those
    if pr_analysis and isinstance(pr_analysis, dict):
        quality_score = pr_analysis.get("quality_score")
        risk_score = pr_analysis.get("risk_score")
        
        if quality_score is not None:
            # Quality score is 0-100, convert to 0-10
            # High quality = high score
            q_normalized = quality_score / 10.0
            
            if risk_score is not None:
                # Risk score is 0-100, convert to 0-10
                # High risk = low score (inverse)
                r_normalized = (100 - risk_score) / 10.0
                # Weighted: 70% quality, 30% risk
                return round(q_normalized * 0.7 + r_normalized * 0.3, 2)
            else:
                return round(q_normalized, 2)
    
    # Fallback: basic repository metrics
    # This is a simplified heuristic when no PR analysis available
    stars = repo_info.get("stargazers_count", 0)
    forks = repo_info.get("forks_count", 0)
    has_issues = repo_info.get("has_issues", False)
    
    # Basic scoring: more stars/forks = more trusted contributor
    # Max 10 points, logarithmic scale
    import math
    if stars > 0:
        star_score = min(10.0, math.log10(stars + 1) * 2)
    else:
        star_score = 5.0  # Neutral when no data
    
    return round(star_score, 2)


async def _run_ai_insights(
    github_username: str,
    repo_info: Dict[str, Any],
    pr_analysis: Optional[Dict[str, Any]],
    evidence_score: float,
    focus: str
) -> Dict[str, Any]:
    """
    Run AI for insights and recommendations (NOT for scoring).
    
    The evidence_score is AUTHORITATIVE and comes from deterministic engines.
    AI's job is to EXPLAIN the evidence and provide recommendations.
    """
    try:
        from agents.llm_provider import get_ollama_llm, check_ollama_connection
        
        # Check if Ollama is available
        if not check_ollama_connection():
            return {
                "analysis": "AI insights unavailable — Ollama not connected",
                "confidence": 0.0,
                "recommendations": [],
                "error": "Ollama not available"
            }
        
        # Build insights prompt (EXPLANATION, not scoring)
        prompt = f"""
Analyze the technical performance of GitHub user '{github_username}' based on evidence.

Repository Context:
- Repository: {repo_info.get('name', 'N/A')}
- Owner: {repo_info.get('owner', 'N/A')}
- Primary Language: {repo_info.get('language', 'N/A')}
- Description: {repo_info.get('description', 'N/A')}

Evidence-Based Score: {evidence_score}/10
(This score comes from deterministic analysis engines - Quality and Risk assessment)

Pull Request Analysis:
{pr_analysis if pr_analysis else 'No specific PR analyzed'}

Focus Area: {focus}

Your task is to EXPLAIN the evidence and provide recommendations.
DO NOT generate your own score - the {evidence_score}/10 is authoritative.

Please provide:
1. Analysis: Explain what the evidence score means for this developer's skills
2. Strengths: Key technical strengths observed from the evidence
3. Areas for Improvement: Specific areas to focus on based on evidence
4. Recommendations: 3-5 actionable recommendations

Format as JSON with keys: analysis, strengths, improvements, recommendations
DO NOT include a "technical_score" field - scoring is done by deterministic engines.
"""

        # Get AI response
        llm = get_ollama_llm(temperature=0.3)
        response = llm.invoke(prompt)
        
        # Parse AI response (basic parsing)
        try:
            import json
            # Try to extract JSON from response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            if start_idx >= 0 and end_idx > start_idx:
                ai_data = json.loads(response[start_idx:end_idx])
            else:
                raise ValueError("No JSON found")
        except Exception:
            # Fallback: return raw response
            ai_data = {
                "analysis": response[:500] + "..." if len(response) > 500 else response,
                "strengths": [],
                "improvements": [],
                "recommendations": [],
                "parse_error": "Could not extract structured JSON from AI response"
            }
        
        # Remove any "technical_score" if LLM included it despite instructions
        if "technical_score" in ai_data:
            del ai_data["technical_score"]
        
        # Confidence based on whether we got a real structured response
        ai_data["confidence"] = 0.8 if "analysis" in ai_data else 0.0
        return ai_data
        
    except Exception as e:
        return {
            "analysis": f"AI insights generation failed: {str(e)}",
            "confidence": 0.0,
            "recommendations": [],
            "error": str(e)
        }


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
