"""
Tests for Performance API HR Data Filtering (GAP 2)

Verifies:
- HR users receive filtered performance outcomes without technical evidence
- Engineering users receive complete performance data including AI evaluation details
- Raw technical evidence is excluded from HR views
"""

import pytest
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
    
    @pytest.mark.anyio
    async def test_get_developer_performance_filters_for_hr(self, mock_db, monkeypatch):
        from core import database
        from api.routes import performance
        from test_performance_scoring_compatibility import assessment
        monkeypatch.setattr(database, "get_db", lambda: mock_db)
        await mock_db.users.insert_many([dict(employee_id="AUDIT-DEV", role="DEVELOPER", org_id="O", is_active=True),
            dict(employee_id="H", role="HR", designation="HR_MANAGER", org_id="O", is_active=True)])
        await mock_db.projects.insert_one(dict(id="AUDIT-PROJECT", org_id="O"))
        record = assessment().model_dump()
        record["ai_evaluation"]["reasoning"] = "SENSITIVE ENGINEERING SOURCE"
        await mock_db.developer_performances.insert_one(record)
        result = await performance.get_developer_performance("AUDIT-DEV", user={"employee_id": "H"})
        assert isinstance(result, PerformanceOutcomeHR)
        assert result.overall_score == 85.4 and "SENSITIVE" not in str(result.model_dump())

    @pytest.mark.anyio
    async def test_get_developer_performance_full_data_for_engineering(self, mock_db, monkeypatch):
        from core import database
        from api.routes import performance
        from domain.models.developer_performance import DeveloperPerformance
        from test_performance_scoring_compatibility import assessment
        monkeypatch.setattr(database, "get_db", lambda: mock_db)
        await mock_db.users.insert_many([dict(employee_id="AUDIT-DEV", role="DEVELOPER", org_id="O", is_active=True),
            dict(employee_id="L", role="LEAD", org_id="O", is_active=True, project_ids=["AUDIT-PROJECT"])])
        await mock_db.projects.insert_one(dict(id="AUDIT-PROJECT", org_id="O"))
        await mock_db.developer_performances.insert_one(assessment().model_dump())
        result = await performance.get_developer_performance("AUDIT-DEV", user={"employee_id": "L"})
        assert isinstance(result, DeveloperPerformance) and result.developer_id == "AUDIT-DEV"


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

    @pytest.mark.anyio
    @pytest.mark.parametrize("subject_role", ["CEO", "HR"])
    async def test_nonengineering_history_does_not_fabricate_a_current_rating(self, mock_db, monkeypatch, subject_role):
        from core import database
        from api.routes import performance
        monkeypatch.setattr(database, "get_db", lambda: mock_db)
        await mock_db.users.insert_many([
            dict(employee_id="SUBJECT", role=subject_role, org_id="O", is_active=True),
            dict(employee_id="H", role="HR", designation="HR_MANAGER", org_id="O", is_active=True)])
        result = await performance.get_developer_dashboard("SUBJECT", periods=6, user={"employee_id": "H"})
        assert result["current_performance"] is None and result["historical_trend"] == []
        assert await mock_db.developer_performances.count_documents({}) == 0

    @pytest.mark.anyio
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
