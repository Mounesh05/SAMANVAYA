"""
GitHubAnalysisService - PR analysis orchestration.

Responsibilities:
- Risk analysis using RiskEngine
- AI analysis (code review, deep analysis)
- Code quality analysis using unified analyzer system
- Delegated current-account and project-scope checks
"""

import logging
import time
from typing import Dict, Any

from intelligence.risk_engine import RiskEngine
from domain.models.code_quality_report import CodeQualityReport, EngineQualityV1
from domain.services.internal_agent_adapter import (
    CodeAuthority, resolve_code_authority, interpret_code, internal_run, failed_interpretation,
)
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class GitHubAnalysisService:
    """Handles all PR analysis operations."""

    def __init__(self):
        """Initialize analysis service."""
        self.risk_engine = RiskEngine()

    async def analyze_risk(
        self,
        pr_id: str,
        files_changed: int,
        lines_added: int,
        lines_deleted: int,
        changed_files: list[str],
        commit_count: int,
        pr_age_hours: float,
    ) -> Dict[str, Any]:
        """
        Analyze PR risk using Intelligence Engine.
        
        Args:
            pr_id: PR identifier
            files_changed: Number of files changed
            lines_added: Lines added
            lines_deleted: Lines deleted
            changed_files: List of file paths
            commit_count: Number of commits
            pr_age_hours: PR age in hours
        
        Returns:
            Risk analysis with score, level, and factors
        """
        return await self.risk_engine.analyze_pull_request(
            pr_id=pr_id,
            files_changed=files_changed,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            changed_files=changed_files,
            commit_count=commit_count,
            pr_age_hours=pr_age_hours,
        )

    async def analyze_with_ai(
        self,
        pr_data: Dict[str, Any],
        risk_evidence: Dict[str, Any],
        use_deep_analysis: bool = False,
        triggered_by: str = "system",
        authorization=None,
    ) -> Dict[str, Any]:
        """
        Run AI analysis on PR.
        
        Args:
            pr_data: PR data (title, author, number, etc.)
            risk_evidence: Risk analysis results
            use_deep_analysis: Whether to run deep static analysis
            triggered_by: User who triggered the analysis
            authorization: Current account identity or server-owned GitHub job scope
        
        Returns:
            Dict with ai_analysis and optionally code_quality_report
        """
        # Discovery must survive a missing model service. Its result is never
        # replaced by generated prose or numerical model confidence.
        discovery = pr_data.get("observed_discovery") or await self.discover_functions(pr_data)
        try:
            try:
                authority = await resolve_code_authority(authorization, {
                    "project_id": pr_data.get("project_id"), "repo": pr_data.get("repo"),
                    "commit_sha": pr_data.get("commit_sha")})
            except HTTPException:
                return {"ai_analysis": failed_interpretation("AUTHORIZATION_FAILED"), "code_quality_report": None,
                        "function_discovery": discovery.model_dump(mode="json"), "ai_run_data": None}
            
            if use_deep_analysis or pr_data.get("analyzed_head_evidence") is not None:
                result = await self._analyze_deep(pr_data, risk_evidence, triggered_by, authority)
            else:
                result = await self._analyze_simple(pr_data, risk_evidence, triggered_by, authority)
            result["function_discovery"] = discovery.model_dump(mode="json")
            if result.get("code_quality_report") is not None:
                result["code_quality_report"].function_discovery = discovery
            return result
        
        except Exception as e:
            logger.error(f"AI analysis failed: {e}", exc_info=True)
            return {
                "ai_analysis": failed_interpretation("AGENT_ADAPTER_FAILED"),
                "code_quality_report": None,
                "function_discovery": discovery.model_dump(mode="json"),
            }

    async def discover_functions(self, pr_data):
        from domain.services.code_quality_service import CodeQualityService
        return await CodeQualityService().discover_functions(pr_data.get("changed_files", []), pr_data)

    async def _analyze_simple(
        self,
        pr_data: Dict[str, Any],
        risk_evidence: Dict[str, Any],
        triggered_by: str,
        authority=None,
    ) -> Dict[str, Any]:
        """
        Simple AI analysis (backward compatible).
        
        Uses risk evidence and lightweight AI agent.
        """
        if not isinstance(authority, CodeAuthority):
            return {"ai_analysis": failed_interpretation("AUTHORIZATION_MISSING"), "code_quality_report": None, "ai_run_data": None}
        context = {
                "pr_title": pr_data.get("title", ""),
                "author": pr_data.get("author", ""),
                "pr_number": pr_data.get("pr_number"),
                "repo": pr_data.get("repo"),
                "project_id": authority.scope["project_id"],
                "organization_id": authority.scope["organization_id"],
                "commit_sha": pr_data.get("commit_sha"),
        }
        ai_analysis = await interpret_code(risk_evidence, context, authority)
        
        return {
            "ai_analysis": ai_analysis,
            "code_quality_report": None,
            "ai_run_data": internal_run(authority, "code_review", risk_evidence, context, ai_analysis, triggered_by),
        }

    async def _analyze_deep(
        self,
        pr_data: Dict[str, Any],
        risk_evidence: Dict[str, Any],
        triggered_by: str,
        authority=None,
    ) -> Dict[str, Any]:
        """
        Deep AI analysis with unified analyzer system.
        
        Runs static analysis, security scanning, complexity metrics, etc.
        """
        from domain.services.code_quality_service import CodeQualityService
        if not isinstance(authority, CodeAuthority):
            return {"ai_analysis": failed_interpretation("AUTHORIZATION_MISSING"), "code_quality_report": None, "ai_run_data": None}
        start_time = time.time()
        pr_context = {
            "pr_title": pr_data.get("title", ""), "author": pr_data.get("author", ""),
            "pr_number": pr_data.get("pr_number"), "repo": pr_data.get("repo"),
            "project_id": pr_data.get("project_id"), "commit_sha": pr_data.get("commit_sha"),
            "organization_id": authority.scope["organization_id"],
            # A local path must be explicitly supplied by the server-owned caller.
            # Never guess a temporary checkout or fall back to the server CWD.
            "repo_path": pr_data.get("repo_path"),
        }
        if "source_files" in pr_data:
            pr_context["source_files"] = pr_data["source_files"]
        evidence_obj = pr_data.get("analyzed_head_evidence") or await CodeQualityService()._analyze_quality_pr(
            pr_data.get("changed_files", []), pr_context, deep_analysis=True)
        if not evidence_obj.files_analyzed or not evidence_obj.tools_executed:
            failed = failed_interpretation("MISSING_SOURCE_EVIDENCE")
            unavailable = {"analysis_scope": "code_quality", "quality_analysis_status": "failed",
                           "quality_unavailable_reason": evidence_obj.analysis_quality.reason,
                           "quality_score": None, "risk_score": None}
            return {"ai_analysis": {**failed, **unavailable}, "code_quality_report": None,
                    "quality_analysis_status": "failed", "quality_unavailable_reason": unavailable["quality_unavailable_reason"],
                    "quality_result": None, "risk_result": None,
                    "ai_run_data": internal_run(authority, "code_review_deep", unavailable, pr_context, failed, triggered_by)}

        # Convert CodeQualityEvidence to dict format for code_agent compatibility
        from intelligence.quality_engine import snapshot_context_diagnostic
        evidence: Dict[str, Any] = {
            "static_analysis": {
                "findings": [
                    {
                        "file": f.file_path,
                        "line": f.line_number,
                        "rule_id": f.rule_id,
                        "category": f.category,
                        "severity": f.severity.value,
                        "message": f.message,
                        "source": f.source_tool,
                    }
                    for f in evidence_obj.static_findings
                    if not snapshot_context_diagnostic(f.source_tool, f.rule_id)
                ],
                "tools_used": evidence_obj.tools_executed,
            },
            "complexity": {
                "average_complexity": evidence_obj.complexity.average_complexity if evidence_obj.complexity else None,
                "max_complexity": evidence_obj.complexity.max_complexity if evidence_obj.complexity else None,
                "high_complexity_functions": evidence_obj.complexity.high_complexity_functions if evidence_obj.complexity else [],
                "lines_of_code": evidence_obj.complexity.lines_of_code if evidence_obj.complexity else None,
            },
            "security": {
                "critical_count": evidence_obj.security.critical_count if evidence_obj.security else 0,
                "high_count": evidence_obj.security.high_count if evidence_obj.security else 0,
                "findings": [
                    {"file": f.file_path, "line": f.line_number, "type": f.rule_id, "severity": f.severity.value}
                    for f in (evidence_obj.security.findings if evidence_obj.security else [])
                ],
            },
            "tests": {
                "total_tests": evidence_obj.testing.total_tests if evidence_obj.testing else 0,
                "passed_tests": evidence_obj.testing.passed_tests if evidence_obj.testing else 0,
                "failed_tests": evidence_obj.testing.failed_tests if evidence_obj.testing else 0,
                "coverage_percentage": evidence_obj.testing.coverage_percentage if evidence_obj.testing else None,
            },
            "dependencies": {
                "new_packages": [],
                "updated_packages": [],
                "vulnerability_count": len(evidence_obj.security.dependency_vulnerabilities) if evidence_obj.security else 0,
            },
            "architecture": {
                "layer_violations": [],
                "circular_dependencies": [],
            },
            # NO FAKE SCORES - Let QualityEngine and RiskEngine calculate
        }

        # Calculate quality and risk using engines (NOT AI)
        from intelligence.quality_engine import QualityEngine
        from intelligence.risk_engine import RiskEngine
        
        quality_result = await QualityEngine().calculate(evidence_obj)
        risk_result = await RiskEngine().analyze_evidence(evidence_obj)
        engine_results = {"schema_version": "engine-results-v1", "quality": quality_result, "risk": risk_result}
        
        # Prepare state for enhanced AI agent
        # AI provides explanation and recommendations, NOT authoritative scores
        # Build CodeQualityReport using ENGINE scores, not AI scores
        try:
            engine_quality = EngineQualityV1.model_validate(quality_result)
        except ValueError:
            failed = failed_interpretation("ENGINE_SCHEMA_INCOMPATIBLE")
            failed["engine_results_v1"] = engine_results
            return {"ai_analysis": failed, "code_quality_report": None,
                    "quality_result": quality_result, "risk_result": risk_result,
                    "engine_results_v1": engine_results,
                    "ai_run_data": internal_run(authority, "code_review_deep", evidence, pr_context, failed, triggered_by)}

        ai_result = await interpret_code(evidence, pr_context, authority,
            evidence_available=evidence_obj.files_analyzed > 0, quality_result=quality_result, risk_result=risk_result)
        
        code_quality_report = CodeQualityReport(
            pr_id=pr_data.get("pr_id"),
            pr_number=pr_data.get("pr_number"),
            pr_title=pr_data.get("title", ""),
            author=pr_data.get("author", ""),
            quality_score=quality_result["quality_score"],  # From QualityEngine
            quality_breakdown=None,
            quality_representation="quality-engine-v1",
            engine_quality=engine_quality,
            engine_risk=risk_result,
            quality_factors=quality_result.get("quality_factors", []),
            failure_risk=risk_result["risk_score"],  # From RiskEngine
            risk_level=risk_result["risk_level"],
            risk_factors=risk_result["risk_factors"],
            static_analysis=evidence.get("static_analysis", {}),
            complexity_metrics=evidence.get("complexity", {}),
            security_findings=evidence.get("security", {}),
            test_metrics=evidence.get("tests", {}),
            dependency_changes=evidence.get("dependencies", {}),
            architecture_analysis=evidence.get("architecture", {}),
            ai_analysis=ai_result.get("analysis"),  # AI explanation only
            ai_status=ai_result["status"],
            ai_errors=ai_result["errors"],
            critical_issues=ai_result.get("critical_issues", []),
            recommendations=ai_result.get("recommendations", []),
            review_focus=ai_result.get("review_focus"),
            confidence=evidence_obj.analysis_quality.confidence,  # From evidence quality
            tools_used=evidence.get("static_analysis", {}).get("tools_used", []),
            analysis_duration_ms=(time.time() - start_time) * 1000,
        )
        
        # AI analysis contains explanation only, not authoritative scores
        ai_analysis = {
            **ai_result,
            "engine_results_v1": engine_results,
            "quality_analysis_status": "partial" if evidence_obj.tools_skipped or evidence_obj.analysis_quality.confidence < 1 else "available",
            "quality_unavailable_reason": evidence_obj.analysis_quality.reason,
            "tools_skipped": evidence_obj.tools_skipped,
            # Engine scores provided separately for reference
            "quality_score": quality_result["quality_score"],
            "risk_score": risk_result["risk_score"],
            "risk_level": risk_result["risk_level"],
        }
        
        return {
            "ai_analysis": ai_analysis,
            "code_quality_report": code_quality_report,
            "engine_results_v1": engine_results,
            "ai_run_data": internal_run(authority, "code_review_deep", evidence, pr_context, ai_analysis, triggered_by),
        }
