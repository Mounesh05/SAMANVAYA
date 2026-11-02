"""Persistence and retrieval for evidence-backed developer evaluations."""

import hashlib
import json
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
        if not self._is_duplicate_eligible(evaluation):
            raise ValueError("Only completed, schema- and evidence-validated evaluations can be persisted")

        duplicate_key = self._duplicate_key(evaluation)
        await self.collection.create_index(
            "duplicate_key",
            unique=True,
            partialFilterExpression={
                "duplicate_key": {"$type": "string"},
                "status": "completed",
                "schema_validated": True,
                "evidence_validated": True,
                "is_preliminary": False,
                "unsupported_references": [],
                "overall_score": {"$gte": 0, "$lte": 10},
                "evidence_manifest.files.0": {"$exists": True},
            },
        )
        eligibility = {
            "status": "completed",
            "overall_score": {"$gte": 0, "$lte": 10},
            "schema_validated": True,
            "evidence_validated": True,
            "is_preliminary": False,
            "evidence_manifest.files.0": {"$exists": True},
            "unsupported_references": {"$exists": True, "$eq": []},
        }
        existing_cursor = self.collection.find(
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
        async for existing in existing_cursor:
            existing_evaluation = DeveloperEvaluation(**existing)
            if self._is_duplicate_eligible(existing_evaluation):
                return existing_evaluation

        evaluation = evaluation.model_copy(update={"duplicate_key": duplicate_key})
        document = evaluation.model_dump(mode="json")
        try:
            await self.collection.insert_one(document)
        except DuplicateKeyError:
            existing = await self.collection.find_one(
                {**eligibility, "duplicate_key": duplicate_key},
                {"_id": 0},
            )
            if existing:
                existing_evaluation = DeveloperEvaluation(**existing)
                if self._is_duplicate_eligible(existing_evaluation):
                    return existing_evaluation
            raise
        return evaluation

    @staticmethod
    def _duplicate_key(evaluation: DeveloperEvaluation) -> str:
        identity = json.dumps(
            (
                "score-contract-v3",
                evaluation.employee_id,
                evaluation.repo_owner,
                evaluation.repo_name,
                str(evaluation.pr_number),
                evaluation.head_commit_sha,
                evaluation.evaluation_focus,
            ),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    @staticmethod
    def _is_duplicate_eligible(evaluation: DeveloperEvaluation) -> bool:
        base_eligibility = (
            evaluation.status == "completed"
            and evaluation.overall_score is not None
            and evaluation.schema_validated
            and evaluation.evidence_validated
            and not evaluation.is_preliminary
            and bool(evaluation.evidence_manifest.get("files"))
            and not evaluation.unsupported_references
            and bool(evaluation.evidence_coverage)
            and set(evaluation.dimensions) == set(evaluation.evidence_coverage)
        )
        if not base_eligibility:
            return False
        for name, coverage in evaluation.evidence_coverage.items():
            dimension = evaluation.dimensions.get(name)
            if not isinstance(dimension, dict) or dimension.get("assessment") != coverage:
                return False
            if coverage in {"insufficient_evidence", "not_assessed"}:
                if "score" in dimension:
                    return False
            elif coverage in {"assessed", "partially_assessable"}:
                score = dimension.get("score")
                if (
                    not isinstance(score, (int, float))
                    or isinstance(score, bool)
                    or not 0 <= score <= 10
                ):
                    return False
            else:
                return False
        return True

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
