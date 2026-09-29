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

router = APIRouter()
engine = RecommendationEngine()


@router.get("/user/{user_id}")
async def get_user_recommendations(
    user_id: str,
    status: Optional[str] = Query("pending", description="Filter by status"),
    current_user: dict = Depends(get_current_user),
):
    """Get all recommendations for a specific user."""
    try:
        recs = await engine.get_recommendations_for_user(user_id, status)
        return {
            "user_id": user_id,
            "status": status,
            "recommendations": recs,
            "count": len(recs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        return {
            "role": role,
            "project_id": project_id,
            "status": status,
            "recommendations": recs,
            "count": len(recs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{entity_type}/{entity_id}")
async def get_entity_recommendations(
    entity_type: str,
    entity_id: str,
    status: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Get all recommendations for a specific entity (PR, task, etc.)."""
    try:
        recs = await engine.get_recommendations_for_entity(entity_type, entity_id, status)
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "status": status,
            "recommendations": recs,
            "count": len(recs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{recommendation_id}/accept")
async def accept_recommendation(
    recommendation_id: str,
    notes: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Accept a recommendation and optionally add implementation notes."""
    try:
        user_id = current_user["employee_id"]
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{recommendation_id}/reject")
async def reject_recommendation(
    recommendation_id: str,
    reason: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Reject a recommendation with optional reason."""
    try:
        user_id = current_user["employee_id"]
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{recommendation_id}/implement")
async def mark_recommendation_implemented(
    recommendation_id: str,
    pr_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Mark a recommendation as implemented, optionally linking to a PR."""
    try:
        user_id = current_user["employee_id"]
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{recommendation_id}")
async def get_recommendation(
    recommendation_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a specific recommendation by ID."""
    try:
        from repositories.recommendation_repository import RecommendationRepository
        repo = RecommendationRepository()
        
        rec = await repo.find_by_id(recommendation_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        return rec
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
