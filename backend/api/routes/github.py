"""
GitHub integration API endpoints.
Allows manual PR sync and repository management.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from core.dependencies import get_current_user, require_permission
from core.permissions import Permission
from core.authorization import verify_project_access
from domain.services.github_sync_service import GitHubSyncService
from domain.services.qa_workflow_provisioning_service import QAWorkflowProvisioningService
from domain.models.github_project_config import GitHubProjectConfig
from core.database import col
from pydantic import BaseModel
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class PRSyncRequest(BaseModel):
    """Request to sync a PR from GitHub."""
    owner: str
    repo: str
    pr_number: int
    project_id: str | None = None
    use_ai: bool = True  # Enable AI analysis by default
    use_deep_analysis: bool = False  # Enable comprehensive deep analysis (static analysis, security, etc.)


class RepoSyncRequest(BaseModel):
    """Request to sync all PRs from a repository."""
    owner: str
    repo: str
    project_id: str
    state: str = "open"
    limit: int = 10


class QAWorkflowProvisionRequest(BaseModel):
    """Repository to configure for automatic Samanvaya QA reporting."""
    owner: str
    repo: str
    project_id: str
    branch: str | None = None


GITHUB_PROJECT_CONFIGS = "github_project_configs"


@router.get("/health")
async def github_integration_health(
    user: dict = Depends(get_current_user),
):
    """
    Check GitHub integration health.
    Requires authentication — prevents credential disclosure.
    """
    try:
        github_service = GitHubSyncService()
        user_info = await github_service.client.get_authenticated_user()
        
        return {
            "status": "operational",
            "rate_limit_remaining": user_info.get("rate_limit", {}).get("remaining"),
        }
    
    except Exception:
        logger.exception("GitHub health check failed")
        return {
            "status": "error",
            "message": "GitHub API is not reachable with the configured token",
            "note": "Ensure GITHUB_TOKEN is set in .env"
        }


@router.get("/repository-info")
async def get_repository_info(
    owner: str = Query(...),
    repo: str = Query(...),
    # Reads GitHub with the server token, so only repository-link holders may use it.
    user: dict = Depends(require_permission(Permission.MANAGE_REPOSITORY_LINK)),
):
    """
    Get repository information from GitHub.
    Requires authentication — uses server's GitHub token.
    
    Example: /github/repository-info?owner=facebook&repo=react
    """
    try:
        github_service = GitHubSyncService()
        repo_info = await github_service.get_repository_info(owner, repo)
        
        return repo_info
    
    except Exception:
        logger.exception("GitHub request failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch repository info. See the server log for details."
        )


@router.get("/list-repositories")
async def list_repositories(
    org: str = Query(None, description="Organization name (optional)"),
    # Reads GitHub with the server token, so only repository-link holders may use it.
    user: dict = Depends(require_permission(Permission.MANAGE_REPOSITORY_LINK)),
):
    """
    List GitHub repositories.
    Requires authentication — uses server's GitHub token.
    
    If org is provided, lists org repositories.
    Otherwise, lists authenticated user's repositories.
    """
    try:
        github_service = GitHubSyncService()
        repos = await github_service.list_repositories(org)
        
        return {
            "org": org,
            "total": len(repos),
            "repositories": repos,
        }
    
    except Exception:
        logger.exception("GitHub request failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to list repositories. See the server log for details."
        )


@router.get("/branches")
async def list_branches(
    owner: str = Query(...),
    repo: str = Query(...),
    # Reads GitHub with the server token, so only repository-link holders may use it.
    user: dict = Depends(require_permission(Permission.MANAGE_REPOSITORY_LINK)),
):
    """List repository branches using the configured read-only GitHub token."""
    try:
        github_service = GitHubSyncService()
        branches = await github_service.api_service.client.list_branches(owner, repo)
        return {
            "owner": owner,
            "repo": repo,
            "total": len(branches),
            "branches": branches,
        }
    except Exception:
        logger.exception("GitHub request failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to list repository branches. See the server log for details."
        )


@router.get("/projects/{project_id}/config", response_model=GitHubProjectConfig)
async def get_project_github_config(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """Return the persisted GitHub configuration for a Samanvaya project."""
    await verify_project_access(user, project_id)
    config = await col(GITHUB_PROJECT_CONFIGS).find_one(
        {"project_id": project_id},
        {"_id": 0},
    )
    if not config:
        raise HTTPException(status_code=404, detail="GitHub project configuration not found")
    return config


@router.put("/projects/{project_id}/config", response_model=GitHubProjectConfig)
async def save_project_github_config(
    project_id: str,
    config: GitHubProjectConfig,
    user: dict = Depends(require_permission(Permission.MANAGE_REPOSITORY_LINK)),
):
    """Validate and persist repository and developer branch configuration.

    CR-003: MANAGE_REPOSITORY_LINK holders (PM, Lead, DevOps; not the CEO since CR-007) link
    repositories for projects they can access. For CEO/PM/Lead read and write
    scope are the same projects; DevOps never hold project write access, so
    the check is project access, not write access.
    """
    await verify_project_access(user, project_id)
    if config.project_id != project_id:
        raise HTTPException(status_code=400, detail="Project ID does not match the URL")

    github_service = GitHubSyncService()
    try:
        repository = await github_service.get_repository_info(
            config.repository_owner,
            config.repository_name,
        )
        branches = await github_service.api_service.client.list_branches(
            config.repository_owner,
            config.repository_name,
        )
    except httpx.HTTPStatusError as error:
        raise HTTPException(
            status_code=error.response.status_code,
            detail="GitHub repository validation failed",
        ) from error

    actual_default = repository.get("default_branch")
    if actual_default != config.default_branch:
        raise HTTPException(
            status_code=400,
            detail=f"Default branch must be {actual_default}",
        )

    branch_names = {branch.get("name") for branch in branches}
    for mapping in config.developer_mappings:
        if mapping.branch not in branch_names:
            raise HTTPException(
                status_code=400,
                detail=f"Branch does not exist: {mapping.branch}",
            )

    expected_url = f"https://github.com/{config.repository_owner}/{config.repository_name}"
    if config.repository_url.rstrip("/") != expected_url:
        raise HTTPException(status_code=400, detail="Repository URL does not match owner and name")

    payload = config.model_dump()
    await col(GITHUB_PROJECT_CONFIGS).replace_one(
        {"project_id": project_id},
        payload,
        upsert=True,
    )
    return payload


@router.post("/provision-qa-workflow")
async def provision_qa_workflow(
    request: QAWorkflowProvisionRequest,
    user: dict = Depends(require_permission(Permission.MANAGE_TEST_AUTOMATION)),
):
    """
    Install the managed QA workflow and encrypted Actions secrets.

    CR-003: same rules as POST /api/qa/projects/{id}/enable-ci: needs
    MANAGE_TEST_AUTOMATION, access to the project, and the repository must be
    the one linked to the project (the org token must not write elsewhere).
    """
    await verify_project_access(user, request.project_id)
    from api.routes.qa_ci_provisioning import _linked_repository
    await _linked_repository(request.project_id, f"{request.owner}/{request.repo}")
    
    try:
        result = await QAWorkflowProvisioningService().provision(
            owner=request.owner,
            repo=request.repo,
            project_id=request.project_id,
            branch=request.branch,
        )
        return result
    except httpx.HTTPStatusError as error:
        detail = error.response.text
        if error.response.status_code == 403:
            detail = (
                "GitHub rejected Actions secret access. Update the GitHub token for "
                "this repository with Contents: Read and write, Actions: Read and write, "
                "and Workflows: Read and write "
                f"permissions. GitHub response: {error.response.text}"
            )
        raise HTTPException(
            status_code=error.response.status_code,
            detail=f"GitHub API error while provisioning QA workflow: {detail}",
        )
    except ValueError as error:
        raise HTTPException(status_code=503, detail=str(error))
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to provision QA workflow: {error}",
        )


@router.get("/projects/{project_id}/pull-requests")
async def list_project_pull_requests(
    project_id: str,
    user: dict = Depends(require_permission(Permission.ANALYZE_PR_RISK)),
):
    """
    Pull requests of one project, read only (CR-002).

    For people who review or test a project's changes without authoring them
    (QA, DevOps). Same project scope as the rest of the project's data.
    """
    await verify_project_access(user, project_id)
    from repositories.pr_repository import PRRepository
    prs = await PRRepository().find_by_project(project_id)
    for pr in prs:
        pr.pop("_id", None)
    prs.sort(key=lambda pr: str(pr.get("updated_at") or pr.get("created_at") or ""), reverse=True)
    return {"project_id": project_id, "pull_requests": prs, "total": len(prs)}


@router.post("/sync-pr")
async def sync_pull_request(
    request: PRSyncRequest,
    user: dict = Depends(require_permission(Permission.SYNC_PR)),
):
    """
    Sync a single PR from GitHub with AI analysis.
    Requires SYNC_PR permission (DEVELOPER role by default).
    
    Fetches PR data, analyzes risk (Layer 5), optionally invokes AI agent (Layer 6),
    and stores results in database.
    
    Example:
    ```json
    {
        "owner": "facebook",
        "repo": "react",
        "pr_number": 25840,
        "project_id": "PRJ-ABC123",
        "use_ai": true
    }
    ```
    """
    project_id = request.project_id
    if not project_id:
        mappings = await col(GITHUB_PROJECT_CONFIGS).find({"repository_owner": request.owner, "repository_name": request.repo}).limit(2).to_list(2)
        if len(mappings) != 1:
            raise HTTPException(status_code=422, detail="Repository must have one authorized project mapping")
        project_id = mappings[0]["project_id"]
    project = await col("projects").find_one({"id": project_id})
    if not project or not user.get("org_id") or project.get("org_id") != user["org_id"]:
        raise HTTPException(status_code=403, detail="Repository project is unavailable in this organization")
    # CR-001: SYNC_PR holders (developers) sync PRs for projects they are
    # assigned to. Requiring project *write* access here made the endpoint
    # unusable: no role holding SYNC_PR has write access.
    await verify_project_access(user, project_id)

    try:
        github_service = GitHubSyncService()

        result = await github_service.sync_pull_request(
            owner=request.owner,
            repo=request.repo,
            pr_number=request.pr_number,
            project_id=project_id,
            use_ai=request.use_ai,
            use_deep_analysis=request.use_deep_analysis,
            triggered_by=user.get("email", "unknown"),
        )
        
        response = {
            "message": "A newer PR revision is already current; stale analysis was skipped" if result.get("revision_superseded") else "PR synced successfully",
            "pr_id": result["pr"]["id"],
            "pr_number": request.pr_number,
            "risk_level": result["pr"]["risk_level"],
            "risk_score": result["pr"]["risk_score"],
            "details": result,
        }
        
        # Add AI analysis to response if available
        if result.get("ai_analysis"):
            response["ai_analysis"] = result["ai_analysis"]
            response["ai_run_id"] = result.get("ai_run_id")
        
        # Add code quality report if deep analysis was run
        if result.get("code_quality_report"):
            response["code_quality_report"] = result["code_quality_report"]
        
        return response
    
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"GitHub API error: {e.response.text}"
        )
    except Exception:
        logger.exception("GitHub request failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to sync PR. See the server log for details."
        )


@router.post("/sync-repository-prs")
async def sync_repository_prs(
    request: RepoSyncRequest,
    user: dict = Depends(require_permission(Permission.SYNC_REPOSITORY_PRS)),
):
    """
    Sync multiple PRs from a repository.
    Requires authentication.
    
    Fetches recent PRs, analyzes each one, and stores in database.
    
    Example:
    ```json
    {
        "owner": "facebook",
        "repo": "react",
        "project_id": "PRJ-ABC123",
        "state": "open",
        "limit": 10
    }
    ```
    """
    # Authorization: verify user has write access to the target project
    await verify_project_access(user, request.project_id, require_write=True)
    
    try:
        github_service = GitHubSyncService()
        
        results = await github_service.sync_repository_prs(
            owner=request.owner,
            repo=request.repo,
            project_id=request.project_id,
            state=request.state,
            limit=request.limit,
        )
        
        successful = [r for r in results if "error" not in r]
        failed = [r for r in results if "error" in r]
        
        return {
            "message": f"Synced {len(successful)} PRs successfully",
            "total_attempted": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "results": results,
        }
    
    except Exception:
        logger.exception("GitHub request failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to sync repository PRs. See the server log for details."
        )
