"""
JavaScript/TypeScript Static Analyzer
Runs ESLint and TypeScript compiler for JavaScript/TypeScript files.
"""

import asyncio
import json
import subprocess
from typing import Dict, Any, List, Optional
from pathlib import Path


class JavaScriptAnalyzer:
    """
    JavaScript/TypeScript static analysis.
    
    Tools:
    - ESLint: Linting and code quality
    - TypeScript: Type checking
    - npm audit: Dependency security (for package.json changes)
    """
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
    
    async def analyze(
        self,
        files: List[str],
        full_analysis: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze JavaScript/TypeScript files.
        
        Args:
            files: List of JS/TS file paths
            full_analysis: If True, run all tools including slow ones.
        
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
        
        # Always run ESLint (fast)
        eslint_result = await self._run_eslint(files)
        if eslint_result:
            self._merge_results(result, eslint_result)
            result["tools_used"].append("ESLint")
        
        # Run TypeScript compiler for .ts/.tsx files
        ts_files = [f for f in files if f.endswith(('.ts', '.tsx'))]
        if ts_files:
            tsc_result = await self._run_tsc(ts_files)
            if tsc_result:
                self._merge_results(result, tsc_result)
                result["tools_used"].append("TypeScript")
        
        if full_analysis:
            # Check if package.json changed - run npm audit
            if any("package.json" in f for f in files):
                audit_result = await self._run_npm_audit()
                if audit_result:
                    self._merge_results(result, audit_result)
                    result["tools_used"].append("npm audit")
        
        return result
    
    async def _run_eslint(self, files: List[str]) -> Optional[Dict[str, Any]]:
        """
        Run ESLint linter.
        
        ESLint checks:
        - Code style
        - Common errors
        - Best practices
        - Security issues
        """
        try:
            cmd = [
                "npx", "eslint",
                "--format=json",
                "--no-color",
            ] + files
            
            result = await self._run_command(cmd)
            
            if result is None:
                return None
            
            return self._parse_eslint_output(result)
        
        except Exception:
            return None
    
    async def _run_tsc(self, files: List[str]) -> Optional[Dict[str, Any]]:
        """
        Run TypeScript compiler for type checking.
        
        TypeScript checks:
        - Type errors
        - Type mismatches
        - Missing type definitions
        """
        try:
            cmd = [
                "npx", "tsc",
                "--noEmit",  # Don't generate output
                "--pretty", "false",
            ] + files
            
            result = await self._run_command(cmd)
            
            if result is None:
                return None
            
            return self._parse_tsc_output(result)
        
        except Exception:
            return None
    
    async def _run_npm_audit(self) -> Optional[Dict[str, Any]]:
        """
        Run npm audit for dependency security.
        
        npm audit checks:
        - Known vulnerabilities in dependencies
        - Outdated packages with security issues
        """
        try:
            cmd = ["npm", "audit", "--json"]
            
            result = await self._run_command(cmd)
            
            if result is None:
                return None
            
            return self._parse_npm_audit_output(result)
        
        except Exception:
            return None
    
    async def _run_command(self, cmd: List[str]) -> Optional[str]:
        """Run command asynchronously and return stdout."""
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
    
    def _parse_eslint_output(self, output: str) -> Dict[str, Any]:
        """Parse ESLint JSON output."""
        try:
            results = json.loads(output)
            
            errors = 0
            warnings = 0
            code_smells = []
            
            for file_result in results:
                messages = file_result.get("messages", [])
                
                for msg in messages:
                    severity = msg.get("severity")
                    
                    if severity == 2:  # Error
                        errors += 1
                    elif severity == 1:  # Warning
                        warnings += 1
                    
                    # Collect top issues
                    if len(code_smells) < 10:
                        code_smells.append({
                            "file": file_result.get("filePath"),
                            "line": msg.get("line"),
                            "message": msg.get("message"),
                            "rule": msg.get("ruleId"),
                        })
            
            return {
                "errors": errors,
                "warnings": warnings,
                "code_smells": code_smells,
            }
        
        except json.JSONDecodeError:
            return {"errors": 0, "warnings": 0}
    
    def _parse_tsc_output(self, output: str) -> Dict[str, Any]:
        """Parse TypeScript compiler output."""
        lines = output.strip().split("\n")
        
        # Count "error TS" lines
        type_errors = sum(1 for line in lines if "error TS" in line)
        
        return {
            "type_errors": type_errors,
        }
    
    def _parse_npm_audit_output(self, output: str) -> Dict[str, Any]:
        """Parse npm audit JSON output."""
        try:
            data = json.loads(output)
            
            vulnerabilities = data.get("metadata", {}).get("vulnerabilities", {})
            
            critical = vulnerabilities.get("critical", 0)
            high = vulnerabilities.get("high", 0)
            moderate = vulnerabilities.get("moderate", 0)
            low = vulnerabilities.get("low", 0)
            
            security_issues = []
            
            # Add summary issues
            if critical > 0:
                security_issues.append({
                    "severity": "CRITICAL",
                    "count": critical,
                    "issue": f"{critical} critical vulnerabilities in dependencies",
                })
            
            if high > 0:
                security_issues.append({
                    "severity": "HIGH",
                    "count": high,
                    "issue": f"{high} high-severity vulnerabilities in dependencies",
                })
            
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
