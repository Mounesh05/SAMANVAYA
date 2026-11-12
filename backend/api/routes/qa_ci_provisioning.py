"""CI Integration provisioning endpoints for QA."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from core.dependencies import get_current_user, require_permission
from core.permissions import Permission
from domain.models.qa_ci_config import CIProvisionRequest
from domain.services.qa_workflow_provisioning_service import QAWorkflowProvisioningService
from domain.services.qa_service import QAService
from repositories.qa_repository import QARepository

router = APIRouter(tags=["QA CI Provisioning"])
qa_service = QAService()
qa_repo = QARepository()


@router.post("/projects/{project_id}/enable-ci", status_code=201)
async def enable_ci_integration(
    project_id: str,
    request: CIProvisionRequest,
    user: dict = Depends(require_permission(Permission.MANAGE_TEST_AUTOMATION)),
):
    """
    Enable CI integration for a project by provisioning GitHub Actions workflow.
    
    This endpoint:
    1. Validates user has access to the project
    2. Provisions GitHub Actions workflow and secrets
    3. Stores CI configuration in database
    4. Returns provisioning status and workflow URL
    
    Requires MANAGE_TEST_AUTOMATION (QA, PM, LEAD, CEO by default).
    """
    # Validate project access
    await qa_service.accessible_project(user, project_id)
    
    # Parse repository owner/name
    try:
        owner, repo = request.repository.split("/")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Repository must be in format 'owner/repo'"
        )
    
    # Provision workflow via existing service
    try:
        provisioning_service = QAWorkflowProvisioningService()
        result = await provisioning_service.provision(
            owner=owner,
            repo=repo,
            project_id=project_id,
            branch=request.branch
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Provisioning failed: {str(e)}"
        )
    
    # Store CI configuration
    now = datetime.now(timezone.utc)
    ci_config = {
        "project_id": project_id,
        "repository": request.repository,
        "branch": request.branch,
        "enabled": True,
        "provisioned_at": now.isoformat(),
        "workflow_url": result.get("workflow_url"),
    }
    await qa_repo.save_ci_config(ci_config)
    
    return {
        "project_id": project_id,
        "repository": request.repository,
        "branch": request.branch,
        "status": "provisioned",
        "workflow_url": result.get("workflow_url"),
        "provisioned_at": now.isoformat(),
        "message": f"CI integration enabled for {request.repository}"
    }


@router.get("/projects/{project_id}/ci-config")
async def get_ci_configs(
    project_id: str,
    branch: str | None = None,
    user: dict = Depends(get_current_user),
):
    """
    Get CI configuration(s) for a project.
    
    If branch is specified, returns config for that branch only.
    Otherwise returns all branch configurations as an array.
    """
    # Validate project access
    await qa_service.accessible_project(user, project_id)
    
    if branch:
        # Get single branch config
        config = await qa_repo.get_ci_config(project_id, branch)
        if not config:
            return {
                "project_id": project_id,
                "branch": branch,
                "enabled": False,
                "repository": None
            }
        return config
    else:
        # Get all branch configs
        configs = await qa_repo.get_all_ci_configs(project_id)
        return {
            "project_id": project_id,
            "configs": configs
        }


@router.delete("/projects/{project_id}/ci-config")
async def disable_ci_integration(
    project_id: str,
    branch: str,
    user: dict = Depends(require_permission(Permission.MANAGE_TEST_AUTOMATION)),
):
    """Disable CI integration for a specific branch (branch passed as query param)."""
    
    await qa_service.accessible_project(user, project_id)
    
    deleted = await qa_repo.delete_ci_config(project_id, branch)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"CI integration not configured for branch '{branch}'"
        )
    
    return {
        "status": "disabled",
        "branch": branch,
        "message": f"CI integration disabled for branch '{branch}'"
    }
