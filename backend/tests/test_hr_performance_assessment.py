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
    HRAssessment,
    HumanEvaluationPolicy,
    HumanEvaluationCompleteness,
    HRDimensionKey,
    ComplianceStatus,
)
from domain.services.hr_performance_service import HRPerformanceService
from domain.models.developer_performance import (
    DeveloperPerformance,
    AIEvaluation,
    PerformanceBreakdown,
    RoleEvaluation,
    LeadFeedback,
    HRFeedback,
)
from core.dependencies import require_roles


class TestHRAssessmentScoring:
    """Tests for the HR performance rubric and scoring service."""

    def setup_method(self):
        self.service = HRPerformanceService()

    def test_calculate_hr_score_all_meets_expectations(self):
        """All dimensions rated 3 (Meets) should yield 75.0 / 100."""
        dimensions = {
            k.value: HRAssessmentDimensionItem(
                dimension=k.value,
                rating=3,
                is_not_observed=False,
            )
            for k in [
                HRDimensionKey.PROFESSIONAL_CONDUCT,
                HRDimensionKey.WORKPLACE_ETHICS,
                HRDimensionKey.POLICY_COMPLIANCE,
                HRDimensionKey.MANDATORY_LEARNING,
                HRDimensionKey.WORKPLACE_ACCOUNTABILITY,
            ]
        }
        score, errors = self.service.calculate_overall_hr_score(dimensions)
        assert len(errors) == 0
        assert score == 75.0

    def test_calculate_hr_score_exceeds(self):
        """All dimensions rated 4 (Exceeds) should yield 100.0 / 100."""
        dimensions = {
            k.value: HRAssessmentDimensionItem(
                dimension=k.value,
                rating=4,
                is_not_observed=False,
            )
            for k in [
                HRDimensionKey.PROFESSIONAL_CONDUCT,
                HRDimensionKey.WORKPLACE_ETHICS,
                HRDimensionKey.POLICY_COMPLIANCE,
                HRDimensionKey.MANDATORY_LEARNING,
                HRDimensionKey.WORKPLACE_ACCOUNTABILITY,
            ]
        }
        score, errors = self.service.calculate_overall_hr_score(dimensions)
        assert len(errors) == 0
        assert score == 100.0

    def test_no_rating_excluded_without_penalty(self):
        """
        N/O (Not Observed) must NOT be converted to 0 or penalize the employee.
        If 3 dimensions are 4 (Exceeds) and 2 are N/O, the score should be 100.0,
        evaluated solely over the 3 observed dimensions.
        """
        dimensions = {
            HRDimensionKey.PROFESSIONAL_CONDUCT.value: HRAssessmentDimensionItem(
                dimension=HRDimensionKey.PROFESSIONAL_CONDUCT.value,
                rating=4,
                is_not_observed=False,
            ),
            HRDimensionKey.WORKPLACE_ETHICS.value: HRAssessmentDimensionItem(
                dimension=HRDimensionKey.WORKPLACE_ETHICS.value,
                rating=4,
                is_not_observed=False,
            ),
            HRDimensionKey.POLICY_COMPLIANCE.value: HRAssessmentDimensionItem(
                dimension=HRDimensionKey.POLICY_COMPLIANCE.value,
                rating=4,
                is_not_observed=False,
            ),
            HRDimensionKey.MANDATORY_LEARNING.value: HRAssessmentDimensionItem(
                dimension=HRDimensionKey.MANDATORY_LEARNING.value,
                rating=None,
                is_not_observed=True,
            ),
            HRDimensionKey.WORKPLACE_ACCOUNTABILITY.value: HRAssessmentDimensionItem(
                dimension=HRDimensionKey.WORKPLACE_ACCOUNTABILITY.value,
                rating=None,
                is_not_observed=True,
            ),
        }
        score, errors = self.service.calculate_overall_hr_score(dimensions)
        assert len(errors) == 0
        # 3 observed dimensions at 100.0% -> average is 100.0%
        assert score == 100.0

    def test_all_no_returns_none_score_without_penalty(self):
        """If all dimensions are N/O, score is None without penalizing the employee."""
        dimensions = {
            k.value: HRAssessmentDimensionItem(
                dimension=k.value,
                rating=None,
                is_not_observed=True,
            )
            for k in [
                HRDimensionKey.PROFESSIONAL_CONDUCT,
                HRDimensionKey.WORKPLACE_ETHICS,
                HRDimensionKey.POLICY_COMPLIANCE,
                HRDimensionKey.MANDATORY_LEARNING,
                HRDimensionKey.WORKPLACE_ACCOUNTABILITY,
            ]
        }
        score, errors = self.service.calculate_overall_hr_score(dimensions)
        assert len(errors) == 0
        assert score is None

    def test_rating_1_or_2_requires_substantiated_evidence(self):
        """Ratings 1 (Unsatisfactory) or 2 (Needs Improvement) must have substantiated evidence."""
        # Missing evidence
        invalid_dim = {
            HRDimensionKey.PROFESSIONAL_CONDUCT.value: HRAssessmentDimensionItem(
                dimension=HRDimensionKey.PROFESSIONAL_CONDUCT.value,
                rating=2,
                evidence_description="",
            )
        }
        score, errors = self.service.calculate_overall_hr_score(invalid_dim)
        assert len(errors) > 0
        assert "substantiated evidence" in errors[0]

        # Too short evidence (< 15 chars)
        short_dim = {
            HRDimensionKey.PROFESSIONAL_CONDUCT.value: HRAssessmentDimensionItem(
                dimension=HRDimensionKey.PROFESSIONAL_CONDUCT.value,
                rating=1,
                evidence_description="bad behavior",
            )
        }
        score, errors = self.service.calculate_overall_hr_score(short_dim)
        assert len(errors) > 0
        assert "minimum 15 characters" in errors[0]

        # Adequate evidence passes
        valid_dim = {
            HRDimensionKey.PROFESSIONAL_CONDUCT.value: HRAssessmentDimensionItem(
                dimension=HRDimensionKey.PROFESSIONAL_CONDUCT.value,
                rating=2,
                evidence_description="Documented late attendance to all sprint ceremonies with HR warning on file.",
            )
        }
        score, errors = self.service.calculate_overall_hr_score(valid_dim)
        assert len(errors) == 0
        assert score == 50.0


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
    async def test_valid_policy_increments_version(self):
        """Valid weights should save policy and increment version."""
        valid_weights = {
            "lead": 0.40,
            "pm": 0.30,
            "hr": 0.20,
            "qa": 0.10,
        }
        mock_current_policy = {"version": "1.0.0", "role_weights": {}}
        with patch.object(self.service.policy_repo, "get_active_policy", new=AsyncMock(return_value=mock_current_policy)), \
             patch.object(self.service.policy_repo, "save_policy", new=AsyncMock(side_effect=lambda doc: doc)), \
             patch("domain.services.hr_performance_service.log_audit", new=AsyncMock()):

            policy = await self.service.configure_policy(
                role_weights=valid_weights,
                notes="Update role weights",
                configured_by="CEO001",
            )
            assert policy.version == "1.0.1"
            assert policy.role_weights["lead"] == 0.40
            assert policy.role_weights["hr"] == 0.20


class TestNinetyTenEvaluationAggregation:
    """Tests for the 90% AI + 10% Human aggregation formula."""

    def setup_method(self):
        self.service = HRPerformanceService()

    @pytest.mark.asyncio
    async def test_formula_aggregation_exactness(self):
        """
        Verify:
        Final Score = (AI Score * 0.90) + (Human Score * 0.10)
        Given:
          AI Score = 80.0
          Lead Feedback = 4/5 (80.0)
          HR Assessment = 90.0
          Policy: Lead weight = 0.5, HR weight = 0.5
        Human Score = 0.5 * 80 + 0.5 * 90 = 85.0
        Final Score = (80.0 * 0.90) + (85.0 * 0.10) = 72.0 + 8.5 = 80.5
        """
        perf = DeveloperPerformance(
            developer_id="EMP101",
            developer_name="Engineer One",
            project_id="PROJ1",
            period_type="quarter",
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            period_label="2024-Q1",
            final_score=80.0,
            grade="B",
            ai_evaluation=AIEvaluation(
                score=80.0,
                breakdown=PerformanceBreakdown(
                    code_quality=22.0,
                    delivery=18.0,
                    collaboration=14.0,
                    reliability=13.0,
                    engineering_impact=8.0,
                    engineering_judgment=5.0,
                ),
                reasoning="Strong technical execution",
                confidence="high",
            ),
            role_evaluation=RoleEvaluation(
                lead=LeadFeedback(criterion_1=4, criterion_2=4, criterion_3=4, criterion_4=4),
                average_score=80.0,
                contribution=8.0,
            ),
            confidence_level="high",
            confidence_reason="Comprehensive data points",
        )

        policy = {
            "version": "1.0.0",
            "role_weights": {"lead": 0.5, "hr": 0.5},
        }

        # Submit HR Assessment with 90.0 score
        hr_submission = HRAssessmentCreate(
            dimensions={
                HRDimensionKey.PROFESSIONAL_CONDUCT.value: HRAssessmentDimensionItem(
                    dimension=HRDimensionKey.PROFESSIONAL_CONDUCT.value,
                    rating=4,  # 100
                ),
                HRDimensionKey.WORKPLACE_ETHICS.value: HRAssessmentDimensionItem(
                    dimension=HRDimensionKey.WORKPLACE_ETHICS.value,
                    rating=4,  # 100
                ),
                HRDimensionKey.POLICY_COMPLIANCE.value: HRAssessmentDimensionItem(
                    dimension=HRDimensionKey.POLICY_COMPLIANCE.value,
                    rating=4,  # 100
                ),
                HRDimensionKey.MANDATORY_LEARNING.value: HRAssessmentDimensionItem(
                    dimension=HRDimensionKey.MANDATORY_LEARNING.value,
                    rating=3,  # 75
                ),
                HRDimensionKey.WORKPLACE_ACCOUNTABILITY.value: HRAssessmentDimensionItem(
                    dimension=HRDimensionKey.WORKPLACE_ACCOUNTABILITY.value,
                    rating=3,  # 75
                ),
            },
            general_comments="Great workplace collaboration.",
        )
        # Expected HR score = (100 + 100 + 100 + 75 + 75) / 5 = 90.0

        hr_user = {"employee_id": "HR001", "name": "HR Specialist", "role": "HR"}

        with patch.object(self.service.performance_repo, "get_by_id", new=AsyncMock(return_value=perf.model_dump())), \
             patch.object(self.service.performance_repo, "update", new=AsyncMock(return_value=True)), \
             patch.object(self.service.assessment_repo, "get_by_performance_id", new=AsyncMock(return_value=None)), \
             patch.object(self.service.assessment_repo, "save_assessment", new=AsyncMock(side_effect=lambda doc: doc)), \
             patch.object(self.service, "get_or_create_policy", new=AsyncMock(return_value=policy)), \
             patch("domain.services.hr_performance_service.log_audit", new=AsyncMock()):

            updated_perf = await self.service.submit_hr_assessment("PERF101", hr_submission, hr_user)

            # Human score: Lead is 80.0, HR is 90.0 -> average = 85.0
            assert updated_perf.role_evaluation.average_score == 85.0
            # 10% human contribution = 8.5
            assert updated_perf.role_evaluation.contribution == 8.5
            # Final Score = (80.0 * 0.90) + (85.0 * 0.10) = 72.0 + 8.5 = 80.5
            assert updated_perf.final_score == 80.5
            assert updated_perf.grade == "B"

    @pytest.mark.asyncio
    async def test_completeness_check(self):
        """Verify completeness report accurately tracks submitted vs pending roles."""
        perf = DeveloperPerformance(
            developer_id="EMP101",
            developer_name="Engineer One",
            project_id="PROJ1",
            period_type="quarter",
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            period_label="2024-Q1",
            final_score=80.0,
            grade="B",
            ai_evaluation=AIEvaluation(
                score=80.0,
                breakdown=PerformanceBreakdown(
                    code_quality=22.0,
                    delivery=18.0,
                    collaboration=14.0,
                    reliability=13.0,
                    engineering_impact=8.0,
                    engineering_judgment=5.0,
                ),
                reasoning="Strong technical execution",
                confidence="high",
            ),
            role_evaluation=RoleEvaluation(
                lead=LeadFeedback(criterion_1=4, criterion_2=4, criterion_3=4, criterion_4=4),
            ),
            confidence_level="high",
            confidence_reason="Comprehensive data points",
        )

        policy = {
            "version": "1.0.0",
            "role_weights": {"lead": 0.40, "pm": 0.30, "hr": 0.20, "qa": 0.10},
        }

        with patch.object(self.service.performance_repo, "get_by_id", new=AsyncMock(return_value=perf.model_dump())), \
             patch.object(self.service, "get_or_create_policy", new=AsyncMock(return_value=policy)):

            report = await self.service.check_human_evaluation_completeness("PERF101")
            assert report.is_complete is False
            assert "lead" in report.submitted_roles
            assert "hr" in report.pending_roles
            assert "pm" in report.pending_roles
            assert "qa" in report.pending_roles


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
