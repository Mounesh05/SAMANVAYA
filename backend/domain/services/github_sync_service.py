"""
GitHubSyncService - Data synchronization and persistence.

Responsibilities:
- Normalize GitHub data to Samanvaya format
- Store/update PRs in database
- Save AI runs
- Orchestrate API, Analysis, and DB operations
"""

import logging
from typing import Optional, List, Dict, Any

from integrations.github.normalizer import GitHubNormalizer
from repositories.pr_repository import PRRepository
from repositories.ai_run_repository import AIRunRepository
from domain.models.ai_run import AIRun
from domain.services.github_api_service import GitHubAPIService
from domain.services.github_analysis_service import GitHubAnalysisService

logger = logging.getLogger(__name__)


class GitHubSyncService:
    """Orchestrates PR synchronization from GitHub to Samanvaya."""

    def __init__(self, github_token: Optional[str] = None):
        """
        Initialize sync service.
        
        Args:
            github_token: GitHub PAT (uses config if not provided)
        """
        self.api_service = GitHubAPIService(github_token=github_token)
        self.analysis_service = GitHubAnalysisService()
        self.normalizer = GitHubNormalizer()
        self.pr_repo = PRRepository()
        self.ai_run_repo = AIRunRepository()

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
        Fetch PR from GitHub, analyze, and store in database.
        
        This is the main orchestration method that coordinates:
        1. Fetching data from GitHub API
        2. Normalizing data
        3. Running analysis (risk + optional AI)
        4. Storing in database
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            project_id: Samanvaya project ID
            use_ai: Whether to invoke AI agent for analysis
            use_deep_analysis: Whether to run comprehensive deep analysis
            triggered_by: User who triggered the sync
        
        Returns:
            Complete PR data with risk analysis and optional AI insights
        """
        # Step 1: Fetch from GitHub API
        github_data = await self.api_service.fetch_pull_request_data(
            owner, repo, pr_number
        )
        
        github_pr = github_data["pr"]
        files = github_data["files"]
        commits = github_data["commits"]
        check_runs = github_data["check_runs"]
        
        # Step 2: Normalize data
        repo_id = f"{owner}/{repo}"
        normalized_pr = self.normalizer.normalize_pull_request(
            github_pr, project_id, repo_id
        )
        
        file_stats = self.normalizer.normalize_pr_files(files)
        ci_data = self.normalizer.normalize_check_runs(check_runs)
        pr_age_hours = self.normalizer.calculate_pr_age_hours(github_pr["created_at"])
        
        # Update PR with file stats and CI status
        normalized_pr.update({
            "files_changed_count": file_stats["files_changed"],
            "ci_status": ci_data["ci_status"],
        })
        
        # Step 3: Analyze risk
        risk_evidence = await self.analysis_service.analyze_risk(
            pr_id=normalized_pr["id"],
            files_changed=file_stats["files_changed"],
            lines_added=file_stats["lines_added"],
            lines_deleted=file_stats["lines_deleted"],
            changed_files=file_stats["changed_files"],
            commit_count=len(commits),
            pr_age_hours=pr_age_hours,
        )
        
        # Add risk analysis to PR
        normalized_pr.update({
            "risk_score": risk_evidence["risk_score"],
            "risk_level": risk_evidence["risk_level"],
        })
        
        # Step 4: Store PR in database
        existing_pr = await self.pr_repo.find_by_pr_number(repo_id, pr_number)
        
        if existing_pr:
            # Update existing PR
            await self.pr_repo.update(
                {"id": existing_pr["id"]},
                normalized_pr
            )
            normalized_pr["id"] = existing_pr["id"]
        else:
            # Insert new PR
            await self.pr_repo.insert(normalized_pr)
        
        # Step 5: Optional AI Analysis
        ai_analysis = None
        ai_run_id = None
        code_quality_report = None
        
        if use_ai:
            pr_data = {
                "pr_id": normalized_pr["id"],
                "title": github_pr.get("title", ""),
                "author": github_pr.get("user", {}).get("login", ""),
                "pr_number": pr_number,
                "repo": f"{owner}/{repo}",
                "project_id": project_id,
                "commit_sha": github_pr.get("head", {}).get("sha"),
                "changed_files": [f["filename"] for f in files],
            }
            
            analysis_result = await self.analysis_service.analyze_with_ai(
                pr_data=pr_data,
                risk_evidence=risk_evidence,
                use_deep_analysis=use_deep_analysis,
                triggered_by=triggered_by,
            )
            
            ai_analysis = analysis_result.get("ai_analysis")
            code_quality_report = analysis_result.get("code_quality_report")
            ai_run_data = analysis_result.get("ai_run_data")
            
            # Save AI run to database if data available
            if ai_run_data:
                ai_run = AIRun(**ai_run_data)
                ai_run_id = await self.ai_run_repo.create(ai_run)
        
        return {
            "pr": normalized_pr,
            "file_stats": file_stats,
            "risk_analysis": risk_evidence,
            "ai_analysis": ai_analysis,
            "ai_run_id": ai_run_id,
            "code_quality_report": code_quality_report.dict() if code_quality_report else None,
            "ci_data": ci_data,
            "commit_count": len(commits),
        }

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
        
        Args:
            owner: Repository owner
            repo: Repository name
            project_id: Samanvaya project ID
            state: PR state (open|closed|all)
            limit: Max PRs to sync
        
        Returns:
            List of synced PRs with analysis
        """
        # Fetch PRs from GitHub
        github_prs = await self.api_service.list_pull_requests(
            owner, repo, state=state, per_page=limit
        )
        
        synced_prs = []
        
        for github_pr in github_prs[:limit]:
            try:
                result = await self.sync_pull_request(
                    owner, repo, github_pr["number"], project_id
                )
                synced_prs.append(result)
            except Exception as e:
                logger.error(f"Failed to sync PR #{github_pr['number']}: {e}")
                synced_prs.append({
                    "pr_number": github_pr["number"],
                    "error": str(e),
                    "status": "failed"
                })
        
        return synced_prs

    async def get_repository_info(
        self, owner: str, repo: str
    ) -> Dict[str, Any]:
        """
        Get repository information from GitHub.
        
        Args:
            owner: Repository owner
            repo: Repository name
        
        Returns:
            Normalized repository data
        """
        github_repo = await self.api_service.get_repository_info(owner, repo)
        return self.normalizer.normalize_repository(github_repo)

    async def list_repositories(
        self, org: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List GitHub repositories.
        
        Args:
            org: Organization name (user repos if None)
        
        Returns:
            List of normalized repository data
        """
        github_repos = await self.api_service.list_repositories(org)
        return [self.normalizer.normalize_repository(repo) for repo in github_repos]
