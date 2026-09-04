"""
GitHub integration API endpoints.
Allows manual PR sync and repository management.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from core.dependencies import get_current_user, require_permission, require_roles
from core.permissions import Permission
from domain.services.github_service import GitHubService
from pydantic import BaseModel
import httpx

router = APIRouter()


class PRSyncRequest(BaseModel):
    """Request to sync a PR from GitHub."""
    owner: str
    repo: str
    pr_number: int
    project_id: str
    use_ai: bool = True  # Enable AI analysis by default
    use_deep_analysis: bool = False  # Enable comprehensive deep analysis (static analysis, security, etc.)


class RepoSyncRequest(BaseModel):
    """Request to sync all PRs from a repository."""
    owner: str
    repo: str
    project_id: str
    state: str = "open"
    limit: int = 10


@router.get("/health")
async def github_integration_health():
    """
    Check GitHub integration health.
    
    Tests if GitHub API is accessible with configured token.
    """
    try:
        github_service = GitHubService()
        user_info = await github_service.client.get_authenticated_user()
        
        return {
            "status": "operational",
            "authenticated_as": user_info.get("login"),
            "rate_limit_remaining": user_info.get("rate_limit", {}).get("remaining"),
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "note": "Ensure GITHUB_TOKEN is set in .env"
        }


@router.get("/repository-info")
async def get_repository_info(
    owner: str = Query(...),
    repo: str = Query(...),
):
    """
    Get repository information from GitHub.
    Public endpoint - no authentication required.
    
    Example: /github/repository-info?owner=facebook&repo=react
    """
    try:
        github_service = GitHubService()
        repo_info = await github_service.get_repository_info(owner, repo)
        
        return repo_info
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch repository info: {str(e)}"
        )


@router.get("/list-repositories")
async def list_repositories(
    org: str = Query(None, description="Organization name (optional)"),
):
    """
    List GitHub repositories.
    Public endpoint - no authentication required.
    
    If org is provided, lists org repositories.
    Otherwise, lists authenticated user's repositories (requires GitHub token in backend config).
    """
    try:
        github_service = GitHubService()
        repos = await github_service.list_repositories(org)
        
        return {
            "org": org,
            "total": len(repos),
            "repositories": repos,
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list repositories: {str(e)}"
        )


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
    try:
        github_service = GitHubService()
        
        result = await github_service.sync_pull_request(
            owner=request.owner,
            repo=request.repo,
            pr_number=request.pr_number,
            project_id=request.project_id,
            use_ai=request.use_ai,
            use_deep_analysis=request.use_deep_analysis,
            triggered_by=user.get("email", "unknown"),
        )
        
        response = {
            "message": "PR synced successfully",
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
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync PR: {str(e)}"
        )


@router.post("/sync-repository-prs")
async def sync_repository_prs(
    request: RepoSyncRequest,
    user: dict = Depends(require_roles("LEAD", "PM")),
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
    try:
        github_service = GitHubService()
        
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
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync repository PRs: {str(e)}"
        )
