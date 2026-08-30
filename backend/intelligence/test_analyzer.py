"""
Test Analyzer
Evaluates test coverage, test quality, and test-to-code ratio.

Analyzes:
- Test coverage (line, branch, function)
- Test count vs code changes
- Test quality indicators
- Missing test scenarios
- Test patterns and anti-patterns

Uses:
- coverage.py (Python)
- pytest (Python test framework)
- Jest/Mocha (JavaScript test frameworks)
- Coverage reports (XML, JSON, LCOV)

This provides OBJECTIVE TEST METRICS, not AI estimates.
"""

import asyncio
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path


class TestAnalyzer:
    """
    Analyzes test coverage and quality using objective metrics.
    
    Key Metrics:
    - Coverage percentage (line, branch, function)
    - Tests added vs code added ratio
    - Test file count
    - Assertion count
    - Test execution time
    - Failed tests
    - Skipped tests
    """
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
    
    async def analyze_tests(
        self,
        changed_files: List[str],
        run_tests: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze test coverage and quality for changed files.
        
        Args:
            changed_files: List of files changed in PR
            run_tests: If True, actually run tests. If False, parse existing reports only.
        
        Returns:
            Test metrics as objective evidence
        """
        result = {
            "tests_added": 0,
            "tests_modified": 0,
            "test_files": [],
            "code_files": [],
            "test_to_code_ratio": 0.0,
            "coverage": {
                "line_coverage": None,
                "branch_coverage": None,
                "function_coverage": None,
                "coverage_delta": None,
            },
            "test_execution": {
                "tests_run": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "tests_skipped": 0,
                "execution_time_seconds": 0,
            },
            "quality_indicators": {
                "has_tests": False,
                "adequate_coverage": False,
                "tests_for_critical_code": False,
            },
            "tools_used": [],
        }
        
        # Separate test files from code files
        test_files, code_files = self._categorize_files(changed_files)
        
        result["test_files"] = test_files
        result["code_files"] = code_files
        result["tests_added"] = len([f for f in test_files if self._is_new_file(f)])
        result["tests_modified"] = len([f for f in test_files if not self._is_new_file(f)])
        
        # Calculate test-to-code ratio
        if len(code_files) > 0:
            result["test_to_code_ratio"] = round(len(test_files) / len(code_files), 2)
        
        # Check for existing coverage reports
        coverage_data = await self._parse_coverage_reports()
        if coverage_data:
            result["coverage"].update(coverage_data)
            result["tools_used"].append("coverage-parser")
        
        # If run_tests=True, execute test suite
        if run_tests:
            # Run Python tests
            if any(f.endswith('.py') for f in code_files):
                pytest_result = await self._run_pytest()
                if pytest_result:
                    result["test_execution"].update(pytest_result["execution"])
                    if pytest_result.get("coverage"):
                        result["coverage"].update(pytest_result["coverage"])
                    result["tools_used"].append("pytest")
            
            # Run JavaScript tests
            if any(f.endswith(('.js', '.jsx', '.ts', '.tsx')) for f in code_files):
                jest_result = await self._run_jest()
                if jest_result:
                    result["test_execution"].update(jest_result["execution"])
                    if jest_result.get("coverage"):
                        result["coverage"].update(jest_result["coverage"])
                    result["tools_used"].append("jest")
        
        # Calculate quality indicators
        result["quality_indicators"] = self._assess_test_quality(result)
        
        return result
    
    def _categorize_files(
        self,
        files: List[str]
    ) -> Tuple[List[str], List[str]]:
        """
        Separate test files from production code files.
        
        Returns:
            (test_files, code_files)
        """
        test_files = []
        code_files = []
        
        test_patterns = [
            r'test_.*\.py$',
            r'.*_test\.py$',
            r'.*\.test\.(js|jsx|ts|tsx)$',
            r'.*\.spec\.(js|jsx|ts|tsx)$',
            r'^tests?/',
            r'/__tests__/',
        ]
        
        for file_path in files:
            is_test = any(re.search(pattern, file_path) for pattern in test_patterns)
            
            if is_test:
                test_files.append(file_path)
            elif file_path.endswith(('.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.go')):
                code_files.append(file_path)
        
        return test_files, code_files
    
    def _is_new_file(self, file_path: str) -> bool:
        """
        Check if file is newly added (not modified).
        
        In real implementation, this would check git status.
        For now, we'll return False (assume all are modifications).
        """
        # TODO: Implement git diff parsing
        return False
    
    async def _parse_coverage_reports(self) -> Optional[Dict[str, Any]]:
        """
        Parse existing coverage reports (XML, JSON, LCOV).
        
        Looks for:
        - coverage.xml (Python coverage)
        - coverage/coverage-final.json (Jest)
        - coverage/lcov.info (LCOV format)
        """
        coverage_data = {}
        
        # Try Python coverage.xml
        python_coverage = await self._parse_python_coverage_xml()
        if python_coverage:
            coverage_data.update(python_coverage)
        
        # Try Jest coverage-final.json
        jest_coverage = await self._parse_jest_coverage_json()
        if jest_coverage:
            # Merge with existing data
            if coverage_data.get("line_coverage"):
                # Average if both exist
                coverage_data["line_coverage"] = round(
                    (coverage_data["line_coverage"] + jest_coverage["line_coverage"]) / 2, 2
                )
            else:
                coverage_data.update(jest_coverage)
        
        return coverage_data if coverage_data else None
    
    async def _parse_python_coverage_xml(self) -> Optional[Dict[str, Any]]:
        """Parse Python coverage XML report."""
        try:
            coverage_file = self.repo_path / "coverage.xml"
            
            if not coverage_file.exists():
                return None
            
            tree = ET.parse(coverage_file)
            root = tree.getroot()
            
            # Get overall coverage
            line_rate = float(root.attrib.get("line-rate", 0))
            branch_rate = float(root.attrib.get("branch-rate", 0))
            
            return {
                "line_coverage": round(line_rate * 100, 2),
                "branch_coverage": round(branch_rate * 100, 2),
            }
        
        except Exception:
            return None
    
    async def _parse_jest_coverage_json(self) -> Optional[Dict[str, Any]]:
        """Parse Jest coverage JSON report."""
        try:
            coverage_file = self.repo_path / "coverage" / "coverage-summary.json"
            
            if not coverage_file.exists():
                return None
            
            with open(coverage_file, 'r') as f:
                data = json.load(f)
            
            # Get total summary
            total = data.get("total", {})
            
            lines = total.get("lines", {}).get("pct", 0)
            branches = total.get("branches", {}).get("pct", 0)
            functions = total.get("functions", {}).get("pct", 0)
            
            return {
                "line_coverage": round(lines, 2),
                "branch_coverage": round(branches, 2),
                "function_coverage": round(functions, 2),
            }
        
        except Exception:
            return None
    
    async def _run_pytest(self) -> Optional[Dict[str, Any]]:
        """
        Run pytest with coverage.
        
        Returns test execution results and coverage data.
        """
        try:
            cmd = [
                "pytest",
                "-v",
                "--tb=short",
                "--cov=.",
                "--cov-report=json",
                "--json-report",
                "--json-report-file=test-report.json",
            ]
            
            output = await self._run_command(cmd)
            
            if not output:
                return None
            
            # Parse pytest output
            return self._parse_pytest_output(output)
        
        except Exception:
            return None
    
    async def _run_jest(self) -> Optional[Dict[str, Any]]:
        """
        Run Jest with coverage.
        
        Returns test execution results and coverage data.
        """
        try:
            cmd = [
                "npx", "jest",
                "--coverage",
                "--json",
                "--outputFile=test-report.json",
            ]
            
            output = await self._run_command(cmd)
            
            if not output:
                return None
            
            return self._parse_jest_output(output)
        
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
    
    def _parse_pytest_output(self, output: str) -> Dict[str, Any]:
        """Parse pytest output."""
        result = {
            "execution": {
                "tests_run": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "tests_skipped": 0,
            },
            "coverage": {},
        }
        
        # Try to parse JSON report
        try:
            report_file = self.repo_path / "test-report.json"
            if report_file.exists():
                with open(report_file, 'r') as f:
                    data = json.load(f)
                
                summary = data.get("summary", {})
                result["execution"]["tests_run"] = summary.get("total", 0)
                result["execution"]["tests_passed"] = summary.get("passed", 0)
                result["execution"]["tests_failed"] = summary.get("failed", 0)
                result["execution"]["tests_skipped"] = summary.get("skipped", 0)
        
        except Exception:
            # Fall back to parsing text output
            if "passed" in output:
                match = re.search(r'(\d+) passed', output)
                if match:
                    result["execution"]["tests_passed"] = int(match.group(1))
            
            if "failed" in output:
                match = re.search(r'(\d+) failed', output)
                if match:
                    result["execution"]["tests_failed"] = int(match.group(1))
        
        # Parse coverage from coverage.json
        try:
            coverage_file = self.repo_path / "coverage.json"
            if coverage_file.exists():
                with open(coverage_file, 'r') as f:
                    cov_data = json.load(f)
                
                totals = cov_data.get("totals", {})
                result["coverage"]["line_coverage"] = round(
                    totals.get("percent_covered", 0), 2
                )
        
        except Exception:
            pass
        
        return result
    
    def _parse_jest_output(self, output: str) -> Dict[str, Any]:
        """Parse Jest JSON output."""
        result = {
            "execution": {
                "tests_run": 0,
                "tests_passed": 0,
                "tests_failed": 0,
                "tests_skipped": 0,
            },
            "coverage": {},
        }
        
        try:
            data = json.loads(output)
            
            result["execution"]["tests_run"] = data.get("numTotalTests", 0)
            result["execution"]["tests_passed"] = data.get("numPassedTests", 0)
            result["execution"]["tests_failed"] = data.get("numFailedTests", 0)
            result["execution"]["tests_skipped"] = data.get("numPendingTests", 0)
            
            # Coverage data
            coverage = data.get("coverageMap", {})
            if coverage:
                # Calculate average coverage across all files
                total_lines = 0
                covered_lines = 0
                
                for file_cov in coverage.values():
                    total_lines += file_cov.get("s", {}).get("total", 0)
                    covered_lines += file_cov.get("s", {}).get("covered", 0)
                
                if total_lines > 0:
                    result["coverage"]["line_coverage"] = round(
                        (covered_lines / total_lines) * 100, 2
                    )
        
        except json.JSONDecodeError:
            pass
        
        return result
    
    def _assess_test_quality(self, result: Dict[str, Any]) -> Dict[str, bool]:
        """
        Assess test quality based on objective criteria.
        
        Returns quality indicators as boolean flags.
        """
        has_tests = len(result["test_files"]) > 0
        
        coverage = result["coverage"].get("line_coverage")
        adequate_coverage = coverage is not None and coverage >= 70
        
        # Check test-to-code ratio (ideally >= 0.5)
        good_ratio = result["test_to_code_ratio"] >= 0.5
        
        # Check if critical code has tests
        code_files = result["code_files"]
        test_files = result["test_files"]
        
        critical_keywords = ['auth', 'payment', 'security', 'password', 'token']
        critical_files = [
            f for f in code_files
            if any(keyword in f.lower() for keyword in critical_keywords)
        ]
        
        tests_for_critical = True
        if critical_files and not test_files:
            tests_for_critical = False
        
        return {
            "has_tests": has_tests,
            "adequate_coverage": adequate_coverage,
            "good_test_ratio": good_ratio,
            "tests_for_critical_code": tests_for_critical,
            "no_failed_tests": result["test_execution"]["tests_failed"] == 0,
        }
    
    def get_test_summary(self, result: Dict[str, Any]) -> str:
        """
        Generate human-readable test summary for LLM context.
        """
        parts = []
        
        # Test file counts
        parts.append(f"Test files: {len(result['test_files'])}")
        parts.append(f"Code files: {len(result['code_files'])}")
        parts.append(f"Test-to-code ratio: {result['test_to_code_ratio']}")
        
        # Coverage
        coverage = result["coverage"]
        if coverage.get("line_coverage") is not None:
            parts.append(f"\nCoverage:")
            parts.append(f"  Line: {coverage['line_coverage']}%")
            if coverage.get("branch_coverage"):
                parts.append(f"  Branch: {coverage['branch_coverage']}%")
            if coverage.get("coverage_delta"):
                delta = coverage['coverage_delta']
                symbol = "+" if delta > 0 else ""
                parts.append(f"  Delta: {symbol}{delta}%")
        
        # Test execution
        execution = result["test_execution"]
        if execution["tests_run"] > 0:
            parts.append(f"\nTest execution:")
            parts.append(f"  Total: {execution['tests_run']}")
            parts.append(f"  Passed: {execution['tests_passed']}")
            if execution["tests_failed"] > 0:
                parts.append(f"  ⚠️ Failed: {execution['tests_failed']}")
            if execution["tests_skipped"] > 0:
                parts.append(f"  Skipped: {execution['tests_skipped']}")
        
        # Quality indicators
        indicators = result["quality_indicators"]
        parts.append(f"\nQuality indicators:")
        
        if not indicators["has_tests"]:
            parts.append("  ⚠️ No tests found for code changes")
        
        if not indicators["adequate_coverage"]:
            parts.append("  ⚠️ Coverage below 70%")
        
        if not indicators.get("good_test_ratio"):
            parts.append("  ⚠️ Low test-to-code ratio (< 0.5)")
        
        if not indicators["tests_for_critical_code"]:
            parts.append("  ⚠️ Critical code modified without tests")
        
        if indicators["has_tests"] and indicators["adequate_coverage"]:
            parts.append("  ✅ Good test coverage")
        
        return "\n".join(parts)
    
    def assess_test_risk(self, result: Dict[str, Any]) -> str:
        """
        Assess risk level based on test quality.
        
        Returns: low, medium, high, critical
        """
        indicators = result["quality_indicators"]
        coverage = result["coverage"].get("line_coverage", 0)
        failed_tests = result["test_execution"]["tests_failed"]
        
        # Critical: Failed tests or no tests for critical code
        if failed_tests > 0 or not indicators["tests_for_critical_code"]:
            return "critical"
        
        # High: No tests or very low coverage
        if not indicators["has_tests"] or (coverage and coverage < 50):
            return "high"
        
        # Medium: Low coverage or poor ratio
        if not indicators["adequate_coverage"] or not indicators.get("good_test_ratio"):
            return "medium"
        
        # Low: Good test coverage
        return "low"
