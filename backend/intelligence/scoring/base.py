"""
BaseScoringAgent — Abstract base class enforcing the common scoring contract
for all specialist engineering intelligence agents.

Lifecycle:
    1. collect_evidence()       -> Filters & aggregates dimension-specific evidence
    2. calculate_metrics()      -> Deterministic metric extraction (NO LLM numbers)
    3. calculate_score()        -> Applies bounded mathematical formulas to metrics
    4. generate_explanation()   -> LLM interpretation/recommendations of deterministic results
    5. validate_score()         -> Enforces 0 <= score <= 100, confidence bounds, audit integrity
    6. evaluate()               -> Full orchestration returning an EmployeeScore
"""

from abc import ABC, abstractmethod
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    EmployeeScore,
    SubscoreBreakdown,
    EvidenceReference,
    EvaluationPeriod,
    ScoreStatus,
)
from .engine import ScoringEngine
from .config import SCORING_VERSION

logger = logging.getLogger("samanvaya.scoring.base")


class BaseScoringAgent(ABC):
    """
    Standard interface for all specialist scoring agents.
    Every agent evaluates strictly ONE engineering dimension.
    """

    def __init__(self, agent_id: str, score_type: str, config: Dict[str, Any]):
        self.agent_id = agent_id
        self.score_type = score_type
        self.config = config
        self.scoring_version = SCORING_VERSION

    @abstractmethod
    def collect_evidence(
        self,
        employee_context: Dict[str, Any],
        period: EvaluationPeriod,
    ) -> List[Dict[str, Any]]:
        """
        Extract only dimension-specific evidence relevant to this agent.
        Must respect time boundaries and ignore unrelated events.
        """
        pass

    @abstractmethod
    def calculate_metrics(
        self,
        evidence_items: List[Dict[str, Any]],
        period: EvaluationPeriod,
    ) -> Dict[str, Any]:
        """
        Derive objective, deterministic metrics from raw evidence.
        The LLM is NOT involved in this step.
        """
        pass

    @abstractmethod
    def calculate_score(
        self,
        metrics: Dict[str, Any],
        evidence_items: List[Dict[str, Any]],
    ) -> Tuple[Optional[float], Dict[str, SubscoreBreakdown], List[EvidenceReference], float]:
        """
        Convert metrics into bounded numeric score and subscores.
        Returns:
            (total_score, subscore_breakdown_dict, evidence_references, confidence)
        """
        pass

    def generate_deterministic_explanation(
        self,
        score: Optional[float],
        subscores: Dict[str, SubscoreBreakdown],
        metrics: Dict[str, Any],
        evidence_items: List[Dict[str, Any]],
        employee_name: str,
        period: EvaluationPeriod,
    ) -> Tuple[str, List[str], List[str], List[str]]:
        """Fallback deterministic explanation generator."""
        if score is None:
            return (
                f"Insufficient evidence available to evaluate {self.score_type} during {period.start_date} to {period.end_date}.",
                [],
                ["No recorded activity in this dimension during the period"],
                [f"Ensure work in {self.score_type} is tracked through monitored repositories/tools."],
            )

        analysis = (
            f"Evaluated {employee_name} for {self.score_type} in period {period.start_date} to {period.end_date}. "
            f"Achieved dimension score of {score:.1f}/100 across {len(evidence_items)} evidence items."
        )
        strengths = [
            f"Solid performance in {name} ({sub.score:.1f}/{sub.max_score:.1f})"
            for name, sub in subscores.items()
            if sub.score >= (0.75 * sub.max_score)
        ]
        weaknesses = [
            f"Growth opportunity in {name} ({sub.score:.1f}/{sub.max_score:.1f})"
            for name, sub in subscores.items()
            if sub.score < (0.65 * sub.max_score)
        ]
        recommendations = [
            f"Focus on improving {name}: {sub.explanation}"
            for name, sub in subscores.items()
            if sub.score < (0.65 * sub.max_score)
        ][:3]

        return analysis, strengths, weaknesses, recommendations

    async def generate_explanation(
        self,
        score: Optional[float],
        subscores: Dict[str, SubscoreBreakdown],
        metrics: Dict[str, Any],
        evidence_items: List[Dict[str, Any]],
        employee_name: str,
        period: EvaluationPeriod,
    ) -> Tuple[str, List[str], List[str], List[str]]:
        """
        LLM synthesizes narrative analysis, strengths, weaknesses, and recommendations.
        Default implementation returns deterministic explanation.
        """
        return self.generate_deterministic_explanation(
            score, subscores, metrics, evidence_items, employee_name, period
        )

    def validate_score(self, score_result: EmployeeScore) -> bool:
        """
        Validates score bounds (0 <= score <= 100), confidence bounds, and consistency.
        """
        if score_result.score is not None:
            if not (0.0 <= score_result.score <= 100.0):
                logger.error(
                    "Score out of bounds for %s: %s",
                    score_result.employee_id,
                    score_result.score,
                )
                return False
        if not (0.0 <= score_result.confidence <= 1.0):
            logger.error(
                "Confidence out of bounds for %s: %s",
                score_result.employee_id,
                score_result.confidence,
            )
            return False
        return True

    async def evaluate(
        self,
        employee_id: str,
        employee_name: str,
        employee_context: Optional[Dict[str, Any]] = None,
        period: Optional[EvaluationPeriod] = None,
        skip_llm: bool = False,
        evidence_data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> EmployeeScore:
        """
        Complete execution pipeline for an individual employee evaluation.
        """
        if employee_context is None and evidence_data is not None:
            employee_context = evidence_data
        if employee_context is None:
            employee_context = {}
        if period is None:
            period = EvaluationPeriod(start_date="2026-09-01", end_date="2026-09-30", label="2026-09")

        import os
        use_fast = skip_llm or (os.environ.get("FAST_EVAL") == "1")
        t0 = time.time()
        logger.info(
            "[%s] Starting evaluation for %s (%s) period=[%s to %s]",
            self.agent_id,
            employee_id,
            employee_name,
            period.start_date,
            period.end_date,
        )

        try:
            # 1. Collect evidence
            evidence_items = self.collect_evidence(employee_context, period)
            min_threshold = self.config.get("min_evidence_threshold", 1)

            # Check for missing/insufficient data
            if not evidence_items or len(evidence_items) < min_threshold:
                logger.info(
                    "[%s] Insufficient evidence (%d items) for employee %s",
                    self.agent_id,
                    len(evidence_items) if evidence_items else 0,
                    employee_id,
                )
                return EmployeeScore(
                    employee_id=employee_id,
                    agent=self.agent_id,
                    score_type=self.score_type,
                    score=None,
                    evaluation_period=period,
                    subscores={},
                    subscore_details={},
                    metrics={"evidence_count": len(evidence_items) if evidence_items else 0},
                    evidence=[],
                    confidence=0.0,
                    status="insufficient_evidence",
                    status_reason=f"No applicable {self.score_type} evidence in the evaluated period.",
                    analysis=f"No relevant {self.score_type} data was recorded for {employee_name} during {period.start_date} to {period.end_date}.",
                    strengths=[],
                    weaknesses=[],
                    recommendations=[f"Record contributions to {self.score_type} in tracked source systems."],
                    scoring_version=self.scoring_version,
                )

            # 2. Extract deterministic metrics
            metrics = self.calculate_metrics(evidence_items, period)

            # 3. Compute score and subscores
            raw_score, subscores_dict, evidence_refs, confidence = self.calculate_score(
                metrics, evidence_items
            )

            # Clamp total score
            final_score = ScoringEngine.clamp(raw_score) if raw_score is not None else None

            # 4. Generate narrative & explanation (fast deterministic or LLM)
            if use_fast:
                analysis, strengths, weaknesses, recommendations = self.generate_deterministic_explanation(
                    final_score,
                    subscores_dict,
                    metrics,
                    evidence_items,
                    employee_name,
                    period,
                )
            else:
                analysis, strengths, weaknesses, recommendations = await self.generate_explanation(
                    final_score,
                    subscores_dict,
                    metrics,
                    evidence_items,
                    employee_name,
                    period,
                )

            # Build simple subscore map
            subscores_simple = {k: v.score for k, v in subscores_dict.items()}

            result = EmployeeScore(
                employee_id=employee_id,
                agent=self.agent_id,
                score_type=self.score_type,
                score=final_score,
                evaluation_period=period,
                subscores=subscores_simple,
                subscore_details=subscores_dict,
                metrics=metrics,
                evidence=evidence_refs,
                confidence=confidence,
                status="complete",
                analysis=analysis,
                strengths=strengths,
                weaknesses=weaknesses,
                recommendations=recommendations,
                scoring_version=self.scoring_version,
            )

            self.validate_score(result)
            ms = round((time.time() - t0) * 1000, 1)
            logger.info(
                "[%s] Completed evaluation for %s in %.0fms: score=%s confidence=%.2f",
                self.agent_id,
                employee_id,
                ms,
                final_score,
                confidence,
            )
            return result

        except Exception as exc:
            logger.exception("[%s] Evaluation error for %s: %s", self.agent_id, employee_id, exc)
            return EmployeeScore(
                employee_id=employee_id,
                agent=self.agent_id,
                score_type=self.score_type,
                score=None,
                evaluation_period=period,
                confidence=0.0,
                status="failed",
                status_reason=str(exc),
                analysis=f"Evaluation failed due to internal error: {exc}",
                scoring_version=self.scoring_version,
            )
