"""
Tests for HR Performance Assessment and 90% AI + 10% Human Evaluation Aggregation.

Verifies:
1. HR Assessment rubric scoring (4/3/2/1/N/O) and dimension score normalization.
2. Evidence validation requirement for negative ratings (1 or 2 requires >= 15 chars).
3. N/O (Not Observed) dimension handling: N/O is never converted to 0 and does not penalize employee.
4. Human evaluation policy configuration, versioning, and validation (weights sum to 1.0, non-negative).
5. 90/10 Score aggregation preserving: Final Score = (AI Score * 0.90) + (Human Score * 0.10).
6. Human evaluation completeness verification across configured roles.
7. HR API authorization barriers: HR cannot trigger or view raw PR code evaluations.
8. HR developer dashboard filtering: technical breakdowns, LOC, and commit stats are suppressed.
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone
from fastapi import HTTPException

from domain.models.hr_performance import (
    HRAssessmentDimensionItem,
    HRAssessmentCreate,
)
from domain.services.hr_performance_service import HRPerformanceService
from domain.models.developer_performance import (
    DeveloperPerformance,
    AIEvaluation,
    PerformanceBreakdown,
    RoleEvaluation,
)
from core.dependencies import require_roles


class TestHRAssessmentScoring:
    """Historical scalar display must never establish a canonical human aggregate."""

    @pytest.mark.parametrize("rating,display", [(1, 25), (2, 50), (3, 75), (4, 100)])
    def test_legacy_scalar_conversion_is_read_compatibility_only(self, rating, display):
        item = HRAssessmentDimensionItem(dimension="professional_conduct", rating=rating)
        assert HRPerformanceService().calculate_hr_dimension_score(item) == display

    def test_legacy_subset_average_cannot_supply_human_credit(self):
        item = HRAssessmentDimensionItem(dimension="professional_conduct", rating=4)
        score, errors = HRPerformanceService().calculate_overall_hr_score({"professional_conduct": item})
        assert score is None and "approved" in " ".join(errors)

    def test_not_observed_never_becomes_neutral(self):
        item = HRAssessmentDimensionItem(dimension="professional_conduct", is_not_observed=True)
        assert HRPerformanceService().calculate_hr_dimension_score(item) is None
        score, _ = HRPerformanceService().calculate_overall_hr_score({"professional_conduct": item})
        assert score is None

    def test_comment_length_cannot_validate_a_negative_assessment(self):
        item = HRAssessmentDimensionItem(dimension="professional_conduct", rating=1, evidence_description="x" * 1000)
        score, errors = HRPerformanceService().calculate_overall_hr_score({"professional_conduct": item})
        assert score is None and "evidence" in " ".join(errors)


class TestEvaluationPolicy:
    """Tests for configurable human evaluation role weights."""

    def setup_method(self):
        self.service = HRPerformanceService()

    @pytest.mark.asyncio
    async def test_policy_weights_must_sum_to_one(self):
        """Policy configuration must enforce sum(weights) == 1.0."""
        invalid_weights = {
            "lead": 0.50,
            "pm": 0.50,
            "hr": 0.20,  # Sum = 1.20
        }
        with pytest.raises(ValueError, match="must sum to 1.0"):
            await self.service.configure_policy(
                role_weights=invalid_weights,
                notes="Invalid weights test",
                configured_by="CEO001",
            )

    @pytest.mark.asyncio
    async def test_policy_rejects_negative_weights(self):
        """Policy must reject negative weights."""
        invalid_weights = {
            "lead": 1.20,
            "pm": -0.20,
        }
        with pytest.raises(ValueError, match="cannot be negative"):
            await self.service.configure_policy(
                role_weights=invalid_weights,
                notes="Negative weights test",
                configured_by="CEO001",
            )

    @pytest.mark.asyncio
    async def test_valid_legacy_weights_cannot_activate_without_governance(self):
        from domain.services.performance_human_service import HumanScoringPending
        with patch.object(self.service.policy_repo, "save_policy", new=AsyncMock()) as save:
            with pytest.raises(HumanScoringPending):
                await self.service.configure_policy({"lead": 0.4, "pm": 0.3, "hr": 0.2, "qa": 0.1}, "CEO001")
            save.assert_not_awaited()


class TestNinetyTenEvaluationAggregation:
    """Historical AI0–90 values cannot be double-weighted by HR submission."""

    @pytest.mark.asyncio
    async def test_legacy_hr_submit_cannot_rewrite_performance(self):
        from domain.services.performance_human_service import HumanScoringPending
        service = HRPerformanceService()
        with patch.object(service.performance_repo, "update", new=AsyncMock()) as update:
            with pytest.raises(HumanScoringPending):
                await service.submit_hr_assessment("PERF101", HRAssessmentCreate(dimensions={}),
                                                   {"employee_id": "HR001", "role": "HR"})
            update.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_unapproved_legacy_completeness_is_unknown(self):
        service = HRPerformanceService()
        with patch.object(service.performance_repo, "get_by_id", new=AsyncMock(return_value={
            "developer_id": "EMP101", "period_label": "2024-Q1", "role_evaluation": {"lead": {"criterion_1": 4}}})):
            result = await service.check_human_evaluation_completeness("PERF101")
        assert not result.is_complete and result.human_score is None
        assert result.required_roles == [] and result.pending_roles == []
        assert result.details["status"] == "POLICY_PENDING"


class TestHREvaluationAPISecurityAndFiltering:
    """Tests that HR cannot access raw engineering data or trigger PR-level evaluations."""

    @pytest.mark.asyncio
    async def test_hr_blocked_by_role_guard_on_pr_level_evaluation(self):
        """HR users must be blocked (403) from triggering PR evaluation."""
        hr_user = {
            "employee_id": "HR001",
            "role": "HR",
            "is_admin": False,
        }
        check_role = require_roles("CEO", "LEAD")
        with pytest.raises(HTTPException) as exc_info:
            await check_role(user=hr_user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_hr_blocked_from_pr_evaluation_by_employee(self):
        """HR users must be blocked (403) from accessing PR-level evaluation diffs for employees."""
        from api.routes import evaluation
        hr_user = {
            "employee_id": "HR001",
            "role": "HR",
            "is_admin": False,
        }

        with pytest.raises(HTTPException) as exc_info:
            await evaluation.list_employee_evaluations(employee_id="EMP001", user=hr_user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_hr_dashboard_suppresses_technical_details(self):
        """
        Calling get_developer_dashboard as HR must return HRDashboardPerformanceView:
        - contribution_credit is None
        - dimension_scores in ai_evaluation is empty
        - is_hr_view is True
        """
        from api.routes import performance
        from domain.services.performance_service import PerformanceService

        hr_user = {
            "employee_id": "HR001",
            "role": "HR",
            "is_admin": False,
            "designation": "HRBP",
        }

        mock_perf = DeveloperPerformance(
            developer_id="EMP001",
            developer_name="Engineer Bob",
            project_id="PROJ1",
            period_type="quarter",
            period_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            period_end=datetime(2024, 3, 31, tzinfo=timezone.utc),
            period_label="2024-Q1",
            final_score=88.5,
            grade="A",
            ai_evaluation=AIEvaluation(
                score=85.0,
                breakdown=PerformanceBreakdown(
                    code_quality=24.0,
                    delivery=19.0,
                    collaboration=14.0,
                    reliability=14.0,
                    engineering_impact=9.0,
                    engineering_judgment=5.0,
                ),
                reasoning="Exemplary engineering performance",
                confidence="high",
            ),
            role_evaluation=RoleEvaluation(average_score=90.0, contribution=9.0),
            confidence_level="high",
            confidence_reason="Comprehensive commit history",
            evaluated_by="LEAD001",
        )

        mock_service = AsyncMock(spec=PerformanceService)
        mock_service.get_developer_performance = AsyncMock(return_value=mock_perf)
        mock_service.get_performance_trend = AsyncMock(return_value=[
            {"period_label": "2024-Q1", "final_score": 88.5, "grade": "A"}
        ])

        with patch.object(performance, "PerformanceService", return_value=mock_service):
            result = await performance.get_developer_dashboard("EMP001", periods=6, user=hr_user)

            assert result["is_hr_view"] is True
            curr = result["current_performance"]
            # Technical metrics must be stripped
            assert curr["contribution_credit"] is None
            assert curr["ai_evaluation"]["dimension_scores"] == {}
            assert curr["ai_evaluation"]["strengths"] == []
            assert curr["ai_evaluation"]["weaknesses"] == []
            # High-level outcome is preserved
            assert curr["overall_score"] == 88.5
            assert curr["grade"] == "A"
            assert curr["rating"] == "Meets Expectations"

    @pytest.mark.asyncio
    async def test_get_hr_assessment_returns_none_when_no_assessment(self):
        """When no HR assessment exists for a developer, get_hr_assessment returns None (200 OK) without 404."""
        from api.routes import performance
        hr_user = {
            "employee_id": "DEMO-HR",
            "role": "HR",
            "is_admin": False,
            "designation": "HR_OFFICER",
        }
        with patch("api.routes.performance.HRPerformanceService") as MockHRService:
            mock_inst = AsyncMock()
            mock_inst.assessment_repo.get_by_performance_id = AsyncMock(return_value=None)
            MockHRService.return_value = mock_inst

            res = await performance.get_hr_assessment("DEMO-LEAD", user=hr_user)
            assert res is None
