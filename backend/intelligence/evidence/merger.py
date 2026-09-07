"""
Evidence Merger - Combines CodeQualityEvidence from multiple language analyzers.

When analyzing multi-language PRs (e.g., Python + JavaScript), we run multiple
analyzers and need to merge their results into a single comprehensive evidence object.

Merging Strategy:
- static_findings: Concatenate all findings from all analyzers
- complexity: Take max values (worst case) or average if specified
- security: Sum all counts (critical, high, medium, low)
- testing: Sum test counts, average coverage if available
- duplication: Sum duplicate counts
- architecture: Concatenate all violations
- cicd: Take worst values (highest failure rate)
- tools_executed: Union of all tools
- detected_languages: Union of all languages
- analysis_quality: Take lowest confidence (most conservative)
"""

import logging
from typing import List, Optional
from intelligence.evidence.models import (
    CodeQualityEvidence,
    ComplexityEvidence,
    SecurityEvidence,
    TestingEvidence,
    DuplicationEvidence,
    ArchitectureEvidence,
    CICDEvidence,
    AnalysisQuality,
    AnalysisLevelEnum,
    Finding,
)

logger = logging.getLogger(__name__)


class EvidenceMerger:
    """Merges CodeQualityEvidence from multiple language analyzers."""

    @staticmethod
    def merge(evidence_list: List[CodeQualityEvidence]) -> CodeQualityEvidence:
        """
        Merge multiple CodeQualityEvidence objects into one comprehensive result.
        
        Args:
            evidence_list: List of evidence objects from different language analyzers
            
        Returns:
            Single merged CodeQualityEvidence object
            
        Raises:
            ValueError: If evidence_list is empty
        """
        if not evidence_list:
            raise ValueError("Cannot merge empty evidence list")
        
        if len(evidence_list) == 1:
            return evidence_list[0]
        
        logger.info(f"Merging evidence from {len(evidence_list)} analyzers")
        
        # Use first evidence as base
        base = evidence_list[0]
        
        # Collect all detected languages
        all_languages = set()
        for ev in evidence_list:
            all_languages.add(ev.primary_language)
            all_languages.update(ev.detected_languages)
        
        # Merge static findings (concatenate all)
        merged_findings = []
        for ev in evidence_list:
            merged_findings.extend(ev.static_findings)
        
        # Merge complexity (take max values for conservatism)
        merged_complexity = EvidenceMerger._merge_complexity(
            [ev.complexity for ev in evidence_list]
        )
        
        # Merge security (sum all counts)
        merged_security = EvidenceMerger._merge_security(
            [ev.security for ev in evidence_list]
        )
        
        # Merge testing (sum counts, average coverage)
        merged_testing = EvidenceMerger._merge_testing(
            [ev.testing for ev in evidence_list]
        )
        
        # Merge duplication (sum all counts)
        merged_duplication = EvidenceMerger._merge_duplication(
            [ev.duplication for ev in evidence_list]
        )
        
        # Merge architecture (concatenate violations)
        merged_architecture = EvidenceMerger._merge_architecture(
            [ev.architecture for ev in evidence_list]
        )
        
        # Merge CI/CD (take worst case)
        merged_cicd = EvidenceMerger._merge_cicd(
            [ev.cicd for ev in evidence_list]
        )
        
        # Merge analysis quality (take lowest confidence)
        merged_quality = EvidenceMerger._merge_quality(
            [ev.analysis_quality for ev in evidence_list]
        )
        
        # Merge metadata
        all_tools = set()
        all_skipped = set()
        total_duration = 0.0
        total_lines_added = 0
        total_lines_deleted = 0
        files_analyzed = 0
        
        for ev in evidence_list:
            all_tools.update(ev.tools_executed)
            all_skipped.update(ev.tools_skipped)
            total_duration += ev.analysis_duration_ms
            total_lines_added += ev.lines_added
            total_lines_deleted += ev.lines_deleted
            files_analyzed += ev.files_analyzed
        
        # Build merged evidence
        merged = CodeQualityEvidence(
            repository_id=base.repository_id,
            pr_number=base.pr_number,
            commit_sha=base.commit_sha,
            primary_language=base.primary_language,  # Keep first as primary
            detected_languages=sorted(list(all_languages)),
            change_context=base.change_context,  # Same for all analyzers
            files_analyzed=files_analyzed,
            lines_added=total_lines_added,
            lines_deleted=total_lines_deleted,
            static_findings=merged_findings,
            complexity=merged_complexity,
            security=merged_security,
            testing=merged_testing,
            duplication=merged_duplication,
            architecture=merged_architecture,
            cicd=merged_cicd,
            analysis_quality=merged_quality,
            tools_executed=sorted(list(all_tools)),
            tools_skipped=sorted(list(all_skipped)),
            analysis_duration_ms=total_duration,
        )
        
        logger.info(
            f"Merged evidence: {len(merged_findings)} findings, "
            f"{len(all_languages)} languages, "
            f"{len(all_tools)} tools executed"
        )
        
        return merged

    @staticmethod
    def _merge_complexity(complexity_list: List[ComplexityEvidence]) -> ComplexityEvidence:
        """
        Merge complexity evidence - use weighted average based on lines_of_code.
        
        Previously used max (conservative but unfair to large codebases).
        Now uses weighted average: a small JS file with complexity 20 shouldn't
        outweigh 200 Python files averaging complexity 6.
        """
        if not complexity_list:
            return ComplexityEvidence()
        
        # Filter out None values
        valid = [c for c in complexity_list if c is not None]
        if not valid:
            return ComplexityEvidence()
        
        # Calculate weighted average complexity based on lines_of_code
        total_loc = sum(c.lines_of_code for c in valid)
        
        if total_loc == 0:
            # Fallback to simple average if no LOC data
            weighted_avg = sum(c.average_complexity for c in valid) / len(valid)
        else:
            # Weighted average: (complexity * LOC) / total_LOC
            weighted_sum = sum(c.average_complexity * c.lines_of_code for c in valid)
            weighted_avg = weighted_sum / total_loc
        
        # Max complexity is still the actual maximum (worst single function)
        max_max = max(c.max_complexity for c in valid)
        
        # Combine high complexity functions from all
        all_high_complexity = []
        for c in valid:
            all_high_complexity.extend(c.high_complexity_functions)
        
        # Average ratios (these are already percentages, simple average is OK)
        valid_comments = [c.comment_ratio for c in valid if c.comment_ratio > 0]
        avg_comment_ratio = sum(valid_comments) / len(valid_comments) if valid_comments else 0.0
        
        valid_func_len = [c.avg_function_length for c in valid if c.avg_function_length > 0]
        avg_func_len = sum(valid_func_len) / len(valid_func_len) if valid_func_len else 0.0
        
        valid_nesting = [c.avg_nesting_depth for c in valid if c.avg_nesting_depth > 0]
        avg_nesting = sum(valid_nesting) / len(valid_nesting) if valid_nesting else 0.0
        
        return ComplexityEvidence(
            average_complexity=weighted_avg,
            max_complexity=max_max,
            high_complexity_functions=all_high_complexity,
            lines_of_code=total_loc,
            comment_ratio=avg_comment_ratio,
            avg_function_length=avg_func_len,
            avg_nesting_depth=avg_nesting,
        )

    @staticmethod
    def _merge_security(security_list: List[SecurityEvidence]) -> SecurityEvidence:
        """Merge security evidence - sum all counts."""
        if not security_list:
            return SecurityEvidence()
        
        valid = [s for s in security_list if s is not None]
        if not valid:
            return SecurityEvidence()
        
        total_critical = sum(s.critical_count for s in valid)
        total_high = sum(s.high_count for s in valid)
        total_medium = sum(s.medium_count for s in valid)
        total_low = sum(s.low_count for s in valid)
        
        all_secrets = []
        all_vulns = []
        all_findings = []
        
        for s in valid:
            all_secrets.extend(s.hardcoded_secrets)
            all_vulns.extend(s.dependency_vulnerabilities)
            all_findings.extend(s.findings)
        
        return SecurityEvidence(
            critical_count=total_critical,
            high_count=total_high,
            medium_count=total_medium,
            low_count=total_low,
            hardcoded_secrets=all_secrets,
            dependency_vulnerabilities=all_vulns,
            findings=all_findings,
        )

    @staticmethod
    def _merge_testing(testing_list: List[TestingEvidence]) -> TestingEvidence:
        """
        Merge testing evidence - sum counts, weighted average for coverage.
        
        Coverage is now weighted by test count as a proxy for codebase size.
        A language with 10 tests at 100% coverage shouldn't have equal influence
        as another with 1000 tests at 60% coverage.
        
        Test frameworks: Currently picks first, but ideally we'd track per-language.
        Future improvement: Change test_framework to Dict[str, str] mapping
        language → framework (e.g., {"python": "pytest", "javascript": "jest"}).
        """
        if not testing_list:
            return TestingEvidence()
        
        valid = [t for t in testing_list if t is not None]
        if not valid:
            return TestingEvidence()
        
        total_tests = sum(t.total_tests for t in valid)
        total_passed = sum(t.passed_tests for t in valid)
        total_failed = sum(t.failed_tests for t in valid)
        total_skipped = sum(t.skipped_tests for t in valid)
        
        # Weighted average coverage using test count as weight
        # (Better proxy than simple average when we don't have LOC)
        valid_coverage = [(t.coverage_percentage, t.total_tests) 
                          for t in valid if t.coverage_percentage is not None and t.total_tests > 0]
        
        if valid_coverage:
            total_weight = sum(weight for _, weight in valid_coverage)
            if total_weight > 0:
                weighted_sum = sum(cov * weight for cov, weight in valid_coverage)
                avg_coverage = weighted_sum / total_weight
            else:
                # Fallback to simple average
                avg_coverage = sum(cov for cov, _ in valid_coverage) / len(valid_coverage)
        else:
            avg_coverage = None
        
        # Same for changed code coverage
        valid_changed_cov = [(t.changed_code_coverage, t.total_tests)
                             for t in valid if t.changed_code_coverage is not None and t.total_tests > 0]
        
        if valid_changed_cov:
            total_weight = sum(weight for _, weight in valid_changed_cov)
            if total_weight > 0:
                weighted_sum = sum(cov * weight for cov, weight in valid_changed_cov)
                avg_changed_cov = weighted_sum / total_weight
            else:
                avg_changed_cov = sum(cov for cov, _ in valid_changed_cov) / len(valid_changed_cov)
        else:
            avg_changed_cov = None
        
        # Collect all untested paths
        all_untested = []
        for t in valid:
            all_untested.extend(t.untested_critical_paths)
        
        # Collect test frameworks and create summary
        # Current model limitation: test_framework is Optional[str], not Dict[str, str]
        # For now, collect all unique frameworks and join with commas
        frameworks = set()
        for t in valid:
            if t.test_framework:
                frameworks.add(t.test_framework)
        
        # Create comma-separated string of frameworks
        # Future: Change model to support {"python": "pytest", "javascript": "jest"}
        test_framework = ", ".join(sorted(frameworks)) if frameworks else None
        
        return TestingEvidence(
            test_framework=test_framework,  # e.g., "jest, pytest"
            total_tests=total_tests,
            passed_tests=total_passed,
            failed_tests=total_failed,
            skipped_tests=total_skipped,
            coverage_percentage=avg_coverage,
            changed_code_coverage=avg_changed_cov,
            untested_critical_paths=all_untested,
        )

    @staticmethod
    def _merge_duplication(duplication_list: List[DuplicationEvidence]) -> DuplicationEvidence:
        """Merge duplication evidence - sum all counts."""
        if not duplication_list:
            return DuplicationEvidence()
        
        valid = [d for d in duplication_list if d is not None]
        if not valid:
            return DuplicationEvidence()
        
        total_blocks = sum(d.duplicate_blocks_count for d in valid)
        total_lines = sum(d.duplicated_lines_count for d in valid)
        
        all_dup_files = []
        for d in valid:
            all_dup_files.extend(d.duplicated_files)
        
        # Calculate overall duplication percentage
        # This is approximate - ideally we'd recalculate from total LOC
        valid_pct = [d.duplication_percentage for d in valid if d.duplication_percentage > 0]
        avg_pct = sum(valid_pct) / len(valid_pct) if valid_pct else 0.0
        
        return DuplicationEvidence(
            duplicate_blocks_count=total_blocks,
            duplicated_lines_count=total_lines,
            duplication_percentage=avg_pct,
            duplicated_files=all_dup_files,
        )

    @staticmethod
    def _merge_architecture(architecture_list: List[ArchitectureEvidence]) -> ArchitectureEvidence:
        """Merge architecture evidence - concatenate all violations."""
        if not architecture_list:
            return ArchitectureEvidence()
        
        valid = [a for a in architecture_list if a is not None]
        if not valid:
            return ArchitectureEvidence()
        
        all_layer_violations = []
        all_circular = []
        all_forbidden = []
        
        for a in valid:
            all_layer_violations.extend(a.layer_violations)
            all_circular.extend(a.circular_dependencies)
            all_forbidden.extend(a.forbidden_imports)
        
        # Average coupling score
        valid_coupling = [a.coupling_score for a in valid if a.coupling_score > 0]
        avg_coupling = sum(valid_coupling) / len(valid_coupling) if valid_coupling else 0.0
        
        return ArchitectureEvidence(
            layer_violations=all_layer_violations,
            circular_dependencies=all_circular,
            forbidden_imports=all_forbidden,
            coupling_score=avg_coupling,
        )

    @staticmethod
    def _merge_cicd(cicd_list: List[CICDEvidence]) -> CICDEvidence:
        """Merge CI/CD evidence - take worst case values."""
        if not cicd_list:
            return CICDEvidence()
        
        valid = [c for c in cicd_list if c is not None]
        if not valid:
            return CICDEvidence()
        
        # Take worst build status
        statuses = [c.last_build_status for c in valid]
        if "failing" in statuses:
            worst_status = "failing"
        elif "unknown" in statuses:
            worst_status = "unknown"
        else:
            worst_status = "passing"
        
        # Take highest failure rate (worst case)
        max_failure_rate = max(c.historical_failure_rate for c in valid)
        total_flaky = sum(c.flaky_test_count for c in valid)
        
        # Average duration
        valid_duration = [c.avg_pipeline_duration_minutes for c in valid if c.avg_pipeline_duration_minutes > 0]
        avg_duration = sum(valid_duration) / len(valid_duration) if valid_duration else 0.0
        
        # Concatenate failed checks
        all_failed_checks = []
        for c in valid:
            all_failed_checks.extend(c.failed_checks)
        
        return CICDEvidence(
            last_build_status=worst_status,
            historical_failure_rate=max_failure_rate,
            flaky_test_count=total_flaky,
            avg_pipeline_duration_minutes=avg_duration,
            failed_checks=all_failed_checks,
        )

    @staticmethod
    def _merge_quality(quality_list: List[AnalysisQuality]) -> AnalysisQuality:
        """Merge analysis quality - take lowest confidence (most conservative)."""
        if not quality_list:
            return AnalysisQuality()
        
        valid = [q for q in quality_list if q is not None]
        if not valid:
            return AnalysisQuality()
        
        # Take lowest confidence (most conservative)
        min_confidence = min(q.confidence for q in valid)
        
        # Take most degraded level
        levels = [q.level for q in valid]
        if AnalysisLevelEnum.INFERRED_ONLY in levels:
            worst_level = AnalysisLevelEnum.INFERRED_ONLY
        elif AnalysisLevelEnum.PARTIAL in levels:
            worst_level = AnalysisLevelEnum.PARTIAL
        else:
            worst_level = AnalysisLevelEnum.FULL
        
        # Collect all degraded dimensions
        all_degraded = set()
        reasons = []
        for q in valid:
            all_degraded.update(q.degraded_dimensions)
            if q.reason:
                reasons.append(q.reason)
        
        combined_reason = "; ".join(reasons) if reasons else None
        
        return AnalysisQuality(
            level=worst_level,
            confidence=min_confidence,
            degraded_dimensions=sorted(list(all_degraded)),
            reason=combined_reason,
        )
