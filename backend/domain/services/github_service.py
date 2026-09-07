"""
GitHubService - Backward-compatible facade.

DEPRECATED: This class is maintained for backward compatibility only.
New code should use:
- GitHubAPIService for GitHub API interactions
- GitHubAnalysisService for PR analysis
- GitHubSyncService for data synchronization

This facade delegates to the refactored services underneath.
"""

import logging
from typing import Optional, List, Dict, Any

from domain.services.github_sync_service import GitHubSyncService

logger = logging.getLogger(__name__)


class GitHubService:
    """
    DEPRECATED: Backward-compatible facade for GitHub operations.
    
    This class exists only for backward compatibility with existing code.
    All new code should use the specialized services directly:
    - GitHubAPIService
    - GitHubAnalysisService  
    - GitHubSyncService
    """

    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize GitHub service (delegates to GitHubSyncService).
        
        Args:
            github_token: GitHub PAT (uses config if not provided)
        """
        logger.warning(
            "GitHubService is deprecated. Use GitHubAPIService, "
            "GitHubAnalysisService, or GitHubSyncService instead."
        )
        # Delegate all operations to sync service (which coordinates API + Analysis)
        self._sync_service = GitHubSyncService(github_token=github_token)

    async def sync_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        project_id: str,
        use_ai: bool = True,
        use_deep_analysis: bool = False,
        triggered_by: str = "system",
    ) -> Dict[str, Any]:
        """
        Fetch PR from GitHub, normalize it, analyze risk, and store in database.
        
        DEPRECATED: Use GitHubSyncService.sync_pull_request() instead.
        """
        return await self._sync_service.sync_pull_request(
            owner=owner,
            repo=repo,
            pr_number=pr_number,
            project_id=project_id,
            use_ai=use_ai,
            use_deep_analysis=use_deep_analysis,
            triggered_by=triggered_by,
        )

    async def sync_repository_prs(
        self,
        owner: str,
        repo: str,
        project_id: str,
        state: str = "open",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Sync multiple PRs from a repository.
        
        DEPRECATED: Use GitHubSyncService.sync_repository_prs() instead.
        """
        return await self._sync_service.sync_repository_prs(
            owner=owner,
            repo=repo,
            project_id=project_id,
            state=state,
            limit=limit,
        )

    async def get_repository_info(
        self, owner: str, repo: str
    ) -> Dict[str, Any]:
        """
        Get repository information from GitHub.
        
        DEPRECATED: Use GitHubSyncService.get_repository_info() instead.
        """
        return await self._sync_service.get_repository_info(owner, repo)

    async def list_repositories(
        self, org: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List GitHub repositories.
        
        DEPRECATED: Use GitHubSyncService.list_repositories() instead.
        """
        return await self._sync_service.list_repositories(org)
