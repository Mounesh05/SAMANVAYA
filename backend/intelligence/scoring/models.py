"""
Scoring Domain Models — Canonical schemas for employee-level specialist scoring.

Ensures evidence-first, auditable, and traceable numeric scoring across
all specialist agents.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, model_validator


ScoreStatus = Literal["complete", "insufficient_evidence", "not_applicable", "failed"]


class EvidenceReference(BaseModel):
    """Traceable link between a metric/score and the raw source item."""
    source: str = Field(..., description="Source system: github_pr, github_commit, ci_run, jira_task, etc.")
    id: str = Field(..., description="ID or key of the evidence item (e.g., 'PR-123', 'commit-sha-abc')")
    metric: str = Field(..., description="Metric key this evidence supports")
    value: Any = Field(..., description="Observed value or characteristic")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Contextual metadata for auditing")

    @model_validator(mode="before")
    @classmethod
    def remap_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "source" not in data and "evidence_type" in data:
                data["source"] = data["evidence_type"]
            if "id" not in data and "identifier" in data:
                data["id"] = str(data["identifier"])
            if "metric" not in data and "impact_dimension" in data:
                data["metric"] = data["impact_dimension"]
            if "value" not in data:
                data["value"] = data.get("details", {})
        return data

    @property
    def identifier(self) -> str:
        return self.id

    @property
    def evidence_type(self) -> str:
        return self.source

    @property
    def impact_dimension(self) -> str:
        return self.details.get("dimension") or self.metric


class SubscoreBreakdown(BaseModel):
    """Subscore dimension with points achieved, max points, and rationale."""
    name: str = Field(..., description="Dimension subscore name")
    score: float = Field(..., ge=0, description="Points scored in this sub-dimension")
    max_score: float = Field(..., gt=0, description="Maximum possible points")
    weight: float = Field(default=1.0, ge=0, description="Weight within dimension")
    explanation: Optional[str] = Field(default="", description="Why this subscore was earned")

    @model_validator(mode="before")
    @classmethod
    def clamp_subscore(cls, data: Any) -> Any:
        if isinstance(data, dict):
            sc = data.get("score")
            mx = data.get("max_score")
            if sc is not None and mx is not None and sc > mx:
                data["score"] = float(mx)
        return data


class EvaluationPeriod(BaseModel):
    """Time boundary for evidence inclusion."""
    start_date: str = Field(..., description="ISO 8601 start date (e.g., '2026-09-01')")
    end_date: str = Field(..., description="ISO 8601 end date (e.g., '2026-09-30')")
    label: Optional[str] = Field(default="custom", description="Period label, e.g., '2026-09' or '2026-Q3'")


class EmployeeScore(BaseModel):
    """
    Standardized, auditable score output produced by any specialist agent.
    """
    employee_id: str = Field(..., description="Unique employee identifier (e.g., 'EMP-001')")
    agent: str = Field(..., description="Identifier of the specialist agent (e.g., 'code_agent')")
    score_type: str = Field(..., description="Scoring dimension (e.g., 'code_quality')")
    score: Optional[float] = Field(None, ge=0, le=100, description="Numeric score 0-100 (null if insufficient evidence)")
    evaluation_period: EvaluationPeriod = Field(..., description="Evaluated time boundaries")
    subscores: Dict[str, float] = Field(default_factory=dict, description="Breakdown of subscores")
    subscore_details: Dict[str, SubscoreBreakdown] = Field(default_factory=dict, description="Detailed subscore items")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Raw extracted deterministic metrics")
    evidence: List[EvidenceReference] = Field(default_factory=list, description="Traceable evidence items")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence level 0.0 to 1.0")
    status: ScoreStatus = Field(default="complete", description="Evaluation status")
    status_reason: Optional[str] = Field(default=None, description="Reason if status is not complete")
    analysis: str = Field(default="", description="LLM/expert interpretation of deterministic metrics")
    strengths: List[str] = Field(default_factory=list, description="Identified strengths")
    weaknesses: List[str] = Field(default_factory=list, description="Areas for improvement")
    recommendations: List[str] = Field(default_factory=list, description="Actionable recommendations")
    scoring_version: str = Field(default="1.0", description="Scoring algorithm version")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @model_validator(mode="before")
    @classmethod
    def remap_legacy_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "score_type" not in data and "dimension" in data:
                data["score_type"] = data["dimension"]
            if "evaluation_period" not in data and "period" in data:
                data["evaluation_period"] = data["period"]
            if "evidence" not in data and "evidence_references" in data:
                data["evidence"] = data["evidence_references"]
            if data.get("status") == "evaluated":
                data["status"] = "complete"
        return data

    @property
    def dimension(self) -> str:
        return self.score_type

    @property
    def evidence_references(self) -> List[EvidenceReference]:
        return self.evidence

    @property
    def explanation(self) -> str:
        return self.analysis

    @property
    def period(self) -> EvaluationPeriod:
        return self.evaluation_period


class AggregatedEmployeeEvaluation(BaseModel):
    """
    Overall employee evaluation combining all specialist agent scores.
    """
    evaluation_id: str = Field(..., description="UUID for this evaluation")
    employee_id: str = Field(..., description="Employee evaluated")
    employee_name: str = Field(..., description="Employee display name")
    company_id: str = Field(..., description="Multi-tenant company/org ID")
    evaluation_period: EvaluationPeriod = Field(..., description="Evaluation time period")
    overall_score: Optional[float] = Field(None, ge=0, le=100, description="Weighted composite score")
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Overall confidence")
    grade: Optional[str] = Field(None, description="Letter grade (A+, A, B+, B, C+, C, D, F)")
    
    # Authoritative 80/20 Marks Architecture:
    # Agent Score = 80 marks | Superior Score = 20 marks | Final Score = 100 marks
    agent_score_marks: Optional[float] = Field(None, ge=0, le=80, description="Agent Score out of 80 marks (overall_score * 0.80)")
    superior_score_marks: Optional[float] = Field(None, ge=0, le=20, description="Superior Score out of 20 marks")
    final_score: Optional[float] = Field(None, ge=0, le=100, description="Final combined score out of 100 marks (Agent + Superior)")

    scores: Dict[str, Optional[float]] = Field(default_factory=dict, description="Agent dimension scores map")
    agent_scores: Dict[str, EmployeeScore] = Field(default_factory=dict, description="Full specialist score objects")
    summary: str = Field(default="", description="Executive narrative summary")
    strengths: List[str] = Field(default_factory=list, description="Consolidated strengths")
    weaknesses: List[str] = Field(default_factory=list, description="Consolidated areas for improvement")
    recommendations: List[str] = Field(default_factory=list, description="Consolidated actionable recommendations")
    weights_used: Dict[str, float] = Field(default_factory=dict, description="Weights applied for aggregation")
    scoring_version: str = Field(default="1.0")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
