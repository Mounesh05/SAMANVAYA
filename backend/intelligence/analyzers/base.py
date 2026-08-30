"""
BaseAnalyzer — Abstract contract every language analyzer must implement.

Key design decisions:
  - `analyze()` always returns CodeQualityEvidence (never raises on missing tools)
  - `_tool_available()` checks host binary before attempting CLI execution
  - `_degrade_quality()` records fallback paths into AnalysisQuality
  - All subclasses must set `language` and `supported_extensions` class attrs
"""

import shutil
from abc import ABC, abstractmethod
from typing import List, Optional

from intelligence.evidence.models import AnalysisLevelEnum, CodeQualityEvidence


class BaseAnalyzer(ABC):
    """
    Abstract base for all language-specific analyzers.

    Subclasses are registered in AnalyzerRegistry and selected automatically
    by LanguageDetector — no if-elif chains anywhere in the application.

    Example subclass:
        class PythonAnalyzer(BaseAnalyzer):
            language = "python"
            supported_extensions = [".py", ".pyi"]

            async def analyze(self, changed_files, repo_path, pr_context):
                evidence = self._empty_evidence(repo_path, pr_context)
                # ... run ruff, radon, pip-audit ...
                return evidence
    """

    # Class-level metadata — must be overridden
    language: str = ""
    supported_extensions: List[str] = []

    @abstractmethod
    async def analyze(
        self,
        changed_files: List[str],
        repo_path: str,
        pr_context: dict,
    ) -> CodeQualityEvidence:
        """
        Run all language-specific tooling on the changed files.

        Args:
            changed_files: List of file paths (relative to repo root)
            repo_path: Absolute path to the cloned repository root
            pr_context: PR metadata dict (pr_number, commit_sha, repo_id, etc.)

        Returns:
            Normalized CodeQualityEvidence — NEVER raises on missing tools.
        """
        ...

    # ── Utility Helpers ──────────────────────────────────────────────────────

    def _tool_available(self, binary: str) -> bool:
        """Return True if a CLI binary is installed on the host."""
        return shutil.which(binary) is not None

    def _degrade_quality(
        self,
        evidence: CodeQualityEvidence,
        dimension: str,
        tool: str,
        penalty: float = 0.2,
    ) -> None:
        """
        Record that a specific evidence dimension is degraded.
        Called whenever a tool is missing and a fallback path is used.

        Args:
            evidence: The evidence object to mutate
            dimension: The dimension name (e.g. "complexity", "testing")
            tool: The binary that was missing (e.g. "mvn", "clang-tidy")
            penalty: How much to reduce the confidence score (default 0.2)
        """
        evidence.tools_skipped.append(tool)
        evidence.analysis_quality.degrade(dimension, tool, penalty)

    def _empty_evidence(
        self, repo_path: str, pr_context: dict
    ) -> CodeQualityEvidence:
        """
        Create a blank CodeQualityEvidence pre-filled with identity fields.
        Subclasses should call this at the start of `analyze()`.
        """
        return CodeQualityEvidence(
            repository_id=pr_context.get("project_id", repo_path),
            pr_number=pr_context.get("pr_number"),
            commit_sha=pr_context.get("commit_sha"),
            primary_language=self.language,
            detected_languages=[self.language],
        )

    def _filter_files(self, changed_files: List[str]) -> List[str]:
        """
        Filter files to only those supported by this analyzer,
        excluding auto-generated, vendor, and build directories.
        """
        EXCLUDED_DIRS = {
            "node_modules", "venv", ".venv", "build", "dist",
            "target", "bin", "obj", "__pycache__", "vendor",
            ".git", "generated", ".gradle", ".mvn",
        }
        result = []
        for f in changed_files:
            parts = set(f.replace("\\", "/").split("/"))
            if parts & EXCLUDED_DIRS:
                continue
            if any(f.endswith(ext) for ext in self.supported_extensions):
                result.append(f)
        return result
