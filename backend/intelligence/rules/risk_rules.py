"""
Risk classification rules.
Defines thresholds and rules for classifying risk levels.
NO LLM - pure business logic.

Gap Fix #2: RISK_DIMENSION_WEIGHTS and QUALITY_DIMENSION_WEIGHTS are the
single source of truth for all scoring formulas. Imported by:
  - intelligence/analyzers/registry.py  (re-exported)
  - intelligence/risk_engine.py         (analyze_evidence)
  - intelligence/quality_engine.py      (QualityEngine)
"""

from typing import List, Dict

# ── Gap Fix #2: Risk Dimension Weight Table ───────────────────────────────────
# R = BASE_RISK + alpha*Z_size + beta*hotspot + gamma*dep + delta*tests
#               + epsilon*security + zeta*complexity
# All weights sum to 100 so the final risk score stays within [0, 100].

RISK_DIMENSION_WEIGHTS: Dict[str, float] = {
    "alpha_size_zscore":   12.0,   # PR size Z-score vs. repo historical median
    "beta_hotspot":        20.0,   # historical incident-prone files changed
    "gamma_dependency":    15.0,   # new or updated third-party packages
    "delta_missing_tests": 18.0,   # changed lines with no test coverage
    "epsilon_security":    25.0,   # CVSS-weighted vulnerability score
    "zeta_complexity":     10.0,   # cyclomatic spike above repo baseline
}
BASE_RISK: float = 10.0            # Every PR starts with 10 base risk points

# ── Quality Dimension Weight Table ────────────────────────────────────────────
# Q = 100 - (w_s*S + w_c*C + w_t*T + w_d*D + w_a*A)
# Weights must sum to 1.0.

QUALITY_DIMENSION_WEIGHTS: Dict[str, float] = {
    "static_security": 0.25,
    "testing":         0.25,
    "complexity":      0.20,
    "architecture":    0.20,
    "duplication":     0.10,
}

# ── Simple Risk Engine Thresholds ────────────────────────────────────────────
# Used by RiskEngine._build_simple_pr_evidence() and related methods.
# These replace hardcoded magic numbers with named, documented constants.

# PR size thresholds (files changed)
PR_SIZE_LARGE_THRESHOLD = 20       # >20 files = large PR
PR_SIZE_MEDIUM_THRESHOLD = 10      # >10 files = medium PR
PR_SIZE_SMALL_THRESHOLD = 5        # >5 files = small PR

PR_SIZE_LARGE_RISK = 30
PR_SIZE_MEDIUM_RISK = 20
PR_SIZE_SMALL_RISK = 10

# Code churn thresholds (lines added + deleted)
CHURN_HIGH_THRESHOLD = 1000
CHURN_MEDIUM_THRESHOLD = 500
CHURN_HIGH_RISK = 20
CHURN_MEDIUM_RISK = 10

# Test failure risk
TEST_FAILURE_RISK = 25
TEST_NONE_PASSING_RISK = 15

# Coverage decrease risk
COVERAGE_DECREASE_RISK = 15

# PR staleness threshold (hours)
PR_STALE_THRESHOLD_HOURS = 168    # 1 week
PR_STALE_RISK = 10

# Sprint risk thresholds
SPRINT_BLOCKED_HIGH_PCT = 20      # >20% blocked = high risk
SPRINT_BLOCKED_HIGH_RISK = 30
SPRINT_BLOCKED_LOW_RISK = 15

SPRINT_BEHIND_SCHEDULE_RISK = 40
SPRINT_SLIGHT_BEHIND_RISK = 20

SPRINT_SCOPE_CREEP_HIGH_PCT = 20  # >20% scope increase
SPRINT_SCOPE_CREEP_HIGH_RISK = 20
SPRINT_SCOPE_CREEP_LOW_RISK = 10

SPRINT_LOW_COMPLETION_RISK = 10
SPRINT_LOW_COMPLETION_PCT = 30
SPRINT_TIME_ELAPSED_PCT = 50

# Deployment risk thresholds
DEPLOY_BUILD_FAILURE_HIGH_PCT = 30
DEPLOY_BUILD_FAILURE_LOW_PCT = 10
DEPLOY_BUILD_FAILURE_HIGH_RISK = 30
DEPLOY_BUILD_FAILURE_LOW_RISK = 15

DEPLOY_DEPLOY_FAILURE_HIGH_PCT = 20
DEPLOY_DEPLOY_FAILURE_LOW_PCT = 10
DEPLOY_DEPLOY_FAILURE_HIGH_RISK = 40
DEPLOY_DEPLOY_FAILURE_LOW_RISK = 20

DEPLOY_ROLLBACK_HIGH_PCT = 10
DEPLOY_ROLLBACK_HIGH_RISK = 30
DEPLOY_ROLLBACK_LOW_RISK = 15


class RiskRules:
    """Risk classification and threshold rules."""

    # Risk level thresholds
    RISK_THRESHOLDS = {
        "CRITICAL": 70,
        "HIGH": 50,
        "MEDIUM": 30,
        "LOW": 0,
    }

    @staticmethod
    def classify_risk_level(risk_score: int) -> str:
        """
        Classify numeric risk score into risk level.
        
        Args:
            risk_score: Integer 0-100
        
        Returns:
            Risk level: CRITICAL|HIGH|MEDIUM|LOW
        """
        if risk_score >= RiskRules.RISK_THRESHOLDS["CRITICAL"]:
            return "CRITICAL"
        elif risk_score >= RiskRules.RISK_THRESHOLDS["HIGH"]:
            return "HIGH"
        elif risk_score >= RiskRules.RISK_THRESHOLDS["MEDIUM"]:
            return "MEDIUM"
        else:
            return "LOW"

    @staticmethod
    def aggregate_risk_scores(scores: List[int], weights: List[float] = None) -> int:
        """
        Aggregate multiple risk scores into a single score.
        
        Args:
            scores: List of risk scores (0-100)
            weights: Optional weights for each score (defaults to equal weight)
        
        Returns:
            Aggregated risk score (0-100)
        """
        if not scores:
            return 0
        
        if weights is None:
            weights = [1.0] * len(scores)
        
        if len(scores) != len(weights):
            raise ValueError("Scores and weights must have same length")
        
        total_weight = sum(weights)
        weighted_sum = sum(score * weight for score, weight in zip(scores, weights))
        
        return min(int(weighted_sum / total_weight), 100)

    @staticmethod
    def determine_action_required(risk_level: str, entity_type: str) -> Dict:
        """
        Determine recommended actions based on risk level and entity type.
        
        Args:
            risk_level: CRITICAL|HIGH|MEDIUM|LOW
            entity_type: pull_request|sprint|deployment|story
        
        Returns:
            Dict with actions and urgency
        """
        actions = {
            "CRITICAL": {
                "pull_request": [
                    "Block merge until issues resolved",
                    "Require senior engineer review",
                    "Add comprehensive tests",
                    "Consider breaking into smaller PRs",
                ],
                "sprint": [
                    "Immediate PM/LEAD review required",
                    "Escalate to management",
                    "Re-prioritize or descope",
                    "Identify and unblock stories",
                ],
                "deployment": [
                    "Hold deployment",
                    "Require QA sign-off",
                    "Prepare rollback plan",
                    "Alert on-call team",
                ],
                "story": [
                    "Reassign or add resources",
                    "Break into smaller tasks",
                    "Escalate blockers",
                ],
            },
            "HIGH": {
                "pull_request": [
                    "Additional reviewer required",
                    "Run extended test suite",
                    "Manual QA before merge",
                ],
                "sprint": [
                    "Daily standup focus",
                    "Remove impediments",
                    "Consider descoping low-priority stories",
                ],
                "deployment": [
                    "Extra monitoring",
                    "Deploy during low-traffic window",
                    "Have rollback ready",
                ],
                "story": [
                    "Pair programming recommended",
                    "Increase test coverage",
                ],
            },
            "MEDIUM": {
                "pull_request": [
                    "Standard review process",
                    "Verify test coverage",
                ],
                "sprint": [
                    "Monitor progress",
                    "Regular check-ins",
                ],
                "deployment": [
                    "Standard monitoring",
                ],
                "story": [
                    "Proceed with normal workflow",
                ],
            },
            "LOW": {
                "pull_request": ["Standard review"],
                "sprint": ["Normal monitoring"],
                "deployment": ["Proceed normally"],
                "story": ["No special action"],
            },
        }
        
        urgency_map = {
            "CRITICAL": "immediate",
            "HIGH": "within_hours",
            "MEDIUM": "within_day",
            "LOW": "normal",
        }
        
        return {
            "actions": actions.get(risk_level, {}).get(entity_type, []),
            "urgency": urgency_map.get(risk_level, "normal"),
            "requires_approval": risk_level in ["CRITICAL", "HIGH"],
        }
