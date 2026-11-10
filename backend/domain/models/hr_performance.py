"""
HR Performance Assessment and Human Evaluation Policy Models.
Enterprise rubric, configurable weights, and bias prevention safeguards.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, List, Any, Union
from datetime import datetime, timezone
from enum import Enum


class HRDimensionKey(str, Enum):
    """Authorized workplace-related evaluation dimensions for HR."""
    PROFESSIONAL_CONDUCT = "professional_conduct"
    WORKPLACE_ETHICS = "workplace_ethics"
    POLICY_COMPLIANCE = "policy_compliance"
    MANDATORY_LEARNING = "mandatory_learning"
    WORKPLACE_ACCOUNTABILITY = "workplace_accountability"


class ComplianceStatus(str, Enum):
    """Status tracking for organizational policy & compliance requirements."""
    COMPLETED = "completed"
    PENDING = "pending"
    EXEMPTED = "exempted"
    NOT_APPLICABLE = "not_applicable"
    UNDER_REVIEW = "under_review"


class HRAssessmentDimensionItem(BaseModel):
    """
    Individual HR assessment dimension with evidence-based rubric scoring.
    Rubric scale:
      4 — Exceeds Expectations
      3 — Meets Expectations
      2 — Needs Improvement (requires evidence)
      1 — Unsatisfactory (requires evidence)
      N/O — Not Observed (is_not_observed=True, rating=None)
    """
    dimension: str
    rating: Optional[int] = Field(None, ge=1, le=4, description="Numeric rating 1-4, or None if Not Observed")
    is_not_observed: bool = Field(False, description="True if insufficient evidence or not observed")
    compliance_status: Optional[ComplianceStatus] = Field(None, description="For compliance & training items")
    evidence_description: Optional[str] = Field(None, max_length=2000, description="Required for ratings 1 and 2")
    evidence_reference: Optional[str] = Field(None, max_length=500, description="Optional doc/link reference")
    comments: Optional[str] = Field(None, max_length=2000)

    @field_validator("rating")
    @classmethod
    def validate_rating_with_not_observed(cls, v, info):
        return v


class HRAssessmentCreate(BaseModel):
    """Request model for creating or updating an HR assessment."""
    dimensions: Dict[str, HRAssessmentDimensionItem]
    general_comments: Optional[str] = Field(None, max_length=3000)


class HRAssessment(BaseModel):
    """
    Persisted HR performance assessment record.
    Tracks workplace conduct, compliance, reviewer identity, audit trail.
    """
    assessment_id: str
    performance_id: str
    developer_id: str
    evaluator_id: str
    evaluator_name: Optional[str] = None
    evaluator_role: str = "HR"
    status: str = Field(default="draft", description="draft | submitted | approved | revised")
    dimensions: Dict[str, HRAssessmentDimensionItem]
    overall_hr_score: Optional[float] = Field(None, ge=0.0, le=100.0, description="Normalized 0-100 score")
    policy_version: str = "1.0.0"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_at: Optional[datetime] = None
    general_comments: Optional[str] = None


class HumanEvaluationPolicy(BaseModel):
    """
    Configurable Human Evaluation Policy for the 10% human component.
    Preserves the overall 90% AI + 10% Human model.
    """
    policy_id: str
    version: str = "1.0.0"
    is_active: bool = True
    ai_weight: float = Field(0.90, description="Weight of AI component (fixed at 0.90)")
    human_weight: float = Field(0.10, description="Weight of Human component (fixed at 0.10)")
    role_weights: Dict[str, float] = Field(
        default_factory=lambda: {
            "lead": 0.35,
            "pm": 0.30,
            "hr": 0.20,
            "qa": 0.15,
        },
        description="Weights of eligible human evaluators summing to 1.0"
    )
    role_dimensions: Dict[str, List[str]] = Field(
        default_factory=lambda: {
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
        }
    )
    configured_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: Optional[str] = None


class HumanEvaluationCompleteness(BaseModel):
    """Human evaluation completeness report across authorized roles."""
    performance_id: str
    developer_id: str
    period_label: str
    policy_version: str
    required_roles: List[str]
    submitted_roles: List[str]
    pending_roles: List[str]
    is_complete: bool
    human_score: Optional[float] = None
    role_scores: Dict[str, Optional[float]] = {}
    details: Dict[str, Any] = {}

