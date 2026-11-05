"""
HR-Safe Data Views
Filtered response models that exclude technical/engineering data from HR users.
"""

from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import date, datetime


class EmployeeHRView(BaseModel):
    """HR-safe employee view - NO technical/engineering data."""
    employee_id: str
    name: str
    email: str
    dept: str
    designation: Optional[str] = None
    role: str
    reporting_manager_id: Optional[str] = None
    current_team_id: Optional[str] = None  # View only
    employment_status: str = "active"
    employment_type: Optional[str] = None
    joining_date: Optional[date] = None
    location: Optional[str] = None
    is_active: bool = True
    created_at: Optional[str] = None
    
    # EXCLUDED from HR view:
    # - github_username (technical)
    # - project_ids (engineering detail)
    # - is_admin (security detail)
    # - task history (engineering detail)
    # - password hashes (security)
    
    @classmethod
    def from_employee(cls, employee: dict) -> "EmployeeHRView":
        """Create HR view from full employee record."""
        return cls(
            employee_id=employee.get("employee_id", ""),
            name=employee.get("name", "Unknown"),
            email=employee.get("email", ""),
            dept=employee.get("dept", ""),
            designation=employee.get("designation"),
            role=employee.get("role", ""),
            reporting_manager_id=employee.get("reporting_manager_id"),
            current_team_id=employee.get("team_id"),
            employment_status="active" if employee.get("is_active", True) else "inactive",
            employment_type=employee.get("employment_type"),
            joining_date=employee.get("joining_date"),
            location=employee.get("location"),
            is_active=employee.get("is_active", True),
            created_at=employee.get("created_at")
        )


class PerformanceOutcomeHR(BaseModel):
    """HR-approved performance outcome - NO raw technical evidence."""
    evaluation_id: str
    employee_id: str
    employee_name: str
    period: str
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    overall_score: Optional[float] = None
    grade: Optional[str] = None  # A+, A, B+, B, C, D, F
    rating: Optional[str] = None  # Exceeds/Meets/Below Expectations
    dimension_scores: Optional[Dict[str, float]] = None  # High-level scores only
    final_feedback: Optional[str] = None  # Summary, no code details
    reviewed_by: Optional[str] = None
    review_date: Optional[datetime] = None
    manager_recommendation: Optional[str] = None
    development_recommendations: Optional[List[str]] = None
    promotion_consideration: Optional[str] = None
    role_feedback_summary: Optional[Dict[str, str]] = None  # PM, Lead, QA feedback summaries
    
    # EXCLUDED from HR view:
    # - raw_evidence (technical details)
    # - github_data (code, PRs, commits)
    # - pr_diffs (source code)
    # - commit_messages (technical details)
    # - cicd_logs (technical infrastructure)
    # - code_review_comments (technical details)
    # - test_failures (technical details)
    # - ai_evaluation.detailed_analysis (technical scoring breakdown)
    
    @classmethod
    def from_performance(cls, performance: dict) -> "PerformanceOutcomeHR":
        """Create HR-safe view from full performance evaluation."""
        # Extract high-level dimension scores only
        dimension_scores = {}
        if performance.get("dimension_scores"):
            dimension_scores = {
                k: v for k, v in performance["dimension_scores"].items()
            }
        
        # Extract role feedback summaries (comments only, no technical criteria)
        role_feedback_summary = {}
        if performance.get("role_feedback"):
            for role, feedback in performance["role_feedback"].items():
                if feedback and feedback.get("comments"):
                    role_feedback_summary[role] = feedback["comments"]
        
        # Extract development recommendations from AI evaluation
        dev_recommendations = []
        if performance.get("ai_evaluation"):
            ai_eval = performance["ai_evaluation"]
            if isinstance(ai_eval, dict):
                # Get recommendations if available
                if ai_eval.get("recommendations"):
                    dev_recommendations = ai_eval["recommendations"]
                elif ai_eval.get("summary"):
                    dev_recommendations = [ai_eval["summary"]]
        
        return cls(
            evaluation_id=performance.get("_id", performance.get("id", "")),
            employee_id=performance.get("developer_id", ""),
            employee_name=performance.get("developer_name", "Unknown"),
            period=performance.get("period_label", ""),
            period_start=performance.get("period_start"),
            period_end=performance.get("period_end"),
            overall_score=performance.get("final_score"),
            grade=performance.get("grade"),
            rating=cls._score_to_rating(performance.get("final_score")),
            dimension_scores=dimension_scores,
            final_feedback=performance.get("overall_summary"),
            reviewed_by=performance.get("evaluated_by"),
            review_date=performance.get("created_at"),
            manager_recommendation=performance.get("manager_notes"),
            development_recommendations=dev_recommendations,
            promotion_consideration=performance.get("promotion_notes"),
            role_feedback_summary=role_feedback_summary
        )
    
    @staticmethod
    def _score_to_rating(score: Optional[float]) -> Optional[str]:
        """Convert numeric score to HR rating category."""
        if score is None:
            return None
        if score >= 90:
            return "Exceeds Expectations"
        elif score >= 70:
            return "Meets Expectations"
        else:
            return "Below Expectations"


class AIRunHRView(BaseModel):
    """HR-safe AI run view - NO technical evidence or debugging details."""
    run_id: str
    agent_type: str
    status: str
    execution_time_ms: float
    triggered_by: str
    created_at: Optional[datetime] = None
    
    # Output summary only - NO technical details
    summary: Optional[str] = None
    recommendations: Optional[List[str]] = None
    risk_level: Optional[str] = None
    confidence: Optional[float] = None
    
    # EXCLUDED from HR view:
    # - input_data.evidence (contains PR diffs, commits, code)
    # - output_data.raw_evidence (technical details)
    # - output_data.agent_history (system internals)
    # - output_data.errors (technical debugging)
    # - output_data.github_data (code details)
    # - output_data.cicd_logs (infrastructure)
    
    @classmethod
    def from_ai_run(cls, run: dict) -> "AIRunHRView":
        """Create HR-safe view from full AI run."""
        output_data = run.get("output_data", {}) or {}
        
        return cls(
            run_id=str(run.get("_id", run.get("id", ""))),
            agent_type=run.get("agent_type", ""),
            status=run.get("status", ""),
            execution_time_ms=run.get("execution_time_ms", 0.0),
            triggered_by=run.get("triggered_by", ""),
            created_at=run.get("created_at"),
            summary=output_data.get("analysis"),
            recommendations=output_data.get("recommendations"),
            risk_level=output_data.get("risk_level"),
            confidence=output_data.get("confidence")
        )
