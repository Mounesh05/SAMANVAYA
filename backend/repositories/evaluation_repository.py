"""Persistence and retrieval for evidence-backed developer evaluations."""

import hashlib
from pymongo.errors import DuplicateKeyError
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
        """Insert a validated evaluation or return an eligible duplicate."""
        duplicate_key = self._duplicate_key(evaluation)
        await self.collection.create_index(
            "duplicate_key",
            unique=True,
            sparse=True,
        )
        eligibility = {
            "status": "completed",
            "overall_score": {"$ne": None},
            "evidence_manifest": {"$exists": True, "$ne": {}},
            "unsupported_references": {"$exists": True, "$eq": []},
        }
        existing = await self.collection.find_one(
            {**eligibility, "$or": [
                {"duplicate_key": duplicate_key},
                {
                    "employee_id": evaluation.employee_id,
                    "repo_owner": evaluation.repo_owner,
                    "repo_name": evaluation.repo_name,
                    "pr_number": evaluation.pr_number,
                    "head_commit_sha": evaluation.head_commit_sha,
                    "evaluation_focus": evaluation.evaluation_focus,
                },
            ]},
            {"_id": 0},
        )
        if existing:
            return DeveloperEvaluation(**existing)

        evaluation = evaluation.model_copy(update={"duplicate_key": duplicate_key})
        document = evaluation.model_dump(mode="json")
        try:
            await self.collection.insert_one(document)
        except DuplicateKeyError:
            existing = await self.collection.find_one(
                {"duplicate_key": duplicate_key},
                {"_id": 0},
            )
            if existing:
                return DeveloperEvaluation(**existing)
            raise
        return evaluation

    @staticmethod
    def _duplicate_key(evaluation: DeveloperEvaluation) -> str:
        identity = "|".join(
            (
                evaluation.employee_id,
                evaluation.repo_owner,
                evaluation.repo_name,
                str(evaluation.pr_number),
                evaluation.head_commit_sha,
                evaluation.evaluation_focus,
            )
        )
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

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
