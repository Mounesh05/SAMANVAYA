"""
Static Analysis Orchestrator
Coordinates multiple language-specific analyzers and aggregates results.
"""

import os
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path
from .python_analyzer import PythonAnalyzer
from .javascript_analyzer import JavaScriptAnalyzer


class StaticAnalysisOrchestrator:
    """
    Orchestrates static analysis across multiple languages.
    
    This is NOT an LLM - it runs objective tools like linters, type checkers,
    and security scanners to collect evidence.
    """
    
    def __init__(self, repo_path: str):
        """
        Initialize orchestrator.
        
        Args:
            repo_path: Path to repository root
        """
        self.repo_path = Path(repo_path)
        self.python_analyzer = PythonAnalyzer(repo_path)
        self.js_analyzer = JavaScriptAnalyzer(repo_path)
    
    async def analyze_files(
        self,
        changed_files: List[str],
        full_analysis: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze changed files using appropriate language analyzers.
        
        Args:
            changed_files: List of file paths relative to repo root
            full_analysis: If True, run all analyzers. If False, run fast checks only.
        
        Returns:
            Aggregated analysis results with objective evidence
        """
        # Group files by language
        python_files = [f for f in changed_files if f.endswith(('.py', '.pyi'))]
        js_ts_files = [f for f in changed_files if f.endswith(('.js', '.jsx', '.ts', '.tsx', '.mjs'))]
        
        # Run analyzers in parallel
        tasks = []
        
        if python_files:
            tasks.append(self.python_analyzer.analyze(python_files, full_analysis))
        
        if js_ts_files:
            tasks.append(self.js_analyzer.analyze(js_ts_files, full_analysis))
        
        # Collect results
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate evidence
        return self._aggregate_results(results, changed_files)
    
    def _aggregate_results(
        self,
        results: List[Any],
        changed_files: List[str]
    ) -> Dict[str, Any]:
        """
        Aggregate results from all analyzers into unified evidence package.
        
        This creates the OBJECTIVE EVIDENCE that the LLM will interpret.
        """
        aggregated = {
            "total_files": len(changed_files),
            "errors": 0,
            "warnings": 0,
            "security_issues": [],
            "complexity_warnings": 0,
            "type_errors": 0,
            "style_violations": 0,
            "code_smells": [],
            "analyzers_run": [],
            "analysis_by_file": {},
        }
        
        for result in results:
            # Skip exceptions
            if isinstance(result, Exception):
                continue
            
            # Skip None results
            if result is None:
                continue
            
            # Aggregate counts
            aggregated["errors"] += result.get("errors", 0)
            aggregated["warnings"] += result.get("warnings", 0)
            aggregated["complexity_warnings"] += result.get("complexity_warnings", 0)
            aggregated["type_errors"] += result.get("type_errors", 0)
            aggregated["style_violations"] += result.get("style_violations", 0)
            
            # Collect security issues
            aggregated["security_issues"].extend(result.get("security_issues", []))
            
            # Collect code smells
            aggregated["code_smells"].extend(result.get("code_smells", []))
            
            # Track which analyzers ran
            aggregated["analyzers_run"].extend(result.get("tools_used", []))
            
            # Store per-file analysis
            for file_path, file_data in result.get("files", {}).items():
                aggregated["analysis_by_file"][file_path] = file_data
        
        # Calculate overall quality indicators
        aggregated["quality_indicators"] = self._calculate_quality_indicators(aggregated)
        
        return aggregated
    
    def _calculate_quality_indicators(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate quality indicators from raw counts.
        
        These are OBJECTIVE metrics, not AI-generated scores.
        """
        total_issues = (
            data["errors"] +
            data["warnings"] +
            len(data["security_issues"]) +
            data["complexity_warnings"] +
            data["type_errors"]
        )
        
        # Issues per file (density)
        issues_per_file = total_issues / max(data["total_files"], 1)
        
        # Severity breakdown
        critical_issues = len([s for s in data["security_issues"] if s.get("severity") == "CRITICAL"])
        high_issues = len([s for s in data["security_issues"] if s.get("severity") == "HIGH"])
        
        return {
            "total_issues": total_issues,
            "issues_per_file": round(issues_per_file, 2),
            "critical_issues": critical_issues,
            "high_severity_issues": high_issues,
            "has_errors": data["errors"] > 0,
            "has_security_issues": len(data["security_issues"]) > 0,
            "has_type_errors": data["type_errors"] > 0,
        }
    
    def get_evidence_summary(self, analysis_result: Dict[str, Any]) -> str:
        """
        Generate human-readable evidence summary for LLM context.
        
        This is what gets sent to the AI agent, not raw tool output.
        """
        indicators = analysis_result.get("quality_indicators", {})
        
        summary_parts = []
        
        # Overall stats
        summary_parts.append(f"Total files analyzed: {analysis_result['total_files']}")
        summary_parts.append(f"Total issues found: {indicators.get('total_issues', 0)}")
        summary_parts.append(f"Issues per file: {indicators.get('issues_per_file', 0)}")
        
        # Breakdown
        if analysis_result["errors"] > 0:
            summary_parts.append(f"⚠️ Errors: {analysis_result['errors']}")
        
        if analysis_result["warnings"] > 0:
            summary_parts.append(f"⚠️ Warnings: {analysis_result['warnings']}")
        
        if len(analysis_result["security_issues"]) > 0:
            summary_parts.append(
                f"🔒 Security issues: {len(analysis_result['security_issues'])} "
                f"({indicators.get('critical_issues', 0)} critical, "
                f"{indicators.get('high_severity_issues', 0)} high)"
            )
        
        if analysis_result["complexity_warnings"] > 0:
            summary_parts.append(f"📊 Complexity warnings: {analysis_result['complexity_warnings']}")
        
        if analysis_result["type_errors"] > 0:
            summary_parts.append(f"🔤 Type errors: {analysis_result['type_errors']}")
        
        # Tools used
        tools = analysis_result.get("analyzers_run", [])
        if tools:
            summary_parts.append(f"\nAnalyzers: {', '.join(tools)}")
        
        return "\n".join(summary_parts)
