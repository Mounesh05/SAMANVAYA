"""
CodeQualityService — Multi-language code analysis orchestrator.

Uses the NEW intelligence/analyzers/* plugin-based system for comprehensive
code quality analysis across multiple programming languages.
"""

import time
from typing import Any, Dict, Optional

from intelligence.evidence.models import (
    AnalysisLevelEnum,
    AnalysisQuality,
    CodeQualityEvidence,
)
from intelligence.analyzers.language_detector import LanguageDetector
from intelligence.analyzers.registry import get_analyzers_for_profile
from domain.models.project_code_config import ProjectCodeConfig


class CodeQualityService:
    """
    Orchestrates multi-language code quality analysis using the unified
    analyzer registry system.
    """

    def __init__(self):
        self._detector = LanguageDetector()

    async def analyze_pr(
        self,
        changed_files: list[str],
        pr_context: Dict[str, Any],
        project_config: Optional[ProjectCodeConfig] = None,
        deep_analysis: bool = False,
    ) -> CodeQualityEvidence:
        """
        Run unified analyzer system and return CodeQualityEvidence.

        Args:
            changed_files: List of file paths changed in the PR
            pr_context: PR metadata (project_id, pr_number, commit_sha, etc.)
            project_config: Optional per-project config; uses defaults if None
            deep_analysis: If True, runs all analyzers; False = fast checks only

        Returns:
            CodeQualityEvidence from unified analyzer system
        """
        repo_id = pr_context.get("project_id", "")
        repo_path = pr_context.get("repo_path", ".")

        start = time.monotonic()

        try:
            # Detect primary language and get appropriate analyzers
            profile = self._detector.detect_from_files(changed_files)
            analyzers = get_analyzers_for_profile(profile)

            if not analyzers:
                # No analyzer available for this language
                aq = AnalysisQuality(
                    level=AnalysisLevelEnum.INFERRED_ONLY,
                    confidence=0.2,
                    reason=f"No analyzer available for languages: {profile.detected_languages}",
                )
                return CodeQualityEvidence(
                    repository_id=repo_id,
                    pr_number=pr_context.get("pr_number"),
                    commit_sha=pr_context.get("commit_sha"),
                    primary_language=profile.primary_language,
                    detected_languages=profile.detected_languages,
                    analysis_quality=aq,
                    analysis_duration_ms=(time.monotonic() - start) * 1000,
                )

            # Run primary analyzer
            primary_analyzer = list(analyzers.values())[0]
            evidence = await primary_analyzer.analyze(
                changed_files=changed_files,
                repo_path=repo_path,
                pr_context=pr_context
            )

            elapsed_ms = (time.monotonic() - start) * 1000
            evidence.analysis_duration_ms = elapsed_ms

            return evidence

        except Exception as e:
            # Return a degraded evidence package rather than propagating the error
            aq = AnalysisQuality(
                level=AnalysisLevelEnum.INFERRED_ONLY,
                confidence=0.1,
                reason=f"Analyzer failed: {str(e)[:200]}",
            )
            return CodeQualityEvidence(
                repository_id=repo_id,
                pr_number=pr_context.get("pr_number"),
                commit_sha=pr_context.get("commit_sha"),
                primary_language="unknown",
                analysis_quality=aq,
                analysis_duration_ms=(time.monotonic() - start) * 1000,
            )
