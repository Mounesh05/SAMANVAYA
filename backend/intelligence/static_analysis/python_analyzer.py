"""
Python Static Analyzer
Runs Ruff, Pylint, MyPy, and Bandit for Python files.
"""

import asyncio
import json
import subprocess
from typing import Dict, Any, List, Optional
from pathlib import Path


class PythonAnalyzer:
    """
    Python static analysis using industry-standard tools.
    
    Tools:
    - Ruff: Fast linter (replaces Flake8, isort, etc.)
    - Pylint: Deep code analysis
    - MyPy: Type checking
    - Bandit: Security scanning
    """
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
    
    async def analyze(
        self,
        files: List[str],
        full_analysis: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze Python files.
        
        Args:
            files: List of Python file paths
            full_analysis: If True, run all tools. If False, run Ruff only (fast).
        
        Returns:
            Objective evidence from static analyzers
        """
        result = {
            "errors": 0,
            "warnings": 0,
            "security_issues": [],
            "complexity_warnings": 0,
            "type_errors": 0,
            "style_violations": 0,
            "code_smells": [],
            "tools_used": [],
            "files": {},
        }
        
        # Always run Ruff (fast)
        ruff_result = await self._run_ruff(files)
        if ruff_result:
            self._merge_results(result, ruff_result)
            result["tools_used"].append("Ruff")
        
        if full_analysis:
            # Run Pylint (slower, deeper analysis)
            pylint_result = await self._run_pylint(files)
            if pylint_result:
                self._merge_results(result, pylint_result)
                result["tools_used"].append("Pylint")
            
            # Run MyPy (type checking)
            mypy_result = await self._run_mypy(files)
            if mypy_result:
                self._merge_results(result, mypy_result)
                result["tools_used"].append("MyPy")
            
            # Run Bandit (security)
            bandit_result = await self._run_bandit(files)
            if bandit_result:
                self._merge_results(result, bandit_result)
                result["tools_used"].append("Bandit")
        
        return result
    
    async def _run_ruff(self, files: List[str]) -> Optional[Dict[str, Any]]:
        """
        Run Ruff linter.
        
        Ruff is extremely fast and covers many rules:
        - Style (PEP 8)
        - Common errors
        - Code smells
        - Imports
        """
        try:
            # Run ruff check with JSON output
            cmd = ["ruff", "check", "--output-format=json"] + files
            
            result = await self._run_command(cmd)
            
            if result is None:
                return None
            
            # Parse Ruff JSON output
            return self._parse_ruff_output(result)
        
        except Exception:
            # Ruff not installed or failed
            return None
    
    async def _run_pylint(self, files: List[str]) -> Optional[Dict[str, Any]]:
        """
        Run Pylint for deep code analysis.
        
        Pylint checks:
        - Code quality
        - Code smells
        - Complexity
        - Best practices
        """
        try:
            cmd = [
                "pylint",
                "--output-format=json",
                "--disable=all",
                "--enable=W,E,C0103,C0301,R0912,R0915",  # Warnings, Errors, specific checks
            ] + files
            
            result = await self._run_command(cmd)
            
            if result is None:
                return None
            
            return self._parse_pylint_output(result)
        
        except Exception:
            return None
    
    async def _run_mypy(self, files: List[str]) -> Optional[Dict[str, Any]]:
        """
        Run MyPy type checker.
        
        MyPy detects:
        - Type errors
        - Type inconsistencies
        - Missing type annotations
        """
        try:
            cmd = [
                "mypy",
                "--show-error-codes",
                "--no-error-summary",
                "--no-color-output",
            ] + files
            
            result = await self._run_command(cmd)
            
            if result is None:
                return None
            
            return self._parse_mypy_output(result)
        
        except Exception:
            return None
    
    async def _run_bandit(self, files: List[str]) -> Optional[Dict[str, Any]]:
        """
        Run Bandit security scanner.
        
        Bandit detects:
        - Hardcoded secrets
        - SQL injection
        - Insecure functions
        - Security misconfigurations
        """
        try:
            cmd = ["bandit", "-f", "json", "-r"] + files
            
            result = await self._run_command(cmd)
            
            if result is None:
                return None
            
            return self._parse_bandit_output(result)
        
        except Exception:
            return None
    
    async def _run_command(self, cmd: List[str]) -> Optional[str]:
        """
        Run command asynchronously and return stdout.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.repo_path),
            )
            
            stdout, stderr = await process.communicate()
            
            # Many tools return non-zero when issues found
            # We still want the output
            return stdout.decode('utf-8', errors='ignore')
        
        except FileNotFoundError:
            # Tool not installed
            return None
        except Exception:
            return None
    
    def _parse_ruff_output(self, output: str) -> Dict[str, Any]:
        """Parse Ruff JSON output."""
        try:
            issues = json.loads(output)
            
            errors = sum(1 for i in issues if i.get("type") == "E")
            warnings = sum(1 for i in issues if i.get("type") == "W")
            style = sum(1 for i in issues if i.get("type") not in ("E", "W"))
            
            return {
                "errors": errors,
                "warnings": warnings,
                "style_violations": style,
                "code_smells": [
                    {
                        "file": i.get("filename"),
                        "line": i.get("location", {}).get("row"),
                        "message": i.get("message"),
                        "code": i.get("code"),
                    }
                    for i in issues[:10]  # Limit to top 10
                ],
            }
        except json.JSONDecodeError:
            return {"errors": 0, "warnings": 0}
    
    def _parse_pylint_output(self, output: str) -> Dict[str, Any]:
        """Parse Pylint JSON output."""
        try:
            issues = json.loads(output)
            
            errors = sum(1 for i in issues if i.get("type") == "error")
            warnings = sum(1 for i in issues if i.get("type") == "warning")
            complexity = sum(1 for i in issues if "too-many" in i.get("symbol", ""))
            
            return {
                "errors": errors,
                "warnings": warnings,
                "complexity_warnings": complexity,
            }
        except json.JSONDecodeError:
            return {"errors": 0, "warnings": 0}
    
    def _parse_mypy_output(self, output: str) -> Dict[str, Any]:
        """Parse MyPy output."""
        lines = output.strip().split("\n")
        
        # Count "error:" lines
        type_errors = sum(1 for line in lines if "error:" in line.lower())
        
        return {
            "type_errors": type_errors,
        }
    
    def _parse_bandit_output(self, output: str) -> Dict[str, Any]:
        """Parse Bandit JSON output."""
        try:
            data = json.loads(output)
            results = data.get("results", [])
            
            security_issues = [
                {
                    "severity": r.get("issue_severity"),
                    "confidence": r.get("issue_confidence"),
                    "file": r.get("filename"),
                    "line": r.get("line_number"),
                    "issue": r.get("issue_text"),
                    "test_id": r.get("test_id"),
                }
                for r in results
            ]
            
            return {
                "security_issues": security_issues,
            }
        except json.JSONDecodeError:
            return {"security_issues": []}
    
    def _merge_results(self, target: Dict[str, Any], source: Dict[str, Any]):
        """Merge analysis results."""
        for key in ["errors", "warnings", "complexity_warnings", "type_errors", "style_violations"]:
            target[key] += source.get(key, 0)
        
        for key in ["security_issues", "code_smells"]:
            target[key].extend(source.get(key, []))
