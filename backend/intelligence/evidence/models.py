"""
Unified Evidence Models — Language-Agnostic Schema.

Every language analyzer (Python, JS/TS, Java, C, C++, Go, Rust, …)
must output data conforming to this schema.

Gap fixes included:
  1. ChangeContext  — what actually changed in the PR (diff context)
  3. CICDEvidence   — build/pipeline history for deployment risk
  4. AnalysisQuality — confidence flag when fallback paths are used
  6. (referenced by ProjectCodeConfig in domain/models/)
"""

import uuid
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Enumerations ─────────────────────────────────────────────────────────────

class SeverityEnum(str, Enum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"
    INFO     = "info"


class AnalysisLevelEnum(str, Enum):
    FULL          = "full"           # All tools ran successfully
    PARTIAL       = "partial"        # Some tools skipped / fell back
    INFERRED_ONLY = "inferred_only"  # No ecosystem tools — regex/AST only


# ── Leaf Models ───────────────────────────────────────────────────────────────

class Finding(BaseModel):
    """A single lint / security / architecture finding."""

    id: str = Field(default_factory=lambda: f"FND-{uuid.uuid4().hex[:8].upper()}")
    file_path: str
    line_number: Optional[int] = None
    end_line: Optional[int] = None
    rule_id: str
    category: str   # "security" | "syntax" | "maintainability" | "type" | "architecture"
    severity: SeverityEnum
    source_tool: str    # "ruff" | "eslint" | "bandit" | "lizard" | "ast" | "cppcheck"
    message: str
    code_snippet: Optional[str] = None
    suggested_fix: Optional[str] = None


# ── Gap Fix #1: ChangeContext ─────────────────────────────────────────────────

class ChangeContext(BaseModel):
    """
    Captures what actually changed in the PR — the diff context.
    Required by the Risk Engine to calculate blast radius.
    """

    changed_files: List[str] = Field(default_factory=list)
    added_files: List[str] = Field(default_factory=list)
    deleted_files: List[str] = Field(default_factory=list)
    renamed_files: List[Dict[str, str]] = Field(default_factory=list)
    hot_paths_touched: List[str] = Field(default_factory=list)
    db_migrations_changed: bool = False
    config_files_changed: bool = False
    public_api_changed: bool = False


# ── Evidence Sub-Dimensions ───────────────────────────────────────────────────

class ComplexityEvidence(BaseModel):
    average_complexity: float = 0.0
    max_complexity: int = 0
    high_complexity_functions: List[Dict[str, Any]] = Field(default_factory=list)
    lines_of_code: int = 0
    comment_ratio: float = 0.0
    avg_function_length: float = 0.0
    avg_nesting_depth: float = 0.0


class DuplicationEvidence(BaseModel):
    duplicate_blocks_count: int = 0
    duplicated_lines_count: int = 0
    duplication_percentage: float = 0.0
    duplicated_files: List[Dict[str, Any]] = Field(default_factory=list)


class TestingEvidence(BaseModel):
    test_framework: Optional[str] = None    # "pytest" | "jest" | "junit" | "ctest"
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    coverage_percentage: Optional[float] = None
    changed_code_coverage: Optional[float] = None   # Coverage on only the changed lines
    untested_critical_paths: List[str] = Field(default_factory=list)


class SecurityEvidence(BaseModel):
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    hardcoded_secrets: List[Dict[str, Any]] = Field(default_factory=list)
    dependency_vulnerabilities: List[Dict[str, Any]] = Field(default_factory=list)
    findings: List[Finding] = Field(default_factory=list)


class ArchitectureEvidence(BaseModel):
    layer_violations: List[Dict[str, Any]] = Field(default_factory=list)
    circular_dependencies: List[str] = Field(default_factory=list)
    forbidden_imports: List[str] = Field(default_factory=list)
    coupling_score: float = 0.0     # 0 = low coupling (good), 1 = high coupling (bad)


# ── Gap Fix #3: CICDEvidence ──────────────────────────────────────────────────

class CICDEvidence(BaseModel):
    """
    CI/CD pipeline history — one of the best deployment risk predictors.
    Historical failure rate is fed directly into the Risk Engine.
    """

    last_build_status: str = "unknown"          # "passing" | "failing" | "unknown"
    historical_failure_rate: float = 0.0        # % of last 30 builds that failed
    flaky_test_count: int = 0
    avg_pipeline_duration_minutes: float = 0.0
    failed_checks: List[str] = Field(default_factory=list)


# ── Gap Fix #4: AnalysisQuality ───────────────────────────────────────────────

class AnalysisQuality(BaseModel):
    """
    Tracks the quality / completeness of the evidence collection itself.
    When fallback paths are used (missing CLI tools), confidence drops.
    The Code Agent reads this to calibrate the certainty of its output.

    Example prompt injection when degraded:
        "Note: analysis confidence is 0.4 (partial). Complexity data was
         inferred via regex — do not make precise judgements about cyclomatic
         scores. Treat complexity findings as directional, not absolute."
    """

    level: AnalysisLevelEnum = AnalysisLevelEnum.FULL
    confidence: float = 1.0                     # 0.0 – 1.0
    degraded_dimensions: List[str] = Field(default_factory=list)
    reason: Optional[str] = None                # Human-readable explanation

    def degrade(self, dimension: str, tool: str, penalty: float = 0.2) -> None:
        """Record that a dimension's evidence is degraded due to missing tool."""
        if dimension not in self.degraded_dimensions:
            self.degraded_dimensions.append(dimension)
        self.confidence = max(0.1, self.confidence - penalty)
        if self.level == AnalysisLevelEnum.FULL:
            self.level = AnalysisLevelEnum.PARTIAL
        if self.reason is None:
            self.reason = f"Tool '{tool}' not available on host"
        else:
            self.reason += f"; '{tool}' not available"

    def prompt_note(self) -> str:
        """Returns a calibration note to inject into Code Agent prompts."""
        if self.level == AnalysisLevelEnum.FULL:
            return ""
        dims = ", ".join(self.degraded_dimensions) if self.degraded_dimensions else "some"
        return (
            f"⚠️  Analysis confidence: {self.confidence:.1f} ({self.level.value}). "
            f"Evidence for [{dims}] was inferred via fallback (regex/AST) because "
            f"{self.reason}. Treat these dimensions as directional, not absolute."
        )


# ── Root Evidence Contract ────────────────────────────────────────────────────

class CodeQualityEvidence(BaseModel):
    """
    The unified, language-agnostic evidence package produced by every analyzer.

    This is the single source of truth passed to:
      - RiskEngine (calculates failure risk)
      - QualityEngine (calculates quality index)
      - CodeAgent (LLM reasoning & recommendations)
    """

    # Identity
    repository_id: str
    pr_number: Optional[int] = None
    commit_sha: Optional[str] = None

    # Language profile
    primary_language: str
    detected_languages: List[str] = Field(default_factory=list)

    # Gap Fix #1 — Change context for blast radius calculation
    change_context: ChangeContext = Field(default_factory=ChangeContext)

    # Raw change counts (summary level)
    files_analyzed: int = 0
    lines_added: int = 0
    lines_deleted: int = 0

    # Evidence dimensions
    static_findings: List[Finding] = Field(default_factory=list)
    complexity: ComplexityEvidence = Field(default_factory=ComplexityEvidence)
    duplication: DuplicationEvidence = Field(default_factory=DuplicationEvidence)
    testing: TestingEvidence = Field(default_factory=TestingEvidence)
    security: SecurityEvidence = Field(default_factory=SecurityEvidence)
    architecture: ArchitectureEvidence = Field(default_factory=ArchitectureEvidence)
    ci_cd: CICDEvidence = Field(default_factory=CICDEvidence)               # Gap Fix #3
    analysis_quality: AnalysisQuality = Field(default_factory=AnalysisQuality)  # Gap Fix #4

    # Execution metadata
    tools_executed: List[str] = Field(default_factory=list)
    tools_skipped: List[str] = Field(default_factory=list)
    analysis_duration_ms: float = 0.0

    # Convenience helpers ──────────────────────────────────────────────────────

    @property
    def total_critical_findings(self) -> int:
        return sum(
            1 for f in self.static_findings
            if f.severity == SeverityEnum.CRITICAL
        ) + self.security.critical_count

    @property
    def total_high_findings(self) -> int:
        return sum(
            1 for f in self.static_findings
            if f.severity == SeverityEnum.HIGH
        ) + self.security.high_count

    @property
    def is_high_risk_change(self) -> bool:
        """Quick check — public API, DB migrations, or config changes."""
        ctx = self.change_context
        return (
            ctx.public_api_changed
            or ctx.db_migrations_changed
            or bool(ctx.hot_paths_touched)
        )
