"""
Complexity Analyzer
Calculates cyclomatic complexity, cognitive complexity, and function/class metrics.

Uses:
- radon for Python (cyclomatic, maintainability index)
- lizard for multi-language support
- Direct AST analysis for detailed metrics

This provides OBJECTIVE EVIDENCE, not AI-generated scores.
"""

import asyncio
import json
import subprocess
from typing import Dict, Any, List, Optional
from pathlib import Path


class ComplexityAnalyzer:
    """
    Analyzes code complexity using objective metrics.
    
    Metrics:
    - Cyclomatic Complexity (CC): Number of independent paths
    - Cognitive Complexity: How difficult code is to understand
    - Maintainability Index: Composite score (0-100)
    - Lines of Code (LOC)
    - Function length
    - Parameter count
    """
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
    
    async def analyze_files(
        self,
        files: List[str]
    ) -> Dict[str, Any]:
        """
        Analyze complexity of changed files.
        
        Args:
            files: List of file paths to analyze
        
        Returns:
            Complexity metrics as objective evidence
        """
        # Group by language
        python_files = [f for f in files if f.endswith('.py')]
        js_ts_files = [f for f in files if f.endswith(('.js', '.jsx', '.ts', '.tsx'))]
        
        results = {
            "files_analyzed": len(files),
            "high_complexity_functions": [],
            "complexity_warnings": 0,
            "maintainability_issues": 0,
            "total_complexity": 0,
            "average_complexity": 0,
            "max_complexity": 0,
            "functions_analyzed": 0,
            "tools_used": [],
        }
        
        # Analyze Python files with radon
        if python_files:
            python_result = await self._analyze_python_complexity(python_files)
            if python_result:
                self._merge_results(results, python_result)
                results["tools_used"].append("radon")
        
        # Analyze all files with lizard (multi-language)
        lizard_result = await self._analyze_with_lizard(files)
        if lizard_result:
            self._merge_results(results, lizard_result)
            results["tools_used"].append("lizard")
        
        # Calculate averages
        if results["functions_analyzed"] > 0:
            results["average_complexity"] = round(
                results["total_complexity"] / results["functions_analyzed"], 2
            )
        
        return results
    
    async def _analyze_python_complexity(
        self,
        files: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze Python files using radon.
        
        radon provides:
        - Cyclomatic Complexity (CC)
        - Maintainability Index (MI)
        - Raw metrics (LOC, LLOC, comments)
        """
        try:
            # Run radon cc (cyclomatic complexity)
            cc_cmd = ["radon", "cc", "-j"] + files
            cc_output = await self._run_command(cc_cmd)
            
            if not cc_output:
                return None
            
            # Run radon mi (maintainability index)
            mi_cmd = ["radon", "mi", "-j"] + files
            mi_output = await self._run_command(mi_cmd)
            
            return self._parse_radon_output(cc_output, mi_output)
        
        except Exception:
            return None
    
    async def _analyze_with_lizard(
        self,
        files: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze with lizard (supports Python, JS, TS, Java, C, C++, etc).
        
        lizard provides:
        - Cyclomatic Complexity (CCN)
        - Lines of Code
        - Token count
        - Parameter count
        - Function length
        """
        try:
            cmd = ["lizard", "--json"] + files
            output = await self._run_command(cmd)
            
            if not output:
                return None
            
            return self._parse_lizard_output(output)
        
        except Exception:
            return None
    
    async def _run_command(self, cmd: List[str]) -> Optional[str]:
        """Run command asynchronously."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.repo_path),
            )
            
            stdout, stderr = await process.communicate()
            return stdout.decode('utf-8', errors='ignore')
        
        except FileNotFoundError:
            return None
        except Exception:
            return None
    
    def _parse_radon_output(
        self,
        cc_output: str,
        mi_output: str
    ) -> Dict[str, Any]:
        """
        Parse radon output.
        
        radon CC grades:
        - A: 1-5 (simple)
        - B: 6-10 (moderate)
        - C: 11-20 (complex)
        - D: 21-30 (very complex)
        - E: 31-40 (extremely complex)
        - F: 41+ (unmaintainable)
        """
        result = {
            "high_complexity_functions": [],
            "complexity_warnings": 0,
            "maintainability_issues": 0,
            "total_complexity": 0,
            "max_complexity": 0,
            "functions_analyzed": 0,
        }
        
        try:
            # Parse CC (cyclomatic complexity)
            cc_data = json.loads(cc_output) if cc_output else {}
            
            for file_path, functions in cc_data.items():
                for func in functions:
                    complexity = func.get("complexity", 0)
                    result["functions_analyzed"] += 1
                    result["total_complexity"] += complexity
                    result["max_complexity"] = max(result["max_complexity"], complexity)
                    
                    # Flag high complexity (> 10)
                    if complexity > 10:
                        result["complexity_warnings"] += 1
                        
                        if complexity > 15:  # Very high
                            result["high_complexity_functions"].append({
                                "file": file_path,
                                "function": func.get("name"),
                                "complexity": complexity,
                                "line": func.get("lineno"),
                                "type": func.get("type"),  # function, method, class
                            })
            
            # Parse MI (maintainability index)
            mi_data = json.loads(mi_output) if mi_output else {}
            
            for file_path, mi_info in mi_data.items():
                mi_score = mi_info.get("mi", 100)
                
                # MI < 20 is concerning, < 10 is critical
                if mi_score < 20:
                    result["maintainability_issues"] += 1
        
        except json.JSONDecodeError:
            pass
        
        return result
    
    def _parse_lizard_output(self, output: str) -> Dict[str, Any]:
        """
        Parse lizard JSON output.
        
        lizard CCN thresholds:
        - 1-5: Simple
        - 6-10: Moderate
        - 11-15: Complex
        - 16-20: Very complex
        - 21+: Extremely complex
        """
        result = {
            "high_complexity_functions": [],
            "complexity_warnings": 0,
            "total_complexity": 0,
            "max_complexity": 0,
            "functions_analyzed": 0,
        }
        
        try:
            data = json.loads(output)
            functions = data.get("function_list", [])
            
            for func in functions:
                ccn = func.get("cyclomatic_complexity", 0)
                nloc = func.get("nloc", 0)  # Lines of code
                params = func.get("parameter_count", 0)
                
                result["functions_analyzed"] += 1
                result["total_complexity"] += ccn
                result["max_complexity"] = max(result["max_complexity"], ccn)
                
                # Flag high complexity
                if ccn > 10:
                    result["complexity_warnings"] += 1
                
                # Flag very high complexity or problematic patterns
                if ccn > 15 or nloc > 100 or params > 5:
                    result["high_complexity_functions"].append({
                        "file": func.get("filename"),
                        "function": func.get("name"),
                        "complexity": ccn,
                        "lines": nloc,
                        "parameters": params,
                        "line": func.get("start_line"),
                    })
        
        except json.JSONDecodeError:
            pass
        
        return result
    
    def _merge_results(
        self,
        target: Dict[str, Any],
        source: Dict[str, Any]
    ):
        """Merge complexity results."""
        target["complexity_warnings"] += source.get("complexity_warnings", 0)
        target["maintainability_issues"] += source.get("maintainability_issues", 0)
        target["total_complexity"] += source.get("total_complexity", 0)
        target["functions_analyzed"] += source.get("functions_analyzed", 0)
        target["max_complexity"] = max(
            target["max_complexity"],
            source.get("max_complexity", 0)
        )
        
        # Merge high complexity functions (keep top 10)
        target["high_complexity_functions"].extend(
            source.get("high_complexity_functions", [])
        )
        target["high_complexity_functions"].sort(
            key=lambda x: x.get("complexity", 0),
            reverse=True
        )
        target["high_complexity_functions"] = target["high_complexity_functions"][:10]
    
    def get_complexity_summary(self, result: Dict[str, Any]) -> str:
        """
        Generate human-readable summary for LLM context.
        
        This translates objective metrics into natural language evidence.
        """
        parts = []
        
        parts.append(f"Functions analyzed: {result['functions_analyzed']}")
        
        if result["average_complexity"] > 0:
            parts.append(f"Average complexity: {result['average_complexity']}")
        
        if result["max_complexity"] > 0:
            parts.append(f"Maximum complexity: {result['max_complexity']}")
        
        if result["complexity_warnings"] > 0:
            parts.append(
                f"⚠️ {result['complexity_warnings']} functions exceed recommended complexity (>10)"
            )
        
        if result["maintainability_issues"] > 0:
            parts.append(
                f"⚠️ {result['maintainability_issues']} files have low maintainability index (<20)"
            )
        
        # Highlight worst offenders
        if result["high_complexity_functions"]:
            parts.append("\nMost complex functions:")
            for func in result["high_complexity_functions"][:3]:
                parts.append(
                    f"  - {func.get('function')} "
                    f"(complexity: {func.get('complexity')}, "
                    f"file: {func.get('file')})"
                )
        
        return "\n".join(parts)
    
    def assess_complexity_risk(self, result: Dict[str, Any]) -> str:
        """
        Assess overall complexity risk level.
        
        Returns: low, medium, high, critical
        """
        avg = result.get("average_complexity", 0)
        max_cc = result.get("max_complexity", 0)
        warnings = result.get("complexity_warnings", 0)
        
        # Critical: Very high complexity or many warnings
        if max_cc > 30 or avg > 15 or warnings > 10:
            return "critical"
        
        # High: High complexity or several warnings
        if max_cc > 20 or avg > 10 or warnings > 5:
            return "high"
        
        # Medium: Moderate complexity or some warnings
        if max_cc > 10 or avg > 7 or warnings > 2:
            return "medium"
        
        # Low: Simple code
        return "low"
