"""
Scoring Engine — Deterministic mathematical utilities for scoring, normalization,
confidence calculation, missing-data handling, and score validation.

Guarantees 0 <= score <= 100 with zero silent weight drift.
"""

from typing import Dict, Any, List, Optional, Tuple
from .models import (
    EmployeeScore,
    SubscoreBreakdown,
    EvidenceReference,
    AggregatedEmployeeEvaluation,
    EvaluationPeriod,
)
from .config import DEFAULT_AGGREGATION_WEIGHTS, SCORING_VERSION


class ScoringEngine:
    """
    Central mathematical engine for computing deterministic, auditable scores.
    """

    @staticmethod
    def clamp(value: float, min_val: float = 0.0, max_val: float = 100.0) -> float:
        """Ensure a score strictly satisfies min_val <= score <= max_val."""
        if value is None:
            return 0.0
        return max(min_val, min(max_val, round(float(value), 2)))

    @staticmethod
    def normalize(
        val: float,
        in_min: float,
        in_max: float,
        out_min: float = 0.0,
        out_max: float = 100.0,
    ) -> float:
        """Linearly scale a value from [in_min, in_max] to [out_min, out_max]."""
        if in_max == in_min:
            return out_min
        ratio = (val - in_min) / (in_max - in_min)
        scaled = out_min + (ratio * (out_max - out_min))
        return ScoringEngine.clamp(scaled, out_min, out_max)

    @staticmethod
    def calculate_confidence(
        evidence_count: int,
        recommended_count: int = 5,
        time_coverage_ratio: float = 1.0,
        source_reliability: float = 1.0,
    ) -> float:
        """
        Calculate deterministic confidence based on:
        - Volume of evidence (asymptotically approaches 1.0)
        - Time coverage (e.g., did we observe activity across the full period)
        - Source reliability (e.g., direct GitHub/CI logs vs manual tasks)
        """
        if evidence_count <= 0:
            return 0.0

        # Asymptotic sample-size factor: 1 - exp(-k * n) or ratio capped at 1.0
        count_factor = min(1.0, evidence_count / max(1, recommended_count))
        # Smooth curve so even 2-3 pieces of evidence give reasonable signal
        sample_confidence = 0.4 + (0.6 * count_factor)

        # Time coverage factor (clamped between 0.5 and 1.0)
        time_factor = ScoringEngine.clamp(time_coverage_ratio, 0.3, 1.0)

        # Source reliability factor (e.g. 0.9 - 1.0)
        source_factor = ScoringEngine.clamp(source_reliability, 0.5, 1.0)

        raw_confidence = sample_confidence * time_factor * source_factor
        return round(max(0.0, min(1.0, raw_confidence)), 2)

    @staticmethod
    def validate_score(score: Optional[float]) -> bool:
        """Check if score is valid within bounds."""
        if score is None:
            return True
        return 0.0 <= score <= 100.0

    @staticmethod
    def determine_grade(score: Optional[float]) -> str:
        """Convert a 0-100 score to a letter grade."""
        if score is None:
            return "N/A"
        if score >= 95.0:
            return "A+"
        elif score >= 90.0:
            return "A"
        elif score >= 85.0:
            return "B+"
        elif score >= 80.0:
            return "B"
        elif score >= 75.0:
            return "C+"
        elif score >= 70.0:
            return "C"
        elif score >= 60.0:
            return "D"
        else:
            return "F"

    @staticmethod
    def aggregate_agent_scores(
        agent_scores: Dict[str, EmployeeScore],
        weights: Optional[Dict[str, float]] = None,
        employee_id: str = "",
        employee_name: str = "",
        company_id: str = "",
        period: Optional[EvaluationPeriod] = None,
        superior_score: Optional[float] = None,
    ) -> AggregatedEmployeeEvaluation:
        """
        Aggregates specialist agent scores using explicit, normalized weights.
        Specialist agents that returned status='insufficient_evidence' or 'not_applicable'
        are excluded from the weighted sum, and the remaining weights are renormalized
        so the employee is NOT penalized for missing data.

        Authoritative Split:
        - Agent Score    = 80 marks
        - Superior Score = 20 marks
        -----------------------------
        - Final Score    = 100 marks
        """
        import uuid
        active_weights = dict(weights or DEFAULT_AGGREGATION_WEIGHTS)
        
        valid_scores: Dict[str, float] = {}
        valid_weights: Dict[str, float] = {}
        total_confidence = 0.0
        active_agents_count = 0

        scores_summary: Dict[str, Optional[float]] = {}

        for score_type, agent_score in agent_scores.items():
            scores_summary[score_type] = agent_score.score
            if agent_score.status == "complete" and agent_score.score is not None:
                w = active_weights.get(score_type, 0.0)
                valid_scores[score_type] = agent_score.score
                valid_weights[score_type] = w
                total_confidence += agent_score.confidence
                active_agents_count += 1

        overall_score: Optional[float] = None
        weights_used: Dict[str, float] = {}

        total_weight = sum(valid_weights.values())
        if total_weight > 0 and len(valid_scores) > 0:
            # Renormalize weights among applicable dimensions
            weighted_sum = 0.0
            for st, score in valid_scores.items():
                norm_w = valid_weights[st] / total_weight
                weights_used[st] = round(norm_w, 4)
                weighted_sum += score * norm_w
            overall_score = ScoringEngine.clamp(weighted_sum)

        avg_confidence = round(total_confidence / max(1, active_agents_count), 2) if active_agents_count > 0 else 0.0

        # Authoritative 80/20 Marks Model:
        agent_score_marks: Optional[float] = None
        superior_score_marks: Optional[float] = None
        final_score: Optional[float] = None

        if overall_score is not None:
            agent_score_marks = round((overall_score / 100.0) * 80.0, 2)
            if superior_score is not None:
                if superior_score > 20.0:
                    superior_score_marks = round((superior_score / 100.0) * 20.0, 2)
                else:
                    superior_score_marks = round(float(superior_score), 2)
                final_score = round(agent_score_marks + superior_score_marks, 2)
            else:
                final_score = overall_score

        # Consolidate strengths, weaknesses, recommendations
        all_strengths: List[str] = []
        all_weaknesses: List[str] = []
        all_recommendations: List[str] = []

        for agent_score in agent_scores.values():
            all_strengths.extend(agent_score.strengths)
            all_weaknesses.extend(agent_score.weaknesses)
            all_recommendations.extend(agent_score.recommendations)

        return AggregatedEmployeeEvaluation(
            evaluation_id=f"EVAL-{uuid.uuid4().hex[:8].upper()}",
            employee_id=employee_id,
            employee_name=employee_name or employee_id,
            company_id=company_id,
            evaluation_period=period or EvaluationPeriod(start_date="N/A", end_date="N/A"),
            overall_score=overall_score,
            overall_confidence=avg_confidence,
            grade=ScoringEngine.determine_grade(final_score or overall_score),
            agent_score_marks=agent_score_marks,
            superior_score_marks=superior_score_marks,
            final_score=final_score,
            scores=scores_summary,
            agent_scores=agent_scores,
            strengths=list(dict.fromkeys(all_strengths))[:6],
            weaknesses=list(dict.fromkeys(all_weaknesses))[:6],
            recommendations=list(dict.fromkeys(all_recommendations))[:6],
            weights_used=weights_used,
            scoring_version=SCORING_VERSION,
        )
