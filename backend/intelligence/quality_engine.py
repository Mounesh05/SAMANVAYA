"""
QualityEngine — Independent Code Quality Index Calculation.

Q is calculated independently from Risk. A codebase can be:
  - High Q + Low R: clean code, small PR → ideal
  - Low Q + Low R: messy code, tiny PR → technical debt but safe to ship
  - High Q + High R: clean code, massive refactor → good quality, risky change
  - Low Q + High R: messy code, large risky change → block / mandatory review

Formula:
  Q = 100 - (w_static * S_pen + w_testing * T_pen +
              w_complexity * C_pen + w_arch * A_pen + w_dup * D_pen)

Each penalty is normalized to [0, 100] before weighting.

Uses configurable quality weights from database (with fallback to defaults).

When SAMANVAYA's own metrics are present (evidence.metrics, Python today):
  - the complexity penalty also considers readability: the share of
    function code above the cognitive complexity limit (15). The larger of
    the cyclomatic and readability penalties is used.
  - the result gains a "maintainability" section (SQALE rating, technical
    debt, maintainability index, issue density). It is reported, not
    weighted, so stored weight configurations stay valid.
Without evidence.metrics the score is calculated exactly as before.
"""

from intelligence.evidence.models import CodeQualityEvidence, SeverityEnum
from domain.services.risk_config_service import get_risk_config_service


class QualityEngine:
    """
    Calculates an independent Code Quality Index (0–100).
    Does NOT reuse or invert the risk score.
    
    Uses configurable quality weights from database (with fallback to defaults).
    """

    # Maximum finding counts before a dimension is fully penalized
    MAX_CRITICAL = 5
    MAX_HIGH = 20
    MAX_MEDIUM = 50
    MAX_COVERAGE_PENALTY = 100.0    # coverage 0% = max penalty
    MIN_COVERAGE_THRESHOLD = 80.0   # below this coverage, penalty applies
    MAX_COMPLEXITY = 50             # avg complexity that triggers max penalty
    MAX_DUPLICATION = 30.0          # duplication % that triggers max penalty
    MAX_ARCH_VIOLATIONS = 10
    MAX_HARD_TO_READ_SHARE = 50.0   # % of function code above the cognitive limit → max penalty

    def __init__(self):
        self._config_service = get_risk_config_service()

    async def calculate(self, evidence: CodeQualityEvidence) -> dict:
        """
        Calculate the Quality Index from a CodeQualityEvidence package.

        Returns:
            {
                "quality_score": int (0-100),
                "quality_grade": str ("A" | "B" | "C" | "D" | "F"),
                "dimension_scores": { dimension: 0-100 },
                "penalties": { dimension: float },
            }
        """
        # Load configurable quality weights
        config = await self._config_service.get_configuration(
            project_id=evidence.repository_id
        )
        
        w = {
            "static_security": config.quality_weights.static_security,
            "testing": config.quality_weights.testing,
            "complexity": config.quality_weights.complexity,
            "architecture": config.quality_weights.architecture,
            "duplication": config.quality_weights.duplication,
        }

        penalties = {
            "static_security": self._static_security_penalty(evidence),
            "testing":         self._testing_penalty(evidence),
            "complexity":      self._complexity_penalty(evidence),
            "architecture":    self._architecture_penalty(evidence),
            "duplication":     self._duplication_penalty(evidence),
        }

        # Weighted sum of penalties
        total_penalty = sum(w[dim] * pen for dim, pen in penalties.items())
        quality_score = max(0, min(100, round(100 - total_penalty)))

        # Per-dimension quality scores (100 = perfect, 0 = max penalty)
        dimension_scores = {
            dim: max(0, min(100, round(100 - pen)))
            for dim, pen in penalties.items()
        }

        result = {
            "quality_score": quality_score,
            "quality_grade": self._grade(quality_score),
            "dimension_scores": dimension_scores,
            "penalties": {k: round(v, 2) for k, v in penalties.items()},
        }
        if evidence.metrics is not None:
            result["maintainability"] = self._maintainability_summary(evidence)
        if evidence.security.rating is not None:
            sec = evidence.security
            result["security"] = {
                "rating": sec.rating,
                "vulnerability_density": sec.vulnerability_density,
                "by_cwe": dict(sec.by_cwe),
                "critical": sec.critical_count,
                "high": sec.high_count,
                "medium": sec.medium_count,
                "low": sec.low_count,
                "dependencies": dict(sec.dependency_summary),
            }
        return result

    # ── Penalty Calculators ───────────────────────────────────────────────────

    def _static_security_penalty(self, evidence: CodeQualityEvidence) -> float:
        """
        Penalty based on static findings severity.
        S_pen = 10*critical + 5*high + 2*medium + 0.5*warnings
        Normalized to [0, 100].
        """
        # Each finding counted once (secrets used to be counted twice: they are
        # in static_findings AND in the security counts).
        totals = evidence.severity_totals()
        critical = totals[SeverityEnum.CRITICAL]
        high     = totals[SeverityEnum.HIGH]
        medium   = totals[SeverityEnum.MEDIUM]
        low      = totals[SeverityEnum.LOW]

        raw = 10 * critical + 5 * high + 2 * medium + 0.5 * low
        return min(100.0, raw)

    def _testing_penalty(self, evidence: CodeQualityEvidence) -> float:
        """
        Penalty based on test coverage gap below threshold.
        
        Returns 0.0 when coverage is None (unavailable) — this follows
        the semantic rule: None = unavailable, not "bad quality".
        
        The caller should reduce confidence instead when coverage is unavailable.
        """
        testing = evidence.testing
        coverage = testing.coverage_percentage

        if coverage is None:
            # No coverage data available — return 0 penalty
            # Confidence reduction is handled by AnalysisQuality logic
            return 0.0

        if coverage >= self.MIN_COVERAGE_THRESHOLD:
            return 0.0

        # Linear penalty: 0% coverage → 100 penalty; threshold → 0 penalty
        gap = self.MIN_COVERAGE_THRESHOLD - coverage
        return min(100.0, (gap / self.MIN_COVERAGE_THRESHOLD) * 100)

    def _complexity_penalty(self, evidence: CodeQualityEvidence) -> float:
        """
        Penalty based on average cyclomatic complexity.
        avg_complexity ≤ 5 → 0 penalty; MAX_COMPLEXITY → 100 penalty.

        With SAMANVAYA metrics, also a readability penalty: the share of
        function code in functions above the cognitive limit, scaled so that
        MAX_HARD_TO_READ_SHARE % → 100. Averages hide a few very complex
        functions; this share does not. The larger penalty is used.
        """
        avg = evidence.complexity.average_complexity
        LOW_BOUND = 5.0
        if avg <= LOW_BOUND:
            cyclomatic_penalty = 0.0
        else:
            ratio = (avg - LOW_BOUND) / (self.MAX_COMPLEXITY - LOW_BOUND)
            cyclomatic_penalty = min(100.0, ratio * 100)

        metrics = evidence.metrics
        if metrics is None or not metrics.function_count:
            return cyclomatic_penalty
        readability_penalty = min(
            100.0, metrics.hard_to_read_code_share / self.MAX_HARD_TO_READ_SHARE * 100
        )
        return max(cyclomatic_penalty, readability_penalty)

    @staticmethod
    def _maintainability_summary(evidence: CodeQualityEvidence) -> dict:
        """SQALE rating, debt and related metrics (reported, not weighted)."""
        m = evidence.metrics
        return {
            "rating": m.maintainability_rating,
            "technical_debt": m.technical_debt,
            "technical_debt_minutes": m.technical_debt_minutes,
            "debt_ratio": m.debt_ratio,
            "maintainability_index": m.maintainability_index,
            "average_function_maintainability": m.average_function_maintainability,
            "cognitive_max": m.cognitive_max,
            "hard_to_read_code_share": m.hard_to_read_code_share,
            "issue_density": m.issue_density,
            "weighted_issue_density": m.weighted_issue_density,
            "source": m.source,
        }

    def _architecture_penalty(self, evidence: CodeQualityEvidence) -> float:
        """
        Penalty based on layer violations and circular dependencies.
        """
        violations = len(evidence.architecture.layer_violations)
        circular   = len(evidence.architecture.circular_dependencies)
        raw = (violations * 10) + (circular * 20)
        return min(100.0, raw)

    def _duplication_penalty(self, evidence: CodeQualityEvidence) -> float:
        """
        Penalty proportional to the duplication percentage.
        0% duplication → 0 penalty; MAX_DUPLICATION% → 100 penalty.
        """
        dup_pct = evidence.duplication.duplication_percentage
        if dup_pct <= 0:
            return 0.0
        ratio = min(dup_pct / self.MAX_DUPLICATION, 1.0)
        return round(ratio * 100, 2)

    # ── Grading ───────────────────────────────────────────────────────────────

    @staticmethod
    def _grade(score: int) -> str:
        if score >= 90:
            return "A"
        if score >= 75:
            return "B"
        if score >= 60:
            return "C"
        if score >= 45:
            return "D"
        return "F"
