"""
GitHub API client.
Handles authenticated requests to GitHub REST API with support for:
1. GitHub App installation tokens (Option 1)
2. Personal access tokens (PAT fallback)
3. GitHub Actions workflow runs, logs, artifacts, and deployments
"""

import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime
from core.config import settings
from core.sanitizer import sanitize_text


class GitHubClient:
    """
    GitHub API client for fetching PR data, commits, reviews, workflow runs, logs, and deployments.
    Supports GitHub App installation access tokens and personal access tokens.
    """
    
    def __init__(self, token: Optional[str] = None, installation_id: Optional[str] = None):
        """
        Initialize GitHub client.
        
        Args:
            token: GitHub personal access token (uses config if not provided)
            installation_id: GitHub App installation ID (for App-based authentication)
        """
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Samanvaya-Backend",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        
        self.token = token
        self.installation_id = installation_id or getattr(settings, "GITHUB_APP_INSTALLATION_ID", "")
        self.timeout = getattr(settings, "GITHUB_TIMEOUT", 30)

    async def _resolve_headers(self) -> Dict[str, str]:
        """Resolves authentication headers using App installation token or PAT."""
        headers = dict(self.headers)
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
            return headers

        # Try GitHub App installation token
        try:
            from integrations.github.app_auth import get_github_app_auth
            app_auth = get_github_app_auth()
            if app_auth.is_configured():
                app_token = await app_auth.get_installation_access_token(self.installation_id)
                if app_token:
                    headers["Authorization"] = f"Bearer {app_token}"
                    return headers
        except Exception:
            pass

        # Fall back to settings.GITHUB_TOKEN
        auth_token = getattr(settings, "GITHUB_TOKEN", "")
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        return headers
    
    async def _make_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make HTTP request with proper redirect handling and auth headers."""
        headers = await self._resolve_headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))

        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.request(
                method, 
                url, 
                headers=headers, 
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            return response
    
    # ── Pull Request Endpoints ───────────────────────────────────────────────

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        """Fetch pull request details."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        response = await self._make_request("GET", url)
        return response.json()
    
    async def get_pr_commits(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Fetch commits for a pull request."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/commits"
        response = await self._make_request("GET", url)
        return response.json()
    
    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Fetch files changed in a pull request."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        response = await self._make_request("GET", url)
        return response.json()
    
    async def get_pr_reviews(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Fetch reviews for a pull request."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        response = await self._make_request("GET", url)
        return response.json()
    
    async def get_pr_comments(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Fetch review comments on PR code."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
        response = await self._make_request("GET", url)
        return response.json()
    
    async def get_commit_details(self, owner: str, repo: str, sha: str) -> Dict[str, Any]:
        """Fetch detailed information for a single commit including file patches."""
        url = f"{self.base_url}/repos/{owner}/{repo}/commits/{sha}"
        response = await self._make_request("GET", url)
        return response.json()
    
    async def get_commit_check_runs(self, owner: str, repo: str, sha: str) -> Dict[str, Any]:
        """Fetch check runs (CI/CD status) for a commit."""
        url = f"{self.base_url}/repos/{owner}/{repo}/commits/{sha}/check-runs"
        response = await self._make_request("GET", url)
        return response.json()

    async def get_check_suite(self, owner: str, repo: str, check_suite_id: int) -> Dict[str, Any]:
        """Fetch check suite details."""
        url = f"{self.base_url}/repos/{owner}/{repo}/check-suites/{check_suite_id}"
        response = await self._make_request("GET", url)
        return response.json()

    # ── GitHub Actions & Workflows Endpoints ─────────────────────────────────

    async def get_workflow_run(self, owner: str, repo: str, run_id: int) -> Dict[str, Any]:
        """Fetch GitHub Actions workflow run details."""
        url = f"{self.base_url}/repos/{owner}/{repo}/actions/runs/{run_id}"
        response = await self._make_request("GET", url)
        return response.json()

    async def get_workflow_run_jobs(self, owner: str, repo: str, run_id: int) -> Dict[str, Any]:
        """Fetch individual jobs for a GitHub Actions workflow run."""
        url = f"{self.base_url}/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        response = await self._make_request("GET", url)
        return response.json()

    async def download_job_logs(self, owner: str, repo: str, job_id: int) -> str:
        """
        Download and immediately sanitize job execution logs.
        Follows temporary 302 download redirect URL and extracts text logs.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"
        try:
            response = await self._make_request("GET", url)
            raw_text = response.text
            return sanitize_text(raw_text)
        except Exception as e:
            return f"Log download unavailable: {e}"

    async def get_workflow_run_artifacts(self, owner: str, repo: str, run_id: int) -> Dict[str, Any]:
        """Fetch list of artifacts produced by a workflow run."""
        url = f"{self.base_url}/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts"
        response = await self._make_request("GET", url)
        return response.json()

    # ── Deployments Endpoints ────────────────────────────────────────────────

    async def get_deployment(self, owner: str, repo: str, deployment_id: int) -> Dict[str, Any]:
        """Fetch deployment record."""
        url = f"{self.base_url}/repos/{owner}/{repo}/deployments/{deployment_id}"
        response = await self._make_request("GET", url)
        return response.json()

    async def get_deployment_statuses(self, owner: str, repo: str, deployment_id: int) -> List[Dict[str, Any]]:
        """Fetch status history for a deployment."""
        url = f"{self.base_url}/repos/{owner}/{repo}/deployments/{deployment_id}/statuses"
        response = await self._make_request("GET", url)
        return response.json()
    
    # ── Repositories & User ──────────────────────────────────────────────────

    async def list_pull_requests(
        self, 
        owner: str, 
        repo: str, 
        state: str = "open",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """List pull requests for a repository."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
        params = {
            "state": state,
            "per_page": min(limit, 100),
            "sort": "updated",
            "direction": "desc"
        }
        response = await self._make_request("GET", url, params=params)
        return response.json()
    
    async def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """Fetch repository details."""
        url = f"{self.base_url}/repos/{owner}/{repo}"
        response = await self._make_request("GET", url)
        return response.json()
    
    async def list_repositories(self, org: Optional[str] = None) -> List[Dict[str, Any]]:
        """List repositories for authenticated user or organization."""
        if org:
            url = f"{self.base_url}/orgs/{org}/repos"
        else:
            url = f"{self.base_url}/user/repos"
        
        params = {
            "per_page": 100,
            "sort": "updated",
            "direction": "desc"
        }
        response = await self._make_request("GET", url, params=params)
        return response.json()
    
    async def get_authenticated_user(self) -> Dict[str, Any]:
        """Get authenticated user or App token information."""
        url = f"{self.base_url}/user"
        response = await self._make_request("GET", url)
        user_data = response.json()
        
        user_data["rate_limit"] = {
            "limit": int(response.headers.get("X-RateLimit-Limit", "0")),
            "remaining": int(response.headers.get("X-RateLimit-Remaining", "0")),
            "reset": int(response.headers.get("X-RateLimit-Reset", "0"))
        }
        
        return user_data
    
    async def check_token_validity(self) -> bool:
        """Check if the configured GitHub token or App authentication is valid."""
        try:
            await self.get_authenticated_user()
            return True
        except Exception:
            # For App tokens, checking installation works even if /user returns 403
            try:
                from integrations.github.app_auth import get_github_app_auth
                app_auth = get_github_app_auth()
                if app_auth.is_configured():
                    tok = await app_auth.get_installation_access_token()
                    return bool(tok)
            except Exception:
                pass
            return False
