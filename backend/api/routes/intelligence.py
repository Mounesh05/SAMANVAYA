"""
Intelligence API endpoints.
Exposes Layer 5 (Intelligence Engine) capabilities for testing and use.
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from core.dependencies import get_current_user
from intelligence.risk_engine import RiskEngine
from typing import Optional

router = APIRouter()
risk_engine = RiskEngine()


@router.post("/analyze-pr/{pr_id}")
async def analyze_pr(
    pr_id: str,
    data: dict = Body(...),
    user: dict = Depends(get_current_user),
):
    """
    Analyze a pull request for risk.
    
    This demonstrates Layer 5 (Intelligence Engine) in action.
    Pure rule-based analysis - NO LLM.
    
    Example payload:
    ```json
    {
        "files_changed": 15,
        "lines_added": 300,
        "lines_deleted": 50,
        "changed_files": ["src/auth/login.py", "src/auth/token.py"],
        "commit_count": 8,
        "pr_age_hours": 48,
        "tests_passed": 120,
        "tests_failed": 3,
        "previous_coverage": 85.5,
        "current_coverage": 82.0
    }
    ```
    """
    try:
        evidence = await risk_engine.analyze_pull_request(
            pr_id=pr_id,
            files_changed=data.get("files_changed"),
            lines_added=data.get("lines_added"),
            lines_deleted=data.get("lines_deleted"),
            changed_files=data.get("changed_files", []),
            commit_count=data.get("commit_count"),
            pr_age_hours=data.get("pr_age_hours"),
            tests_passed=data.get("tests_passed", 0),
            tests_failed=data.get("tests_failed", 0),
            previous_coverage=data.get("previous_coverage"),
            current_coverage=data.get("current_coverage"),
        )
        return evidence
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-sprint/{sprint_id}")
async def analyze_sprint(
    sprint_id: str,
    data: dict = Body(default={}),
    user: dict = Depends(get_current_user),
):
    """
    Analyze sprint health: Plan vs Reality.
    
    This is the core intelligence calculation.
    
    Example payload:
    ```json
    {
        "total_stories": 15,
        "completed_stories": 8,
        "in_progress_stories": 4,
        "blocked_stories": 2,
        "total_points": 75,
        "completed_points": 40,
        "original_points": 65
    }
    ```
    """
    try:
        evidence = await risk_engine.analyze_sprint(
            sprint_id=sprint_id,
            stories_data=data if data else None,
        )
        return evidence
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-deployment/{deployment_id}")
async def analyze_deployment(
    deployment_id: str,
    data: dict = Body(...),
    user: dict = Depends(get_current_user),
):
    """
    Analyze deployment risk based on CI/CD metrics.
    
    Example payload:
    ```json
    {
        "ci_data": {
            "builds_total": 20,
            "builds_passed": 18,
            "builds_failed": 2
        },
        "deployment_data": {
            "deployments_total": 10,
            "deployments_successful": 9,
            "deployments_failed": 1,
            "rollbacks": 0
        }
    }
    ```
    """
    try:
        evidence = await risk_engine.analyze_deployment(
            deployment_id=deployment_id,
            ci_data=data.get("ci_data"),
            deployment_data=data.get("deployment_data"),
        )
        return evidence
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def intelligence_health():
    """
    Health check for Intelligence Engine.
    Returns available analyzers and their status.
    """
    return {
        "status": "operational",
        "layer": "5 - Intelligence Engine",
        "capabilities": [
            "PR risk analysis",
            "Sprint health analysis (Plan vs Reality)",
            "Deployment risk analysis",
            "Code metrics calculation",
            "Quality metrics calculation",
            "DevOps metrics calculation",
            "Sprint metrics calculation",
        ],
        "note": "All analysis is rule-based. NO LLM used in this layer.",
    }
