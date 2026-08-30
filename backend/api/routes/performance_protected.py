"""
Helper script to add permission checks to all feedback endpoints.
This will be integrated into performance.py
"""

# Template for feedback endpoints with permission checks
FEEDBACK_ENDPOINTS = """
@router.post("/feedback/{performance_id}/lead", response_model=DeveloperPerformance)
async def add_lead_feedback(
    performance_id: str,
    technical_skill: int = Body(..., ge=1, le=5),
    code_quality: int = Body(..., ge=1, le=5),
    mentoring: int = Body(..., ge=1, le=5),
    technical_ownership: int = Body(..., ge=1, le=5),
    comments: Optional[str] = Body(None),
    user: dict = Depends(get_current_user)
):
    # Check permission - LEAD role only
    from core.permissions import get_user_permissions, Permission
    user_permissions = get_user_permissions(user.get('role', '').upper(), user.get('is_admin', False))
    if Permission.SUBMIT_LEAD_FEEDBACK not in user_permissions:
        raise HTTPException(status_code=403, detail="Only LEAD role can submit lead feedback")
    
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
    comments: Optional[str] = Body(None),
    user: dict = Depends(get_current_user)
):
    # Check permission - QA role only
    from core.permissions import get_user_permissions, Permission
    user_permissions = get_user_permissions(user.get('role', '').upper(), user.get('is_admin', False))
    if Permission.SUBMIT_QA_FEEDBACK not in user_permissions:
        raise HTTPException(status_code=403, detail="Only QA role can submit QA feedback")
    
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
    comments: Optional[str] = Body(None),
    user: dict = Depends(get_current_user)
):
    # Check permission - DEVOPS role only
    from core.permissions import get_user_permissions, Permission
    user_permissions = get_user_permissions(user.get('role', '').upper(), user.get('is_admin', False))
    if Permission.SUBMIT_DEVOPS_FEEDBACK not in user_permissions:
        raise HTTPException(status_code=403, detail="Only DEVOPS role can submit DevOps feedback")
    
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
    comments: Optional[str] = Body(None),
    user: dict = Depends(get_current_user)
):
    # Check permission - CEO role only
    from core.permissions import get_user_permissions, Permission
    user_permissions = get_user_permissions(user.get('role', '').upper(), user.get('is_admin', False))
    if Permission.SUBMIT_CEO_FEEDBACK not in user_permissions:
        raise HTTPException(status_code=403, detail="Only CEO role can submit CEO feedback")
    
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
    comments: Optional[str] = Body(None),
    user: dict = Depends(get_current_user)
):
    # Check permission - HR role only
    from core.permissions import get_user_permissions, Permission
    user_permissions = get_user_permissions(user.get('role', '').upper(), user.get('is_admin', False))
    if Permission.SUBMIT_HR_FEEDBACK not in user_permissions:
        raise HTTPException(status_code=403, detail="Only HR role can submit HR feedback")
    
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
"""

print("Feedback endpoints with permission checks ready!")
print("Copy these into performance.py to replace the existing feedback endpoints")
