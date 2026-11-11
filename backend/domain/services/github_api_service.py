"""
GitHubAPIService - Pure GitHub API interactions.

Responsibilities:
- Fetch PRs, files, commits, check runs
- List repositories
- Get repository info
- No business logic, no database operations
"""

import logging
import asyncio
import base64
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

    async def fetch_pull_request_evidence(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> Dict[str, Any]:
        """Fetch all read-only evidence needed for a PR evaluation."""
        evidence = await self.fetch_pull_request_data(owner, repo, pr_number)
        github_pr = evidence["pr"]
        reviews = await self.client.get_pr_reviews(owner, repo, pr_number)
        comments = await self.client.get_pr_comments(owner, repo, pr_number)
        return {
            "pr": github_pr,
            "files": evidence["files"],
            "commits": evidence["commits"],
            "check_runs": evidence["check_runs"],
            "reviews": reviews,
            "comments": comments,
        }

    async def fetch_analysis_sources(self, owner, repo, files, revision, include_context=False):
        """Fetch bounded supported source at the immutable PR head, never patches."""
        from intelligence.algorithms.discovery.service import (
            MAX_FILES, MAX_SOURCE_BYTES, MAX_TOTAL_BYTES, safe_relative_path, source_language,
        )
        if not revision:
            return {}, [{"kind": "missing_source_revision"}]
        paths = [f["filename"] for f in files if f.get("status") != "removed"
                 and isinstance(f.get("filename"), str) and safe_relative_path(f["filename"])
                 and source_language(f["filename"])]
        diagnostics = []
        if include_context:
            try:
                tree = await self.client.get_source_tree(owner, repo, revision)
                symlinks = {entry.get("path") for entry in tree.get("tree", []) if entry.get("mode") == "120000"}
                paths = [path for path in paths if path not in symlinks]
                context_paths = [entry["path"] for entry in tree.get("tree", [])
                                 if entry.get("type") == "blob" and entry.get("mode") != "120000"
                                 and isinstance(entry.get("path"), str) and safe_relative_path(entry["path"])
                                 and (source_language(entry["path"]) or entry["path"] == ".samanvaya/requirements.json")]
                # Changed files first, then tests, then other caller context.
                paths.extend(sorted(context_paths, key=lambda p: (p != ".samanvaya/requirements.json", "test" not in p.lower() and "spec" not in p.lower(), p)))
                if tree.get("truncated"):
                    diagnostics.append({"kind": "repository_tree_truncated"})
            except Exception:
                diagnostics.append({"kind": "repository_context_unavailable"})
        paths = list(dict.fromkeys(paths))
        semaphore = asyncio.Semaphore(4)

        async def read(path):
            async with semaphore:
                try:
                    data = await self.client.get_file(owner, repo, path, ref=revision)
                    if not isinstance(data, dict) or data.get("type") != "file" or data.get("encoding") != "base64" or data.get("size", MAX_SOURCE_BYTES + 1) > MAX_SOURCE_BYTES:
                        return path, None
                    raw = base64.b64decode("".join(data.get("content", "").split()), validate=True)
                    if len(raw) > MAX_SOURCE_BYTES:
                        return path, None
                    return path, raw.decode("utf-8-sig")
                except Exception:
                    return path, None
        rows = await asyncio.gather(*(read(path) for path in paths[:MAX_FILES]))
        sources, total = {}, 0
        for path, source in rows:
            if source is None:
                diagnostics.append({"path": path, "kind": "source_unavailable"})
            elif total + len(source.encode()) > MAX_TOTAL_BYTES:
                diagnostics.append({"path": path, "kind": "source_bound"})
            else:
                sources[path] = source
                total += len(source.encode())
        if len(paths) > MAX_FILES:
            diagnostics.append({"kind": "file_bound"})
        return sources, diagnostics

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
            return await self.client.list_repositories(org)
        else:
            return await self.client.list_repositories()
