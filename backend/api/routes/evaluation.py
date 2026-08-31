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
    human_score: float = 5.0               # Human baseline score (1-10)
    evaluation_focus: str = "code_quality" # Focus area


class EvaluationResult(BaseModel):
    """AI evaluation result."""
    evaluation_id: str
    github_username: str
    repo_info: Dict[str, Any]
    human_score: float
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
        from domain.services.github_service import GitHubService
        github_service = GitHubService()
        
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
        
        # Step 3: Run AI evaluation
        ai_analysis = await _run_ai_evaluation(
            github_username=request.github_username,
            repo_info=repo_info,
            pr_analysis=pr_analysis,
            human_score=request.human_score,
            focus=request.evaluation_focus
        )
        
        # Step 4: Calculate overall score
        ai_score = ai_analysis.get("technical_score", 0.0)
        if ai_score > 0:
            overall_score = (request.human_score * 0.3 + ai_score * 0.7)
        else:
            overall_score = request.human_score  # AI unavailable, use human only
        
        # Step 5: Get recommendations from AI (no hardcoded fallbacks)
        recommendations = ai_analysis.get("recommendations", [])
        
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
            ai_analysis=ai_analysis,
            overall_score=round(overall_score, 2),
            recommendations=recommendations,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {str(e)}"
        )


async def _run_ai_evaluation(
    github_username: str,
    repo_info: Dict[str, Any],
    pr_analysis: Optional[Dict[str, Any]],
    human_score: float,
    focus: str
) -> Dict[str, Any]:
    """Run AI evaluation using Ollama."""
    try:
        from agents.llm_provider import get_ollama_llm, check_ollama_connection
        
        # Check if Ollama is available
        if not check_ollama_connection():
            return {
                "technical_score": 0.0,
                "analysis": "AI evaluation unavailable — Ollama not connected",
                "confidence": 0.0,
                "recommendations": [],
                "error": "Ollama not available"
            }
        
        # Build evaluation prompt
        prompt = f"""
Evaluate the technical performance of GitHub user '{github_username}' based on:

Repository Context:
- Repository: {repo_info.get('name', 'N/A')}
- Owner: {repo_info.get('owner', 'N/A')}
- Primary Language: {repo_info.get('language', 'N/A')}
- Description: {repo_info.get('description', 'N/A')}

Human Assessment: {human_score}/10

Pull Request Analysis:
{pr_analysis if pr_analysis else 'No specific PR analyzed'}

Focus Area: {focus}

Please provide:
1. Technical Score (1-10): Based on code quality, architecture, best practices
2. Analysis: Detailed assessment of technical skills
3. Strengths: Key technical strengths observed
4. Areas for Improvement: Specific areas to focus on
5. Recommendations: 3-5 actionable recommendations

Format as JSON with keys: technical_score, analysis, strengths, improvements, recommendations
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
            # Fallback: return raw response without fabricating scores
            ai_data = {
                "technical_score": 0.0,
                "analysis": response[:500] + "..." if len(response) > 500 else response,
                "strengths": [],
                "improvements": [],
                "recommendations": [],
                "parse_error": "Could not extract structured JSON from AI response"
            }
        
        # Ensure technical_score is numeric
        if "technical_score" not in ai_data or not isinstance(ai_data["technical_score"], (int, float)):
            ai_data["technical_score"] = 0.0
        
        # Confidence based on whether we got a real structured response
        ai_data["confidence"] = 0.8 if ai_data["technical_score"] > 0 else 0.0
        return ai_data
        
    except Exception as e:
        return {
            "technical_score": 0.0,
            "analysis": f"AI evaluation failed: {str(e)}",
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
