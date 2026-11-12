"""Developer performance models and auditable contribution-credit records."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, computed_field
from domain.models.performance_scoring import LegacyScoringMetadata, legacy_metadata_for_record


class PerformanceBreakdown(BaseModel):
    """Dimensional breakdown of performance score"""
    code_quality: float = Field(..., ge=0, le=25, description="Code quality score (0-25)")
    delivery: float = Field(..., ge=0, le=20, description="Delivery & execution score (0-20)")
    collaboration: float = Field(..., ge=0, le=15, description="PR & collaboration score (0-15)")
    reliability: float = Field(..., ge=0, le=15, description="Testing & reliability score (0-15)")
    engineering_impact: float = Field(..., ge=0, le=10, description="Engineering impact score (0-10)")
    engineering_judgment: float = Field(..., ge=0, le=5, description="Engineering judgment score (0-5)")


class AIEvaluation(BaseModel):
    """AI-generated evaluation of developer performance"""
    score: float = Field(..., ge=0, le=90, description="Total AI evaluation score (0-90)")
    breakdown: PerformanceBreakdown
    strengths: List[str] = Field(default_factory=list, description="Identified strengths")
    weaknesses: List[str] = Field(default_factory=list, description="Areas for improvement")
    recommendations: List[str] = Field(default_factory=list, description="Actionable recommendations")
    reasoning: str = Field(..., description="AI's reasoning for the scores")
    confidence: str = Field(..., description="Confidence level: low, medium, high")
    data_quality: Dict[str, Any] = Field(default_factory=dict, description="Quality of input data")


class RoleFeedbackCriteria(BaseModel):
    """Structured feedback criteria (1-5 scale)"""
    criterion_1: int = Field(..., ge=1, le=5)
    criterion_2: int = Field(..., ge=1, le=5)
    criterion_3: int = Field(..., ge=1, le=5)
    criterion_4: int = Field(..., ge=1, le=5)
    comments: Optional[str] = None


class PMFeedback(RoleFeedbackCriteria):
    """Product Manager feedback"""
    criterion_1: int = Field(..., ge=1, le=5, description="Requirement understanding")
    criterion_2: int = Field(..., ge=1, le=5, description="Delivery reliability")
    criterion_3: int = Field(..., ge=1, le=5, description="Communication")
    criterion_4: int = Field(..., ge=1, le=5, description="Business alignment")


class LeadFeedback(RoleFeedbackCriteria):
    """Team Lead feedback"""
    criterion_1: int = Field(..., ge=1, le=5, description="Technical skill")
    criterion_2: int = Field(..., ge=1, le=5, description="Code quality")
    criterion_3: int = Field(..., ge=1, le=5, description="Mentoring")
    criterion_4: int = Field(..., ge=1, le=5, description="Technical ownership")


class QAFeedback(RoleFeedbackCriteria):
    """QA Engineer feedback"""
    criterion_1: int = Field(..., ge=1, le=5, description="Quality focus")
    criterion_2: int = Field(..., ge=1, le=5, description="Test coverage")
    criterion_3: int = Field(..., ge=1, le=5, description="Bug response")
    criterion_4: int = Field(..., ge=1, le=5, description="Regression awareness")


class DevOpsFeedback(RoleFeedbackCriteria):
    """DevOps Engineer feedback"""
    criterion_1: int = Field(..., ge=1, le=5, description="Deployment quality")
    criterion_2: int = Field(..., ge=1, le=5, description="CI/CD compliance")
    criterion_3: int = Field(..., ge=1, le=5, description="Monitoring awareness")
    criterion_4: int = Field(..., ge=1, le=5, description="Incident response")


class CEOFeedback(RoleFeedbackCriteria):
    """CEO feedback"""
    criterion_1: int = Field(..., ge=1, le=5, description="Business impact")
    criterion_2: int = Field(..., ge=1, le=5, description="Innovation")
    criterion_3: int = Field(..., ge=1, le=5, description="Company alignment")
    criterion_4: int = Field(..., ge=1, le=5, description="Leadership potential")


class HRFeedback(RoleFeedbackCriteria):
    """HR feedback with enterprise rubric support"""
    criterion_1: Optional[int] = Field(None, ge=1, le=5, description="Professional conduct (1-5 or 1-4)")
    criterion_2: Optional[int] = Field(None, ge=1, le=5, description="Workplace ethics (1-5 or 1-4)")
    criterion_3: Optional[int] = Field(None, ge=1, le=5, description="Policy compliance (1-5 or 1-4)")
    criterion_4: Optional[int] = Field(None, ge=1, le=5, description="Workplace accountability (1-5 or 1-4)")
    assessment_id: Optional[str] = None
    status: Optional[str] = "submitted"
    dimensions: Optional[Dict[str, Any]] = None
    normalized_score: Optional[float] = None
    policy_version: Optional[str] = None
    evaluator_id: Optional[str] = None
    evaluator_name: Optional[str] = None
    submitted_at: Optional[datetime] = None


class RoleEvaluation(BaseModel):
    """Combined role feedback evaluation"""
    pm: Optional[PMFeedback] = None
    lead: Optional[LeadFeedback] = None
    qa: Optional[QAFeedback] = None
    devops: Optional[DevOpsFeedback] = None
    ceo: Optional[CEOFeedback] = None
    hr: Optional[HRFeedback] = None
    
    average_score: float = Field(default=0, ge=0, le=100, description="Average role score (0-100)")
    contribution: float = Field(default=0, ge=0, le=10, description="Role contribution (0-10)")


class ContributionCredit(BaseModel):
    """Hybrid contribution signal with evidence, AI, and limitations."""
    methodology_version: str
    score: float = Field(..., ge=0, le=100)
    confidence: str
    components: Dict[str, Optional[float]] = Field(default_factory=dict)
    evidence_counts: Dict[str, int] = Field(default_factory=dict)
    missing_evidence: List[str] = Field(default_factory=list)
    is_advisory_only: bool = True


class DeveloperPerformance(BaseModel):
    """Complete developer performance evaluation"""
    id: Optional[str] = None
    developer_id: str = Field(..., description="User ID of the developer")
    developer_name: str = Field(..., description="Name of the developer")
    project_id: str = Field(..., description="Project ID")
    
    # Period
    period_type: str = Field(..., description="sprint, month, quarter")
    period_start: datetime
    period_end: datetime
    period_label: str = Field(..., description="e.g., 'Sprint-23', 'Q1-2024'")
    
    # AI explanation (advisory; not the authoritative credit)
    ai_evaluation: AIEvaluation
    
    # Optional human feedback
    role_evaluation: RoleEvaluation
    
    # Final Score
    final_score: float = Field(..., ge=0, le=100, description="Total performance score (0-100)")
    contribution_credit: Optional[ContributionCredit] = None
    credit_history: List[Dict[str, Any]] = Field(default_factory=list)
    credit_status: str = Field(default="advisory", description="advisory, appealed, reviewed")
    appeal: Optional[Dict[str, Any]] = None
    hr_assessment: Optional[Dict[str, Any]] = None
    human_evaluation_policy_version: Optional[str] = None
    grade: str = Field(..., description="A+, A, B+, B, C+, C, D, F")
    
    # Trend Analysis
    previous_score: Optional[float] = None
    score_change: Optional[float] = None
    trend: Optional[str] = Field(None, description="improving, declining, stable")
    
    # Confidence
    confidence_level: str = Field(..., description="low, medium, high")
    confidence_reason: str = Field(..., description="Reason for confidence level")
    data_points: Dict[str, int] = Field(default_factory=dict, description="Amount of data analyzed")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    evaluated_by: str = Field(default="system", description="Who triggered the evaluation")

    @computed_field(return_type=LegacyScoringMetadata)
    @property
    def scoring(self) -> LegacyScoringMetadata:
        """Read-only compatibility metadata; legacy numbers are never canonical evidence."""
        return legacy_metadata_for_record(self)


class DeveloperPerformanceCreate(BaseModel):
    """Request to create performance evaluation"""
    developer_id: str
    project_id: str
    period_type: str = "sprint"
    period_start: datetime
    period_end: datetime
    period_label: str
    include_role_feedback: bool = True


class DeveloperPerformanceTrend(BaseModel):
    """Historical trend data"""
    developer_id: str
    developer_name: str
    scores: List[Dict[str, Any]] = Field(default_factory=list, description="Historical scores")
    trend: str = Field(..., description="Overall trend direction")
    current_score: float
    average_score: float
    best_score: float
    worst_score: float
