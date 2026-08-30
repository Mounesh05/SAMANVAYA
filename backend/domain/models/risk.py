"""
Risk domain models.
Risks are calculated by the Intelligence Engine and can be attached to any entity.
"""

from pydantic import BaseModel
from typing import Optional


class RiskFactor(BaseModel):
    """Individual risk factor contributing to overall risk score."""
    
    factor: str  # e.g., "high_complexity", "low_test_coverage"
    contribution: int  # points contributed to total risk score
    detail: str  # human-readable explanation


class Risk(BaseModel):
    """
    Risk record attached to an entity (PR, sprint, deployment, etc.).
    Calculated by Layer 5 (Intelligence Engine) with explanation from Layer 6 (AI Agents).
    """
    
    id: str
    entity_type: str  # pull_request|sprint|deployment|story|member
    entity_id: str
    project_id: str
    
    risk_level: str  # LOW|MEDIUM|HIGH|CRITICAL
    risk_score: int  # 0-100
    factors: list[RiskFactor] = []
    
    status: str = "open"  # open|acknowledged|resolved|false_positive
    created_at: str = ""
    resolved_at: Optional[str] = None
