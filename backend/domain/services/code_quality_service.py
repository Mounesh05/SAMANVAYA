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

    def _file_matches_language(self, filepath: str, language: str) -> bool:
        """Check if a file extension matches the given language."""
        from intelligence.analyzers.language_detector import EXTENSION_MAP
        
        # Get all extensions for this language
        lang_extensions = [ext for ext, lang in EXTENSION_MAP.items() if lang == language]
        
        # Check if file ends with any of these extensions
        return any(filepath.endswith(ext) for ext in lang_extensions)

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
                # Calculate confidence: no tools available = 0.0
                aq = AnalysisQuality(
                    level=AnalysisLevelEnum.INFERRED_ONLY,
                    confidence=0.0,  # No tools = no confidence
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

            # Run ALL analyzers (multi-language support)
            # For polyglot repos, we need to analyze each language separately
            # and merge the results intelligently
            all_evidence = []
            
            for lang, analyzer in analyzers.items():
                # Filter files relevant to this language using extension map
                lang_files = [
                    f for f in changed_files 
                    if self._file_matches_language(f, lang)
                ]
                
                if not lang_files:
                    continue  # Skip if no files for this language
                
                try:
                    evidence = await analyzer.analyze(
                        changed_files=lang_files,
                        repo_path=repo_path,
                        pr_context=pr_context
                    )
                    all_evidence.append((lang, evidence))
                except Exception as e:
                    # Log but don't fail entire analysis if one language fails
                    import logging
                    logging.warning(f"Analyzer for {lang} failed: {str(e)[:200]}")
                    continue
            
            # Merge evidence from all languages
            if not all_evidence:
                # Fallback if all analyzers failed
                # Calculate confidence: analyzers ran but all failed = very low
                aq = AnalysisQuality(
                    level=AnalysisLevelEnum.INFERRED_ONLY,
                    confidence=0.1,  # Tried but all failed
                    reason="All language analyzers failed or had no relevant files",
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
            
            # Merge evidence from multiple analyzers
            merged_evidence = self._merge_evidence(all_evidence, profile, repo_id, pr_context)
            
            elapsed_ms = (time.monotonic() - start) * 1000
            merged_evidence.analysis_duration_ms = elapsed_ms

            return merged_evidence

        except Exception as e:
            # Return a degraded evidence package rather than propagating the error
            # Calculate confidence: exception during analysis = minimal
            aq = AnalysisQuality(
                level=AnalysisLevelEnum.INFERRED_ONLY,
                confidence=0.05,  # Exception = almost no confidence
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

    def _merge_evidence(
        self,
        all_evidence: list[tuple[str, CodeQualityEvidence]],
        profile,
        repo_id: str,
        pr_context: Dict[str, Any],
    ) -> CodeQualityEvidence:
        """
        Merge evidence from multiple language analyzers.
        
        Strategy:
        - Use primary language's evidence as base
        - Aggregate findings, complexity, security from all languages
        - Use weighted averages where appropriate
        - Merge tool lists
        """
        # Start with primary language evidence if available
        primary_lang = profile.primary_language
        base_evidence = None
        
        for lang, evidence in all_evidence:
            if lang == primary_lang:
                base_evidence = evidence
                break
        
        # Fallback to first evidence if primary not found
        if base_evidence is None:
            base_evidence = all_evidence[0][1]
        
        # Create merged evidence starting from base
        merged = CodeQualityEvidence(
            repository_id=repo_id,
            pr_number=pr_context.get("pr_number"),
            commit_sha=pr_context.get("commit_sha"),
            primary_language=profile.primary_language,
            detected_languages=profile.detected_languages,
        )
        
        # Aggregate across all languages
        total_files = 0
        total_lines_added = 0
        total_lines_deleted = 0
        all_findings = []
        all_tools = set()
        all_skipped = set()
        
        # Complexity aggregation (weighted by files)
        complexity_sum = 0.0
        max_complexity = 0
        high_complexity_funcs = []
        total_loc = 0
        comment_ratios = []
        func_lengths = []
        nesting_depths = []
        
        # Duplication aggregation
        dup_blocks = 0
        dup_lines = 0
        dup_files_list = []
        
        # Testing aggregation
        total_tests_all = 0
        passed_tests_all = 0
        failed_tests_all = 0
        skipped_tests_all = 0
        coverage_values = []
        
        # Security aggregation
        sec_critical = 0
        sec_high = 0
        sec_medium = 0
        sec_low = 0
        sec_findings = []
        hardcoded_secrets_all = []
        dep_vulns_all = []
        
        # Architecture aggregation
        arch_layer_violations = []
        arch_circular_deps = []
        arch_forbidden_imports = []
        coupling_scores = []
        
        # Change context (merge from all)
        all_changed_files = []
        all_added_files = []
        all_deleted_files = []
        all_renamed_files = []
        hot_paths = []
        has_db_migration = False
        has_config_change = False
        has_api_change = False
        
        # Lowest analysis quality (worst case)
        worst_quality = AnalysisQuality(
            level=AnalysisLevelEnum.FULL,
            confidence=1.0,
        )
        
        for lang, evidence in all_evidence:
            # Files and lines
            total_files += evidence.files_analyzed
            total_lines_added += evidence.lines_added
            total_lines_deleted += evidence.lines_deleted
            
            # Findings
            all_findings.extend(evidence.static_findings)
            
            # Tools
            all_tools.update(evidence.tools_executed)
            all_skipped.update(evidence.tools_skipped)
            
            # Complexity
            complexity_sum += evidence.complexity.average_complexity * evidence.files_analyzed
            max_complexity = max(max_complexity, evidence.complexity.max_complexity)
            high_complexity_funcs.extend(evidence.complexity.high_complexity_functions)
            total_loc += evidence.complexity.lines_of_code
            if evidence.complexity.comment_ratio > 0:
                comment_ratios.append(evidence.complexity.comment_ratio)
            if evidence.complexity.avg_function_length > 0:
                func_lengths.append(evidence.complexity.avg_function_length)
            if evidence.complexity.avg_nesting_depth > 0:
                nesting_depths.append(evidence.complexity.avg_nesting_depth)
            
            # Duplication
            dup_blocks += evidence.duplication.duplicate_blocks_count
            dup_lines += evidence.duplication.duplicated_lines_count
            dup_files_list.extend(evidence.duplication.duplicated_files)
            
            # Testing
            total_tests_all += evidence.testing.total_tests
            passed_tests_all += evidence.testing.passed_tests
            failed_tests_all += evidence.testing.failed_tests
            skipped_tests_all += evidence.testing.skipped_tests
            if evidence.testing.coverage_percentage is not None:
                coverage_values.append(evidence.testing.coverage_percentage)
            
            # Security
            sec_critical += evidence.security.critical_count
            sec_high += evidence.security.high_count
            sec_medium += evidence.security.medium_count
            sec_low += evidence.security.low_count
            sec_findings.extend(evidence.security.findings)
            hardcoded_secrets_all.extend(evidence.security.hardcoded_secrets)
            dep_vulns_all.extend(evidence.security.dependency_vulnerabilities)
            
            # Architecture
            arch_layer_violations.extend(evidence.architecture.layer_violations)
            arch_circular_deps.extend(evidence.architecture.circular_dependencies)
            arch_forbidden_imports.extend(evidence.architecture.forbidden_imports)
            if evidence.architecture.coupling_score > 0:
                coupling_scores.append(evidence.architecture.coupling_score)
            
            # Change context
            all_changed_files.extend(evidence.change_context.changed_files)
            all_added_files.extend(evidence.change_context.added_files)
            all_deleted_files.extend(evidence.change_context.deleted_files)
            all_renamed_files.extend(evidence.change_context.renamed_files)
            hot_paths.extend(evidence.change_context.hot_paths_touched)
            has_db_migration = has_db_migration or evidence.change_context.db_migrations_changed
            has_config_change = has_config_change or evidence.change_context.config_files_changed
            has_api_change = has_api_change or evidence.change_context.public_api_changed
            
            # Track worst analysis quality
            if evidence.analysis_quality.confidence < worst_quality.confidence:
                worst_quality = evidence.analysis_quality
        
        # Build merged complexity
        merged.complexity.average_complexity = complexity_sum / max(total_files, 1)
        merged.complexity.max_complexity = max_complexity
        merged.complexity.high_complexity_functions = high_complexity_funcs[:10]  # Top 10
        merged.complexity.lines_of_code = total_loc
        merged.complexity.comment_ratio = sum(comment_ratios) / max(len(comment_ratios), 1)
        merged.complexity.avg_function_length = sum(func_lengths) / max(len(func_lengths), 1)
        merged.complexity.avg_nesting_depth = sum(nesting_depths) / max(len(nesting_depths), 1)
        
        # Build merged duplication
        merged.duplication.duplicate_blocks_count = dup_blocks
        merged.duplication.duplicated_lines_count = dup_lines
        merged.duplication.duplication_percentage = (dup_lines / max(total_loc, 1)) * 100
        merged.duplication.duplicated_files = dup_files_list
        
        # Build merged testing
        merged.testing.total_tests = total_tests_all
        merged.testing.passed_tests = passed_tests_all
        merged.testing.failed_tests = failed_tests_all
        merged.testing.skipped_tests = skipped_tests_all
        merged.testing.coverage_percentage = sum(coverage_values) / max(len(coverage_values), 1) if coverage_values else None
        
        # Build merged security
        merged.security.critical_count = sec_critical
        merged.security.high_count = sec_high
        merged.security.medium_count = sec_medium
        merged.security.low_count = sec_low
        merged.security.findings = sec_findings
        merged.security.hardcoded_secrets = hardcoded_secrets_all
        merged.security.dependency_vulnerabilities = dep_vulns_all
        
        # Build merged architecture
        merged.architecture.layer_violations = arch_layer_violations
        merged.architecture.circular_dependencies = list(set(arch_circular_deps))
        merged.architecture.forbidden_imports = list(set(arch_forbidden_imports))
        merged.architecture.coupling_score = sum(coupling_scores) / max(len(coupling_scores), 1) if coupling_scores else 0.0
        
        # Build merged change context
        merged.change_context.changed_files = list(set(all_changed_files))
        merged.change_context.added_files = list(set(all_added_files))
        merged.change_context.deleted_files = list(set(all_deleted_files))
        merged.change_context.renamed_files = all_renamed_files
        merged.change_context.hot_paths_touched = list(set(hot_paths))
        merged.change_context.db_migrations_changed = has_db_migration
        merged.change_context.config_files_changed = has_config_change
        merged.change_context.public_api_changed = has_api_change
        
        # Set aggregated values
        merged.files_analyzed = total_files
        merged.lines_added = total_lines_added
        merged.lines_deleted = total_lines_deleted
        merged.static_findings = all_findings
        merged.tools_executed = list(all_tools)
        merged.tools_skipped = list(all_skipped)
        
        # Calculate real confidence from evidence completeness
        calculated_confidence = AnalysisQuality.calculate_confidence(
            tools_executed=list(all_tools),
            tools_skipped=list(all_skipped),
            files_analyzed=total_files,
            files_total=len(all_changed_files),
            has_test_data=(total_tests_all > 0),
            has_coverage_data=(len(coverage_values) > 0),
            has_security_scan=(sec_critical > 0 or sec_high > 0 or sec_medium > 0 or len(sec_findings) > 0),
        )
        
        # Use worst quality level but calculated confidence
        worst_quality.confidence = calculated_confidence
        merged.analysis_quality = worst_quality
        
        # Copy CI/CD from primary language evidence (doesn't vary by language)
        merged.ci_cd = base_evidence.ci_cd
        
        return merged
