"""
Log Analyzer (Intelligence Engine - Layer 5)
Parses CI/CD logs and extracts objective failure information.
NO LLM - pure log parsing and pattern detection.

This prepares evidence for the CI/CD Agent (Layer 6) to interpret.
"""

import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


class LogAnalyzer:
    """
    Analyzes CI/CD logs to extract failure evidence.
    This is Layer 5 - objective facts only, no interpretation.
    """
    
    # Common error patterns across CI/CD systems
    ERROR_PATTERNS = [
        r"ERROR[:|\s]",
        r"FAILED[:|\s]",
        r"Exception[:|\s]",
        r"Error[:|\s]",
        r"FATAL[:|\s]",
        r"npm ERR!",
        r"AssertionError",
        r"Test failed",
        r"Build failed",
        r"Deployment failed",
    ]
    
    WARNING_PATTERNS = [
        r"WARNING[:|\s]",
        r"WARN[:|\s]",
        r"deprecated",
        r"⚠",
    ]
    
    TEST_FAILURE_PATTERNS = [
        r"(\d+) failed",
        r"(\d+) error",
        r"FAIL[:|\s].*test",
        r"Test.*failed",
    ]
    
    TIMEOUT_PATTERNS = [
        r"timeout",
        r"timed out",
        r"exceeded.*limit",
        r"killed.*timeout",
    ]
    
    MEMORY_PATTERNS = [
        r"OutOfMemory",
        r"out of memory",
        r"MemoryError",
        r"heap.*exceeded",
    ]
    
    NETWORK_PATTERNS = [
        r"ConnectionError",
        r"connection.*refused",
        r"Network.*unreachable",
        r"DNS.*failed",
        r"ECONNREFUSED",
    ]

    @staticmethod
    def analyze_build_log(
        log_content: str,
        exit_code: int,
        duration_seconds: float,
        build_step: str = "unknown",
    ) -> Dict[str, Any]:
        """
        Analyze build log and extract failure evidence.
        
        Args:
            log_content: Full log content
            exit_code: Process exit code
            duration_seconds: Build duration
            build_step: Which step failed (e.g., "npm install", "compile")
            
        Returns:
            Evidence dict with error details, patterns, and log excerpt
        """
        # Count errors and warnings
        error_count = LogAnalyzer._count_patterns(log_content, LogAnalyzer.ERROR_PATTERNS)
        warning_count = LogAnalyzer._count_patterns(log_content, LogAnalyzer.WARNING_PATTERNS)
        
        # Detect failure patterns
        failure_patterns = LogAnalyzer._detect_failure_patterns(log_content)
        
        # Extract error context (last 50 lines before failure)
        error_excerpt = LogAnalyzer._extract_error_context(log_content, lines=50)
        
        # Classify failure type
        failure_type = LogAnalyzer._classify_failure_type(log_content, failure_patterns)
        
        # Calculate risk score
        risk_score = LogAnalyzer._calculate_log_risk_score(
            error_count=error_count,
            exit_code=exit_code,
            failure_type=failure_type,
            duration_seconds=duration_seconds,
        )
        
        return {
            "log_type": "build",
            "exit_code": exit_code,
            "duration_seconds": duration_seconds,
            "failed_step": build_step,
            "error_count": error_count,
            "warning_count": warning_count,
            "failure_patterns": failure_patterns,
            "failure_type": failure_type,
            "log_excerpt": error_excerpt,
            "risk_score": risk_score,
            "risk_level": LogAnalyzer._classify_risk_level(risk_score),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def analyze_test_log(
        log_content: str,
        tests_run: int,
        tests_passed: int,
        tests_failed: int,
        duration_seconds: float,
    ) -> Dict[str, Any]:
        """
        Analyze test log and extract failure evidence.
        
        Args:
            log_content: Full test log
            tests_run: Total tests executed
            tests_passed: Number passed
            tests_failed: Number failed
            duration_seconds: Test duration
            
        Returns:
            Evidence dict with test failure details
        """
        # Extract failed test names
        failed_tests = LogAnalyzer._extract_failed_test_names(log_content)
        
        # Detect flaky test indicators
        flaky_indicators = LogAnalyzer._detect_flaky_indicators(log_content)
        
        # Extract error messages
        error_excerpt = LogAnalyzer._extract_error_context(log_content, lines=100)
        
        # Calculate test health score
        test_pass_rate = (tests_passed / max(tests_run, 1)) * 100
        risk_score = LogAnalyzer._calculate_test_risk_score(
            test_pass_rate=test_pass_rate,
            tests_failed=tests_failed,
            has_flaky_indicators=len(flaky_indicators) > 0,
        )
        
        return {
            "log_type": "test",
            "tests_run": tests_run,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
            "test_pass_rate": round(test_pass_rate, 2),
            "failed_tests": failed_tests,
            "flaky_indicators": flaky_indicators,
            "duration_seconds": duration_seconds,
            "log_excerpt": error_excerpt,
            "risk_score": risk_score,
            "risk_level": LogAnalyzer._classify_risk_level(risk_score),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def analyze_deployment_log(
        log_content: str,
        deployment_status: str,
        environment: str,
        duration_seconds: float,
    ) -> Dict[str, Any]:
        """
        Analyze deployment log and extract failure evidence.
        
        Args:
            log_content: Full deployment log
            deployment_status: success|failed|rolled_back
            environment: staging|production
            duration_seconds: Deployment duration
            
        Returns:
            Evidence dict with deployment failure details
        """
        # Detect deployment issues
        deployment_issues = LogAnalyzer._detect_deployment_issues(log_content)
        
        # Extract error context
        error_excerpt = LogAnalyzer._extract_error_context(log_content, lines=75)
        
        # Calculate deployment risk
        risk_score = LogAnalyzer._calculate_deployment_risk_score(
            deployment_status=deployment_status,
            environment=environment,
            issue_count=len(deployment_issues),
        )
        
        return {
            "log_type": "deployment",
            "deployment_status": deployment_status,
            "environment": environment,
            "duration_seconds": duration_seconds,
            "deployment_issues": deployment_issues,
            "log_excerpt": error_excerpt,
            "risk_score": risk_score,
            "risk_level": LogAnalyzer._classify_risk_level(risk_score),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ── Helper Methods ──────────────────────────────────────────

    @staticmethod
    def _count_patterns(text: str, patterns: List[str]) -> int:
        """Count occurrences of regex patterns in text."""
        count = 0
        for pattern in patterns:
            count += len(re.findall(pattern, text, re.IGNORECASE))
        return count

    @staticmethod
    def _detect_failure_patterns(log_content: str) -> List[str]:
        """Detect specific failure patterns in logs."""
        patterns_found = []
        
        # Check for test failures
        if LogAnalyzer._count_patterns(log_content, LogAnalyzer.TEST_FAILURE_PATTERNS) > 0:
            patterns_found.append("test_failures")
        
        # Check for timeouts
        if LogAnalyzer._count_patterns(log_content, LogAnalyzer.TIMEOUT_PATTERNS) > 0:
            patterns_found.append("timeout")
        
        # Check for memory issues
        if LogAnalyzer._count_patterns(log_content, LogAnalyzer.MEMORY_PATTERNS) > 0:
            patterns_found.append("out_of_memory")
        
        # Check for network issues
        if LogAnalyzer._count_patterns(log_content, LogAnalyzer.NETWORK_PATTERNS) > 0:
            patterns_found.append("network_error")
        
        # Dependency issues
        if ("npm ERR!" in log_content or "pip install" in log_content) and "ERROR" in log_content:
            patterns_found.append("dependency_error")
        
        return patterns_found

    @staticmethod
    def _extract_error_context(log_content: str, lines: int = 50) -> str:
        """Extract relevant log lines around errors."""
        log_lines = log_content.split("\n")
        
        # Find first error line
        error_line_idx = None
        for i, line in enumerate(log_lines):
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in LogAnalyzer.ERROR_PATTERNS):
                error_line_idx = i
                break
        
        if error_line_idx is None:
            # No error found, return last N lines
            return "\n".join(log_lines[-lines:])
        
        # Extract context around error
        start_idx = max(0, error_line_idx - 10)
        end_idx = min(len(log_lines), error_line_idx + lines)
        
        return "\n".join(log_lines[start_idx:end_idx])

    @staticmethod
    def _classify_failure_type(log_content: str, failure_patterns: List[str]) -> str:
        """Classify the type of failure based on patterns."""
        if "test_failures" in failure_patterns:
            return "test_failure"
        elif "timeout" in failure_patterns:
            return "timeout"
        elif "out_of_memory" in failure_patterns:
            return "memory_issue"
        elif "network_error" in failure_patterns:
            return "network_issue"
        elif "dependency_error" in failure_patterns:
            return "dependency_issue"
        elif "compile" in log_content.lower() or "syntax" in log_content.lower():
            return "compilation_error"
        else:
            return "unknown"

    @staticmethod
    def _extract_failed_test_names(log_content: str) -> List[str]:
        """Extract names of failed tests from log."""
        failed_tests = []
        
        # Common test failure patterns
        patterns = [
            r"FAIL\s+(.+?)(?:\n|$)",
            r"✖\s+(.+?)(?:\n|$)",
            r"FAILED\s+(.+?)(?:\n|$)",
            r"Error:\s+(.+?)\s+failed",
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, log_content, re.MULTILINE)
            failed_tests.extend([m.strip() for m in matches])
        
        return list(set(failed_tests))[:10]  # Return up to 10 unique

    @staticmethod
    def _detect_flaky_indicators(log_content: str) -> List[str]:
        """Detect indicators of flaky tests."""
        indicators = []
        
        flaky_patterns = {
            "timing": r"timeout|async|await.*failed|promise.*rejected",
            "race_condition": r"race condition|concurrent|parallel",
            "network": r"connection.*refused|ECONNREFUSED|network.*error",
            "random": r"Math\.random|random|flaky",
        }
        
        for indicator_type, pattern in flaky_patterns.items():
            if re.search(pattern, log_content, re.IGNORECASE):
                indicators.append(indicator_type)
        
        return indicators

    @staticmethod
    def _detect_deployment_issues(log_content: str) -> List[str]:
        """Detect deployment-specific issues."""
        issues = []
        
        deployment_patterns = {
            "Database migration failed": r"migration.*failed|rollback.*migration",
            "Health check failed": r"health.*check.*failed|unhealthy",
            "Service not ready": r"service.*not.*ready|timeout.*waiting",
            "Port conflict": r"port.*already.*in.*use|EADDRINUSE",
            "Permission denied": r"permission.*denied|access.*denied",
        }
        
        for issue_name, pattern in deployment_patterns.items():
            if re.search(pattern, log_content, re.IGNORECASE):
                issues.append(issue_name)
        
        return issues

    @staticmethod
    def _calculate_log_risk_score(
        error_count: int,
        exit_code: int,
        failure_type: str,
        duration_seconds: float,
    ) -> int:
        """Calculate risk score based on log analysis."""
        risk_score = 0
        
        # Exit code
        if exit_code != 0:
            risk_score += 30
        
        # Error count
        if error_count > 10:
            risk_score += 30
        elif error_count > 5:
            risk_score += 20
        elif error_count > 0:
            risk_score += 10
        
        # Failure type
        if failure_type in ["memory_issue", "timeout"]:
            risk_score += 25
        elif failure_type in ["test_failure", "compilation_error"]:
            risk_score += 15
        
        # Duration (very slow builds are risky)
        if duration_seconds > 1800:  # 30 minutes
            risk_score += 15
        
        return min(risk_score, 100)

    @staticmethod
    def _calculate_test_risk_score(
        test_pass_rate: float,
        tests_failed: int,
        has_flaky_indicators: bool,
    ) -> int:
        """Calculate risk score for test failures."""
        risk_score = 0
        
        # Pass rate
        if test_pass_rate < 70:
            risk_score += 50
        elif test_pass_rate < 85:
            risk_score += 30
        elif test_pass_rate < 95:
            risk_score += 15
        
        # Failed count
        if tests_failed > 10:
            risk_score += 30
        elif tests_failed > 5:
            risk_score += 20
        elif tests_failed > 0:
            risk_score += 10
        
        # Flaky indicators
        if has_flaky_indicators:
            risk_score += 20
        
        return min(risk_score, 100)

    @staticmethod
    def _calculate_deployment_risk_score(
        deployment_status: str,
        environment: str,
        issue_count: int,
    ) -> int:
        """Calculate risk score for deployment."""
        risk_score = 0
        
        # Status
        if deployment_status == "failed":
            risk_score += 60
        elif deployment_status == "rolled_back":
            risk_score += 50
        
        # Environment
        if environment == "production":
            risk_score += 20  # Production failures are more critical
        
        # Issue count
        risk_score += issue_count * 10
        
        return min(risk_score, 100)

    @staticmethod
    def _classify_risk_level(risk_score: int) -> str:
        """Classify numeric risk score into level."""
        if risk_score >= 70:
            return "CRITICAL"
        elif risk_score >= 50:
            return "HIGH"
        elif risk_score >= 30:
            return "MEDIUM"
        else:
            return "LOW"
