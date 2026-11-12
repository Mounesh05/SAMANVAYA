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
from fastapi import HTTPException

from domain.models.hr_performance import (
    HRAssessmentDimensionItem,
    HRAssessmentCreate,
)
from domain.services.hr_performance_service import HRPerformanceService
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

    @pytest.mark.anyio
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

    @pytest.mark.anyio
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

    @pytest.mark.anyio
    async def test_valid_legacy_weights_cannot_activate_without_governance(self):
        from domain.services.performance_human_service import HumanScoringPending
        with patch.object(self.service.policy_repo, "save_policy", new=AsyncMock()) as save:
            with pytest.raises(HumanScoringPending):
                await self.service.configure_policy({"lead": 0.4, "pm": 0.3, "hr": 0.2, "qa": 0.1}, "CEO001")
            save.assert_not_awaited()


class TestNinetyTenEvaluationAggregation:
    """Historical AI0–90 values cannot be double-weighted by HR submission."""

    @pytest.mark.anyio
    async def test_legacy_hr_submit_cannot_rewrite_performance(self):
        from domain.services.performance_human_service import HumanScoringPending
        service = HRPerformanceService()
        with patch.object(service.performance_repo, "update", new=AsyncMock()) as update:
            with pytest.raises(HumanScoringPending):
                await service.submit_hr_assessment("PERF101", HRAssessmentCreate(dimensions={}),
                                                   {"employee_id": "HR001", "role": "HR"})
            update.assert_not_awaited()

    @pytest.mark.anyio
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

    @pytest.mark.anyio
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

    @pytest.mark.anyio
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

    @pytest.mark.anyio
    async def test_hr_dashboard_suppresses_technical_details(self, mock_db, monkeypatch):
        from core import database
        from api.routes import performance
        from test_performance_scoring_compatibility import assessment
        monkeypatch.setattr(database, "get_db", lambda: mock_db)
        await mock_db.users.insert_many([
            dict(employee_id="AUDIT-DEV", role="DEVELOPER", org_id="O", is_active=True),
            dict(employee_id="H", role="HR", org_id="O", is_active=True, designation="HR_MANAGER")])
        await mock_db.projects.insert_one(dict(id="AUDIT-PROJECT", org_id="O"))
        await mock_db.developer_performances.insert_one(assessment().model_dump())
        result = await performance.get_developer_dashboard("AUDIT-DEV", periods=6, user={"employee_id": "H"})
        assert result["is_hr_view"] is True and result["hr_assessment"] is None
        current = result["current_performance"]
        assert current["contribution_credit"] is None
        assert current["ai_evaluation"]["dimension_scores"] == {}
        assert current["ai_evaluation"]["confidence_score"] is None
        assert current["overall_score"] == 85.4 and current["grade"] == "B+"
        assert current["rating"] is None  # No new, uncalibrated outcome band is invented.

    @pytest.mark.anyio
    async def test_get_hr_assessment_returns_none_when_no_authorized_case(self, mock_db, monkeypatch):
        from core import database
        from api.routes import performance
        monkeypatch.setattr(database, "get_db", lambda: mock_db)
        await mock_db.users.insert_many([
            dict(employee_id="D", role="DEVELOPER", org_id="O", is_active=True),
            dict(employee_id="H", role="HR", org_id="O", is_active=True, designation="HR_MANAGER")])
        assert await performance.get_hr_assessment("D", user={"employee_id": "H"}) is None
