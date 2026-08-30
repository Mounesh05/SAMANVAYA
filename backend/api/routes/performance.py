"""
Developer Performance API Routes
Complete REST API for AI-driven performance evaluation system.
Protected with RBAC permissions.
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Dict, Any, Optional, List
from datetime import datetime
from domain.services.performance_service import PerformanceService
from domain.models.developer_performance import (
    DeveloperPerformance,
    DeveloperPerformanceCreate,
    DeveloperPerformanceTrend,
    PMFeedback,
    LeadFeedback,
    QAFeedback,
    DevOpsFeedback,
    CEOFeedback,
    HRFeedback
)
from core.config import settings
from core.dependencies import get_current_user, require_admin
from core.permissions import Permission, check_resource_access

router = APIRouter()


@router.post("/evaluate/bulk", status_code=202)
async def bulk_evaluate_developers(
    developer_ids: List[str] = Body(..., description="List of developer IDs to evaluate"),
    period: str = Body(..., description="Evaluation period (e.g., '2026-Q3')"),
    project_id: str = Body("default-project", description="Project ID"),
    period_type: str = Body("quarter", description="Period type: sprint, month, quarter"),
    user: dict = Depends(get_current_user)
):
    """
    Bulk evaluate multiple developers at once.
    
    **Required Permission:** TRIGGER_BULK_EVALUATION (ADMIN only)
    
    This is an async operation that triggers evaluations for multiple developers.
    Returns immediately with a status message. Evaluations run in background.
    
    Useful for:
    - End of quarter evaluations
    - Bulk processing after data sync
    - Team-wide evaluations
    
    Example:
    ```json
    {
      "developer_ids": ["dev001", "dev002", "dev003"],
      "period": "2026-Q3",
      "project_id": "default-project",
      "period_type": "quarter"
    }
    ```
    
    Returns:
    ```json
    {
      "message": "Bulk evaluation started",
      "developer_count": 3,
      "period": "2026-Q3",
      "status": "processing"
    }
    ```
    """
    # Check permission - ADMIN only
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False)
    )
    
    if Permission.TRIGGER_BULK_EVALUATION not in user_permissions:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Only ADMIN can trigger bulk evaluations."
        )
    
    if not developer_ids or len(developer_ids) == 0:
        raise HTTPException(
            status_code=400,
            detail="No developer IDs provided"
        )
    
    if len(developer_ids) > 100:
        raise HTTPException(
            status_code=400,
            detail="Maximum 100 developers per bulk evaluation"
        )
    
    try:
        # Parse period to dates
        from datetime import datetime, timedelta
        
        if 'Q' in period:
            year_str, quarter_str = period.split('-Q')
            year = int(year_str)
            quarter = int(quarter_str)
            
            month_start = (quarter - 1) * 3 + 1
            month_end = month_start + 2
            
            period_start = datetime(year, month_start, 1)
            if month_end == 12:
                period_end = datetime(year, 12, 31, 23, 59, 59)
            else:
                next_month = datetime(year, month_end + 1, 1)
                period_end = next_month - timedelta(seconds=1)
        else:
            period_end = datetime.now()
            period_start = period_end - timedelta(days=30)
        
        # Get developer details from repository
        from repositories.user_repository import UserRepository
        user_repo = UserRepository()
        
        successful = []
        failed = []
        
        # Process each developer
        for dev_id in developer_ids:
            try:
                # Get developer info
                developer = await user_repo.find_by_employee_id(dev_id)
                if not developer:
                    failed.append({"developer_id": dev_id, "reason": "Not found"})
                    continue
                
                developer_name = developer.get("name", "Unknown")
                developer_email = developer.get("email", f"{dev_id}@example.com")
                
                # Create request
                request = DeveloperPerformanceCreate(
                    developer_id=dev_id,
                    project_id=project_id,
                    period_type=period_type,
                    period_start=period_start,
                    period_end=period_end,
                    period_label=period
                )
                
                # Initialize service
                service = PerformanceService(
                    github_token=settings.GITHUB_TOKEN if hasattr(settings, 'GITHUB_TOKEN') else None
                )
                
                # Evaluate (this could be made async with background tasks)
                performance = await service.evaluate_developer(
                    request=request,
                    developer_name=developer_name,
                    developer_email=developer_email,
                    evaluated_by=f"bulk_eval_by_{user.get('employee_id')}"
                )
                
                successful.append({
                    "developer_id": dev_id,
                    "developer_name": developer_name,
                    "score": performance.final_score,
                    "grade": performance.grade
                })
                
            except Exception as e:
                failed.append({
                    "developer_id": dev_id,
                    "reason": str(e)
                })
        
        return {
            "message": "Bulk evaluation completed",
            "total": len(developer_ids),
            "successful": len(successful),
            "failed": len(failed),
            "period": period,
            "period_type": period_type,
            "results": {
                "successful": successful,
                "failed": failed
            },
            "status": "completed" if len(failed) == 0 else "partial"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Bulk evaluation failed: {str(e)}"
        )


@router.post("/evaluate", response_model=DeveloperPerformance, status_code=201)
async def evaluate_developer_performance(
    developer_id: str = Body(..., description="Developer's user ID"),
    developer_name: str = Body(..., description="Developer's name"),
    period: str = Body(..., description="Evaluation period (e.g., '2026-Q3')"),
    developer_email: Optional[str] = Body(None, description="Developer's email for GitHub matching"),
    project_id: str = Body("default-project", description="Project ID"),
    period_type: str = Body("quarter", description="Period type: sprint, month, quarter"),
    repo_owner: Optional[str] = Body(None, description="GitHub repo owner"),
    repo_name: Optional[str] = Body(None, description="GitHub repo name"),
    evaluated_by: str = Body("api", description="Who triggered the evaluation"),
    user: dict = Depends(get_current_user)
):
    """
    Evaluate developer performance using AI.
    
    **Required Permission:** TRIGGER_AI_EVALUATION (CEO or ADMIN only)
    
    This endpoint:
    1. Collects all developer data (commits, PRs, tasks, etc.)
    2. Sends to AI for evaluation across 6 dimensions
    3. Calculates performance score (0-100)
    4. Returns detailed breakdown with recommendations
    
    **AI evaluates:**
    - Code Quality (25 pts) - Reads actual code diffs
    - Delivery (20 pts) - Evaluates task completion quality
    - Collaboration (15 pts) - Analyzes PR conversations
    - Reliability (15 pts) - Checks tests and bugs
    - Engineering Impact (10 pts) - Assesses business value
    - Engineering Judgment (5 pts) - Pattern analysis
    
    **Total: 90 pts from AI + 10 pts from role feedback**
    """
    # Check permission
    from core.permissions import get_user_permissions
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False)
    )
    
    if Permission.TRIGGER_AI_EVALUATION not in user_permissions:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Only CEO or ADMIN can trigger evaluations."
        )
    
    try:
        # Parse period to dates (simple quarter parsing)
        # Format: "2026-Q3" or "2024-Jan" or custom range
        from datetime import datetime, timedelta
        
        if 'Q' in period:
            # Quarter format: "2026-Q3"
            year_str, quarter_str = period.split('-Q')
            year = int(year_str)
            quarter = int(quarter_str)
            
            month_start = (quarter - 1) * 3 + 1
            month_end = month_start + 2
            
            period_start = datetime(year, month_start, 1)
            if month_end == 12:
                period_end = datetime(year, 12, 31, 23, 59, 59)
            else:
                next_month = datetime(year, month_end + 1, 1)
                period_end = next_month - timedelta(seconds=1)
        else:
            # Default to last 30 days
            period_end = datetime.now()
            period_start = period_end - timedelta(days=30)
        
        # Create request
        request = DeveloperPerformanceCreate(
            developer_id=developer_id,
            project_id=project_id,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            period_label=period
        )
        
        # Initialize service
        service = PerformanceService(github_token=settings.GITHUB_TOKEN if hasattr(settings, 'GITHUB_TOKEN') else None)
        
        # Evaluate
        performance = await service.evaluate_developer(
            request=request,
            developer_name=developer_name,
            developer_email=developer_email or f"{developer_id}@example.com",
            repo_owner=repo_owner,
            repo_name=repo_name,
            evaluated_by=evaluated_by
        )
        
        return performance
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.get("/developer/{developer_id}", response_model=DeveloperPerformance)
async def get_developer_performance(
    developer_id: str,
    period_label: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """
    Get performance evaluation for a developer.
    
    **Permission Check:** 
    - Own data: Requires VIEW_OWN_PERFORMANCE
    - Team data: Requires VIEW_TEAM_PERFORMANCE (LEAD)
    - Any data: ADMIN or CEO
    
    Args:
        developer_id: Developer's user ID
        period_label: Specific period (optional, returns latest if not specified)
    
    Returns:
        Complete performance evaluation with scores and recommendations
    """
    # Check if user can view this developer's performance
    from core.permissions import get_user_permissions
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False)
    )
    
    # Admin can view anyone
    if not user.get('is_admin', False):
        # Check if viewing own data
        if developer_id == user.get('employee_id'):
            if Permission.VIEW_OWN_PERFORMANCE not in user_permissions:
                raise HTTPException(status_code=403, detail="Cannot view own performance")
        # Check if viewing team data
        elif Permission.VIEW_TEAM_PERFORMANCE in user_permissions:
            # TODO: Verify they're in the same team
            pass
        # Check if has organization-wide view
        elif Permission.VIEW_ORGANIZATION_PERFORMANCE not in user_permissions:
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions to view this developer's performance"
            )
    
    try:
        service = PerformanceService()
        performance = await service.get_developer_performance(developer_id, period_label)
        
        if not performance:
            raise HTTPException(
                status_code=404,
                detail=f"No performance data found for developer {developer_id}"
            )
        
        return performance
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/developer/{developer_id}/trend")
async def get_performance_trend(
    developer_id: str,
    limit: int = 10
):
    """
    Get historical performance trend for a developer.
    
    Returns last N evaluations with scores and trends.
    Perfect for displaying performance graphs.
    
    Args:
        developer_id: Developer's user ID
        limit: Number of periods to return (default: 10)
    
    Returns:
        ```json
        {
          "developer_id": "dev123",
          "current_score": 85.2,
          "trend": "improving",
          "history": [
            {
              "period_label": "Sprint-23",
              "final_score": 85.2,
              "grade": "B+",
              "period_start": "2024-01-01"
            },
            ...
          ]
        }
        ```
    """
    try:
        service = PerformanceService()
        trend_data = await service.get_performance_trend(developer_id, limit)
        
        if not trend_data:
            raise HTTPException(
                status_code=404,
                detail=f"No performance history found for developer {developer_id}"
            )
        
        # Calculate trend
        if len(trend_data) >= 2:
            recent = trend_data[0]['final_score']
            previous = trend_data[1]['final_score']
            trend = "improving" if recent > previous else "declining" if recent < previous else "stable"
        else:
            trend = "insufficient_data"
        
        return {
            "developer_id": developer_id,
            "current_score": trend_data[0]['final_score'] if trend_data else 0,
            "trend": trend,
            "history": trend_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/feedback/{performance_id}/pm", response_model=DeveloperPerformance)
async def add_pm_feedback(
    performance_id: str,
    requirement_understanding: int = Body(..., ge=1, le=5),
    delivery_reliability: int = Body(..., ge=1, le=5),
    communication: int = Body(..., ge=1, le=5),
    business_alignment: int = Body(..., ge=1, le=5),
    comments: Optional[str] = Body(None),
    user: dict = Depends(get_current_user)
):
    """
    Add Product Manager feedback (structured 1-5 ratings).
    
    **Required Permission:** SUBMIT_PM_FEEDBACK (PM role only)
    
    **PM evaluates:**
    - Requirement understanding (1-5)
    - Delivery reliability (1-5)
    - Communication (1-5)
    - Business alignment (1-5)
    
    Score automatically recalculated with 10% weight.
    """
    # Check permission
    from core.permissions import get_user_permissions
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False)
    )
    
    if Permission.SUBMIT_PM_FEEDBACK not in user_permissions:
        raise HTTPException(
            status_code=403,
            detail="Only PM role can submit PM feedback"
        )
    
    try:
        service = PerformanceService()
        feedback = {
            "criterion_1": requirement_understanding,
            "criterion_2": delivery_reliability,
            "criterion_3": communication,
            "criterion_4": business_alignment,
            "comments": comments
        }
        return await service.add_role_feedback(performance_id, "pm", feedback)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback/{performance_id}/lead", response_model=DeveloperPerformance)
async def add_lead_feedback(
    performance_id: str,
    technical_skill: int = Body(..., ge=1, le=5),
    code_quality: int = Body(..., ge=1, le=5),
    mentoring: int = Body(..., ge=1, le=5),
    technical_ownership: int = Body(..., ge=1, le=5),
    comments: Optional[str] = Body(None)
):
    """
    Add Team Lead feedback (structured 1-5 ratings).
    
    **Lead evaluates:**
    - Technical skill (1-5)
    - Code quality (1-5)
    - Mentoring (1-5)
    - Technical ownership (1-5)
    """
    try:
        service = PerformanceService()
        feedback = {
            "criterion_1": technical_skill,
            "criterion_2": code_quality,
            "criterion_3": mentoring,
            "criterion_4": technical_ownership,
            "comments": comments
        }
        return await service.add_role_feedback(performance_id, "lead", feedback)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback/{performance_id}/qa", response_model=DeveloperPerformance)
async def add_qa_feedback(
    performance_id: str,
    quality_focus: int = Body(..., ge=1, le=5),
    test_coverage: int = Body(..., ge=1, le=5),
    bug_response: int = Body(..., ge=1, le=5),
    regression_awareness: int = Body(..., ge=1, le=5),
    comments: Optional[str] = Body(None)
):
    """
    Add QA Engineer feedback (structured 1-5 ratings).
    
    **QA evaluates:**
    - Quality focus (1-5)
    - Test coverage (1-5)
    - Bug response (1-5)
    - Regression awareness (1-5)
    """
    try:
        service = PerformanceService()
        feedback = {
            "criterion_1": quality_focus,
            "criterion_2": test_coverage,
            "criterion_3": bug_response,
            "criterion_4": regression_awareness,
            "comments": comments
        }
        return await service.add_role_feedback(performance_id, "qa", feedback)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback/{performance_id}/devops", response_model=DeveloperPerformance)
async def add_devops_feedback(
    performance_id: str,
    deployment_quality: int = Body(..., ge=1, le=5),
    ci_cd_compliance: int = Body(..., ge=1, le=5),
    monitoring_awareness: int = Body(..., ge=1, le=5),
    incident_response: int = Body(..., ge=1, le=5),
    comments: Optional[str] = Body(None)
):
    """
    Add DevOps Engineer feedback (structured 1-5 ratings).
    
    **DevOps evaluates:**
    - Deployment quality (1-5)
    - CI/CD compliance (1-5)
    - Monitoring awareness (1-5)
    - Incident response (1-5)
    """
    try:
        service = PerformanceService()
        feedback = {
            "criterion_1": deployment_quality,
            "criterion_2": ci_cd_compliance,
            "criterion_3": monitoring_awareness,
            "criterion_4": incident_response,
            "comments": comments
        }
        return await service.add_role_feedback(performance_id, "devops", feedback)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback/{performance_id}/ceo", response_model=DeveloperPerformance)
async def add_ceo_feedback(
    performance_id: str,
    business_impact: int = Body(..., ge=1, le=5),
    innovation: int = Body(..., ge=1, le=5),
    company_alignment: int = Body(..., ge=1, le=5),
    leadership_potential: int = Body(..., ge=1, le=5),
    comments: Optional[str] = Body(None)
):
    """
    Add CEO feedback (structured 1-5 ratings).
    
    **CEO evaluates:**
    - Business impact (1-5)
    - Innovation (1-5)
    - Company alignment (1-5)
    - Leadership potential (1-5)
    """
    try:
        service = PerformanceService()
        feedback = {
            "criterion_1": business_impact,
            "criterion_2": innovation,
            "criterion_3": company_alignment,
            "criterion_4": leadership_potential,
            "comments": comments
        }
        return await service.add_role_feedback(performance_id, "ceo", feedback)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback/{performance_id}/hr", response_model=DeveloperPerformance)
async def add_hr_feedback(
    performance_id: str,
    collaboration: int = Body(..., ge=1, le=5),
    professionalism: int = Body(..., ge=1, le=5),
    communication_skills: int = Body(..., ge=1, le=5),
    cultural_fit: int = Body(..., ge=1, le=5),
    comments: Optional[str] = Body(None)
):
    """
    Add HR feedback (structured 1-5 ratings).
    
    **HR evaluates:**
    - Collaboration (1-5)
    - Professionalism (1-5)
    - Communication skills (1-5)
    - Cultural fit (1-5)
    """
    try:
        service = PerformanceService()
        feedback = {
            "criterion_1": collaboration,
            "criterion_2": professionalism,
            "criterion_3": communication_skills,
            "criterion_4": cultural_fit,
            "comments": comments
        }
        return await service.add_role_feedback(performance_id, "hr", feedback)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/team/{project_id}/{period_label}")
async def get_team_performance(
    project_id: str,
    period_label: str
):
    """
    Get performance summary for all developers in a project/period.
    
    Special values:
    - project_id="all" - Get from all projects
    - period_label="current" - Get latest period
    
    Perfect for team dashboards and comparative analysis.
    """
    try:
        service = PerformanceService()
        
        # Handle special case: "all" project and "current" period
        # Get latest evaluations for all developers
        if project_id == "all" and period_label == "current":
            from repositories.performance_repository import PerformanceRepository
            repo = PerformanceRepository()
            
            # Get all unique developers and their latest evaluation
            developers_data = []
            
            # Query to get latest evaluation for each developer
            pipeline = [
                {"$sort": {"created_at": -1}},
                {"$group": {
                    "_id": "$developer_id",
                    "latest": {"$first": "$$ROOT"}
                }}
            ]
            
            async for doc in repo.collection.aggregate(pipeline):
                latest = doc['latest']
                
                # Map trend to frontend format
                trend_map = {
                    'improving': 'up',
                    'declining': 'down',
                    'stable': 'stable'
                }
                
                developers_data.append({
                    "developer_id": latest['developer_id'],
                    "developer_name": latest['developer_name'],
                    "overall_score": latest['final_score'],  # Map final_score to overall_score
                    "grade": latest['grade'],
                    "trend": trend_map.get(latest.get('trend', 'stable'), 'stable'),
                    "last_evaluated": latest['created_at'].isoformat()
                })
            
            if not developers_data:
                raise HTTPException(
                    status_code=404,
                    detail="No performance data found. Run an evaluation first."
                )
            
            # Calculate team stats
            total_score = sum(d['overall_score'] for d in developers_data)
            average_score = total_score / len(developers_data) if developers_data else 0
            
            return developers_data
        
        # Original behavior for specific project/period
        team_data = await service.get_team_performance(project_id, period_label)
        
        if not team_data:
            raise HTTPException(
                status_code=404,
                detail=f"No performance data for project {project_id}, period {period_label}"
            )
        
        # Transform to match frontend TeamMember interface
        trend_map = {
            'improving': 'up',
            'declining': 'down',
            'stable': 'stable'
        }
        
        transformed_data = []
        for member in team_data:
            created_at = member.get('created_at')
            if created_at:
                # If it's a datetime object, convert to ISO string
                if hasattr(created_at, 'isoformat'):
                    last_eval = created_at.isoformat()
                else:
                    last_eval = str(created_at)
            else:
                last_eval = datetime.now().isoformat()
            
            transformed_data.append({
                "developer_id": member['developer_id'],
                "developer_name": member['developer_name'],
                "overall_score": member['final_score'],  # Map to overall_score
                "grade": member['grade'],
                "trend": trend_map.get(member.get('trend', 'stable'), 'stable'),
                "last_evaluated": last_eval
            })
        
        return transformed_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard/{developer_id}")
async def get_developer_dashboard(
    developer_id: str,
    periods: int = 6
):
    """
    Complete developer dashboard data - matches frontend DashboardData interface.
    
    Returns everything needed for a beautiful dashboard:
    - Current score and grade
    - Dimensional breakdown
    - Trend over time
    - Strengths and weaknesses
    - AI recommendations
    - Confidence level
    
    **This is your main dashboard endpoint!**
    
    Returns structure matching frontend types:
    ```json
    {
      "current_performance": {
        "developer_id": "dev001",
        "developer_name": "John Doe",
        "period": "2026-Q3",
        "overall_score": 85.2,
        "grade": "A",
        "ai_evaluation": {
          "overall_score": 76.8,
          "dimension_scores": {
            "code_quality": 22.5,
            "delivery_speed": 18.0,
            "collaboration": 13.5,
            "reliability": 13.0,
            "business_impact": 6.8,
            "technical_judgment": 3.0
          },
          "strengths": ["Strong code quality", "Excellent collaboration"],
          "weaknesses": ["Could improve delivery speed"],
          "recommendations": ["Focus on breaking down tasks"],
          "confidence_score": 85,
          "evaluation_summary": "Strong performer with great technical skills"
        },
        "role_evaluations": [],
        "trend_data": [],
        "last_evaluated": "2026-08-10T00:00:00Z",
        "evaluation_count": 1
      },
      "historical_trend": [
        {
          "period": "2026-Q3",
          "score": 85.2,
          "grade": "A"
        }
      ],
      "peer_comparison": {
        "team_average": 78.5,
        "rank": 3,
        "total_developers": 12
      }
    }
    ```
    """
    try:
        service = PerformanceService()
        
        # Get latest performance
        current = await service.get_developer_performance(developer_id)
        
        if not current:
            raise HTTPException(
                status_code=404,
                detail=f"No performance data found for developer {developer_id}. Run an evaluation first at POST /api/performance/evaluate"
            )
        
        # Get trend
        trend_data = await service.get_performance_trend(developer_id, periods)
        
        # Transform to frontend format
        current_performance = {
            "developer_id": current.developer_id,
            "developer_name": current.developer_name,
            "period": current.period_label,
            "overall_score": current.final_score,
            "grade": current.grade,
            "ai_evaluation": {
                "overall_score": current.ai_evaluation.score,
                "dimension_scores": {
                    "code_quality": current.ai_evaluation.breakdown.code_quality,
                    "delivery_speed": current.ai_evaluation.breakdown.delivery,
                    "collaboration": current.ai_evaluation.breakdown.collaboration,
                    "reliability": current.ai_evaluation.breakdown.reliability,
                    "business_impact": current.ai_evaluation.breakdown.engineering_impact,
                    "technical_judgment": current.ai_evaluation.breakdown.engineering_judgment
                },
                "strengths": current.ai_evaluation.strengths,
                "weaknesses": current.ai_evaluation.weaknesses,
                "recommendations": current.ai_evaluation.recommendations,
                "confidence_score": 85.0 if current.ai_evaluation.confidence == "high" else 70.0 if current.ai_evaluation.confidence == "medium" else 50.0,
                "evaluation_summary": current.ai_evaluation.reasoning or "AI evaluation completed successfully"
            },
            "role_evaluations": [],  # Can be expanded to include role feedback details
            "trend_data": [],
            "last_evaluated": current.created_at.isoformat(),
            "evaluation_count": len(trend_data) if trend_data else 1
        }
        
        # Transform trend data to frontend format
        historical_trend = []
        if trend_data:
            for item in trend_data:
                historical_trend.append({
                    "period": item.get('period_label', ''),
                    "score": item.get('final_score', 0),
                    "grade": item.get('grade', 'N/A')
                })
        
        # Build dashboard response matching frontend DashboardData interface
        dashboard = {
            "current_performance": current_performance,
            "historical_trend": historical_trend,
            "peer_comparison": None  # Will be None if no team data available
        }
        
        return dashboard
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard error: {str(e)}")
