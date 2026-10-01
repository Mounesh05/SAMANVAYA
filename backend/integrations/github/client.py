"""
GitHub API client.
Handles authenticated requests to GitHub REST API.
"""

import httpx
import base64
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from core.config import settings
from nacl.public import PublicKey, SealedBox


class GitHubClient:
    """
    GitHub API client for fetching PR data, commits, and reviews.
    Uses personal access token for authentication.
    """
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub client.
        
        Args:
            token: GitHub personal access token (uses config if not provided)
        """
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Samanvaya-Backend"
        }
        
        # Use provided token or fall back to config
        auth_token = token or settings.GITHUB_TOKEN
        if auth_token:
            self.headers["Authorization"] = f"Bearer {auth_token}"
        
        self.timeout = getattr(settings, 'GITHUB_TIMEOUT', 30)
        if auth_token:
            self.headers["Authorization"] = "Bearer " + auth_token
    
    async def _make_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make HTTP request with proper redirect handling."""
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.request(
                method, 
                url, 
                headers=self.headers, 
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            return response
    
    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        """
        Fetch pull request details.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            
        Returns:
            PR data from GitHub API
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        response = await self._make_request("GET", url)
        return response.json()
    
    async def get_pr_commits(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Fetch commits for a pull request.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            
        Returns:
            List of commit data
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/commits"
        response = await self._make_request("GET", url)
        return response.json()
    
    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Fetch files changed in a pull request.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            
        Returns:
            List of file changes
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        response = await self._make_request("GET", url)
        return response.json()
    
    async def get_pr_reviews(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Fetch reviews for a pull request.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            
        Returns:
            List of review data
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        response = await self._make_request("GET", url)
        return response.json()
    
    async def get_pr_comments(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Fetch review comments for a pull request.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            
        Returns:
            List of review comments
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
        response = await self._make_request("GET", url)
        return response.json()
    
    async def get_commit_details(self, owner: str, repo: str, sha: str) -> Dict[str, Any]:
        """
        Fetch details for a specific commit.
        
        Args:
            owner: Repository owner
            repo: Repository name
            sha: Commit SHA
            
        Returns:
            Commit data
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/commits/{sha}"
        response = await self._make_request("GET", url)
        return response.json()

    async def get_commit(self, owner: str, repo: str, sha: str) -> Dict[str, Any]:
        """Fetch a commit, including its changed files and statistics."""
        return await self.get_commit_details(owner, repo, sha)

    async def get_commits(
        self,
        owner: str,
        repo: str,
        author: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        per_page: int = 100,
    ) -> List[Dict[str, Any]]:
        """List repository commits within an optional date range."""
        url = f"{self.base_url}/repos/{owner}/{repo}/commits"
        params: Dict[str, Any] = {
            "per_page": min(max(per_page, 1), 100),
        }
        # GitHub's author filter accepts a username or author email only on
        # some API versions; email matching is handled locally by the caller.
        if author and "@" not in author:
            params["author"] = author
        if since:
            params["since"] = since
        if until:
            params["until"] = until
        response = await self._make_request("GET", url, params=params)
        return response.json()
    
    async def get_commit_check_runs(self, owner: str, repo: str, sha: str) -> Dict[str, Any]:
        """
        Fetch check runs for a specific commit (CI/CD status).
        
        Args:
            owner: Repository owner
            repo: Repository name
            sha: Commit SHA
            
        Returns:
            Check runs data
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/commits/{sha}/check-runs"
        response = await self._make_request("GET", url)
        return response.json()
    
    async def list_pull_requests(
        self, 
        owner: str, 
        repo: str, 
        state: str = "open",
        per_page: int = 30
    ) -> List[Dict[str, Any]]:
        """
        List pull requests for a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            state: PR state (open, closed, all)
            per_page: Results per page
            
        Returns:
            List of PRs
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
        params = {
            "state": state,
            "per_page": per_page,
            "sort": "updated",
            "direction": "desc"
        }
        response = await self._make_request("GET", url, params=params)
        return response.json()
    
    async def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Fetch repository details.
        
        Args:
            owner: Repository owner
            repo: Repository name
            
        Returns:
            Repository data
        """
        url = f"{self.base_url}/repos/{owner}/{repo}"
        response = await self._make_request("GET", url)
        return response.json()

    async def get_actions_public_key(self, owner: str, repo: str) -> Dict[str, Any]:
        """Fetch the public key GitHub requires for Actions secret encryption."""
        url = f"{self.base_url}/repos/{owner}/{repo}/actions/secrets/public-key"
        response = await self._make_request("GET", url)
        return response.json()

    async def set_actions_secret(
        self, owner: str, repo: str, name: str, value: str, public_key: Dict[str, Any]
    ) -> None:
        """Create or update an encrypted repository Actions secret."""
        sealed_box = SealedBox(PublicKey(base64.b64decode(public_key["key"])))
        encrypted_value = base64.b64encode(
            sealed_box.encrypt(value.encode("utf-8"))
        ).decode("ascii")
        url = f"{self.base_url}/repos/{owner}/{repo}/actions/secrets/{name}"
        response = await self._make_request(
            "PUT",
            url,
            json={"encrypted_value": encrypted_value, "key_id": public_key["key_id"]},
        )
        if response.status_code not in (201, 204):
            response.raise_for_status()

    async def get_file(
        self, owner: str, repo: str, path: str, ref: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Return a repository file, or None when it does not exist."""
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
        try:
            params = {"ref": ref} if ref else None
            response = await self._make_request("GET", url, params=params)
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                return None
            raise
        return response.json()

    async def upsert_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: Optional[str] = None,
        sha: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create or update a repository file through the Contents API."""
        url = f"{self.base_url}/repos/{owner}/{repo}/contents/{path}"
        payload: Dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        }
        if branch:
            payload["branch"] = branch
        if sha:
            payload["sha"] = sha
        response = await self._make_request("PUT", url, json=payload)
        return response.json()
    
    async def list_repositories(self, org: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List repositories for authenticated user or organization.
        
        Args:
            org: Organization name (optional)
            
        Returns:
            List of repositories
        """
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
        """
        Get authenticated user information.
        
        Returns:
            User data and rate limit info
        """
        url = f"{self.base_url}/user"
        response = await self._make_request("GET", url)
        user_data = response.json()
        
        # Add rate limit info from headers
        user_data["rate_limit"] = {
            "limit": int(response.headers.get("X-RateLimit-Limit", "0")),
            "remaining": int(response.headers.get("X-RateLimit-Remaining", "0")),
            "reset": int(response.headers.get("X-RateLimit-Reset", "0"))
        }
        
        return user_data
    
    async def check_token_validity(self) -> bool:
        """
        Check if the configured GitHub token is valid.
        
        Returns:
            True if token is valid, False otherwise
        """
        try:
            await self.get_authenticated_user()
            return True
        except Exception:
            return False
