"""
Incident and deployment repositories (DORA data).
"""

from typing import List, Optional

from core.database import col

from .base import BaseRepository


class IncidentRepository(BaseRepository):
    def __init__(self):
        super().__init__(col("incidents"))

    async def find_by_id(self, incident_id: str) -> Optional[dict]:
        return await self.find_one({"id": incident_id})

    async def find_for_projects(self, project_ids: List[str], status: Optional[str] = None) -> list:
        query: dict = {"project_id": {"$in": list(project_ids)}}
        if status:
            query["status"] = status
        return await self.find_all(query)


class DeploymentRepository(BaseRepository):
    def __init__(self):
        super().__init__(col("deployments"))

    async def find_by_id(self, deployment_id: str) -> Optional[dict]:
        return await self.find_one({"id": deployment_id})

    async def find_by_project(self, project_id: str) -> list:
        return await self.find_all({"project_id": project_id})
