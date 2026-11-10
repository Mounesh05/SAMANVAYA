"""
Repository for HR Performance Assessments and Human Evaluation Policies.
Persists evidence-based HR assessments and versioned evaluation policies.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from core.database import col


DEFAULT_HUMAN_EVALUATION_POLICY = {
    "policy_id": "POLICY-V1-DEFAULT",
    "version": "1.0.0",
    "is_active": True,
    "ai_weight": 0.90,
    "human_weight": 0.10,
    "role_weights": {
        "lead": 0.35,
        "pm": 0.30,
        "hr": 0.20,
        "qa": 0.15,
    },
    "role_dimensions": {
        "lead": ["technical_skill", "code_quality", "mentoring", "technical_ownership"],
        "pm": ["requirement_understanding", "delivery_reliability", "communication", "business_alignment"],
        "hr": [
            "professional_conduct",
            "workplace_ethics",
            "policy_compliance",
            "mandatory_learning",
            "workplace_accountability"
        ],
        "qa": ["quality_focus", "test_coverage", "bug_response", "regression_awareness"],
        "devops": ["deployment_quality", "ci_cd_compliance", "monitoring_awareness", "incident_response"],
        "ceo": ["business_impact", "innovation", "company_alignment", "leadership_potential"],
    },
    "configured_by": "system",
    "created_at": datetime.now(timezone.utc).isoformat(),
    "updated_at": datetime.now(timezone.utc).isoformat(),
    "notes": "Default 90% AI + 10% Human Evaluation Policy",
}


class HRAssessmentRepository:
    """Repository for managing HR workplace performance assessments."""

    def __init__(self):
        self.collection = col("hr_assessments")

    async def get_by_id(self, assessment_id: str) -> Optional[Dict[str, Any]]:
        return await self.collection.find_one({"assessment_id": assessment_id}, {"_id": 0})

    async def get_by_performance_id(self, performance_id: str) -> Optional[Dict[str, Any]]:
        doc = await self.collection.find_one({"performance_id": performance_id}, {"_id": 0})
        if not doc:
            # Fallback: check if performance_id was passed as a developer_id
            cursor = self.collection.find({"developer_id": performance_id}, {"_id": 0}).sort("created_at", -1).limit(1)
            docs = [d async for d in cursor]
            return docs[0] if docs else None
        return doc

    async def get_by_developer_id(self, developer_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        cursor = self.collection.find({"developer_id": developer_id}, {"_id": 0}).sort("created_at", -1).limit(limit)
        return [doc async for doc in cursor]

    async def save_assessment(self, assessment_dict: Dict[str, Any]) -> Dict[str, Any]:
        assessment_id = assessment_dict.get("assessment_id")
        existing = await self.get_by_id(assessment_id) if assessment_id else None
        if not existing and assessment_dict.get("performance_id"):
            existing = await self.get_by_performance_id(assessment_dict["performance_id"])
        if not existing and assessment_dict.get("developer_id"):
            existing = await self.get_by_performance_id(assessment_dict["developer_id"])

        if existing:
            target_id = existing.get("assessment_id", assessment_id)
            assessment_dict["assessment_id"] = target_id
            await self.collection.update_one(
                {"assessment_id": target_id},
                {"$set": assessment_dict}
            )
        else:
            await self.collection.insert_one(dict(assessment_dict))
        return assessment_dict


class EvaluationPolicyRepository:
    """Repository for managing human evaluation policies with version history."""

    def __init__(self):
        self.collection = col("evaluation_policies")

    async def get_active_policy(self) -> Dict[str, Any]:
        policy = await self.collection.find_one({"is_active": True}, {"_id": 0})
        if not policy:
            # Seed default policy if not present
            policy = dict(DEFAULT_HUMAN_EVALUATION_POLICY)
            try:
                await self.collection.insert_one(dict(policy))
            except Exception:
                pass
        return policy

    async def save_policy(self, policy_data: Dict[str, Any]) -> Dict[str, Any]:
        # Deactivate previous active policies if saving an active policy
        if policy_data.get("is_active", True):
            await self.collection.update_many({"is_active": True}, {"$set": {"is_active": False}})
        
        await self.collection.insert_one(dict(policy_data))
        return policy_data

    async def get_policy_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        cursor = self.collection.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
        history = [doc async for doc in cursor]
        if not history:
            return [DEFAULT_HUMAN_EVALUATION_POLICY]
        return history

