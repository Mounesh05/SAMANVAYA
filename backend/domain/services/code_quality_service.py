"""
CodeQualityService — Phase 0 Shim.

Wraps the existing EvidenceBuilder pipeline and adapts its output into the
new CodeQualityEvidence contract. This shim is replaced in Phase 5 with
full multi-language orchestration.

The existing github_service.py → EvidenceBuilder → code_analysis_node
pipeline remains completely unchanged.
"""

import time
from typing import Any, Dict, Optional

from intelligence.evidence.models import (
    AnalysisLevelEnum,
    AnalysisQuality,
    ChangeContext,
    CICDEvidence,
    CodeQualityEvidence,
    DuplicationEvidence,
    Finding,
    SeverityEnum,
    SecurityEvidence,
    TestingEvidence,
    ComplexityEvidence,
    ArchitectureEvidence,
)
from intelligence.evidence_builder import EvidenceBuilder
from domain.models.project_code_config import ProjectCodeConfig


class CodeQualityService:
    """
    Phase 0 shim — orchestrates the existing pipeline and normalizes
    its output into CodeQualityEvidence.

    Replaced in Phase 5 with full multi-language AnalyzerRegistry dispatch.
    """

    def __init__(self):
        self._evidence_builder: Optional[EvidenceBuilder] = None

    async def analyze_pr(
        self,
        changed_files: list[str],
        pr_context: Dict[str, Any],
        project_config: Optional[ProjectCodeConfig] = None,
        deep_analysis: bool = False,
    ) -> CodeQualityEvidence:
        """
        Run the existing EvidenceBuilder pipeline and convert its output
        into the normalized CodeQualityEvidence schema.

        Args:
            changed_files: List of file paths changed in the PR
            pr_context: PR metadata (project_id, pr_number, commit_sha, etc.)
            project_config: Optional per-project config; uses defaults if None
            deep_analysis: If True, runs all analyzers; False = fast checks only

        Returns:
            CodeQualityEvidence normalized from old EvidenceBuilder output
        """
        repo_id = pr_context.get("project_id", "")
        repo_path = pr_context.get("repo_path", "")

        # Detect primary language from changed files (rough heuristic for shim)
        primary_language = self._detect_primary_language(changed_files)

        # Build the EvidenceBuilder for the repo
        if not self._evidence_builder:
            self._evidence_builder = EvidenceBuilder(repo_path or ".")

        start = time.monotonic()

        try:
            old_evidence = await self._evidence_builder.build_evidence(
                changed_files=changed_files,
                pr_context=pr_context,
                deep_analysis=deep_analysis,
            )
        except Exception as e:
            # Return a degraded evidence package rather than propagating the error
            aq = AnalysisQuality(
                level=AnalysisLevelEnum.INFERRED_ONLY,
                confidence=0.1,
                reason=f"EvidenceBuilder failed: {str(e)[:200]}",
            )
            return CodeQualityEvidence(
                repository_id=repo_id,
                pr_number=pr_context.get("pr_number"),
                commit_sha=pr_context.get("commit_sha"),
                primary_language=primary_language,
                analysis_quality=aq,
                analysis_duration_ms=(time.monotonic() - start) * 1000,
            )

        elapsed_ms = (time.monotonic() - start) * 1000

        return self._adapt_old_evidence(
            old_evidence=old_evidence,
            pr_context=pr_context,
            primary_language=primary_language,
            elapsed_ms=elapsed_ms,
        )

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _adapt_old_evidence(
        self,
        old_evidence: Dict[str, Any],
        pr_context: Dict[str, Any],
        primary_language: str,
        elapsed_ms: float,
    ) -> CodeQualityEvidence:
        """Convert old EvidenceBuilder dict → CodeQualityEvidence."""

        changed_files = old_evidence.get("changed_files", [])
        pr_context_data = old_evidence.get("pr_context", pr_context)

        # ── ChangeContext ─────────────────────────────────────────────────────
        change_ctx = ChangeContext(
            changed_files=changed_files,
            config_files_changed=any(
                "config" in f.lower() or ".env" in f.lower()
                for f in changed_files
            ),
            db_migrations_changed=any(
                "migration" in f.lower() or "alembic" in f.lower()
                for f in changed_files
            ),
        )

        # ── SecurityEvidence ──────────────────────────────────────────────────
        old_sec = old_evidence.get("security", {})
        security = SecurityEvidence(
            critical_count=old_sec.get("critical_findings", 0),
            high_count=old_sec.get("high_findings", 0),
            medium_count=old_sec.get("medium_findings", 0),
            hardcoded_secrets=old_sec.get("secrets_found", []),
            dependency_vulnerabilities=old_sec.get("vulnerable_deps", []),
        )

        # ── TestingEvidence ───────────────────────────────────────────────────
        old_tests = old_evidence.get("tests", {})
        testing = TestingEvidence(
            total_tests=old_tests.get("total_tests", 0),
            passed_tests=old_tests.get("tests_passed", 0),
            failed_tests=old_tests.get("tests_failed", 0),
            coverage_percentage=old_tests.get("coverage_pct"),
        )

        # ── ComplexityEvidence ────────────────────────────────────────────────
        old_cx = old_evidence.get("complexity", {})
        complexity = ComplexityEvidence(
            average_complexity=old_cx.get("average_complexity", 0.0),
            max_complexity=old_cx.get("max_complexity", 0),
            high_complexity_functions=old_cx.get("high_complexity_functions", []),
            lines_of_code=old_cx.get("total_loc", 0),
        )

        # ── ArchitectureEvidence ──────────────────────────────────────────────
        old_arch = old_evidence.get("architecture", {})
        architecture = ArchitectureEvidence(
            layer_violations=old_arch.get("violations", []),
        )

        # ── CICDEvidence ──────────────────────────────────────────────────────
        # Old pipeline doesn't capture CI/CD; mark as unknown
        ci_cd = CICDEvidence(last_build_status="unknown")

        return CodeQualityEvidence(
            repository_id=pr_context.get("project_id", ""),
            pr_number=pr_context.get("pr_number"),
            commit_sha=pr_context.get("commit_sha"),
            primary_language=primary_language,
            detected_languages=[primary_language],
            change_context=change_ctx,
            files_analyzed=old_evidence.get("files_analyzed", len(changed_files)),
            lines_added=pr_context_data.get("additions", 0),
            lines_deleted=pr_context_data.get("deletions", 0),
            security=security,
            testing=testing,
            complexity=complexity,
            architecture=architecture,
            ci_cd=ci_cd,
            analysis_quality=AnalysisQuality(
                level=AnalysisLevelEnum.PARTIAL,
                confidence=0.75,
                degraded_dimensions=["ci_cd", "duplication"],
                reason="Phase 0 shim — duplication and CI/CD not yet collected by EvidenceBuilder",
            ),
            tools_executed=old_evidence.get("tools_used", []),
            analysis_duration_ms=elapsed_ms,
        )

    @staticmethod
    def _detect_primary_language(files: list[str]) -> str:
        """Rough heuristic to detect the dominant language in a changed-file list."""
        counts: Dict[str, int] = {}
        ext_map = {
            ".py": "python", ".pyi": "python",
            ".js": "javascript", ".jsx": "javascript",
            ".ts": "typescript", ".tsx": "typescript",
            ".java": "java",
            ".c": "c", ".h": "c",
            ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp",
            ".go": "go",
            ".rs": "rust",
        }
        for f in files:
            for ext, lang in ext_map.items():
                if f.endswith(ext):
                    counts[lang] = counts.get(lang, 0) + 1
        return max(counts, key=counts.get) if counts else "unknown"
