"""
Pull Request repository with author and project queries.
"""

from .base import BaseRepository
from core.database import col


class PRRepository(BaseRepository):
    def __init__(self):
        super().__init__(col("pull_requests"))

    async def find_by_author(self, author_id: str) -> list:
        """Find all PRs by an author."""
        return await self.find_all({"author_id": author_id})

    async def find_open(self, project_id: str) -> list:
        """Find all open PRs in a project."""
        return await self.find_all({"project_id": project_id, "status": "open"})

    async def find_by_project(self, project_id: str) -> list:
        """Find all PRs in a project."""
        return await self.find_all({"project_id": project_id})

    async def find_by_pr_number(self, repo_id: str, pr_number: int):
        """Find PR by repo and PR number."""
        return await self.find_one({"repo_id": repo_id, "pr_number": pr_number})

    async def find_by_id(self, pr_id: str):
        """Find PR by ID."""
        return await self.find_one({"id": pr_id})
