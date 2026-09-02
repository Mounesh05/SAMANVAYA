"""
AI Run repository with agent execution tracking.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from .base import BaseRepository
from core.database import col
from domain.models.ai_run import AIRun
import uuid


class AIRunRepository(BaseRepository):
    def __init__(self):
        super().__init__(col("ai_runs"))

    async def create(self, ai_run: AIRun) -> str:
        """Create a new AI run record."""
        run_id = str(uuid.uuid4())
        doc = {
            "id": run_id,
            "agent_type": ai_run.agent_type,
            "input_data": ai_run.input_data,
            "output_data": ai_run.output_data,
            "status": ai_run.status,
            "error_message": ai_run.error_message,
            "execution_time_ms": ai_run.execution_time_ms,
            "model_name": ai_run.model_name,
            "triggered_by": ai_run.triggered_by,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.insert(doc)
        return run_id

    async def get_by_id(self, run_id: str) -> Optional[AIRun]:
        """Find AI run by ID."""
        doc = await self.find_one({"id": run_id})
        return AIRun(**doc) if doc else None

    async def list(
        self,
        limit: int = 50,
        skip: int = 0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[AIRun]:
        """List AI runs with optional filtering."""
        query = filters or {}
        result = await self.find_many(
            query=query,
            limit=limit,
            skip=skip,
            sort_field="created_at",
            sort_dir=-1,
        )
        return [AIRun(**doc) for doc in result["data"]]

    async def find_by_agent_type(self, agent_type: str, limit: int = 50) -> List[AIRun]:
        """Find runs by specific agent type."""
        result = await self.find_many(
            query={"agent_type": agent_type},
            limit=limit,
            sort_field="created_at",
            sort_dir=-1,
        )
        return [AIRun(**doc) for doc in result["data"]]

    async def find_by_user(self, user_email: str, limit: int = 50) -> List[AIRun]:
        """Find runs triggered by specific user."""
        result = await self.find_many(
            query={"triggered_by": user_email},
            limit=limit,
            sort_field="created_at",
            sort_dir=-1,
        )
        return [AIRun(**doc) for doc in result["data"]]

    async def get_recent(self, limit: int = 20) -> List[AIRun]:
        """Get most recent AI runs."""
        result = await self.find_many(
            query={},
            limit=limit,
            sort_field="created_at",
            sort_dir=-1,
        )
        return [AIRun(**doc) for doc in result["data"]]
