"""
Recommendations API Routes.

Provides endpoints for:
- Viewing recommendations by user, entity, or role
- Accepting/rejecting recommendations
- Tracking implementation status

All endpoints require JWT authentication.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from domain.services.recommendation_engine import RecommendationEngine
from core.dependencies import get_current_user
from core.authorization import verify_can_view_user_tasks, get_accessible_project_ids, has_org_access, verify_task_access, verify_story_access, verify_project_access
import logging

router = APIRouter()
engine = RecommendationEngine()
logger = logging.getLogger(__name__)


async def _visible_algorithm_recommendations(recommendations, user, *, strict=False):
    """Keep algorithm evidence under its existing project/org read boundary."""
    from api.routes.algorithms import project_access
    visible = []
    for recommendation in recommendations:
        if recommendation.get("algorithm_analysis_run_id"):
            try:
                await project_access(user, recommendation["project_id"])
            except HTTPException as error:
                if strict or error.status_code not in {403, 404}:
                    raise
                continue
        visible.append(recommendation)
    return visible


@router.get("/user/{user_id}")
async def get_user_recommendations(
    user_id: str,
    status: Optional[str] = Query("pending", description="Filter by status"),
    current_user: dict = Depends(get_current_user),
):
    """Get all recommendations for a specific user."""
    try:
        # Authorization: verify current user can view target user's recommendations
        await verify_can_view_user_tasks(current_user, user_id)
        
        recs = await engine.get_recommendations_for_user(user_id, status)
        recs = await _visible_algorithm_recommendations(recs, current_user)
        return {
            "user_id": user_id,
            "status": status,
            "recommendations": recs,
            "count": len(recs)
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/role/{role}")
async def get_role_recommendations(
    role: str,
    project_id: Optional[str] = None,
    status: Optional[str] = Query("pending", description="Filter by status"),
    current_user: dict = Depends(get_current_user),
):
    """Get all recommendations for a specific role."""
    try:
        recs = await engine.get_recommendations_for_role(role, project_id, status)
        
        # Authorization: filter by accessible projects
        accessible = await get_accessible_project_ids(current_user)
        recs = [r for r in recs if r.get("project_id") in accessible]
        recs = await _visible_algorithm_recommendations(recs, current_user)
        
        return {
            "role": role,
            "project_id": project_id,
            "status": status,
            "recommendations": recs,
            "count": len(recs)
        }
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/entity/{entity_type}/{entity_id}")
async def get_entity_recommendations(
    entity_type: str,
    entity_id: str,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Get all recommendations for a specific entity (PR, task, etc.)."""
    # Authorization: verify user has access to this entity
    if entity_type == "task":
        await verify_task_access(current_user, entity_id)
    elif entity_type == "story":
        await verify_story_access(current_user, entity_id)
    elif entity_type == "project":
        await verify_project_access(current_user, entity_id)
    elif entity_type == "pr":
        # For PRs, verify access to the project with validation
        from repositories.pr_repository import PRRepository
        from repositories.project_repository import ProjectRepository
        
        pr = await PRRepository().find_by_id(entity_id)
        if not pr:
            raise HTTPException(status_code=404, detail="PR not found")
        
        project_id = pr.get("project_id")
        if project_id:
            # Validate PR-to-project mapping
            project = await ProjectRepository().find_by_id(project_id)
            if project:
                # Verify project access
                await verify_project_access(current_user, project_id)
            else:
                # Invalid project_id - require org access
                if not has_org_access(current_user):
                    raise HTTPException(status_code=403, detail="PR's project reference is invalid")
        else:
            # PR not linked to project - require org access
            if not has_org_access(current_user):
                raise HTTPException(status_code=403, detail="PR is not linked to a project")
    
    try:
        recs = await engine.get_recommendations_for_entity(entity_type, entity_id, status)
        recs = await _visible_algorithm_recommendations(recs, current_user, strict=True)
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "status": status,
            "recommendations": recs,
            "count": len(recs)
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{recommendation_id}/accept")
async def accept_recommendation(
    recommendation_id: str,
    notes: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Accept a recommendation and optionally add implementation notes."""
    try:
        user_id = current_user["employee_id"]
        
        # Authorization: verify user can accept this recommendation
        rec = await engine.repo.find_by_id(recommendation_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        await _visible_algorithm_recommendations([rec], current_user, strict=True)
        
        if rec.get("user_id") != user_id and not has_org_access(current_user):
            raise HTTPException(status_code=403, detail="Access denied")
        
        success = await engine.accept_recommendation(recommendation_id, user_id, notes)
        if not success:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        return {
            "recommendation_id": recommendation_id,
            "status": "accepted",
            "success": True
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{recommendation_id}/reject")
async def reject_recommendation(
    recommendation_id: str,
    reason: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Reject a recommendation with optional reason."""
    try:
        user_id = current_user["employee_id"]
        
        # Authorization: verify user can reject this recommendation
        rec = await engine.repo.find_by_id(recommendation_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        await _visible_algorithm_recommendations([rec], current_user, strict=True)
        
        if rec.get("user_id") != user_id and not has_org_access(current_user):
            raise HTTPException(status_code=403, detail="Access denied")
        
        success = await engine.reject_recommendation(recommendation_id, user_id, reason)
        if not success:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        return {
            "recommendation_id": recommendation_id,
            "status": "rejected",
            "success": True
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/{recommendation_id}/implement")
async def mark_recommendation_implemented(
    recommendation_id: str,
    pr_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Mark a recommendation as implemented, optionally linking to a PR."""
    # Authorization: verify user can implement this recommendation
    rec = await engine.repo.find_by_id(recommendation_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    await _visible_algorithm_recommendations([rec], current_user, strict=True)
    
    user_id = current_user["employee_id"]
    if rec.get("user_id") != user_id and not has_org_access(current_user):
        raise HTTPException(status_code=403, detail="Access denied")
    
    try:
        success = await engine.mark_implemented(recommendation_id, user_id, pr_id)
        if not success:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        return {
            "recommendation_id": recommendation_id,
            "status": "implemented",
            "pr_id": pr_id,
            "success": True
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{recommendation_id}")
async def get_recommendation(
    recommendation_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a specific recommendation by ID."""
    try:
        rec = await engine.repo.find_by_id(recommendation_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        await _visible_algorithm_recommendations([rec], current_user, strict=True)
        
        # Authorization: verify user has access to this recommendation
        rec_user_id = rec.get("user_id")
        if rec_user_id:
            await verify_can_view_user_tasks(current_user, rec_user_id)
        elif rec.get("project_id"):
            # If recommendation is project-scoped, verify project access
            await verify_project_access(current_user, rec["project_id"])
        
        return rec
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")
