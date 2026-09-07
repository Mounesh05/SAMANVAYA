"""
Quality metrics calculator.
Analyzes test results, bug trends, and code quality indicators.
NO LLM - pure data analysis.
"""

from typing import Optional


class QualityMetrics:
    """Calculate quality-related metrics."""

    @staticmethod
    def calculate_test_health(
        tests_passed: int,
        tests_failed: int,
        tests_skipped: int = 0,
    ) -> dict:
        """
        Calculate test health metrics.
        
        Returns:
            Test pass rate, failure analysis, and risk score
        """
        total_tests = tests_passed + tests_failed + tests_skipped
        
        if total_tests == 0:
            return {
                "total_tests": 0,
                "pass_rate": None,  # None = unknown, not 0%
                "risk_score": None,  # Cannot calculate risk without data
                "risk_level": "UNKNOWN",
                "risk_factors": ["No test data available"],
                "data_quality": "insufficient",
            }
        
        pass_rate = (tests_passed / total_tests) * 100
        
        risk_score = 0
        risk_factors = []
        
        # Test failure risk
        if tests_failed > 0:
            failure_pct = (tests_failed / total_tests) * 100
            if failure_pct > 20:
                risk_score += 40
                risk_factors.append(f"High test failure rate: {failure_pct:.1f}%")
            elif failure_pct > 10:
                risk_score += 25
                risk_factors.append(f"Moderate test failure rate: {failure_pct:.1f}%")
            elif failure_pct > 5:
                risk_score += 15
                risk_factors.append(f"Some tests failing: {tests_failed}")
            else:
                risk_score += 5
                risk_factors.append(f"Minor test failures: {tests_failed}")
        
        # Skipped tests concern
        if tests_skipped > 0:
            skip_pct = (tests_skipped / total_tests) * 100
            if skip_pct > 10:
                risk_score += 20
                risk_factors.append(f"Many tests skipped: {skip_pct:.1f}%")
            elif skip_pct > 5:
                risk_score += 10
                risk_factors.append(f"Some tests skipped: {tests_skipped}")
        
        # Risk level classification
        if risk_score >= 50:
            risk_level = "CRITICAL"
        elif risk_score >= 30:
            risk_level = "HIGH"
        elif risk_score >= 15:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        return {
            "total_tests": total_tests,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
            "data_quality": "complete",
            "tests_skipped": tests_skipped,
            "pass_rate": round(pass_rate, 2),
            "risk_score": min(risk_score, 100),
            "risk_level": risk_level,
            "risk_factors": risk_factors,
        }

    @staticmethod
    def calculate_bug_density(
        open_bugs: int,
        critical_bugs: int,
        high_bugs: int,
        total_stories: int = 1,
    ) -> dict:
        """
        Calculate bug density and severity distribution.
        
        Args:
            open_bugs: Total open bugs
            critical_bugs: Critical severity bugs
            high_bugs: High severity bugs
            total_stories: Number of stories (for density calculation)
        """
        bug_density = open_bugs / max(total_stories, 1)
        
        risk_score = 0
        risk_factors = []
        
        # Critical bugs = immediate risk
        if critical_bugs > 0:
            risk_score += critical_bugs * 30
            risk_factors.append(f"{critical_bugs} critical bugs open")
        
        # High severity bugs
        if high_bugs > 0:
            risk_score += high_bugs * 15
            risk_factors.append(f"{high_bugs} high severity bugs")
        
        # Overall bug density
        if bug_density > 2:
            risk_score += 25
            risk_factors.append(f"High bug density: {bug_density:.1f} bugs per story")
        elif bug_density > 1:
            risk_score += 10
            risk_factors.append(f"Moderate bug density: {bug_density:.1f}")
        
        risk_level = "CRITICAL" if risk_score >= 60 else \
                     "HIGH" if risk_score >= 40 else \
                     "MEDIUM" if risk_score >= 20 else "LOW"
        
        return {
            "open_bugs": open_bugs,
            "critical_bugs": critical_bugs,
            "high_bugs": high_bugs,
            "bug_density": round(bug_density, 2),
            "risk_score": min(risk_score, 100),
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "data_quality": "complete",
        }

    @staticmethod
    def calculate_coverage_change(
        previous_coverage: Optional[float],
        current_coverage: Optional[float],
    ) -> dict:
        """
        Analyze test coverage changes.
        
        Decreasing coverage is a quality concern.
        """
        if previous_coverage is None or current_coverage is None:
            return {
                "previous_coverage": previous_coverage,
                "current_coverage": current_coverage,
                "coverage_change": None,
                "risk_score": None,  # Cannot calculate without data
                "risk_level": "UNKNOWN",
                "risk_factors": ["Coverage data unavailable"],
                "data_quality": "insufficient",
            }
        
        coverage_change = current_coverage - previous_coverage
        
        risk_score = 0
        risk_factors = []
        
        if coverage_change < -5:
            risk_score += 30
            risk_factors.append(f"Significant coverage drop: {coverage_change:.1f}%")
        elif coverage_change < -2:
            risk_score += 15
            risk_factors.append(f"Coverage decreased: {coverage_change:.1f}%")
        elif coverage_change < 0:
            risk_score += 5
            risk_factors.append(f"Minor coverage drop: {coverage_change:.1f}%")
        elif coverage_change > 5:
            risk_factors.append(f"Coverage improved: +{coverage_change:.1f}%")
        
        # Low absolute coverage concern
        if current_coverage < 60:
            risk_score += 20
            risk_factors.append(f"Low coverage: {current_coverage:.1f}%")
        elif current_coverage < 70:
            risk_score += 10
            risk_factors.append(f"Below target coverage: {current_coverage:.1f}%")
        
        return {
            "previous_coverage": round(previous_coverage, 2),
            "current_coverage": round(current_coverage, 2),
            "coverage_change": round(coverage_change, 2),
            "risk_score": min(risk_score, 100),
            "risk_factors": risk_factors,
            "data_quality": "complete",
        }

    @staticmethod
    def calculate_regression_risk(
        changed_modules: list[str],
        historical_bug_modules: list[str],
        recent_failures: int = 0,
    ) -> dict:
        """
        Calculate regression risk based on historical bug patterns.
        
        Modules that have had bugs before are riskier to change.
        """
        buggy_modules_touched = [
            module for module in changed_modules
            if module in historical_bug_modules
        ]
        
        risk_score = len(buggy_modules_touched) * 15
        risk_factors = []
        
        if buggy_modules_touched:
            risk_factors.append(
                f"{len(buggy_modules_touched)} historically buggy modules changed"
            )
        
        if recent_failures > 0:
            risk_score += recent_failures * 10
            risk_factors.append(f"{recent_failures} recent test failures")
        
        risk_level = "HIGH" if risk_score >= 40 else \
                     "MEDIUM" if risk_score >= 20 else "LOW"
        
        return {
            "changed_modules": len(changed_modules),
            "buggy_modules_touched": len(buggy_modules_touched),
            "modules_at_risk": buggy_modules_touched,
            "recent_failures": recent_failures,
            "risk_score": min(risk_score, 100),
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "data_quality": "complete" if changed_modules else "insufficient",
        }
