"""
ProjectCodeConfig — per-project code quality configuration.

Gap Fix #6: formalizes the per-project settings mentioned in the blueprint
but never modelled. Stored in the `project_configs` MongoDB collection.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# Default paths excluded from all analysis to avoid distorting metrics
DEFAULT_EXCLUDED_PATHS: List[str] = [
    "node_modules", "venv", ".venv", "build", "dist",
    "target", "bin", "obj", "__pycache__", "vendor",
    ".git", "generated", ".gradle", ".mvn",
    "coverage", ".nyc_output", "htmlcov",
]

# Default quality thresholds (can be overridden per-project)
DEFAULT_QUALITY_THRESHOLDS: Dict[str, float] = {
    "min_coverage":          80.0,  # minimum test coverage %
    "max_complexity":        15.0,  # maximum cyclomatic complexity per function
    "max_duplication_pct":    5.0,  # maximum duplicate code percentage
    "max_critical_findings":  0.0,  # zero tolerance for critical security findings
    "max_high_findings":      3.0,  # allow up to 3 high-severity findings
}


class ArchitectureRule(BaseModel):
    """Defines a single forbidden dependency between layers."""
    from_layer: str         # e.g. "api"
    to_layer: str           # e.g. "database"
    reason: str = ""        # Human-readable reason for the rule


class ProjectCodeConfig(BaseModel):
    """
    Per-project code quality configuration.
    Collection: `project_configs`

    Example (Java payment service):
        project_id: "PAY-001"
        primary_language: "java"
        build_command: "mvn compile -q"
        test_command: "mvn test -q"
        coverage_command: "mvn jacoco:report"
        architecture_rules:
          - from_layer: "controller", to_layer: "repository", reason: "No direct DB access"

    Example (Embedded C++ controller):
        project_id: "EMB-002"
        primary_language: "cpp"
        build_command: "cmake --build ./build"
        test_command: "ctest --test-dir ./build"
    """

    project_id: str
    primary_language: str = "auto"         # "auto" = LanguageDetector decides

    # Build & test commands (None = auto-detected by analyzer)
    build_command: Optional[str] = None
    test_command: Optional[str] = None
    coverage_command: Optional[str] = None

    # Paths excluded from analysis
    excluded_paths: List[str] = Field(default_factory=lambda: DEFAULT_EXCLUDED_PATHS.copy())

    # Architecture layer rules (forbidden import boundaries)
    architecture_rules: List[ArchitectureRule] = []

    # Quality gates — analysis fails (alerts) if thresholds are breached
    quality_thresholds: Dict[str, float] = Field(
        default_factory=lambda: DEFAULT_QUALITY_THRESHOLDS.copy()
    )

    # Analysis behavior
    default_analysis_level: str = "standard"    # "quick" | "standard" | "deep"
    use_ai_by_default: bool = True
    max_files_per_run: int = 500                # Safety cap to prevent OOM on huge PRs

    model_config = {"protected_namespaces": ()}

    def is_excluded(self, file_path: str) -> bool:
        """Return True if the given file path should be excluded from analysis."""
        normalized = file_path.replace("\\", "/")
        for excluded in self.excluded_paths:
            if excluded in normalized.split("/"):
                return True
        return False

    def threshold(self, key: str) -> float:
        """Get a threshold value, falling back to default if not configured."""
        return self.quality_thresholds.get(
            key, DEFAULT_QUALITY_THRESHOLDS.get(key, 0.0)
        )
