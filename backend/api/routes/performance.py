"""
Developer Performance API Routes
Complete REST API for AI-driven performance evaluation system.
Protected with RBAC permissions.
"""

from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Union, Dict
from domain.services.performance_service import PerformanceService, PeriodScoringPending
from domain.models.developer_performance import (
    DeveloperPerformance,
)
from domain.models.hr_performance import (
    HRAssessment,
    HRAssessmentCreate,
    HumanEvaluationPolicy,
    HumanEvaluationCompleteness,
)
from domain.schemas.hr_views import PerformanceOutcomeHR
from domain.models.performance_evidence import EvidencePreview, EvidencePreviewRequest
from domain.models.performance_claims import (
    ClaimReview, ClaimReviewRequest, InterpretationDetails, InterpretationRun, ReviewerAssignmentRequest,
)
from domain.models.performance_human import HumanPolicyDraftRequest, HumanReviewerAssignmentRequest, HumanReviewRequest, HumanReviewRevisionRequest
from core.dependencies import get_current_user
from core.permissions import Permission, get_user_permissions

router = APIRouter()


from domain.models.performance_lifecycle import (
    ApproverAssignmentRequest, AssessmentActionRequest, AssessmentAppealRequest, AssessmentCreateRequest, PolicyReviewRequest,
)
from domain.services.performance_access_service import ExportRequest


@router.post("/assessments", status_code=201)
async def create_scoped_assessment(body: AssessmentCreateRequest, user: dict = Depends(get_current_user)):
    from domain.services.performance_lifecycle_service import AssessmentLifecycleService
    return await AssessmentLifecycleService().create(body, user)


@router.get("/assessments/{assessment_id}/history")
async def get_scoped_assessment_history(assessment_id: str, user: dict = Depends(get_current_user)):
    from domain.services.performance_lifecycle_service import AssessmentLifecycleService
    return await AssessmentLifecycleService().get(assessment_id, user)


@router.get("/assessments/{assessment_id}/revisions/{revision}/replay")
async def replay_scoped_assessment(assessment_id: str, revision: int, user: dict = Depends(get_current_user)):
    from domain.services.performance_lifecycle_service import AssessmentLifecycleService
    return await AssessmentLifecycleService().replay(assessment_id, revision, user)


@router.post("/assessments/{assessment_id}/actions", status_code=201)
async def transition_scoped_assessment(assessment_id: str, body: AssessmentActionRequest, user: dict = Depends(get_current_user)):
    from domain.services.performance_lifecycle_service import AssessmentLifecycleService
    return await AssessmentLifecycleService().transition(assessment_id, body, user)


@router.post("/assessments/{assessment_id}/appeals", status_code=201)
async def appeal_scoped_assessment(assessment_id: str, body: AssessmentAppealRequest, user: dict = Depends(get_current_user)):
    from domain.services.performance_lifecycle_service import AssessmentLifecycleService
    return await AssessmentLifecycleService().appeal(assessment_id, body, user)


@router.post("/assessments/{assessment_id}/approvers", status_code=201)
async def assign_scoped_approver(assessment_id: str, body: ApproverAssignmentRequest, user: dict = Depends(get_current_user)):
    from domain.services.performance_lifecycle_service import AssessmentLifecycleService
    return await AssessmentLifecycleService().assign_approver(assessment_id, body, user)


@router.post("/human/policy-drafts/{draft_id}/reviews", status_code=201)
async def review_scoped_policy(draft_id: str, body: PolicyReviewRequest, user: dict = Depends(get_current_user)):
    from domain.services.performance_lifecycle_service import AssessmentLifecycleService
    return await AssessmentLifecycleService().review_policy(draft_id, body, user)


@router.get("/human/policy-drafts/{draft_id}")
async def inspect_scoped_policy_draft(draft_id: str, user: dict = Depends(get_current_user)):
    from domain.services.performance_lifecycle_service import AssessmentLifecycleService
    return await AssessmentLifecycleService().policy_detail(draft_id, user)


@router.post("/developer/{employee_id}/export")
async def export_scoped_summary(employee_id: str, body: ExportRequest, user: dict = Depends(get_current_user)):
    from domain.services.performance_access_service import PerformanceAccessService
    return await PerformanceAccessService().export(employee_id, body, user)


@router.get("/developer/{employee_id}/shadow")
async def inspect_scoped_shadow(employee_id: str, user: dict = Depends(get_current_user)):
    from domain.services.performance_access_service import PerformanceAccessService
    return await PerformanceAccessService().shadow(employee_id, user)


def pending_human_response(ceo=False):
    from domain.services.performance_human_service import HumanScoringPending
    pending = HumanScoringPending(ceo)
    return JSONResponse(status_code=409, content={"detail": str(pending), "status": pending.status,
        "human_review_endpoint": "/api/performance/human-reviewers"})


@router.post("/human-reviewers", status_code=201)
async def assign_human_reviewer(body: HumanReviewerAssignmentRequest, user: dict = Depends(get_current_user)):
    from domain.services.performance_human_service import HumanFeedbackService
    return await HumanFeedbackService().assign(body, user)


@router.post("/human-reviews/{assignment_id}", status_code=201)
async def submit_assigned_human_review(assignment_id: str, body: HumanReviewRequest, user: dict = Depends(get_current_user)):
    from domain.services.performance_human_service import HumanFeedbackService
    return await HumanFeedbackService().submit(assignment_id, body, user)


@router.post("/human-reviews/{assignment_id}/hr", status_code=201)
async def submit_assigned_hr_review(assignment_id: str, body: HumanReviewRequest, user: dict = Depends(get_current_user)):
    from domain.services.performance_human_service import HumanFeedbackService
    return await HumanFeedbackService().submit(assignment_id, body, user, required_role="HR")


@router.get("/human-reviews/{assignment_id}")
async def get_own_human_review(assignment_id: str, user: dict = Depends(get_current_user)):
    from domain.services.performance_human_service import HumanFeedbackService
    return await HumanFeedbackService().get_review(assignment_id, user)


@router.post("/human-reviews/{assignment_id}/revisions", status_code=201)
async def revise_own_human_review(assignment_id: str, body: HumanReviewRevisionRequest, user: dict = Depends(get_current_user)):
    from domain.services.performance_human_service import HumanFeedbackService
    return await HumanFeedbackService().revise(assignment_id, body, user)


@router.get("/human/{run_id}/completeness")
async def get_scoped_human_completeness(run_id: str, user: dict = Depends(get_current_user)):
    from domain.services.performance_human_service import HumanFeedbackService
    return await HumanFeedbackService().summary(run_id, user)


@router.post("/human/policy-drafts", status_code=201)
async def propose_human_policy(body: HumanPolicyDraftRequest, user: dict = Depends(get_current_user)):
    from domain.services.performance_human_service import HumanFeedbackService
    return await HumanFeedbackService().propose_policy(body, user)


def pending_period_response():
    detail = PeriodScoringPending().detail
    return JSONResponse(status_code=409, content={"detail": detail["message"], "status": detail["status"],
        "interpretation_endpoint": detail["interpretation_endpoint"]})


@router.post("/evidence/preview", response_model=EvidencePreview)
async def preview_performance_evidence(body: EvidencePreviewRequest, user: dict = Depends(get_current_user)):
    """Inspect scoped, redacted evidence without creating an employee rating."""
    return await PerformanceService.inspect_evidence(body, user)


@router.post("/interpretations", response_model=InterpretationRun, status_code=201)
async def create_performance_interpretation(body: EvidencePreviewRequest, user: dict = Depends(get_current_user)):
    from domain.services.performance_claim_service import PerformanceClaimService
    return await PerformanceClaimService().create(body, user)


@router.get("/interpretations/{run_id}", response_model=InterpretationDetails)
async def get_performance_interpretation(run_id: str, user: dict = Depends(get_current_user)):
    from domain.services.performance_claim_service import PerformanceClaimService
    return await PerformanceClaimService().get(run_id, user)


@router.post("/claim-reviewers", status_code=201)
async def assign_performance_claim_reviewer(body: ReviewerAssignmentRequest, user: dict = Depends(get_current_user)):
    from domain.services.performance_claim_service import PerformanceClaimService
    return await PerformanceClaimService().assign_reviewer(body, user)


@router.post("/interpretations/{run_id}/claims/{claim_id}/reviews", response_model=ClaimReview, status_code=201)
async def review_performance_claim(run_id: str, claim_id: str, body: ClaimReviewRequest,
                                   user: dict = Depends(get_current_user)):
    from domain.services.performance_claim_service import PerformanceClaimService
    return await PerformanceClaimService().review(run_id, claim_id, body, user)


class CreditAppealRequest(BaseModel):
    reason: str = Field(..., min_length=20, max_length=2000)
    evidence: List[str] = Field(default_factory=list, max_length=20)


@router.post("/credit/{performance_id}/appeal")
async def appeal_credit(
    performance_id: str,
    body: CreditAppealRequest,
    user: dict = Depends(get_current_user),
):
    """Append an immutable scoped appeal without mutating the historical assessment."""
    from domain.services.performance_access_service import PerformanceAccessService
    return await PerformanceAccessService().appeal_legacy(performance_id, body.model_dump(), user)


@router.post("/evaluate/bulk", status_code=202, deprecated=True)
async def bulk_evaluate_developers(
    developer_ids: List[str] = Body(..., description="List of developer IDs to evaluate"),
    period: str = Body(..., description="Evaluation period (e.g., '2026-Q3')"),
    project_id: str = Body("default-project", description="Project ID"),
    period_type: str = Body("quarter", description="Period type: sprint, month, quarter"),
    user: dict = Depends(get_current_user)
):
    """Deprecated numeric bulk workflow: returns POLICY_PENDING without writing scores."""
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

    return pending_period_response()


@router.post("/evaluate", response_model=DeveloperPerformance, status_code=201, deprecated=True)
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
    """Deprecated numeric workflow. Use scoped advisory interpretations while policy is pending."""
    # Check permission
    from core.permissions import get_user_permissions
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False)
    )
    
    if Permission.TRIGGER_AI_EVALUATION not in user_permissions:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Team Leads run individual evaluations."
        )
    # CR-004: Leads evaluate only their team members (CR-015: the CEO no longer runs them).
    from core.authorization import verify_can_view_person_evaluations
    await verify_can_view_person_evaluations(user, developer_id)

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
    
    return pending_period_response()


@router.get("/developer/{developer_id}", response_model=Union[DeveloperPerformance, PerformanceOutcomeHR])
async def get_developer_performance(
    developer_id: str,
    period_label: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Current-account scoped historical view; HR/CEO receive allowlisted summaries."""
    from domain.services.performance_access_service import PerformanceAccessService
    return await PerformanceAccessService().detail(developer_id, user, period_label)


@router.get("/developer/{developer_id}/trend")
async def get_performance_trend(
    developer_id: str,
    limit: int = 10,
    user: dict = Depends(get_current_user),
):
    """Preserve historical numbers without claiming verified comparable trends."""
    from domain.services.performance_access_service import PerformanceAccessService
    return await PerformanceAccessService().trend(developer_id, user, limit)



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


@router.post("/feedback/{performance_id}/pm", response_model=DeveloperPerformance, deprecated=True)
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
    
    return pending_human_response(ceo=False)


@router.post("/feedback/{performance_id}/lead", response_model=DeveloperPerformance, deprecated=True)
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
    
    return pending_human_response(ceo=False)


@router.post("/feedback/{performance_id}/qa", response_model=DeveloperPerformance, deprecated=True)
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
    
    return pending_human_response(ceo=False)


@router.post("/feedback/{performance_id}/devops", response_model=DeveloperPerformance, deprecated=True)
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
    Retired DevOps Engineer numeric feedback: returns 409; use scoped assigned human reviews.

    **Required Permission:** SUBMIT_DEVOPS_FEEDBACK (DEVOPS role only)
    """
    from core.permissions import get_user_permissions
    user_permissions = get_user_permissions(user.get('role', '').upper(), user.get('is_admin', False))
    if Permission.SUBMIT_DEVOPS_FEEDBACK not in user_permissions:
        raise HTTPException(status_code=403, detail="Only DevOps role can submit DevOps feedback")
    
    return pending_human_response(ceo=False)


@router.post("/feedback/{performance_id}/ceo", response_model=DeveloperPerformance, deprecated=True)
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
    Retired CEO numeric feedback: returns 409; use scoped assigned human reviews.

    **Required Permission:** SUBMIT_CEO_FEEDBACK (CEO role only)
    """
    from core.permissions import get_user_permissions
    user_permissions = get_user_permissions(user.get('role', '').upper(), user.get('is_admin', False))
    if Permission.SUBMIT_CEO_FEEDBACK not in user_permissions:
        raise HTTPException(status_code=403, detail="Only CEO role can submit CEO feedback")
    
    return pending_human_response(ceo=True)


@router.post("/feedback/{performance_id}/hr", response_model=DeveloperPerformance, deprecated=True)
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
    Retired HR numeric feedback: returns 409; use scoped assigned human reviews.

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
    
    return pending_human_response(ceo=False)


@router.get("/assessment/hr/{performance_id}", response_model=Optional[HRAssessment])
async def get_hr_assessment(
    performance_id: str,
    user: dict = Depends(get_current_user),
):
    """Only current HR authors may retrieve their scoped confidential case detail."""
    from domain.services.performance_access_service import PerformanceAccessService
    return await PerformanceAccessService().hr_case(performance_id, user)


@router.post("/assessment/hr/{performance_id}", deprecated=True)
async def save_hr_assessment_draft(
    performance_id: str,
    data: HRAssessmentCreate,
    user: dict = Depends(get_current_user),
):
    """
    Retired mutable HR draft intake: returns 409; use scoped assigned human reviews.
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
        # CR-008: no separate admin bypass; admins hold only ADMIN_PERMISSIONS.
    ):
        raise HTTPException(status_code=403, detail="Insufficient permissions to create HR assessment draft")

    return pending_human_response()


@router.post("/assessment/hr/{performance_id}/submit", response_model=DeveloperPerformance, deprecated=True)
async def submit_hr_assessment(
    performance_id: str,
    data: HRAssessmentCreate,
    user: dict = Depends(get_current_user),
):
    """
    Retired legacy HR numerical submission: returns 409 without changing historical scores.
    Use assigned HR observations; approved calibration and validated evidence are required for H.
    Required Permission: SUBMIT_HR_PERFORMANCE_ASSESSMENT
    """
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False),
        user.get('designation')
    )
    if (
        Permission.SUBMIT_HR_PERFORMANCE_ASSESSMENT not in user_permissions
        # CR-008: no separate admin bypass; admins hold only ADMIN_PERMISSIONS.
    ):
        raise HTTPException(status_code=403, detail="Insufficient permissions to submit HR performance assessment")

    return pending_human_response()


@router.get("/assessments/{performance_id}/completeness", response_model=HumanEvaluationCompleteness)
async def check_human_evaluation_completeness(
    performance_id: str,
    user: dict = Depends(get_current_user),
):
    """Scoped historical completeness; legacy presence cannot establish canonical H."""
    from domain.services.performance_access_service import PerformanceAccessService
    return await PerformanceAccessService().completeness(performance_id, user)


@router.get("/policy")
async def get_human_evaluation_policy(
    user: dict = Depends(get_current_user),
):
    """
    Get active human evaluation policy defining weights across human roles.
    """
    from domain.services.performance_access_service import PerformanceAccessService
    history = await PerformanceAccessService().policy_history(user, 1)
    return {"status": "POLICY_PENDING", "is_active": False, "role_weights": {}, "ceo_weight": 0,
            "legacy_policy": history[0] if history else None}


@router.post("/policy", response_model=HumanEvaluationPolicy, deprecated=True)
async def configure_human_evaluation_policy(
    role_weights: Dict[str, float] = Body(..., description="Map of role name to weight, summing to 1.0"),
    notes: Optional[str] = Body(None, description="Reason or notes for policy change"),
    user: dict = Depends(get_current_user),
):
    """
    Retired legacy activation: returns 409. Scoped policy proposals remain inactive drafts.
    Required Permission: MANAGE_EVALUATION_POLICY (CEO)
    """
    user_permissions = get_user_permissions(
        user.get('role', '').upper(),
        user.get('is_admin', False),
        user.get('designation')
    )
    if (
        Permission.MANAGE_EVALUATION_POLICY not in user_permissions
        # CR-008: no separate admin bypass; admins hold only ADMIN_PERMISSIONS.
    ):
        raise HTTPException(status_code=403, detail="Only the CEO can configure evaluation policies")

    return pending_human_response()


@router.get("/policy/history")
async def get_human_evaluation_policy_history(
    limit: int = 20,
    user: dict = Depends(get_current_user),
):
    """
    Get version history of human evaluation policies.
    """
    from domain.services.performance_access_service import PerformanceAccessService
    return await PerformanceAccessService().policy_history(user, limit)


@router.get("/team/{project_id}/{period_label}")
async def get_team_performance(
    project_id: str,
    period_label: str,
    user: dict = Depends(get_current_user),
):
    """Scoped historical summaries; do not rank unverifiable cross-role values."""
    from domain.services.performance_access_service import PerformanceAccessService
    return await PerformanceAccessService().team(project_id, period_label, user)


@router.get("/dashboard/{developer_id}")
async def get_developer_dashboard(
    developer_id: str,
    periods: int = 6,
    user: dict = Depends(get_current_user),
):
    """Preserve dashboard fields with scoped redaction and legacy comparison caveats."""
    from domain.services.performance_access_service import PerformanceAccessService
    return await PerformanceAccessService().dashboard(developer_id, user, periods)
