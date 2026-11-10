"""
PR risk model endpoints (see intelligence/risk_model/RISK_MODEL.md).

    POST /api/risk-model/projects/{project_id}/train   start training (background)
    GET  /api/risk-model/projects/{project_id}         status + held-out evaluation
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from core.authorization import verify_project_access
from core.config import settings
from core.dependencies import get_current_user, require_roles
from domain.services.risk_model_service import RiskModelService

router = APIRouter()


@router.post("/projects/{project_id}/train", status_code=202)
async def train_risk_model(
    project_id: str,
    background: BackgroundTasks,
    user: dict = Depends(require_roles("LEAD", "PM")),
):
    """Clone the project's configured repository, label its history with SZZ,
    and train the risk model. Runs in the background; poll the GET endpoint."""
    await verify_project_access(user, project_id, require_write=True)
    service = RiskModelService()
    if not await service.configs.find_one({"project_id": project_id}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="GitHub project configuration not found")
    if not await service.mark_training(project_id, user.get("id") or user.get("user_id")):
        raise HTTPException(status_code=409, detail="Training already in progress")
    background.add_task(service.train, project_id, settings.GITHUB_TOKEN)
    return {"project_id": project_id, "status": "training"}


@router.get("/projects/{project_id}")
async def get_risk_model(project_id: str, user: dict = Depends(get_current_user)):
    """Training status, whether the model is used for scoring, and how it
    performed on the held-out (most recent labelled) period."""
    await verify_project_access(user, project_id)
    doc = await RiskModelService().summary(project_id)
    if not doc:
        return {"project_id": project_id, "status": "not_trained", "usable": False,
                "scoring_method": "rules"}
    doc["scoring_method"] = "ml" if doc.get("usable") else "rules"
    return doc
