"""Persistence and retrieval for evidence-backed developer evaluations."""

from typing import Any, Dict, List, Optional

from core.database import col
from domain.models.developer_evaluation import DeveloperEvaluation


class EvaluationRepository:
    """Repository for the developer_evaluations collection."""

    def __init__(self):
        self.collection = col("developer_evaluations")

    async def create_or_get(
        self,
        evaluation: DeveloperEvaluation,
    ) -> DeveloperEvaluation:
        """Return an existing completed attempt or insert this evaluation."""
        identity = {
            "employee_id": evaluation.employee_id,
            "repo_owner": evaluation.repo_owner,
            "repo_name": evaluation.repo_name,
            "pr_number": evaluation.pr_number,
            "head_commit_sha": evaluation.head_commit_sha,
            "evaluation_focus": evaluation.evaluation_focus,
            "status": "completed",
        }
        existing = await self.collection.find_one(identity, {"_id": 0})
        if existing:
            return DeveloperEvaluation(**existing)

        document = evaluation.model_dump(mode="json")
        await self.collection.insert_one(document)
        return evaluation

    async def get_by_id(self, evaluation_id: str) -> Optional[DeveloperEvaluation]:
        document = await self.collection.find_one(
            {"evaluation_id": evaluation_id},
            {"_id": 0},
        )
        return DeveloperEvaluation(**document) if document else None

    async def list(
        self,
        query: Dict[str, Any],
        limit: int = 50,
    ) -> List[DeveloperEvaluation]:
        cursor = self.collection.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
        return [DeveloperEvaluation(**document) async for document in cursor]

    async def latest(self, query: Dict[str, Any]) -> Optional[DeveloperEvaluation]:
        results = await self.list(query, limit=1)
        return results[0] if results else None
