"""
CodeQualityService — Multi-language code analysis orchestrator.

Uses the NEW intelligence/analyzers/* plugin-based system for comprehensive
code quality analysis across multiple programming languages.
"""

import time
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

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
        self, changed_files, pr_context, project_config=None, deep_analysis=False,
    ) -> CodeQualityEvidence:
        # Discovery is deterministic, model-independent, and preserved even if
        # unrelated quality tools fail. No benchmark jobs are submitted here.
        discovery = await self.discover_functions(changed_files, pr_context)
        evidence = await self._analyze_quality_pr(changed_files, pr_context, project_config, deep_analysis)
        evidence.function_discovery = discovery
        return evidence

    async def discover_functions(self, changed_files, pr_context):
        from intelligence.algorithms.discovery.service import discover_repository, discover_sources
        from intelligence.evidence.function_purpose import FunctionDiscovery

        repository_id = pr_context.get("project_id") or pr_context.get("repository_id") or "unknown"
        revision = pr_context.get("commit_sha")
        try:
            if isinstance(pr_context.get("source_files"), dict):
                return await discover_sources(pr_context["source_files"], repository_id, revision,
                                              pr_context.get("source_diagnostics", []))
            return await discover_repository(pr_context.get("repo_path"), repository_id, revision, changed_files)
        except Exception:
            logger.exception("Function discovery could not complete")
            return FunctionDiscovery(status="unavailable", source_revision=revision,
                                     diagnostics=[{"kind": "discovery_unavailable"}])

    async def _analyze_quality_pr(
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

            # Run ALL detected language analyzers and MERGE results
            # Filter files per language to avoid wasting work
            from intelligence.evidence.merger import EvidenceMerger
            from intelligence.analyzers.language_detector import filter_files_for_language
            
            evidence_list = []
            for lang, analyzer in analyzers.items():
                # Filter to only files relevant to this language
                lang_files = filter_files_for_language(changed_files, lang)
                
                if not lang_files:
                    logger.info(f"No {lang} files found, skipping analyzer")
                    continue
                
                logger.info(f"Running {lang} analyzer on {len(lang_files)} files")
                evidence_obj = await analyzer.analyze(
                    changed_files=lang_files,  # Only pass relevant files
                    repo_path=repo_path,
                    pr_context=pr_context
                )
                evidence_list.append(evidence_obj)
            
            # Merge all evidence from all analyzers
            if not evidence_list:
                # No analyzers produced evidence (shouldn't happen, but defensive)
                aq = AnalysisQuality(
                    level=AnalysisLevelEnum.INFERRED_ONLY,
                    confidence=0.1,
                    reason="No files matched detected languages",
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
            
            evidence = EvidenceMerger.merge(evidence_list)
            logger.info(f"Merged evidence from {len(evidence_list)} analyzers")

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
