"""
DevOps metrics calculator.
Analyzes deployment frequency, CI/CD health, and operational metrics.
NO LLM - pure data analysis.
"""

from typing import Optional
from datetime import datetime


class DevOpsMetrics:
    """Calculate DevOps and deployment-related metrics."""

    @staticmethod
    def calculate_ci_health(
        builds_total: int,
        builds_passed: int,
        builds_failed: int,
        avg_build_time_minutes: Optional[float] = None,
    ) -> dict:
        """
        Calculate CI pipeline health.
        
        Returns:
            Build success rate and pipeline health risk
        """
        if builds_total == 0:
            return {
                "builds_total": 0,
                "success_rate": None,  # Unknown, not 0%
                "risk_score": None,  # Cannot assess risk without data
                "risk_level": "UNKNOWN",
                "risk_factors": ["No build data available"],
                "data_quality": "insufficient",
            }
        
        success_rate = (builds_passed / builds_total) * 100
        
        risk_score = 0
        risk_factors = []
        
        # Build failure risk
        if success_rate < 50:
            risk_score += 50
            risk_factors.append(f"Very low build success rate: {success_rate:.1f}%")
        elif success_rate < 70:
            risk_score += 30
            risk_factors.append(f"Low build success rate: {success_rate:.1f}%")
        elif success_rate < 85:
            risk_score += 15
            risk_factors.append(f"Moderate build success rate: {success_rate:.1f}%")
        
        # Build time concern
        if avg_build_time_minutes and avg_build_time_minutes > 30:
            risk_score += 15
            risk_factors.append(f"Slow builds: {avg_build_time_minutes:.1f} min average")
        elif avg_build_time_minutes and avg_build_time_minutes > 15:
            risk_score += 5
            risk_factors.append(f"Build time above target: {avg_build_time_minutes:.1f} min")
        
        risk_level = "CRITICAL" if risk_score >= 50 else \
                     "HIGH" if risk_score >= 30 else \
                     "MEDIUM" if risk_score >= 15 else "LOW"
        
        return {
            "builds_total": builds_total,
            "builds_passed": builds_passed,
            "builds_failed": builds_failed,
            "success_rate": round(success_rate, 2),
            "avg_build_time_minutes": avg_build_time_minutes,
            "risk_score": min(risk_score, 100),
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "data_quality": "complete",
        }

    @staticmethod
    def calculate_deployment_health(
        deployments_total: int,
        deployments_successful: int,
        deployments_failed: int,
        rollbacks: int = 0,
    ) -> dict:
        """
        Calculate deployment health and reliability.
        
        Returns:
            Deployment success rate and risk assessment
        """
        if deployments_total == 0:
            return {
                "deployments_total": 0,
                "success_rate": None,  # Unknown deployment health
                "risk_score": None,  # No baseline to assess
                "risk_level": "UNKNOWN",
                "risk_factors": ["No deployment history"],
                "data_quality": "insufficient",
            }
        
        success_rate = (deployments_successful / deployments_total) * 100
        
        risk_score = 0
        risk_factors = []
        
        # Deployment failure risk
        if success_rate < 80:
            risk_score += 40
            risk_factors.append(f"Low deployment success rate: {success_rate:.1f}%")
        elif success_rate < 90:
            risk_score += 20
            risk_factors.append(f"Moderate deployment success rate: {success_rate:.1f}%")
        
        # Rollback risk
        if rollbacks > 0:
            rollback_pct = (rollbacks / deployments_total) * 100
            if rollback_pct > 20:
                risk_score += 40
                risk_factors.append(f"High rollback rate: {rollback_pct:.1f}%")
            elif rollback_pct > 10:
                risk_score += 25
                risk_factors.append(f"Moderate rollback rate: {rollback_pct:.1f}%")
            else:
                risk_score += 10
                risk_factors.append(f"{rollbacks} rollbacks occurred")
        
        risk_level = "CRITICAL" if risk_score >= 50 else \
                     "HIGH" if risk_score >= 30 else \
                     "MEDIUM" if risk_score >= 15 else "LOW"
        
        return {
            "deployments_total": deployments_total,
            "deployments_successful": deployments_successful,
            "deployments_failed": deployments_failed,
            "rollbacks": rollbacks,
            "success_rate": round(success_rate, 2),
            "risk_score": min(risk_score, 100),
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "data_quality": "complete",
        }

    @staticmethod
    def calculate_deployment_frequency(
        deployments_last_week: int,
        deployments_last_month: int,
    ) -> dict:
        """
        Analyze deployment frequency patterns.
        
        Higher frequency generally indicates better DevOps maturity.
        """
        # Guard: If no deployment data at all, return None for risk_score
        if deployments_last_week == 0 and deployments_last_month == 0:
            return {
                "deployments_last_week": 0,
                "deployments_last_month": 0,
                "weekly_average": 0.0,
                "maturity_level": "UNKNOWN",
                "risk_score": None,  # None = no data
                "risk_factors": ["No deployment data available"],
                "data_quality": "insufficient",
            }
        
        weekly_avg = deployments_last_month / 4  # approximate
        
        risk_score = 0
        risk_factors = []
        maturity_level = ""
        
        # DORA metrics-inspired frequency classification
        if deployments_last_week >= 5:
            maturity_level = "Elite"
            risk_factors.append("High deployment frequency (Elite)")
        elif deployments_last_week >= 1:
            maturity_level = "High"
            risk_factors.append("Good deployment frequency")
        elif weekly_avg >= 0.5:
            maturity_level = "Medium"
            risk_score += 10
            risk_factors.append("Moderate deployment frequency")
        else:
            maturity_level = "Low"
            risk_score += 25
            risk_factors.append("Low deployment frequency - may indicate bottlenecks")
        
        return {
            "deployments_last_week": deployments_last_week,
            "deployments_last_month": deployments_last_month,
            "weekly_average": round(weekly_avg, 2),
            "maturity_level": maturity_level,
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "data_quality": "complete",
        }

    @staticmethod
    def calculate_mttr(
        incidents_count: int,
        total_resolution_time_hours: float,
    ) -> dict:
        """
        Calculate Mean Time To Recovery (MTTR).
        
        Lower MTTR indicates better incident response.
        """
        # Note: 0 incidents is actually GOOD (no risk), not missing data
        if incidents_count == 0:
            return {
                "incidents_count": 0,
                "mttr_hours": 0.0,
                "risk_score": 0,  # 0 = actually no risk (no incidents)
                "risk_factors": ["No incidents in period"],
                "data_quality": "complete",  # This IS complete data
            }
        
        mttr = total_resolution_time_hours / incidents_count
        
        risk_score = 0
        risk_factors = []
        
        # MTTR thresholds (DORA metrics-inspired)
        if mttr > 24:
            risk_score += 40
            risk_factors.append(f"High MTTR: {mttr:.1f} hours")
        elif mttr > 8:
            risk_score += 25
            risk_factors.append(f"Moderate MTTR: {mttr:.1f} hours")
        elif mttr > 2:
            risk_score += 10
            risk_factors.append(f"MTTR: {mttr:.1f} hours")
        else:
            risk_factors.append(f"Good MTTR: {mttr:.1f} hours")
        
        return {
            "incidents_count": incidents_count,
            "mttr_hours": round(mttr, 2),
            "risk_score": min(risk_score, 100),
            "risk_factors": risk_factors,
        }
