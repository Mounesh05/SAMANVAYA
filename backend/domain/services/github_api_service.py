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
import hashlib
import re
from typing import Optional, List, Dict, Any

from integrations.github.client import GitHubClient
from integrations.github.ci_evidence import collect_actions_ci, failure_details, unavailable_actions_ci

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
        actions_ci = None
        try:
            check_runs = await self.client.get_commit_check_runs(owner, repo, head_sha)
        except Exception as e:
            response = getattr(e, "response", None)
            status = getattr(response, "status_code", None)
            reason = f"GitHub check runs unavailable (HTTP {status})" if status else "GitHub check runs unavailable"
            logger.warning("%s for %s/%s#%s", reason, owner, repo, pr_number)
            # Preserve the API response shape without claiming an empty CI run
            # was observed. Optional evidence failure must not abort PR sync.
            check_runs = {"check_runs": [], "evidence_status": "unavailable", "unavailable_reason": reason}
            failure = failure_details(e)
            check_runs.update(failure_kind=failure["kind"], http_status=failure["http_status"])
            # Actions is a separate API source, not permission expansion and
            # not a synthetic replacement for third-party check-run records.
            if failure["kind"] == "rate_limited":
                actions_ci = unavailable_actions_ci(owner, repo, head_sha, {"resource": "checks_api", **failure})
            else:
                actions_ci = await collect_actions_ci(self.client, owner, repo, head_sha)
        
        return {
            "pr": github_pr,
            "files": files,
            "commits": commits,
            "check_runs": check_runs,
            "actions_ci": actions_ci,
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
            "actions_ci": evidence.get("actions_ci"),
            "reviews": reviews,
            "comments": comments,
        }

    async def fetch_analysis_sources(self, owner, repo, files, revision, include_context=False, verified_snapshot=False,
                                     *, include_quality_context=True):
        """Fetch bounded supported source at the immutable PR head, never patches."""
        from intelligence.algorithms.discovery.service import (
            MAX_FILES, MAX_SOURCE_BYTES, MAX_TOTAL_BYTES, QUALITY_CONTEXT_MANIFESTS, safe_relative_path, source_language,
        )
        if not revision:
            return {}, [{"kind": "missing_source_revision"}]
        paths = [f["filename"] for f in files if f.get("status") != "removed"
                 and isinstance(f.get("filename"), str) and safe_relative_path(f["filename"])
                 and source_language(f["filename"])]
        diagnostics = []
        regular = {}
        if verified_snapshot:
            try:
                if not isinstance(revision, str) or not re.fullmatch(r"[a-f0-9]{40}", revision):
                    raise ValueError("Exact revision required")
                commit = await self.client.get_commit(owner, repo, revision)
                tree_sha = commit.get("commit", {}).get("tree", {}).get("sha")
                if not isinstance(tree_sha, str) or not re.fullmatch(r"[a-f0-9]{40}", tree_sha):
                    raise ValueError("Missing commit tree identity")
                tree = await self.client.get_source_tree(owner, repo, tree_sha)
                if (commit.get("sha") != revision or tree.get("truncated")
                        or tree.get("sha") != tree_sha):
                    raise ValueError("Exact regular-file tree required")
                regular = {entry["path"]: entry for entry in tree.get("tree", [])
                           if entry.get("type") == "blob" and entry.get("mode") in {"100644", "100755"}}
                if include_quality_context:
                    paths.extend(path for path in regular if safe_relative_path(path)
                                 and path.rsplit("/", 1)[-1] in QUALITY_CONTEXT_MANIFESTS)
            except Exception:
                return {}, [{"kind": "verified_regular_source_tree_unavailable"}]
        if include_context:
            try:
                if not verified_snapshot:
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
        if verified_snapshot:
            paths = [path for path in paths if path in regular]
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
                    if verified_snapshot:
                        git_hash = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
                        if data.get("path") != path or data.get("size") != len(raw) or git_hash != regular[path].get("sha"):
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
