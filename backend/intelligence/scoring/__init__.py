"""
Scoring package — common contracts and deterministic engine.
"""

from .models import (
    EmployeeScore,
    EvidenceReference,
    SubscoreBreakdown,
    EvaluationPeriod,
    AggregatedEmployeeEvaluation,
    ScoreStatus,
)
from .config import (
    CODE_QUALITY_CONFIG,
    QA_TESTING_CONFIG,
    DEVOPS_CONFIG,
    CICD_CONFIG,
    MEETING_AGILE_CONFIG,
    DEFAULT_AGGREGATION_WEIGHTS,
    SCORING_VERSION,
)
from .engine import ScoringEngine
from .base import BaseScoringAgent

__all__ = [
    "EmployeeScore",
    "EvidenceReference",
    "SubscoreBreakdown",
    "EvaluationPeriod",
    "AggregatedEmployeeEvaluation",
    "ScoreStatus",
    "CODE_QUALITY_CONFIG",
    "QA_TESTING_CONFIG",
    "DEVOPS_CONFIG",
    "CICD_CONFIG",
    "MEETING_AGILE_CONFIG",
    "DEFAULT_AGGREGATION_WEIGHTS",
    "SCORING_VERSION",
    "ScoringEngine",
    "BaseScoringAgent",
]
