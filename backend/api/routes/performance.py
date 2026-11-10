"""
Developer Performance API Routes
Complete REST API for AI-driven performance evaluation system.
Protected with RBAC permissions.
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel, Field
from typing import Optional, List, Union, Dict, Any
from datetime import datetime
from domain.services.performance_service import PerformanceService
from domain.services.hr_performance_service import HRPerformanceService
from domain.models.developer_performance import (
    DeveloperPerformance,
    DeveloperPerformanceCreate
)
from domain.models.hr_performance import (
    HRAssessment,
    HRAssessmentCreate,
    HumanEvaluationPolicy,
    HumanEvaluationCompleteness,
)
from domain.schemas.hr_views import PerformanceOutcomeHR, HRDashboardPerformanceView
from core.config import settings
from core.dependencies import get_current_user
from core.permissions import Permission, get_user_permissions
from core.authorization import verify_can_view_user_tasks, get_accessible_project_ids, has_org_access
from core.audit import log_audit, AuditAction

router = APIRouter()


class CreditAppealRequest(BaseModel):
    reason: str = Field(..., min_length=20, max_length=2000)
    evidence: List[str] = Field(default_factory=list, max_length=20)


@router.post("/credit/{performance_id}/appeal")
async def appeal_credit(
    performance_id: str,
    body: CreditAppealRequest,
    user: dict = Depends(get_current_user),
):
    """Record a developer's appeal without overwriting the original score."""
    from repositories.performance_repository import PerformanceRepository

    repository = PerformanceRepository()
    performance = await repository.get_by_id(performance_id)
    if not performance:
        raise HTTPException(status_code=404, detail="Performance evaluation not found")

    developer_id = performance.get("developer_id")
    if developer_id != user.get("employee_id") and not user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Only the developer or an administrator can appeal")

    appeal = {
        "submitted_by": user.get("employee_id", user.get("id", "")),
        "reason": body.reason,
        "evidence": body.evidence,
        "submitted_at": datetime.utcnow().isoformat(),
        "status": "pending",
    }
    await repository.update(performance_id, {"appeal": appeal, "credit_status": "appealed"})
    await log_audit(
        action=AuditAction.CREDIT_APPEALED,
        actor=user,
        resource_type="performance",
        resource_id=performance_id,
        details={"evidence_count": len(body.evidence)},
    )
    return {"performance_id": performance_id, "credit_status": "appealed", "appeal": appeal}


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

    # Disallow evaluating executive or administrative roles (CEO, HR)
    try:
        from repositories.user_repository import UserRepository
        user_repo = UserRepository()
        for d_id in developer_ids:
            t_user = await user_repo.find_by_employee_id(d_id)
            if t_user and t_user.get("role", "").upper() in ("CEO", "HR"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot evaluate employee {d_id} with role {t_user.get('role')}. Performance evaluations only apply to engineering contributors."
                )
    except HTTPException:
        raise
    except Exception:
        pass
    
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
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
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

    # Disallow evaluating executive or administrative roles (CEO, HR)
    try:
        from repositories.user_repository import UserRepository
        user_repo = UserRepository()
        target_emp = await user_repo.find_by_employee_id(developer_id)
        if target_emp:
            target_role = target_emp.get("role", "").upper()
            if target_role in ("CEO", "HR"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot evaluate employee {developer_id} with role {target_role}. Performance evaluations only apply to engineering contributors."
                )
    except HTTPException:
        raise
    except Exception:
        pass
    
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
        
        # Check if AI evaluation failed
        if performance.ai_evaluation.data_quality.get("ai_evaluation_failed", False):
            raise HTTPException(
                status_code=503,
                detail="AI evaluation service unavailable. The evaluation was saved but AI insights are missing. Please retry when Ollama is running."
            )
        
        # Audit log
        await log_audit(
            action=AuditAction.EVALUATION_TRIGGERED,
            actor=user,
            resource_type="performance",
            resource_id=developer_id,
            details={"period": period, "project_id": project_id}
        )
        
        return performance
        
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/developer/{developer_id}", response_model=Union[DeveloperPerformance, PerformanceOutcomeHR])
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
    - HR: Requires VIEW_PERFORMANCE_OUTCOMES (filtered view, no technical details)
    
    Args:
        developer_id: Developer's user ID
        period_label: Specific period (optional, returns latest if not specified)
    
    Returns:
        Complete performance evaluation with scores and recommendations.
        **HR users receive filtered outcome without technical evidence.**
    """
    # Check if user can view this developer's performance
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False),
        user.get('designation')
    )
    
    # Determine if HR user
    is_hr_user = user.get('role', '').upper() == 'HR'
    
    # Admin can view anyone
    if not user.get('is_admin', False):
        # Check if viewing own data
        if developer_id == user.get('employee_id'):
            if Permission.VIEW_OWN_PERFORMANCE not in user_permissions:
                raise HTTPException(status_code=403, detail="Cannot view own performance")
        # Check if HR viewing performance outcomes
        elif is_hr_user and Permission.VIEW_PERFORMANCE_OUTCOMES in user_permissions:
            pass  # HR can view, but will get filtered data
        # Check if viewing team data (LEAD must be same team)
        elif Permission.VIEW_TEAM_PERFORMANCE in user_permissions:
            # Verify user has access to the developer's data (same team for LEAD)
            await verify_can_view_user_tasks(user, developer_id)
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
        
        # Convert to dict if needed
        perf_dict = performance if isinstance(performance, dict) else performance.dict() if hasattr(performance, 'dict') else performance.__dict__
        
        # Return filtered view for HR users
        if is_hr_user:
            return PerformanceOutcomeHR.from_performance(perf_dict)
        
        return performance
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.get("/developer/{developer_id}/trend")
async def get_performance_trend(
    developer_id: str,
    limit: int = 10,
    user: dict = Depends(get_current_user),
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
    # Authorization: verify user can view this developer's performance
    user_role = user.get('role', user.get('organizational_role', '')).upper()
    if user_role == "HR":
        user_permissions = get_user_permissions(
            user_role,
            user.get('is_admin', False),
            user.get('designation')
        )
        if (
            Permission.VIEW_PERFORMANCE_OUTCOMES not in user_permissions
            and Permission.VIEW_HR_PERFORMANCE_ASSESSMENT not in user_permissions
        ):
            raise HTTPException(
                status_code=403,
                detail="Insufficient permissions to view developer performance outcomes"
            )
    else:
        await verify_can_view_user_tasks(user, developer_id)

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
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")



async def _resolve_evaluatable_developer(performance_id: str, service: PerformanceService):
    """Safely resolve developer ID from performance ID or employee ID, barring CEO/HR evaluations."""
    performance = await service.repository.get_by_id(performance_id)
    if performance:
        return performance.get("developer_id"), performance
    from repositories.user_repository import UserRepository
    user_repo = UserRepository()
    target_emp = await user_repo.find_by_employee_id(performance_id)
    if not target_emp:
        raise HTTPException(status_code=404, detail="Performance evaluation or employee not found")
    target_role = target_emp.get("role", "").upper()
    if target_role in ("CEO", "HR"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot evaluate employee with role {target_role}. Performance evaluations only apply to engineering contributors."
        )
    return target_emp.get("employee_id"), None


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
    """
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
    
    # Authorization: verify user can view the target developer's performance
    service = PerformanceService()
    developer_id, _ = await _resolve_evaluatable_developer(performance_id, service)
    await verify_can_view_user_tasks(user, developer_id)
    
    try:
        feedback = {
            "criterion_1": requirement_understanding,
            "criterion_2": delivery_reliability,
            "criterion_3": communication,
            "criterion_4": business_alignment,
            "comments": comments
        }
        return await service.add_role_feedback(performance_id, "pm", feedback)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.post("/feedback/{performance_id}/lead", response_model=DeveloperPerformance)
async def add_lead_feedback(
    performance_id: str,
    technical_skill: int = Body(..., ge=1, le=5),
    code_quality: int = Body(..., ge=1, le=5),
    mentoring: int = Body(..., ge=1, le=5),
    technical_ownership: int = Body(..., ge=1, le=5),
    comments: Optional[str] = Body(None),
    user: dict = Depends(get_current_user),
):
    """
    Add Team Lead feedback (structured 1-5 ratings).

    **Required Permission:** SUBMIT_LEAD_FEEDBACK (LEAD role only)
    """
    from core.permissions import get_user_permissions
    user_permissions = get_user_permissions(user.get('role', '').upper(), user.get('is_admin', False))
    if Permission.SUBMIT_LEAD_FEEDBACK not in user_permissions:
        raise HTTPException(status_code=403, detail="Only Lead role can submit Lead feedback")
    
    # Authorization: verify user can view the target developer's performance
    service = PerformanceService()
    developer_id, _ = await _resolve_evaluatable_developer(performance_id, service)
    await verify_can_view_user_tasks(user, developer_id)
    
    try:
        feedback = {
            "criterion_1": technical_skill,
            "criterion_2": code_quality,
            "criterion_3": mentoring,
            "criterion_4": technical_ownership,
            "comments": comments
        }
        return await service.add_role_feedback(performance_id, "lead", feedback)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.post("/feedback/{performance_id}/qa", response_model=DeveloperPerformance)
async def add_qa_feedback(
    performance_id: str,
    quality_focus: int = Body(..., ge=1, le=5),
    test_coverage: int = Body(..., ge=1, le=5),
    bug_response: int = Body(..., ge=1, le=5),
    regression_awareness: int = Body(..., ge=1, le=5),
    comments: Optional[str] = Body(None),
    user: dict = Depends(get_current_user),
):
    """
    Add QA Engineer feedback (structured 1-5 ratings).

    **Required Permission:** SUBMIT_QA_FEEDBACK (QA role only)
    """
    from core.permissions import get_user_permissions
    user_permissions = get_user_permissions(user.get('role', '').upper(), user.get('is_admin', False))
    if Permission.SUBMIT_QA_FEEDBACK not in user_permissions:
        raise HTTPException(status_code=403, detail="Only QA role can submit QA feedback")
    
    # Authorization: verify user can view the target developer's performance
    service = PerformanceService()
    developer_id, _ = await _resolve_evaluatable_developer(performance_id, service)
    await verify_can_view_user_tasks(user, developer_id)
    
    try:
        feedback = {
            "criterion_1": quality_focus,
            "criterion_2": test_coverage,
            "criterion_3": bug_response,
            "criterion_4": regression_awareness,
            "comments": comments
        }
        return await service.add_role_feedback(performance_id, "qa", feedback)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.post("/feedback/{performance_id}/devops", response_model=DeveloperPerformance)
async def add_devops_feedback(
    performance_id: str,
    deployment_quality: int = Body(..., ge=1, le=5),
    ci_cd_compliance: int = Body(..., ge=1, le=5),
    monitoring_awareness: int = Body(..., ge=1, le=5),
    incident_response: int = Body(..., ge=1, le=5),
    comments: Optional[str] = Body(None),
    user: dict = Depends(get_current_user),
):
    """
    Add DevOps Engineer feedback (structured 1-5 ratings).

    **Required Permission:** SUBMIT_DEVOPS_FEEDBACK (DEVOPS role only)
    """
    from core.permissions import get_user_permissions
    user_permissions = get_user_permissions(user.get('role', '').upper(), user.get('is_admin', False))
    if Permission.SUBMIT_DEVOPS_FEEDBACK not in user_permissions:
        raise HTTPException(status_code=403, detail="Only DevOps role can submit DevOps feedback")
    
    # Authorization: verify user can view the target developer's performance
    service = PerformanceService()
    developer_id, _ = await _resolve_evaluatable_developer(performance_id, service)
    await verify_can_view_user_tasks(user, developer_id)
    
    try:
        feedback = {
            "criterion_1": deployment_quality,
            "criterion_2": ci_cd_compliance,
            "criterion_3": monitoring_awareness,
            "criterion_4": incident_response,
            "comments": comments
        }
        return await service.add_role_feedback(performance_id, "devops", feedback)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.post("/feedback/{performance_id}/ceo", response_model=DeveloperPerformance)
async def add_ceo_feedback(
    performance_id: str,
    business_impact: int = Body(..., ge=1, le=5),
    innovation: int = Body(..., ge=1, le=5),
    company_alignment: int = Body(..., ge=1, le=5),
    leadership_potential: int = Body(..., ge=1, le=5),
    comments: Optional[str] = Body(None),
    user: dict = Depends(get_current_user),
):
    """
    Add CEO feedback (structured 1-5 ratings).

    **Required Permission:** SUBMIT_CEO_FEEDBACK (CEO role only)
    """
    from core.permissions import get_user_permissions
    user_permissions = get_user_permissions(user.get('role', '').upper(), user.get('is_admin', False))
    if Permission.SUBMIT_CEO_FEEDBACK not in user_permissions:
        raise HTTPException(status_code=403, detail="Only CEO role can submit CEO feedback")
    
    # Authorization: verify user can view the target developer's performance
    service = PerformanceService()
    developer_id, _ = await _resolve_evaluatable_developer(performance_id, service)
    await verify_can_view_user_tasks(user, developer_id)
    
    try:
        feedback = {
            "criterion_1": business_impact,
            "criterion_2": innovation,
            "criterion_3": company_alignment,
            "criterion_4": leadership_potential,
            "comments": comments
        }
        return await service.add_role_feedback(performance_id, "ceo", feedback)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.post("/feedback/{performance_id}/hr", response_model=DeveloperPerformance)
async def add_hr_feedback(
    performance_id: str,
    collaboration: int = Body(..., ge=1, le=5),
    professionalism: int = Body(..., ge=1, le=5),
    communication_skills: int = Body(..., ge=1, le=5),
    cultural_fit: int = Body(..., ge=1, le=5),
    comments: Optional[str] = Body(None),
    user: dict = Depends(get_current_user),
):
    """
    Add HR feedback (structured 1-5 ratings).

    **Required Permission:** SUBMIT_HR_FEEDBACK (HR role only)
    """
    from core.permissions import get_user_permissions
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False),
        user.get('designation')
    )
    if (
        Permission.SUBMIT_HR_FEEDBACK not in user_permissions
        and Permission.SUBMIT_HR_PERFORMANCE_ASSESSMENT not in user_permissions
    ):
        raise HTTPException(status_code=403, detail="Only authorized HR role can submit HR feedback")
    
    # Verify performance evaluation exists
    service = PerformanceService()
    developer_id, _ = await _resolve_evaluatable_developer(performance_id, service)
    
    try:
        feedback = {
            "criterion_1": collaboration,
            "criterion_2": professionalism,
            "criterion_3": communication_skills,
            "criterion_4": cultural_fit,
            "comments": comments
        }
        return await service.add_role_feedback(performance_id, "hr", feedback)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.get("/assessment/hr/{performance_id}", response_model=Optional[HRAssessment])
async def get_hr_assessment(
    performance_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Get HR assessment record for a developer's evaluation (draft or submitted).
    Returns null with 200 OK if no HR assessment has been created yet for this developer.
    Required Permission: VIEW_HR_PERFORMANCE_ASSESSMENT or VIEW_PERFORMANCE_OUTCOMES
    """
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False),
        user.get('designation')
    )
    if (
        Permission.VIEW_HR_PERFORMANCE_ASSESSMENT not in user_permissions
        and Permission.VIEW_PERFORMANCE_OUTCOMES not in user_permissions
        and not user.get('is_admin', False)
    ):
        raise HTTPException(status_code=403, detail="Insufficient permissions to view HR performance assessment")

    hr_service = HRPerformanceService()
    assessment = await hr_service.assessment_repo.get_by_performance_id(performance_id)
    if not assessment:
        return None
    return assessment


@router.post("/assessment/hr/{performance_id}")
async def save_hr_assessment_draft(
    performance_id: str,
    data: HRAssessmentCreate,
    user: dict = Depends(get_current_user),
):
    """
    Save HR assessment draft without affecting the final evaluation score.
    Required Permission: CREATE_HR_PERFORMANCE_ASSESSMENT or SUBMIT_HR_PERFORMANCE_ASSESSMENT
    """
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False),
        user.get('designation')
    )
    if (
        Permission.CREATE_HR_PERFORMANCE_ASSESSMENT not in user_permissions
        and Permission.SUBMIT_HR_PERFORMANCE_ASSESSMENT not in user_permissions
        and not user.get('is_admin', False)
    ):
        raise HTTPException(status_code=403, detail="Insufficient permissions to create HR assessment draft")

    hr_service = HRPerformanceService()
    try:
        return await hr_service.save_hr_assessment_draft(performance_id, data, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save HR assessment draft: {e}")


@router.post("/assessment/hr/{performance_id}/submit", response_model=DeveloperPerformance)
async def submit_hr_assessment(
    performance_id: str,
    data: HRAssessmentCreate,
    user: dict = Depends(get_current_user),
):
    """
    Submit finalized HR performance assessment with enterprise rubric.
    Enforces documented evidence requirement for negative ratings (1 or 2).
    Recalculates human component and the overall 90% AI + 10% Human final score.
    Required Permission: SUBMIT_HR_PERFORMANCE_ASSESSMENT
    """
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False),
        user.get('designation')
    )
    if (
        Permission.SUBMIT_HR_PERFORMANCE_ASSESSMENT not in user_permissions
        and not user.get('is_admin', False)
    ):
        raise HTTPException(status_code=403, detail="Insufficient permissions to submit HR performance assessment")

    hr_service = HRPerformanceService()
    try:
        return await hr_service.submit_hr_assessment(performance_id, data, user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit HR assessment: {e}")


@router.get("/assessments/{performance_id}/completeness", response_model=HumanEvaluationCompleteness)
async def check_human_evaluation_completeness(
    performance_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Review completeness of human evaluations across configured roles.
    Required Permission: REVIEW_HUMAN_EVALUATION_COMPLETENESS or VIEW_PERFORMANCE_OUTCOMES
    """
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False),
        user.get('designation')
    )
    if (
        Permission.REVIEW_HUMAN_EVALUATION_COMPLETENESS not in user_permissions
        and Permission.VIEW_PERFORMANCE_OUTCOMES not in user_permissions
        and not user.get('is_admin', False)
    ):
        raise HTTPException(status_code=403, detail="Insufficient permissions to review evaluation completeness")

    hr_service = HRPerformanceService()
    try:
        return await hr_service.check_human_evaluation_completeness(performance_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check evaluation completeness: {e}")


@router.get("/policy")
async def get_human_evaluation_policy(
    user: dict = Depends(get_current_user),
):
    """
    Get active human evaluation policy defining weights across human roles.
    """
    hr_service = HRPerformanceService()
    return await hr_service.get_or_create_policy()


@router.post("/policy", response_model=HumanEvaluationPolicy)
async def configure_human_evaluation_policy(
    role_weights: Dict[str, float] = Body(..., description="Map of role name to weight, summing to 1.0"),
    notes: Optional[str] = Body(None, description="Reason or notes for policy change"),
    user: dict = Depends(get_current_user),
):
    """
    Configure human evaluation role weights for the 10% human component.
    Preserves 90% AI + 10% Human model.
    Required Permission: MANAGE_EVALUATION_POLICY (CEO or ADMIN)
    """
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False),
        user.get('designation')
    )
    if (
        Permission.MANAGE_EVALUATION_POLICY not in user_permissions
        and not user.get('is_admin', False)
    ):
        raise HTTPException(status_code=403, detail="Only CEO or ADMIN can configure evaluation policies")

    hr_service = HRPerformanceService()
    try:
        configured_by = user.get("employee_id", user.get("id", "admin"))
        return await hr_service.configure_policy(role_weights, configured_by=configured_by, notes=notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to configure policy: {e}")


@router.get("/policy/history")
async def get_human_evaluation_policy_history(
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    """
    Get version history of human evaluation policies.
    """
    hr_service = HRPerformanceService()
    return await hr_service.policy_repo.get_policy_history(limit)


@router.get("/team/{project_id}/{period_label}")
async def get_team_performance(
    project_id: str,
    period_label: str,
    user: dict = Depends(get_current_user),
):
    """
    Get performance summary for all developers in a project/period.
    
    Special values:
    - project_id="all" - Get from all projects
    - period_label="current" - Get latest period
    
    Perfect for team dashboards and comparative analysis.
    """
    # Authorization: verify user has appropriate access
    user_role = user.get('role', '').upper()
    if user_role == 'DEVELOPER':
        raise HTTPException(
            status_code=403,
            detail="Developers cannot view team performance data"
        )

    try:
        service = PerformanceService()
        
        # Handle special case: "all" project and "current" period
        # Get latest evaluations for all developers
        if project_id == "all" and period_label == "current":
            from repositories.performance_repository import PerformanceRepository
            repo = PerformanceRepository()
            
            # Authorization: filter by accessible projects for non-admin users
            accessible_projects = await get_accessible_project_ids(user)
            
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
                
                # Filter by accessible projects for non-admin users
                if not has_org_access(user):
                    if latest.get('project_id') not in accessible_projects:
                        continue
                
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
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")


@router.get("/dashboard/{developer_id}")
async def get_developer_dashboard(
    developer_id: str,
    periods: int = 6,
    user: dict = Depends(get_current_user),
):
    """
    Complete developer dashboard data - matches frontend DashboardData interface.
    
    Scope enforcement:
    - DEVELOPER: own dashboard only
    - LEAD/PM/QA/DEVOPS: authorized scope
    - HR/CEO: organization-wide
    """
    # Scope enforcement: DEVELOPER can only view own dashboard
    user_role = user.get('role', '').upper()
    user_id = user.get('employee_id', '')
    if user_role == 'DEVELOPER' and developer_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Developers can only view their own performance dashboard"
        )

    # Protect executive and administrative non-evaluatee roles (CEO, HR)
    try:
        from repositories.user_repository import UserRepository
        user_repo = UserRepository()
        target_user = await user_repo.find_by_employee_id(developer_id)
        if target_user:
            target_role = target_user.get("role", "").upper()
            if target_role == "CEO":
                raise HTTPException(
                    status_code=400,
                    detail=f"Employee {developer_id} has the CEO role. The CEO is an executive and is not evaluated under the developer performance evaluation framework."
                )
            if target_role == "HR":
                raise HTTPException(
                    status_code=400,
                    detail=f"Employee {developer_id} has the HR role. HR personnel are evaluators and are not evaluated under the developer performance evaluation framework."
                )
    except HTTPException:
        raise
    except Exception:
        pass

    try:
        service = PerformanceService()
        
        # Get latest performance
        current = await service.get_developer_performance(developer_id)
        
        if not current:
            return {
                "current_performance": None,
                "historical_trend": [],
                "peer_comparison": None,
                "hr_assessment": None,
                "is_hr_view": user_role == 'HR',
                "developer_id": developer_id,
            }
        
        # Get trend
        trend_data = await service.get_performance_trend(developer_id, periods)
        
        # Check if HR user: return sanitized HR-safe dashboard view
        if user_role == 'HR':
            hr_assessment_dict = None
            if current.hr_assessment:
                hr_assessment_dict = (
                    current.hr_assessment.model_dump()
                    if hasattr(current.hr_assessment, "model_dump")
                    else current.hr_assessment
                )
            
            hr_current_performance = {
                "developer_id": current.developer_id,
                "developer_name": current.developer_name,
                "period": current.period_label,
                "overall_score": current.final_score,
                "grade": current.grade,
                "rating": PerformanceOutcomeHR._score_to_rating(current.final_score),
                "contribution_credit": None,  # Suppressed for HR (contains LOC, commits, PR metrics)
                "ai_evaluation": {
                    "overall_score": current.ai_evaluation.score if current.ai_evaluation else None,
                    "confidence_score": (
                        85.0 if current.ai_evaluation and current.ai_evaluation.confidence == "high"
                        else 70.0 if current.ai_evaluation and current.ai_evaluation.confidence == "medium"
                        else 50.0
                    ),
                    "evaluation_summary": (current.ai_evaluation.reasoning if current.ai_evaluation else "") or "Performance evaluation summary",
                    "recommendations": current.ai_evaluation.recommendations if current.ai_evaluation else [],
                    "dimension_scores": {},  # Technical scores suppressed
                    "strengths": [],
                    "weaknesses": []
                },
                "human_evaluation_summary": {
                    "average_score": current.role_evaluation.average_score if current.role_evaluation else None,
                    "roles_evaluated": [
                        r for r in ("pm", "lead", "qa", "devops", "ceo", "hr")
                        if getattr(current.role_evaluation, r, None) is not None
                    ] if current.role_evaluation else [],
                },
                "last_evaluated": current.created_at.isoformat() if current.created_at else None,
                "evaluation_count": len(trend_data) if trend_data else 1
            }
            
            historical_trend = []
            if trend_data:
                for item in trend_data:
                    historical_trend.append({
                        "period": item.get('period_label', ''),
                        "score": item.get('final_score', 0),
                        "grade": item.get('grade', 'N/A')
                    })
            
            return HRDashboardPerformanceView(
                current_performance=hr_current_performance,
                historical_trend=historical_trend,
                peer_comparison=None,
                hr_assessment=hr_assessment_dict,
                is_hr_view=True
            ).model_dump()

        # Transform to frontend format for Engineering / Leadership
        current_performance = {
            "developer_id": current.developer_id,
            "developer_name": current.developer_name,
            "period": current.period_label,
            "overall_score": current.final_score,
            "grade": current.grade,
            "contribution_credit": (
                current.contribution_credit.model_dump()
                if current.contribution_credit
                else None
            ),
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
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")
