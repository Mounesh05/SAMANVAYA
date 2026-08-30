"""
Evidence Builder
Aggregates all analysis results into structured evidence package for LLM.

This is the KEY INTEGRATION POINT that combines:
- Static analysis
- Complexity metrics
- Security findings
- Test analysis
- Dependency changes
- Historical data
- Architecture analysis

And creates a STRUCTURED EVIDENCE PACKAGE that Ollama interprets.
"""

from typing import Dict, Any, List
from pathlib import Path
from .static_analysis.orchestrator import StaticAnalysisOrchestrator
from .complexity_analyzer import ComplexityAnalyzer
from .security_scanner import SecurityScanner
from .test_analyzer import TestAnalyzer
from .dependency_analyzer import DependencyAnalyzer
from .historical_analyzer import HistoricalAnalyzer
from .architecture_analyzer import ArchitectureAnalyzer


class EvidenceBuilder:
    """
    Orchestrates all analyzers and builds comprehensive evidence package.
    
    This is NOT an LLM - it collects OBJECTIVE EVIDENCE from tools.
    """
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        
        # Initialize all analyzers
        self.static_analyzer = StaticAnalysisOrchestrator(repo_path)
        self.complexity_analyzer = ComplexityAnalyzer(repo_path)
        self.security_scanner = SecurityScanner(repo_path)
        self.test_analyzer = TestAnalyzer(repo_path)
        self.dependency_analyzer = DependencyAnalyzer(repo_path)
        self.historical_analyzer = HistoricalAnalyzer(repo_path)
        self.architecture_analyzer = ArchitectureAnalyzer(repo_path)
    
    async def build_evidence(
        self,
        changed_files: List[str],
        pr_context: Dict[str, Any],
        deep_analysis: bool = True
    ) -> Dict[str, Any]:
        """
        Build comprehensive evidence package from all analyzers.
        
        Args:
            changed_files: List of files changed in PR
            pr_context: PR metadata (title, author, description, etc.)
            deep_analysis: If True, run all analyzers. If False, run fast checks only.
        
        Returns:
            Structured evidence package ready for LLM interpretation
        """
        evidence = {
            "pr_context": pr_context,
            "files_analyzed": len(changed_files),
            "changed_files": changed_files,
            
            # Evidence from each analyzer
            "static_analysis": {},
            "complexity": {},
            "security": {},
            "tests": {},
            "dependencies": {},
            "history": {},
            "architecture": {},
            
            # Aggregated metrics
            "overall_risk_score": 0,
            "risk_factors": [],
            "quality_score": 0,
            "quality_factors": [],
            
            # Human-readable summaries for LLM
            "evidence_summary": "",
        }
        
        # Run all analyzers (in parallel where possible)
        import asyncio
        
        # Layer 1: Static Analysis (fast)
        static_result = await self.static_analyzer.analyze_files(
            changed_files,
            full_analysis=deep_analysis
        )
        evidence["static_analysis"] = static_result
        
        # Layer 2: Complexity Analysis
        complexity_result = await self.complexity_analyzer.analyze_files(changed_files)
        evidence["complexity"] = complexity_result
        
        # Layer 3: Security Scanning
        security_result = await self.security_scanner.analyze_files(
            changed_files,
            full_scan=deep_analysis
        )
        evidence["security"] = security_result
        
        # Layer 4: Test Analysis
        test_result = await self.test_analyzer.analyze_tests(
            changed_files,
            run_tests=False  # Don't run tests by default (too slow)
        )
        evidence["tests"] = test_result
        
        # Layer 5: Dependency Analysis
        dep_result = await self.dependency_analyzer.analyze_dependencies(changed_files)
        evidence["dependencies"] = dep_result
        
        # Layer 6: Historical Analysis
        history_result = await self.historical_analyzer.analyze_history(
            changed_files,
            pr_context.get("project_id", "")
        )
        evidence["history"] = history_result
        
        # Layer 7: Architecture Analysis
        arch_result = await self.architecture_analyzer.analyze_architecture(changed_files)
        evidence["architecture"] = arch_result
        
        # Calculate aggregated scores
        evidence["overall_risk_score"] = self._calculate_risk_score(evidence)
        evidence["risk_factors"] = self._identify_risk_factors(evidence)
        evidence["quality_score"] = self._calculate_quality_score(evidence)
        evidence["quality_factors"] = self._identify_quality_factors(evidence)
        
        # Generate human-readable summary for LLM
        evidence["evidence_summary"] = self._generate_evidence_summary(evidence)
        
        return evidence
    
    def _calculate_risk_score(self, evidence: Dict[str, Any]) -> int:
        """
        Calculate overall risk score (0-100) from objective evidence.
        
        This is FORMULA-BASED, not AI-generated.
        """
        score = 0
        
        # Static analysis (max 25 points)
        static = evidence["static_analysis"]
        error_penalty = min(static.get("errors", 0) * 5, 25)
        score += error_penalty
        
        # Security (max 30 points)
        security = evidence["security"]
        security_penalty = (
            security.get("critical_issues", 0) * 15 +
            security.get("high_issues", 0) * 5
        )
        score += min(security_penalty, 30)
        
        # Complexity (max 20 points)
        complexity = evidence["complexity"]
        complexity_risk = self.complexity_analyzer.assess_complexity_risk(complexity)
        complexity_score = {"low": 0, "medium": 10, "high": 15, "critical": 20}
        score += complexity_score.get(complexity_risk, 0)
        
        # Tests (max 15 points)
        tests = evidence["tests"]
        test_risk = self.test_analyzer.assess_test_risk(tests)
        test_score = {"low": 0, "medium": 7, "high": 12, "critical": 15}
        score += test_score.get(test_risk, 0)
        
        # History (max 10 points)
        history = evidence["history"]
        if history.get("previous_incidents", 0) > 0:
            score += min(history["previous_incidents"] * 3, 10)
        
        return min(score, 100)
    
    def _calculate_quality_score(self, evidence: Dict[str, Any]) -> int:
        """
        Calculate code quality score (0-100) from objective evidence.
        
        Higher is better (opposite of risk score).
        """
        score = 100
        
        # Deduct for static analysis issues
        static = evidence["static_analysis"]
        score -= min(static.get("errors", 0) * 3, 20)
        score -= min(static.get("warnings", 0), 15)
        
        # Deduct for complexity
        complexity = evidence["complexity"]
        if complexity.get("average_complexity", 0) > 10:
            score -= 10
        
        # Deduct for missing tests
        tests = evidence["tests"]
        if not tests.get("quality_indicators", {}).get("has_tests"):
            score -= 20
        elif not tests.get("quality_indicators", {}).get("adequate_coverage"):
            score -= 10
        
        # Deduct for security issues
        security = evidence["security"]
        score -= security.get("critical_issues", 0) * 10
        score -= security.get("high_issues", 0) * 3
        
        return max(score, 0)
    
    def _identify_risk_factors(self, evidence: Dict[str, Any]) -> List[str]:
        """Identify key risk factors from evidence."""
        factors = []
        
        if evidence["security"].get("critical_issues", 0) > 0:
            factors.append("Critical security issues detected")
        
        if evidence["static_analysis"].get("errors", 0) > 5:
            factors.append(f"{evidence['static_analysis']['errors']} code errors")
        
        if evidence["complexity"].get("max_complexity", 0) > 20:
            factors.append("Very high code complexity")
        
        if not evidence["tests"].get("quality_indicators", {}).get("has_tests"):
            factors.append("No tests for code changes")
        
        if evidence["history"].get("previous_incidents", 0) > 0:
            factors.append("Modified files have incident history")
        
        if evidence["dependencies"].get("major_version_changes", 0) > 0:
            factors.append("Major dependency version changes")
        
        return factors
    
    def _identify_quality_factors(self, evidence: Dict[str, Any]) -> List[str]:
        """Identify positive quality factors."""
        factors = []
        
        if evidence["static_analysis"].get("errors", 0) == 0:
            factors.append("No static analysis errors")
        
        if evidence["tests"].get("quality_indicators", {}).get("adequate_coverage"):
            factors.append("Good test coverage")
        
        if evidence["security"].get("critical_issues", 0) == 0:
            factors.append("No critical security issues")
        
        if evidence["complexity"].get("average_complexity", 0) < 7:
            factors.append("Low code complexity")
        
        return factors
    
    def _generate_evidence_summary(self, evidence: Dict[str, Any]) -> str:
        """
        Generate comprehensive human-readable summary for LLM.
        
        This is what the AI agent will read to provide recommendations.
        """
        sections = []
        
        # PR Context
        context = evidence["pr_context"]
        sections.append(f"# Pull Request: {context.get('title', 'Untitled')}")
        sections.append(f"Author: {context.get('author', 'Unknown')}")
        sections.append(f"Files changed: {evidence['files_analyzed']}\n")
        
        # Overall Scores
        sections.append(f"## Overall Assessment")
        sections.append(f"Risk Score: {evidence['overall_risk_score']}/100")
        sections.append(f"Quality Score: {evidence['quality_score']}/100\n")
        
        # Static Analysis
        sections.append(f"## Static Analysis")
        sections.append(self.static_analyzer.get_evidence_summary(evidence["static_analysis"]))
        sections.append("")
        
        # Complexity
        sections.append(f"## Complexity")
        sections.append(self.complexity_analyzer.get_complexity_summary(evidence["complexity"]))
        sections.append("")
        
        # Security
        sections.append(f"## Security")
        sections.append(self.security_scanner.get_security_summary(evidence["security"]))
        sections.append("")
        
        # Tests
        sections.append(f"## Tests")
        sections.append(self.test_analyzer.get_test_summary(evidence["tests"]))
        sections.append("")
        
        # Dependencies
        if evidence["dependencies"].get("dependency_files_changed"):
            sections.append(f"## Dependencies")
            sections.append(self.dependency_analyzer.get_dependency_summary(evidence["dependencies"]))
            sections.append("")
        
        # History
        if evidence["history"].get("previous_incidents", 0) > 0:
            sections.append(f"## Historical Risk")
            sections.append(self.historical_analyzer.get_history_summary(evidence["history"]))
            sections.append("")
        
        # Architecture
        if evidence["architecture"].get("violations"):
            sections.append(f"## Architecture")
            sections.append(self.architecture_analyzer.get_architecture_summary(evidence["architecture"]))
            sections.append("")
        
        return "\n".join(sections)
