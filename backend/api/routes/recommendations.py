"""
Recommendations API Routes.

Provides endpoints for:
- Viewing recommendations by user, entity, or role
- Accepting/rejecting recommendations
- Tracking implementation status
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from domain.services.recommendation_engine import RecommendationEngine

router = APIRouter()
engine = RecommendationEngine()


@router.get("/user/{user_id}")
async def get_user_recommendations(
    user_id: str,
    status: Optional[str] = Query("pending", description="Filter by status")
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
    status: Optional[str] = Query("pending", description="Filter by status")
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
    status: Optional[str] = None
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
    user_id: str,
    notes: Optional[str] = None
):
    """Accept a recommendation and optionally add implementation notes."""
    try:
        success = await engine.accept_recommendation(recommendation_id, user_id, notes)
        if not success:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        return {
            "recommendation_id": recommendation_id,
            "status": "accepted",
            "success": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{recommendation_id}/reject")
async def reject_recommendation(
    recommendation_id: str,
    user_id: str,
    reason: Optional[str] = None
):
    """Reject a recommendation with optional reason."""
    try:
        success = await engine.reject_recommendation(recommendation_id, user_id, reason)
        if not success:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        return {
            "recommendation_id": recommendation_id,
            "status": "rejected",
            "success": True
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{recommendation_id}/implement")
async def mark_recommendation_implemented(
    recommendation_id: str,
    user_id: str,
    pr_id: Optional[str] = None
):
    """Mark a recommendation as implemented, optionally linking to a PR."""
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{recommendation_id}")
async def get_recommendation(recommendation_id: str):
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
