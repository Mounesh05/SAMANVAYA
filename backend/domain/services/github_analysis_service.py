"""
GitHubAnalysisService - PR analysis orchestration.

Responsibilities:
- Risk analysis using RiskEngine
- AI analysis (code review, deep analysis)
- Code quality analysis using unified analyzer system
- No GitHub API calls, no database operations
"""

import logging
import time
import tempfile
import os
from typing import Dict, Any, Optional

from intelligence.risk_engine import RiskEngine
from domain.models.code_quality_report import CodeQualityReport, QualityBreakdown

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
    ) -> Dict[str, Any]:
        """
        Run AI analysis on PR.
        
        Args:
            pr_data: PR data (title, author, number, etc.)
            risk_evidence: Risk analysis results
            use_deep_analysis: Whether to run deep static analysis
            triggered_by: User who triggered the analysis
        
        Returns:
            Dict with ai_analysis and optionally code_quality_report
        """
        try:
            from agents.llm_provider import check_ollama_connection
            
            # Check if Ollama is available
            if not check_ollama_connection():
                return {
                    "ai_analysis": {"error": "Ollama not available"},
                    "code_quality_report": None,
                }
            
            if use_deep_analysis:
                return await self._analyze_deep(pr_data, risk_evidence, triggered_by)
            else:
                return await self._analyze_simple(pr_data, risk_evidence, triggered_by)
        
        except Exception as e:
            logger.error(f"AI analysis failed: {e}", exc_info=True)
            return {
                "ai_analysis": {"error": f"AI analysis failed: {str(e)}"},
                "code_quality_report": None,
            }

    async def _analyze_simple(
        self,
        pr_data: Dict[str, Any],
        risk_evidence: Dict[str, Any],
        triggered_by: str,
    ) -> Dict[str, Any]:
        """
        Simple AI analysis (backward compatible).
        
        Uses risk evidence and lightweight AI agent.
        """
        from agents.code_agent import code_analysis_node
        
        agent_state = {
            "task_type": "code_review",
            "evidence": risk_evidence,
            "context": {
                "pr_title": pr_data.get("title", ""),
                "author": pr_data.get("author", ""),
                "pr_number": pr_data.get("pr_number"),
                "repo": pr_data.get("repo"),
            },
            "agent_history": [],
            "errors": [],
        }
        
        # Invoke code agent
        ai_result = code_analysis_node(agent_state)
        
        # Extract AI insights
        ai_analysis = {
            "analysis": ai_result.get("analysis"),
            "recommendations": ai_result.get("recommendations", []),
            "risk_level": ai_result.get("risk_level"),
            "confidence": ai_result.get("confidence"),
        }
        
        return {
            "ai_analysis": ai_analysis,
            "code_quality_report": None,
            "ai_run_data": {
                "agent_type": "code_review",
                "input_data": {
                    "evidence": risk_evidence,
                    "context": agent_state["context"],
                },
                "output_data": ai_analysis,
                "status": "completed",
                "model_name": "ollama",
                "triggered_by": triggered_by,
            },
        }

    async def _analyze_deep(
        self,
        pr_data: Dict[str, Any],
        risk_evidence: Dict[str, Any],
        triggered_by: str,
    ) -> Dict[str, Any]:
        """
        Deep AI analysis with unified analyzer system.
        
        Runs static analysis, security scanning, complexity metrics, etc.
        """
        from intelligence.analyzers.language_detector import LanguageDetector
        from intelligence.analyzers.registry import get_analyzers_for_profile
        from agents.code_agent import code_analysis_node
        
        start_time = time.time()
        
        # Use platform-appropriate temp directory
        temp_dir = tempfile.gettempdir()
        owner, repo = pr_data.get("repo", "/").split("/")
        repo_work_dir = os.path.join(temp_dir, f"samanvaya-repo-{owner}-{repo}")
        
        pr_context = {
            "pr_title": pr_data.get("title", ""),
            "author": pr_data.get("author", ""),
            "pr_number": pr_data.get("pr_number"),
            "repo": pr_data.get("repo"),
            "project_id": pr_data.get("project_id"),
            "commit_sha": pr_data.get("commit_sha"),
        }
        
        changed_file_paths = pr_data.get("changed_files", [])
        
        # Detect languages and get appropriate analyzers
        detector = LanguageDetector()
        language_profile = detector.detect_from_files(changed_file_paths)
        analyzers = get_analyzers_for_profile(language_profile)
        
        if not analyzers:
            logger.warning(
                f"No analyzers available for languages: {language_profile.detected_languages}"
            )
            # Return error - no fake scores
            # Quality and risk will be calculated by engines if possible
            return {
                "ai_analysis": {
                    "error": f"No analyzer available for languages: {language_profile.detected_languages}",
                    "analysis": "Unable to perform deep analysis - language not supported",
                    "recommendations": ["Add support for this language's analyzer"],
                },
                "code_quality_report": None,
                "ai_run_data": {
                    "agent_type": "code_review_deep",
                    "input_data": {
                        "languages": language_profile.detected_languages,
                    },
                    "output_data": {"error": "No analyzer available"},
                    "status": "failed",
                    "model_name": "ollama",
                    "triggered_by": triggered_by,
                },
            }
        else:
            # Run analysis with primary language analyzer
            primary_analyzer = list(analyzers.values())[0]
            evidence_obj = await primary_analyzer.analyze(
                changed_files=changed_file_paths,
                repo_path=repo_work_dir,
                pr_context=pr_context
            )
            
            # Convert CodeQualityEvidence to dict format for code_agent compatibility
            evidence = {
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
                    ],
                    "tools_used": evidence_obj.tools_executed,
                },
                "complexity": {
                    "average_complexity": evidence_obj.complexity.average_complexity if evidence_obj.complexity else 0,
                    "max_complexity": evidence_obj.complexity.max_complexity if evidence_obj.complexity else 0,
                    "high_complexity_functions": evidence_obj.complexity.high_complexity_functions if evidence_obj.complexity else [],
                    "lines_of_code": evidence_obj.complexity.lines_of_code if evidence_obj.complexity else 0,
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
                    "coverage_percentage": evidence_obj.testing.coverage_percentage if evidence_obj.testing else 0,
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
        
        # Prepare state for enhanced AI agent
        # AI provides explanation and recommendations, NOT authoritative scores
        agent_state = {
            "task_type": "code_review",
            "evidence": evidence,
            "quality_result": quality_result,  # Pass engine results to AI
            "risk_result": risk_result,
            "context": pr_context,
            "agent_history": [],
            "errors": [],
        }
        
        # Invoke enhanced code agent for explanation only
        ai_result = code_analysis_node(agent_state)
        
        # Build CodeQualityReport using ENGINE scores, not AI scores
        quality_breakdown = QualityBreakdown(
            correctness=quality_result["dimension_scores"].get("correctness", 0),
            maintainability=quality_result["dimension_scores"].get("maintainability", 0),
            security=quality_result["dimension_scores"].get("security", 0),
            testing=quality_result["dimension_scores"].get("testing", 0),
            performance=quality_result["dimension_scores"].get("performance", 0),
            architecture=quality_result["dimension_scores"].get("architecture", 0),
            readability=quality_result["dimension_scores"].get("readability", 0),
        )
        
        code_quality_report = CodeQualityReport(
            pr_id=pr_data.get("pr_id"),
            pr_number=pr_data.get("pr_number"),
            pr_title=pr_data.get("title", ""),
            author=pr_data.get("author", ""),
            quality_score=quality_result["quality_score"],  # From QualityEngine
            quality_breakdown=quality_breakdown,
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
            critical_issues=ai_result.get("critical_issues", []),
            recommendations=ai_result.get("recommendations", []),
            review_focus=ai_result.get("review_focus"),
            confidence=evidence_obj.analysis_quality.confidence,  # From evidence quality
            tools_used=evidence.get("static_analysis", {}).get("tools_used", []),
            analysis_duration_ms=(time.time() - start_time) * 1000,
        )
        
        # AI analysis contains explanation only, not authoritative scores
        ai_analysis = {
            "analysis": ai_result.get("analysis"),
            "recommendations": ai_result.get("recommendations", []),
            "critical_issues": ai_result.get("critical_issues", []),
            "review_focus": ai_result.get("review_focus"),
            # Engine scores provided separately for reference
            "quality_score": quality_result["quality_score"],
            "risk_score": risk_result["risk_score"],
            "risk_level": risk_result["risk_level"],
        }
        
        return {
            "ai_analysis": ai_analysis,
            "code_quality_report": code_quality_report,
            "ai_run_data": {
                "agent_type": "code_review_deep",
                "input_data": {
                    "evidence": evidence,
                    "context": pr_context,
                },
                "output_data": ai_analysis,
                "status": "completed",
                "model_name": "ollama",
                "triggered_by": triggered_by,
            },
        }
