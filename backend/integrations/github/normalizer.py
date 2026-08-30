"""
GitHub Data Normalizer.
Converts raw GitHub API responses to Samanvaya domain models.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional
import uuid


class GitHubNormalizer:
    """Normalizes GitHub data to Samanvaya format."""

    @staticmethod
    def normalize_pull_request(
        github_pr: Dict[str, Any],
        project_id: str,
        repo_id: str,
    ) -> Dict[str, Any]:
        """
        Normalize GitHub PR to Samanvaya PullRequest format.
        
        Args:
            github_pr: Raw GitHub PR JSON
            project_id: Samanvaya project ID
            repo_id: Repository identifier
        
        Returns:
            Normalized PR data ready for database insertion
        """
        pr_id = f"PR-{uuid.uuid4().hex[:8].upper()}"
        
        # Extract basic info
        pr_number = github_pr["number"]
        title = github_pr["title"]
        state = github_pr["state"]  # open|closed
        
        # Author information
        author_login = github_pr["user"]["login"]
        author_id = github_pr["user"]["login"]  # Use GitHub login as ID fallback
        
        # Branch info
        branch = github_pr["head"]["ref"]
        base_branch = github_pr["base"]["ref"]
        
        # Timestamps
        created_at = github_pr["created_at"]
        merged_at = github_pr.get("merged_at")
        
        # Stats
        # Note: GitHub PR endpoint doesn't include full file stats by default
        # These need to be fetched separately via /pulls/{pr_number}/files
        files_changed_count = github_pr.get("changed_files", 0)
        commit_count = github_pr.get("commits", 0)
        
        # Status determination
        if github_pr.get("merged"):
            status = "merged"
        elif state == "closed":
            status = "closed"
        else:
            status = "open"
        
        # Review status (requires separate API call for detailed review info)
        # For now, use mergeable_state as proxy
        mergeable_state = github_pr.get("mergeable_state", "unknown")
        
        if mergeable_state == "clean":
            review_status = "approved"
        elif mergeable_state == "blocked":
            review_status = "changes_requested"
        elif mergeable_state == "behind" or mergeable_state == "dirty":
            review_status = "in_review"
        else:
            review_status = "pending"
        
        return {
            "id": pr_id,
            "pr_number": pr_number,
            "repo_id": repo_id,
            "project_id": project_id,
            "title": title,
            "author_id": author_id,
            "author_login": author_login,
            "branch": branch,
            "base_branch": base_branch,
            "status": status,
            "review_status": review_status,
            "ci_status": None,  # Set separately from check runs
            "alignment_score": None,  # Calculated by AI later
            "risk_score": None,  # Calculated by Intelligence Engine
            "risk_level": None,  # Calculated by Intelligence Engine
            "files_changed_count": files_changed_count,
            "commit_count": commit_count,
            "created_at": created_at,
            "merged_at": merged_at,
            # Store GitHub URL for reference
            "github_url": github_pr["html_url"],
            "github_id": github_pr["id"],
        }

    @staticmethod
    def normalize_pr_files(
        github_files: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Normalize GitHub PR files data.
        
        Args:
            github_files: List of changed files from GitHub
        
        Returns:
            Aggregated file change statistics
        """
        total_files = len(github_files)
        total_additions = sum(f.get("additions", 0) for f in github_files)
        total_deletions = sum(f.get("deletions", 0) for f in github_files)
        total_changes = sum(f.get("changes", 0) for f in github_files)
        
        # Extract file paths
        changed_files = [f["filename"] for f in github_files]
        
        # Categorize changes
        additions_only = [f for f in github_files if f.get("deletions", 0) == 0]
        deletions_only = [f for f in github_files if f.get("additions", 0) == 0]
        modifications = [
            f for f in github_files
            if f.get("additions", 0) > 0 and f.get("deletions", 0) > 0
        ]
        
        return {
            "files_changed": total_files,
            "lines_added": total_additions,
            "lines_deleted": total_deletions,
            "total_changes": total_changes,
            "changed_files": changed_files,
            "new_files": len(additions_only),
            "deleted_files": len(deletions_only),
            "modified_files": len(modifications),
        }

    @staticmethod
    def normalize_commit(
        github_commit: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Normalize GitHub commit data.
        
        Args:
            github_commit: Raw GitHub commit JSON
        
        Returns:
            Normalized commit data
        """
        return {
            "sha": github_commit["sha"],
            "message": github_commit["commit"]["message"],
            "author": github_commit["commit"]["author"]["name"],
            "author_email": github_commit["commit"]["author"]["email"],
            "author_login": github_commit.get("author", {}).get("login") if github_commit.get("author") else None,
            "committed_at": github_commit["commit"]["author"]["date"],
            "github_url": github_commit["html_url"],
        }

    @staticmethod
    def normalize_check_runs(
        check_runs_response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Normalize GitHub check runs (CI/CD status).
        
        Args:
            check_runs_response: GitHub check runs API response
        
        Returns:
            Normalized CI status
        """
        check_runs = check_runs_response.get("check_runs", [])
        
        if not check_runs:
            return {
                "ci_status": None,
                "total_checks": 0,
                "passed_checks": 0,
                "failed_checks": 0,
                "pending_checks": 0,
            }
        
        total = len(check_runs)
        passed = len([c for c in check_runs if c.get("conclusion") == "success"])
        failed = len([c for c in check_runs if c.get("conclusion") == "failure"])
        pending = len([c for c in check_runs if c.get("status") == "in_progress" or c.get("status") == "queued"])
        
        # Determine overall CI status
        if failed > 0:
            ci_status = "failing"
        elif pending > 0:
            ci_status = "pending"
        elif passed == total:
            ci_status = "passing"
        else:
            ci_status = "unknown"
        
        return {
            "ci_status": ci_status,
            "total_checks": total,
            "passed_checks": passed,
            "failed_checks": failed,
            "pending_checks": pending,
            "check_runs": [
                {
                    "name": c["name"],
                    "status": c["status"],
                    "conclusion": c.get("conclusion"),
                    "started_at": c.get("started_at"),
                    "completed_at": c.get("completed_at"),
                }
                for c in check_runs
            ],
        }

    @staticmethod
    def normalize_branch(
        github_branch: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Normalize GitHub branch data.
        
        Args:
            github_branch: Raw GitHub branch JSON
        
        Returns:
            Normalized branch data
        """
        return {
            "name": github_branch["name"],
            "commit_sha": github_branch["commit"]["sha"],
            "protected": github_branch.get("protected", False),
        }

    @staticmethod
    def normalize_repository(
        github_repo: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Normalize GitHub repository data.
        
        Args:
            github_repo: Raw GitHub repository JSON
        
        Returns:
            Normalized repository data
        """
        return {
            "repo_id": f"REPO-{github_repo['id']}",
            "name": github_repo["name"],
            "full_name": github_repo["full_name"],
            "owner": github_repo["owner"]["login"],
            "description": github_repo.get("description"),
            "default_branch": github_repo["default_branch"],
            "language": github_repo.get("language"),
            "private": github_repo["private"],
            "github_url": github_repo["html_url"],
            "clone_url": github_repo["clone_url"],
            "created_at": github_repo["created_at"],
            "updated_at": github_repo["updated_at"],
        }

    @staticmethod
    def calculate_pr_age_hours(created_at: str) -> float:
        """
        Calculate PR age in hours from creation timestamp.
        
        Args:
            created_at: ISO 8601 timestamp
        
        Returns:
            Age in hours
        """
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            now = datetime.now(created.tzinfo)
            age = (now - created).total_seconds() / 3600
            return round(age, 2)
        except Exception:
            return 0.0
