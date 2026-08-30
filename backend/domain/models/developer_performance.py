"""
Developer Performance Models
Pure AI-driven performance evaluation with role feedback
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


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
    """HR feedback"""
    criterion_1: int = Field(..., ge=1, le=5, description="Collaboration")
    criterion_2: int = Field(..., ge=1, le=5, description="Professionalism")
    criterion_3: int = Field(..., ge=1, le=5, description="Communication skills")
    criterion_4: int = Field(..., ge=1, le=5, description="Cultural fit")


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
    
    # AI Evaluation (90%)
    ai_evaluation: AIEvaluation
    
    # Role Evaluation (10%)
    role_evaluation: RoleEvaluation
    
    # Final Score
    final_score: float = Field(..., ge=0, le=100, description="Total performance score (0-100)")
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
