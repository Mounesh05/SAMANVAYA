"""
Tests for Performance API HR Data Filtering (GAP 2)

Verifies:
- HR users receive filtered performance outcomes without technical evidence
- Engineering users receive complete performance data including AI evaluation details
- Raw technical evidence is excluded from HR views
"""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime
from domain.schemas.hr_views import PerformanceOutcomeHR


class TestPerformanceHRFiltering:
    """Test performance data filtering for HR users."""
    
    def test_performance_outcome_hr_excludes_technical_evidence(self):
        """HR view should exclude raw evidence, code diffs, CI/CD logs."""
        performance_data = {
            "_id": "PERF001",
            "developer_id": "EMP001",
            "developer_name": "John Doe",
            "period_label": "2024-Q1",
            "final_score": 85.5,
            "grade": "B+",
            "dimension_scores": {
                "code_quality": 22.0,
                "delivery": 18.0,
                "collaboration": 13.0,
            },
            "overall_summary": "Strong performance this quarter",
            "evaluated_by": "LEAD001",
            "created_at": datetime.now(),
            # Technical fields that should be excluded
            "raw_evidence": {
                "pr_diffs": "SENSITIVE CODE DIFF",
                "commits": "Detailed commit history",
            },
            "github_data": {
                "prs": ["PR #123", "PR #124"],
                "commits": 50,
            },
            "ai_evaluation": {
                "detailed_analysis": "Technical scoring breakdown",
                "recommendations": ["Add more unit tests", "Improve documentation"],
            },
        }
        
        hr_view = PerformanceOutcomeHR.from_performance(performance_data)
        
        # Should have high-level fields
        assert hr_view.evaluation_id == "PERF001"
        assert hr_view.employee_id == "EMP001"
        assert hr_view.employee_name == "John Doe"
        assert hr_view.period == "2024-Q1"
        assert hr_view.overall_score == 85.5
        assert hr_view.grade == "B+"
        assert hr_view.rating == "Meets Expectations"
        
        # Should have dimension scores (high-level)
        assert hr_view.dimension_scores is not None
        assert "code_quality" in hr_view.dimension_scores
        
        # Should have development recommendations
        assert hr_view.development_recommendations is not None
        
        # Verify technical fields are NOT in the model
        hr_dict = hr_view.model_dump()
        assert "raw_evidence" not in hr_dict
        assert "github_data" not in hr_dict
        assert "pr_diffs" not in hr_dict
        assert "commit_messages" not in hr_dict
        assert "cicd_logs" not in hr_dict
    
    def test_performance_rating_conversion(self):
        """Test score to rating conversion for HR view."""
        # Exceeds Expectations (90+)
        assert PerformanceOutcomeHR._score_to_rating(95.0) == "Exceeds Expectations"
        assert PerformanceOutcomeHR._score_to_rating(90.0) == "Exceeds Expectations"
        
        # Meets Expectations (70-89)
        assert PerformanceOutcomeHR._score_to_rating(85.0) == "Meets Expectations"
        assert PerformanceOutcomeHR._score_to_rating(70.0) == "Meets Expectations"
        
        # Below Expectations (<70)
        assert PerformanceOutcomeHR._score_to_rating(65.0) == "Below Expectations"
        assert PerformanceOutcomeHR._score_to_rating(50.0) == "Below Expectations"
        
        # None
        assert PerformanceOutcomeHR._score_to_rating(None) is None
    
    def test_performance_outcome_includes_role_feedback_summaries(self):
        """HR view should include role feedback comments (not technical criteria)."""
        performance_data = {
            "_id": "PERF001",
            "developer_id": "EMP001",
            "developer_name": "Jane Smith",
            "period_label": "2024-Q1",
            "final_score": 88.0,
            "grade": "B+",
            "role_feedback": {
                "pm": {
                    "criterion_1": 4,  # Technical rating - HR doesn't need
                    "criterion_2": 5,
                    "comments": "Excellent delivery and communication",
                },
                "lead": {
                    "criterion_1": 4,
                    "criterion_2": 5,
                    "comments": "Strong technical skills and mentoring",
                },
            },
        }
        
        hr_view = PerformanceOutcomeHR.from_performance(performance_data)
        
        # Should have role feedback summaries (comments only)
        assert hr_view.role_feedback_summary is not None
        assert "pm" in hr_view.role_feedback_summary
        assert hr_view.role_feedback_summary["pm"] == "Excellent delivery and communication"
        assert "lead" in hr_view.role_feedback_summary
        
        # Technical criteria should not be in HR view
        hr_dict = hr_view.model_dump()
        assert "criterion_1" not in str(hr_dict)
        assert "criterion_2" not in str(hr_dict)
    
    @pytest.mark.asyncio
    async def test_get_developer_performance_filters_for_hr(self, monkeypatch):
        """Get developer performance endpoint should return filtered data for HR users."""
        from api.routes import performance
        from domain.services.performance_service import PerformanceService
        
        hr_user = {
            "employee_id": "HR001",
            "role": "HR",
            "is_admin": False,
            "designation": "HR_MANAGER",
        }
        
        mock_performance = {
            "_id": "PERF001",
            "developer_id": "EMP001",
            "developer_name": "Developer One",
            "period_label": "2024-Q1",
            "final_score": 82.0,
            "grade": "B",
            "dimension_scores": {"code_quality": 20.0},
            "raw_evidence": {"pr_diffs": "SENSITIVE"},  # Should be filtered
            "github_data": {"commits": 40},  # Should be filtered
        }
        
        mock_service = AsyncMock(spec=PerformanceService)
        mock_service.get_developer_performance = AsyncMock(return_value=mock_performance)
        
        with patch.object(performance, 'PerformanceService', return_value=mock_service):
            result = await performance.get_developer_performance("EMP001", user=hr_user)
        
        # Should return PerformanceOutcomeHR
        assert isinstance(result, PerformanceOutcomeHR)
        assert result.evaluation_id == "PERF001"
        assert result.overall_score == 82.0
        
        # Technical fields should not be in the response
        result_dict = result.model_dump()
        assert "raw_evidence" not in result_dict
        assert "github_data" not in result_dict
        assert "pr_diffs" not in result_dict
    
    @pytest.mark.asyncio
    async def test_get_developer_performance_full_data_for_engineering(self, monkeypatch):
        """Get developer performance should return complete data for engineering users."""
        from api.routes import performance
        from domain.services.performance_service import PerformanceService
        from domain.models.developer_performance import (
            DeveloperPerformance,
            AIEvaluation,
            PerformanceBreakdown,
            RoleEvaluation
        )
        from datetime import datetime
        
        lead_user = {
            "employee_id": "LEAD001",
            "role": "LEAD",
            "is_admin": False,
            "team_id": "TEAM001",
        }
        
        mock_performance = DeveloperPerformance(
            developer_id="EMP001",
            developer_name="Developer One",
            project_id="PROJ001",
            period_type="quarter",
            period_start=datetime.utcnow(),
            period_end=datetime.utcnow(),
            period_label="2024-Q1",
            final_score=82.0,
            grade="B",
            ai_evaluation=AIEvaluation(
                score=75.0,
                breakdown=PerformanceBreakdown(
                    code_quality=20.0,
                    delivery=15.0,
                    collaboration=12.0,
                    reliability=13.0,
                    engineering_impact=10.0,
                    engineering_judgment=5.0,
                ),
                reasoning="Solid engineering delivery",
                confidence="high",
            ),
            role_evaluation=RoleEvaluation(average_score=70.0, contribution=7.0),
            confidence_level="high",
            confidence_reason="Comprehensive data points",
            evaluated_by="LEAD001",
        )
        
        mock_service = AsyncMock(spec=PerformanceService)
        mock_service.get_developer_performance = AsyncMock(return_value=mock_performance)
        
        # Mock verify_can_view_user_tasks
        async def mock_verify(*args, **kwargs):
            pass
        
        with patch.object(performance, 'PerformanceService', return_value=mock_service), \
             patch.object(performance, 'verify_can_view_user_tasks', new=mock_verify):
            result = await performance.get_developer_performance("EMP001", user=lead_user)
        
        # Should return full DeveloperPerformance object
        assert isinstance(result, DeveloperPerformance)
        assert result.developer_id == "EMP001"


class TestPerformanceTechnicalFieldExclusions:
    """Test specific technical field exclusions from HR performance view."""
    
    def test_pr_diffs_excluded(self):
        """PR diffs should not be in HR view."""
        performance = {
            "_id": "PERF001",
            "developer_id": "EMP001",
            "developer_name": "Test",
            "period_label": "2024-Q1",
            "final_score": 80.0,
            "pr_diffs": "SENSITIVE CODE CHANGES",
        }
        
        hr_view = PerformanceOutcomeHR.from_performance(performance)
        hr_dict = hr_view.model_dump()
        
        assert "pr_diffs" not in hr_dict
    
    def test_commit_messages_excluded(self):
        """Commit messages should not be in HR view."""
        performance = {
            "_id": "PERF001",
            "developer_id": "EMP001",
            "developer_name": "Test",
            "period_label": "2024-Q1",
            "final_score": 80.0,
            "commit_messages": ["fix: critical bug in auth", "feat: new API endpoint"],
        }
        
        hr_view = PerformanceOutcomeHR.from_performance(performance)
        hr_dict = hr_view.model_dump()
        
        assert "commit_messages" not in hr_dict
    
    def test_cicd_logs_excluded(self):
        """CI/CD logs should not be in HR view."""
        performance = {
            "_id": "PERF001",
            "developer_id": "EMP001",
            "developer_name": "Test",
            "period_label": "2024-Q1",
            "final_score": 80.0,
            "cicd_logs": "Build failed: test_auth.py line 45",
        }
        
        hr_view = PerformanceOutcomeHR.from_performance(performance)
        hr_dict = hr_view.model_dump()
        
        assert "cicd_logs" not in hr_dict
    
    def test_code_review_comments_excluded(self):
        """Code review comments should not be in HR view."""
        performance = {
            "_id": "PERF001",
            "developer_id": "EMP001",
            "developer_name": "Test",
            "period_label": "2024-Q1",
            "final_score": 80.0,
            "code_review_comments": ["LGTM", "Please refactor this function"],
        }
        
        hr_view = PerformanceOutcomeHR.from_performance(performance)
        hr_dict = hr_view.model_dump()
        
        assert "code_review_comments" not in hr_dict

    @pytest.mark.asyncio
    async def test_get_developer_dashboard_rejects_ceo(self, monkeypatch):
        """get_developer_dashboard rejects requests for CEO with 400 Bad Request."""
        from api.routes import performance
        from repositories.user_repository import UserRepository
        from fastapi import HTTPException

        async def mock_find_by_employee_id(self, emp_id):
            if emp_id == "DEMO-CEO":
                return {"employee_id": "DEMO-CEO", "role": "CEO"}
            return None

        monkeypatch.setattr(UserRepository, "find_by_employee_id", mock_find_by_employee_id)

        caller = {"employee_id": "DEMO-HR", "role": "HR", "is_admin": False}

        with pytest.raises(HTTPException) as exc_info:
            await performance.get_developer_dashboard("DEMO-CEO", periods=6, user=caller)

        assert exc_info.value.status_code == 400
        assert "CEO is an executive and is not evaluated" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_developer_dashboard_rejects_hr(self, monkeypatch):
        """get_developer_dashboard rejects requests for HR with 400 Bad Request."""
        from api.routes import performance
        from repositories.user_repository import UserRepository
        from fastapi import HTTPException

        async def mock_find_by_employee_id(self, emp_id):
            if emp_id == "DEMO-HR":
                return {"employee_id": "DEMO-HR", "role": "HR"}
            return None

        monkeypatch.setattr(UserRepository, "find_by_employee_id", mock_find_by_employee_id)

        caller = {"employee_id": "DEMO-HR", "role": "HR", "is_admin": False}

        with pytest.raises(HTTPException) as exc_info:
            await performance.get_developer_dashboard("DEMO-HR", periods=6, user=caller)

        assert exc_info.value.status_code == 400
        assert "HR personnel are evaluators and are not evaluated" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_evaluate_developer_rejects_ceo_and_hr(self, monkeypatch):
        """evaluate_developer_performance rejects evaluations targeting CEO or HR."""
        from api.routes import performance
        from repositories.user_repository import UserRepository
        from fastapi import HTTPException

        async def mock_find_by_employee_id(self, emp_id):
            if emp_id == "DEMO-CEO":
                return {"employee_id": "DEMO-CEO", "role": "CEO"}
            return None

        monkeypatch.setattr(UserRepository, "find_by_employee_id", mock_find_by_employee_id)

        admin_caller = {"employee_id": "ADMIN1", "role": "CEO", "is_admin": True}

        with pytest.raises(HTTPException) as exc_info:
            await performance.evaluate_developer_performance(
                developer_id="DEMO-CEO",
                developer_name="Demo CEO",
                period="2026-Q3",
                user=admin_caller,
            )

        assert exc_info.value.status_code == 400
        assert "Cannot evaluate employee DEMO-CEO with role CEO" in exc_info.value.detail


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
