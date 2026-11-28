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
"""

from intelligence.evidence.models import CodeQualityEvidence, SeverityEnum
from domain.services.risk_config_service import get_risk_config_service


def snapshot_context_diagnostic(source_tool, rule_id):
    """Offline type-checker resolution and project-wide diagnostics are context for review."""
    return source_tool == "tsc-repo-wide" or rule_id in {"MYPY-import-not-found", "MYPY-import-untyped"}


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
        
        w = self._weights(config)

        penalties = {
            "static_security": self._static_security_penalty(evidence),
            "testing":         self._testing_penalty(evidence),
            "complexity":      self._complexity_penalty(evidence),
            "architecture":    self._architecture_penalty(evidence),
            "duplication":     self._duplication_penalty(evidence),
        }

        missing = self._missing_dimensions(evidence)
        weight = sum(w[dim] for dim in penalties if dim not in missing)
        if not weight:
            return {"quality_score": None, "quality_grade": None, "dimension_scores": {}, "penalties": {}}
        # Weighted sum of observed penalties
        total_penalty = sum(w[dim] * pen for dim, pen in penalties.items() if dim not in missing) / weight
        quality_score = max(0, min(100, round(100 - total_penalty)))

        # Per-dimension quality scores (100 = perfect, 0 = max penalty)
        dimension_scores = {
            dim: None if dim in missing else max(0, min(100, round(100 - pen)))
            for dim, pen in penalties.items()
        }

        return {
            "quality_score": quality_score,
            "quality_grade": self._grade(quality_score),
            "dimension_scores": dimension_scores,
            "penalties": {k: None if k in missing else round(v, 2) for k, v in penalties.items()},
        }

    @staticmethod
    def _weights(config) -> dict:
        return {
            "static_security": config.quality_weights.static_security,
            "testing": config.quality_weights.testing,
            "complexity": config.quality_weights.complexity,
            "architecture": config.quality_weights.architecture,
            "duplication": config.quality_weights.duplication,
        }

    @staticmethod
    def _missing_dimensions(evidence: CodeQualityEvidence) -> set:
        """Pinned snapshots only score dimensions the worker could observe."""
        missing = set()
        if evidence.execution_provenance.get("method") == "quality-snapshot-v1":
            if evidence.testing.coverage_percentage is None:
                missing.add("testing")
            if not evidence.complexity.is_available or evidence.complexity.average_complexity is None:
                missing.add("complexity")
            if "python" not in evidence.detected_languages or "architecture" in evidence.analysis_quality.degraded_dimensions:
                missing.add("architecture")
            if "duplication-pipeline-failed" in evidence.tools_skipped:
                missing.add("duplication")
            # v4 CQ-10: the AST fallback only proves the file parses; it is not lint or security evidence.
            if not set(evidence.tools_executed).intersection({"ruff", "mypy", "bandit", "eslint", "tsc", "flake8"}):
                missing.add("static_security")
            # v4 CQ-01/CQ-17: with no analysed file, or no lint/security tool run, the remaining
            # dimensions (e.g. duplication alone) cannot stand for the code's quality. Leave it unscored.
            if not evidence.files_analyzed or "static_security" in missing:
                missing.update({"static_security", "testing", "complexity", "architecture", "duplication"})
        return missing

    async def effective_policy(self, evidence: CodeQualityEvidence) -> dict:
        """CQ-04: the weights and scored dimensions that calculate() applies to this evidence.

        Kept separate so the v1 engine result contract is unchanged.
        """
        config = await self._config_service.get_configuration(project_id=evidence.repository_id)
        weights = self._weights(config)
        return {"weights": weights, "scored_dimensions": sorted(set(weights) - self._missing_dimensions(evidence)),
                "source": "project" if getattr(config, "project_id", None) else "default"}

    # ── Penalty Calculators ───────────────────────────────────────────────────

    def _static_security_penalty(self, evidence: CodeQualityEvidence) -> float:
        """
        Penalty based on static findings severity.
        S_pen = 10*critical + 5*high + 2*medium + 0.5*warnings
        Normalized to [0, 100].
        """
        findings = evidence.static_findings
        if evidence.execution_provenance.get("method") == "quality-snapshot-v1":
            findings = [f for f in findings if not snapshot_context_diagnostic(f.source_tool, f.rule_id)]
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
        """
        avg = evidence.complexity.average_complexity
        LOW_BOUND = 5.0
        if avg is None or avg <= LOW_BOUND:
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
