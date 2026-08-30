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
"""

from intelligence.evidence.models import CodeQualityEvidence, SeverityEnum
from intelligence.rules.risk_rules import QUALITY_DIMENSION_WEIGHTS


class QualityEngine:
    """
    Calculates an independent Code Quality Index (0–100).
    Does NOT reuse or invert the risk score.
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

    def calculate(self, evidence: CodeQualityEvidence) -> dict:
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
        w = QUALITY_DIMENSION_WEIGHTS

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

        return {
            "quality_score": quality_score,
            "quality_grade": self._grade(quality_score),
            "dimension_scores": dimension_scores,
            "penalties": {k: round(v, 2) for k, v in penalties.items()},
        }

    # ── Penalty Calculators ───────────────────────────────────────────────────

    def _static_security_penalty(self, evidence: CodeQualityEvidence) -> float:
        """
        Penalty based on static findings severity.
        S_pen = 10*critical + 5*high + 2*medium + 0.5*warnings
        Normalized to [0, 100].
        """
        findings = evidence.static_findings
        critical = sum(1 for f in findings if f.severity == SeverityEnum.CRITICAL)
        high     = sum(1 for f in findings if f.severity == SeverityEnum.HIGH)
        medium   = sum(1 for f in findings if f.severity == SeverityEnum.MEDIUM)
        low      = sum(1 for f in findings if f.severity == SeverityEnum.LOW)

        # Also add security-specific counts
        critical += evidence.security.critical_count
        high     += evidence.security.high_count
        medium   += evidence.security.medium_count

        raw = 10 * critical + 5 * high + 2 * medium + 0.5 * low
        return min(100.0, raw)

    def _testing_penalty(self, evidence: CodeQualityEvidence) -> float:
        """
        Penalty based on test coverage gap below threshold.
        No coverage data = maximum penalty.
        """
        testing = evidence.testing
        coverage = testing.coverage_percentage

        if coverage is None:
            return 60.0  # No coverage data — significant penalty but not maximum

        if coverage >= self.MIN_COVERAGE_THRESHOLD:
            return 0.0

        # Linear penalty: 0% coverage → 100 penalty; threshold → 0 penalty
        gap = self.MIN_COVERAGE_THRESHOLD - coverage
        return min(100.0, (gap / self.MIN_COVERAGE_THRESHOLD) * 100)

    def _complexity_penalty(self, evidence: CodeQualityEvidence) -> float:
        """
        Penalty based on average cyclomatic complexity.
        avg_complexity ≤ 5 → 0 penalty; MAX_COMPLEXITY → 100 penalty.
        """
        avg = evidence.complexity.average_complexity
        LOW_BOUND = 5.0
        if avg <= LOW_BOUND:
            return 0.0
        ratio = (avg - LOW_BOUND) / (self.MAX_COMPLEXITY - LOW_BOUND)
        return min(100.0, ratio * 100)

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
