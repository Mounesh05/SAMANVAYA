"""
Pull Request repository with author and project queries.
"""

from .base import BaseRepository
from core.database import col
from pymongo.errors import DuplicateKeyError
from intelligence.algorithms.decision import fingerprint
import re


class PRRepository(BaseRepository):
    def __init__(self):
        super().__init__(col("pull_requests"))

    async def find_by_author(self, author_id: str) -> list:
        """Find all PRs by an author."""
        return await self.find_all({"author_id": author_id})

    @staticmethod
    def _organization(record):
        organization = record.get("org_id")
        if (not isinstance(organization, str) or not organization.strip()
                or record.get("organization_id", organization) != organization):
            return None
        return organization

    @staticmethod
    def _project_scope(project_ids, organization):
        # Mongo scalar equality/$in also matches arrays: ambiguous identities
        # must not inherit access through one matching array element.
        return {"project_id": {"$in": project_ids, "$not": {"$type": "array"}},
                "$and": [{"$or": [{key: {"$exists": False}},
                    {key: {"$eq": organization, "$not": {"$type": "array"}}}]}
                    for key in ("org_id", "organization_id")]}

    async def _member_project_ids(self, person):
        organization = self._organization(person)
        if organization is None or person.get("is_active", True) is not True:
            return []
        assigned = person.get("project_ids")
        assigned = [p for p in assigned if isinstance(p, str) and p] if isinstance(assigned, list) else []
        team = person.get("team_id")
        team = team if isinstance(team, str) and team else None
        membership = [{"id": {"$in": assigned}}]
        if team:
            membership.append({"team_id": team})
        projects = await col("projects").find({"org_id": organization, "$or": membership},
            {"id": 1, "org_id": 1, "organization_id": 1, "team_id": 1}).to_list(None)
        return sorted({p["id"] for p in projects if isinstance(p.get("id"), str)
                       and p["id"] and self._organization(p) == organization
                       and (p["id"] in assigned or team is not None and p.get("team_id") == team)})

    async def find_by_employee(self, employee_id: str) -> list:
        """Explicit GitHub identity and legacy employee identity, within current scope."""
        person = await col("users").find_one({"employee_id": employee_id})
        if not person:
            return []
        projects = await self._member_project_ids(person)
        if not projects:
            return []
        authors = [{"author_id": {"$eq": employee_id, "$not": {"$type": "array"}}}]
        login = person.get("github_username")
        if isinstance(login, str) and login.strip():
            match = {"$regex": "^" + re.escape(login.strip()) + "$", "$options": "i", "$not": {"$type": "array"}}
            authors.extend([{"author_id": match}, {"author_login": match}])
        return await self.find_all({**self._project_scope(projects, self._organization(person)), "$or": authors})

    async def find_for_member(self, person: dict) -> list:
        """Project/team read membership; author mappings do not grant project access."""
        projects = await self._member_project_ids(person)
        if not projects:
            return []
        return await self.find_all(self._project_scope(projects, self._organization(person)))

    async def find_open(self, project_id: str) -> list:
        """Find all open PRs in a project."""
        return await self.find_all({"project_id": project_id, "status": "open"})

    async def find_by_project(self, project_id: str) -> list:
        """Find all PRs in a project."""
        if not isinstance(project_id, str) or not project_id:
            return []
        project = await col("projects").find_one({"id": {"$eq": project_id, "$not": {"$type": "array"}}})
        organization = self._organization(project or {})
        if organization is None:
            return []
        return await self.find_all(self._project_scope([project_id], organization))

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
