"""
Code Quality Report Model
Comprehensive report with separate quality and risk scores.
"""

from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Dict, Any, List, Optional, Literal, Annotated
from datetime import datetime
from intelligence.evidence.function_purpose import FunctionDiscovery


class QualityBreakdown(BaseModel):
    """Legacy advisory point contributions with a maximum total of 100."""
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


EngineScore = Annotated[int, Field(strict=True, ge=0, le=100)]
EnginePenalty = Annotated[float, Field(strict=True, ge=0, le=100, allow_inf_nan=False)]


class EngineDimensionsV1(BaseModel):
    """Independent quality indices in original 0–100 units."""
    model_config = ConfigDict(extra="forbid", strict=True)
    static_security: EngineScore
    testing: EngineScore
    complexity: EngineScore
    architecture: EngineScore
    duplication: EngineScore


class EnginePenaltiesV1(BaseModel):
    """Unweighted penalties in original 0–100 units."""
    model_config = ConfigDict(extra="forbid", strict=True)
    static_security: EnginePenalty
    testing: EnginePenalty
    complexity: EnginePenalty
    architecture: EnginePenalty
    duplication: EnginePenalty


class EngineQualityV1(BaseModel):
    """Versioned QualityEngine measurements in their original units."""
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["quality-engine-v1"] = "quality-engine-v1"
    quality_score: EngineScore
    quality_grade: Literal["A", "B", "C", "D", "F"]
    dimension_scores: EngineDimensionsV1
    penalties: EnginePenaltiesV1


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
    quality_breakdown: Optional[QualityBreakdown] = None
    quality_representation: Literal["legacy-advisory-v1", "quality-engine-v1"] = "legacy-advisory-v1"
    engine_quality: Optional[EngineQualityV1] = None
    engine_risk: Optional[Dict[str, Any]] = None
    quality_factors: List[str] = Field(default_factory=list, description="Positive quality indicators")
    
    # Risk Assessment (0-100)
    failure_risk: int = Field(..., ge=0, le=100, description="RiskEngine risk index (0-100)")
    risk_level: str = Field(..., description="critical|high|medium|low")
    risk_factors: List[str] = Field(default_factory=list, description="Risk contributors")
    
    # Evidence from Tools (Objective)
    static_analysis: Dict[str, Any] = Field(default_factory=dict)
    complexity_metrics: Dict[str, Any] = Field(default_factory=dict)
    security_findings: Dict[str, Any] = Field(default_factory=dict)
    test_metrics: Dict[str, Any] = Field(default_factory=dict)
    dependency_changes: Dict[str, Any] = Field(default_factory=dict)
    architecture_analysis: Dict[str, Any] = Field(default_factory=dict)
    function_discovery: FunctionDiscovery = Field(default_factory=FunctionDiscovery)
    
    # AI Interpretation (from Ollama)
    ai_analysis: Optional[str] = None
    ai_status: Optional[Literal["completed", "failed", "unavailable", "skipped"]] = None
    ai_errors: List[str] = Field(default_factory=list)
    critical_issues: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    review_focus: Optional[str] = None
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    
    # Metadata
    tools_used: List[str] = Field(default_factory=list)
    analysis_duration_ms: Optional[float] = None

    @model_validator(mode="after")
    def consistent_quality_representation(self):
        if self.quality_representation == "quality-engine-v1":
            if self.engine_quality is None or self.quality_breakdown is not None:
                raise ValueError("Engine v1 requires its exact engine representation and an absent legacy breakdown")
            if self.quality_score != self.engine_quality.quality_score:
                raise ValueError("The report must preserve the engine quality score")
        elif self.engine_quality is not None:
            raise ValueError("Engine measurements require an explicit quality-engine-v1 representation")
        return self
    
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
