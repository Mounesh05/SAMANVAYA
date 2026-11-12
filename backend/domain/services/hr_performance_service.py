"""
Historical HR read compatibility and the shared canonical human-review composition.
Legacy mutation and subset-average paths are retired; no AI score is an engineering measurement.
"""

from typing import Dict, Any, Optional, List, Tuple
import logging
from domain.models.hr_performance import (
    HRAssessment,
    HRAssessmentDimensionItem,
    HRAssessmentCreate,
    HumanEvaluationPolicy,
    HumanEvaluationCompleteness,
)
from repositories.hr_performance_repository import (
    HRAssessmentRepository,
    EvaluationPolicyRepository,
)
from repositories.performance_repository import PerformanceRepository

logger = logging.getLogger(__name__)


class HRPerformanceService:
    """Orchestrates HR workplace evaluations and human score aggregation."""

    def __init__(self):
        self.assessment_repo = HRAssessmentRepository()
        self.policy_repo = EvaluationPolicyRepository()
        self.performance_repo = PerformanceRepository()

    def calculate_hr_dimension_score(self, item: HRAssessmentDimensionItem) -> Optional[float]:
        """
        Historical display conversion only; this is not canonical H or an approved scale.
        N/O (Not Observed) returns None and is NEVER converted to 0.
        """
        if item.is_not_observed or item.rating is None:
            return None
        # 1 -> 25.0, 2 -> 50.0, 3 -> 75.0, 4 -> 100.0
        return round((float(item.rating) / 4.0) * 100.0, 2)

    def calculate_overall_hr_score(
        self,
        dimensions: Dict[str, HRAssessmentDimensionItem]
    ) -> Tuple[Optional[float], List[str]]:
        """Retired legacy subset average; comment length cannot validate evidence."""
        return None, ["Canonical H requires approved scale anchors, assigned complete reviews and validated evidence"]

    async def get_or_create_policy(self) -> Dict[str, Any]:
        """Retrieve current active human evaluation policy."""
        return await self.policy_repo.get_active_policy()

    async def configure_policy(
        self,
        role_weights: Dict[str, float],
        configured_by: str,
        notes: Optional[str] = None
    ) -> HumanEvaluationPolicy:
        """Legacy role-weight configuration cannot activate an official policy."""
        from decimal import Decimal
        from domain.models.performance_scoring import strict_decimal
        from domain.services.performance_human_service import HumanScoringPending
        if not role_weights:
            raise ValueError("Role weights dictionary cannot be empty")
        values = {r: strict_decimal(w) for r, w in role_weights.items()}
        if any(w < 0 for w in values.values()):
            raise ValueError("Role weights cannot be negative")
        if any(r.upper() not in {"LEAD", "PM", "QA", "DEVOPS", "HR"} for r in values):
            raise ValueError("Routine CEO scoring and unsupported reviewer roles are prohibited")
        if sum(values.values()) != Decimal(1):
            raise ValueError("Role weights must sum to 1.0 exactly")
        raise HumanScoringPending()

    @staticmethod
    def compose_human_reviews(policy, reviews, engineering=None):
        from intelligence.performance_human import aggregate_human_reviews
        return aggregate_human_reviews(policy, reviews, engineering)

    def calculate_aggregated_human_score(self, performance, policy):
        """Unapproved legacy policies/fields cannot establish canonical human credit."""
        result = self.compose_human_reviews(None, ())
        return result.calculation.human_score, {}

    async def save_hr_assessment_draft(
        self,
        performance_id: str,
        data: HRAssessmentCreate,
        user: dict
    ) -> HRAssessment:
        """Use signed, period-assigned observation intake instead of mutable legacy drafts."""
        from domain.services.performance_human_service import HumanScoringPending
        raise HumanScoringPending()

    async def submit_hr_assessment(self, performance_id, data, user):
        """Never fabricate a performance row, rating, engineering value or grade."""
        from domain.services.performance_human_service import HumanScoringPending
        raise HumanScoringPending()

    async def check_human_evaluation_completeness(
        self,
        performance_id: str
    ) -> HumanEvaluationCompleteness:
        """Legacy submission presence is not proof of approved reviewer completeness."""
        record = await self.performance_repo.get_by_id(performance_id)
        if record:
            developer_id = record["developer_id"]
            label = record.get("period_label", "UNKNOWN")
        else:
            from repositories.user_repository import UserRepository
            subject = await UserRepository().find_by_employee_id(performance_id)
            if not subject:
                raise ValueError(f"Performance evaluation or employee '{performance_id}' not found")
            developer_id, label = subject["employee_id"], "UNKNOWN"
        return HumanEvaluationCompleteness(performance_id=performance_id, developer_id=developer_id,
            period_label=label, policy_version="UNAPPROVED_LEGACY", required_roles=[], submitted_roles=[],
            pending_roles=[], is_complete=False, human_score=None, role_scores={},
            details={"status": "POLICY_PENDING", "reason": "Use exact-period signed human review completeness"})

