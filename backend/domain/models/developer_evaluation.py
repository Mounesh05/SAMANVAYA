"""Persisted, evidence-backed AI developer evaluations."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DeveloperEvaluation(BaseModel):
    """A completed or failed evaluation for one developer contribution."""
    
    model_config = {"protected_namespaces": ()}

    evaluation_id: str
    employee_id: str
    github_username: str
    repo_owner: str
    repo_name: str
    pr_number: int
    head_commit_sha: str
    evaluation_focus: str
    ai_provider: str
    model_name: str
    overall_score: Optional[float] = Field(default=None, ge=0, le=10)
    human_score: Optional[float] = Field(default=None, ge=1, le=10)
    dimensions: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    analysis: Optional[str] = None
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    evidence_references: List[Dict[str, Any]] = Field(default_factory=list)
    repo_info: Dict[str, Any] = Field(default_factory=dict)
    status: str = Field(default="completed")
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    evidence_manifest: Dict[str, Any] = Field(default_factory=dict)
    evidence_coverage: Dict[str, str] = Field(default_factory=dict)
    evidence_coverage_reasons: Dict[str, str] = Field(default_factory=dict)
    score_dimensions: List[str] = Field(default_factory=list)
    score_weights: Dict[str, float] = Field(default_factory=dict)
    score_coverage: Dict[str, Any] = Field(default_factory=dict)
    unsupported_references: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    schema_validated: bool = False
    evidence_validated: bool = False
    is_preliminary: bool = True
    duplicate_key: Optional[str] = None
