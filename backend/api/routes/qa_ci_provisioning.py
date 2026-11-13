"""CI Integration provisioning endpoints for QA."""

import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException

from core.config import settings
from core.database import col
from core.dependencies import get_current_user, require_permission
from core.permissions import Permission
from domain.models.qa_ci_config import CIProvisionRequest
from domain.services.qa_workflow_provisioning_service import QAWorkflowProvisioningService
from domain.services.qa_service import QAService
from repositories.qa_repository import QARepository

logger = logging.getLogger(__name__)
router = APIRouter(tags=["QA CI Provisioning"])

# Same collection GitHub Sync uses to link a project to its repository.
GITHUB_PROJECT_CONFIGS = "github_project_configs"


async def _linked_repository(project_id: str, requested: str | None) -> tuple[str, str]:
    """The repository linked to this project. CI writes a workflow file and
    repository secrets with the organisation's GitHub token, so it may only
    target the project's own repository, never one typed in by the user."""
    link = await col(GITHUB_PROJECT_CONFIGS).find_one({"project_id": project_id}, {"_id": 0})
    if not link or not link.get("repository_owner") or not link.get("repository_name"):
        raise HTTPException(
            status_code=400,
            detail="Link this project to its GitHub repository (GitHub Sync settings) before enabling CI",
        )
    owner, repo = link["repository_owner"], link["repository_name"]
    if requested and requested.lower() != f"{owner}/{repo}".lower():
        raise HTTPException(
            status_code=400,
            detail=f"CI can only be enabled for this project's repository ({owner}/{repo})",
        )
    return owner, repo


def _github_failure(error: httpx.HTTPStatusError) -> HTTPException:
    """Explain GitHub refusals without echoing GitHub's raw response."""
    status = error.response.status_code if error.response is not None else None
    if status in (401, 403):
        return HTTPException(
            status_code=502,
            detail="GitHub refused the request. Check that GITHUB_TOKEN can write workflows, contents and Actions secrets for this repository",
        )
    if status == 404:
        return HTTPException(
            status_code=400,
            detail="GitHub repository or branch not found, or GITHUB_TOKEN has no access to it",
        )
    return HTTPException(status_code=502, detail="GitHub could not complete CI provisioning. Try again later")
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
    
    Requires MANAGE_TEST_AUTOMATION (QA, PM, LEAD by default).
    """
    # Validate project access
    await qa_service.accessible_project(user, project_id)
    owner, repo = await _linked_repository(project_id, request.repository)
    if not settings.GITHUB_TOKEN:
        raise HTTPException(status_code=400, detail="GITHUB_TOKEN must be configured on the server before enabling CI")
    
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
        # Configuration problems with a safe, specific message (missing URL/token).
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPStatusError as e:
        logger.warning("CI provisioning refused by GitHub for project %s: %s", project_id, e.response.status_code)
        raise _github_failure(e)
    except Exception:
        logger.exception("CI provisioning failed for project %s", project_id)
        raise HTTPException(status_code=502, detail="CI provisioning failed. Check the server logs for details")
    
    # Store CI configuration
    now = datetime.now(timezone.utc)
    ci_config = {
        "project_id": project_id,
        "repository": f"{owner}/{repo}",
        "branch": request.branch,
        "enabled": True,
        "provisioned_at": now.isoformat(),
        "workflow_url": result.get("workflow_url"),
    }
    await qa_repo.save_ci_config(ci_config)
    
    return {
        "project_id": project_id,
        "repository": f"{owner}/{repo}",
        "branch": request.branch,
        "status": "provisioned",
        "workflow_url": result.get("workflow_url"),
        "provisioned_at": now.isoformat(),
        "message": f"CI integration enabled for {owner}/{repo}"
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
