"""
GitHubAPIService - Pure GitHub API interactions.

Responsibilities:
- Fetch PRs, files, commits, check runs
- List repositories
- Get repository info
- No business logic, no database operations
"""

import logging
from typing import Optional, List, Dict, Any

from integrations.github.client import GitHubClient

logger = logging.getLogger(__name__)


class GitHubAPIService:
    """Handles all GitHub API interactions."""

    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize GitHub API service.
        
        Args:
            github_token: GitHub PAT (uses config if not provided)
        """
        self.client = GitHubClient(token=github_token)

    async def fetch_pull_request_data(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> Dict[str, Any]:
        """
        Fetch all PR-related data from GitHub API.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
        
        Returns:
            Dict with pr, files, commits, check_runs
        """
        # Fetch PR
        github_pr = await self.client.get_pull_request(owner, repo, pr_number)
        
        # Fetch additional PR data in parallel would be better, but keep sequential for now
        files = await self.client.get_pr_files(owner, repo, pr_number)
        commits = await self.client.get_pr_commits(owner, repo, pr_number)
        
        # Get CI status
        head_sha = github_pr["head"]["sha"]
        try:
            check_runs = await self.client.get_commit_check_runs(owner, repo, head_sha)
        except Exception as e:
            logger.warning(f"Failed to fetch check runs for {owner}/{repo}#{pr_number}: {e}")
            check_runs = []
        
        return {
            "pr": github_pr,
            "files": files,
            "commits": commits,
            "check_runs": check_runs,
        }

    async def list_pull_requests(
        self,
        owner: str,
        repo: str,
        state: str = "open",
        per_page: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        List PRs from a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            state: PR state (open|closed|all)
            per_page: Results per page
        
        Returns:
            List of PR data from GitHub API
        """
        return await self.client.list_pull_requests(
            owner, repo, state=state, per_page=per_page
        )

    async def get_repository_info(
        self, owner: str, repo: str
    ) -> Dict[str, Any]:
        """
        Get repository information from GitHub.
        
        Args:
            owner: Repository owner
            repo: Repository name
        
        Returns:
            Repository data from GitHub API
        """
        return await self.client.get_repository(owner, repo)

    async def list_repositories(
        self, org: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List GitHub repositories.
        
        Args:
            org: Organization name (user repos if None)
        
        Returns:
            List of repository data from GitHub API
        """
        if org:
            return await self.client.list_org_repositories(org)
        else:
            return await self.client.list_user_repositories()
