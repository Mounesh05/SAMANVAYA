"""
Code Quality Report Model
Comprehensive report with separate quality and risk scores.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime


class QualityBreakdown(BaseModel):
    """Quality score breakdown by dimension."""
    correctness: int = Field(..., ge=0, le=20, description="Code correctness (0-20)")
    maintainability: int = Field(..., ge=0, le=20, description="Maintainability (0-20)")
    security: int = Field(..., ge=0, le=20, description="Security (0-20)")
    testing: int = Field(..., ge=0, le=15, description="Test coverage (0-15)")
    performance: int = Field(..., ge=0, le=10, description="Performance (0-10)")
    architecture: int = Field(..., ge=0, le=10, description="Architecture (0-10)")
    readability: int = Field(..., ge=0, le=5, description="Readability (0-5)")
    
    @property
    def total(self) -> int:
        """Calculate total quality score."""
        return (
            self.correctness +
            self.maintainability +
            self.security +
            self.testing +
            self.performance +
            self.architecture +
            self.readability
        )


class CodeQualityReport(BaseModel):
    """
    Comprehensive code quality report.
    
    Separates:
    - Code Quality (how good the code is)
    - Failure Risk (how likely it is to fail)
    """
    
    # Identification
    pr_id: str
    pr_number: int
    pr_title: str
    author: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Quality Assessment (0-100)
    quality_score: int = Field(..., ge=0, le=100, description="Overall code quality")
    quality_breakdown: QualityBreakdown
    quality_factors: List[str] = Field(default_factory=list, description="Positive quality indicators")
    
    # Risk Assessment (0-100)
    failure_risk: int = Field(..., ge=0, le=100, description="Probability of failure")
    risk_level: str = Field(..., description="critical|high|medium|low")
    risk_factors: List[str] = Field(default_factory=list, description="Risk contributors")
    
    # Evidence from Tools (Objective)
    static_analysis: Dict[str, Any] = Field(default_factory=dict)
    complexity_metrics: Dict[str, Any] = Field(default_factory=dict)
    security_findings: Dict[str, Any] = Field(default_factory=dict)
    test_metrics: Dict[str, Any] = Field(default_factory=dict)
    dependency_changes: Dict[str, Any] = Field(default_factory=dict)
    historical_data: Dict[str, Any] = Field(default_factory=dict)
    architecture_analysis: Dict[str, Any] = Field(default_factory=dict)
    
    # AI Interpretation (from Ollama)
    ai_analysis: Optional[str] = None
    critical_issues: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    review_focus: Optional[str] = None
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    
    # Metadata
    tools_used: List[str] = Field(default_factory=list)
    analysis_duration_ms: Optional[float] = None
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "pr_id": "PR-12345",
                "pr_number": 142,
                "pr_title": "Implement password reset",
                "author": "dev@example.com",
                "quality_score": 78,
                "quality_breakdown": {
                    "correctness": 18,
                    "maintainability": 15,
                    "security": 16,
                    "testing": 10,
                    "performance": 8,
                    "architecture": 8,
                    "readability": 3,
                },
                "failure_risk": 65,
                "risk_level": "medium",
                "risk_factors": [
                    "Missing expiration test",
                    "Coverage decreased by 8%",
                    "Modified critical module"
                ],
                "critical_issues": [
                    "Token expiration lacks regression testing",
                    "Coverage decreased by 8%"
                ],
                "recommendations": [
                    "Add token-expiration tests before merge",
                    "Increase test coverage for auth module",
                    "Review dependency upgrade impact"
                ],
            }
        }
    }


class CodeQualityReportResponse(BaseModel):
    """API response for code quality analysis."""
    report: CodeQualityReport
    evidence_summary: str
    analysis_complete: bool = True
    warnings: List[str] = Field(default_factory=list)
