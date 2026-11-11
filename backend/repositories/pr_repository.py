"""
Pull Request repository with author and project queries.
"""

from .base import BaseRepository
from core.database import col
from pymongo.errors import DuplicateKeyError
from intelligence.algorithms.decision import fingerprint


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

    async def find_by_date_range(self, repo_id: str, start_date, end_date) -> list:
        """Find repository PRs created within an inclusive date range."""
        return await self.find_all({
            "repo_id": repo_id,
            "created_at": {
                "$gte": start_date.isoformat(),
                "$lte": end_date.isoformat(),
            },
        })

    async def find_by_pr_number(self, repo_id: str, pr_number: int):
        """Find PR by repo and PR number."""
        return await self.find_one({"repo_id": repo_id, "pr_number": pr_number})

    async def find_by_id(self, pr_id: str):
        """Find PR by ID."""
        return await self.find_one({"id": pr_id})

    async def store_revision(self, document, validate_current=None):
        """CAS sync preserves stable PR IDs and rejects older concurrent fetches."""
        identity = fingerprint([document["project_id"], document["repo_id"], document["pr_number"]])
        await self.col.create_index("github_identity", unique=True, sparse=True)
        document = {**document, "github_identity": identity}
        query = {k: document[k] for k in ("project_id", "repo_id", "pr_number")}
        for _ in range(4):
            previous = await self.find_one(query)
            if validate_current is not None and not await validate_current():
                return previous or document, False
            if previous:
                if previous.get("updated_at") and (not document.get("updated_at") or previous["updated_at"] > document["updated_at"]):
                    return previous, False
                document["id"] = previous["id"]
                result = await self.col.update_one({"id": previous["id"], "head_sha": previous.get("head_sha"), "updated_at": previous.get("updated_at")}, {"$set": document})
                if result.matched_count:
                    return document, True
            else:
                try:
                    await self.col.insert_one(document.copy())
                    return document, True
                except DuplicateKeyError:
                    continue
        raise ValueError("PR revision changed repeatedly during synchronization; retry with the current head")
