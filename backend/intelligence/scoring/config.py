"""
Scoring Configuration — Configurable weights, sub-dimensions, and thresholds.

Can be modified or overridden per company/organization without rewriting agents.
"""

from typing import Dict, Any

SCORING_VERSION = "1.0"

# ─────────────────────────────────────────────────────────────────────────────
# Sub-dimension configurations for each specialist agent
# ─────────────────────────────────────────────────────────────────────────────

CODE_QUALITY_CONFIG: Dict[str, Any] = {
    "agent_id": "code_agent",
    "score_type": "code_quality",
    "total_points": 100.0,
    "min_evidence_threshold": 1,  # At least 1 PR or commit needed
    "subscores": {
        "correctness": {
            "max": 20.0,
            "description": "Functional correctness, bug fixes, defect-free commits",
        },
        "maintainability": {
            "max": 20.0,
            "description": "Cyclomatic complexity, modularity, small clean diffs, maintainability index",
        },
        "security": {
            "max": 20.0,
            "description": "Absence of vulnerabilities, secret leaks, injection flaws, and static security flags",
        },
        "testing_in_code": {
            "max": 15.0,
            "description": "Inclusion of unit/integration tests alongside PR changes",
        },
        "performance": {
            "max": 10.0,
            "description": "Absence of performance anti-patterns, efficient algorithms, zero memory leaks",
        },
        "architecture": {
            "max": 10.0,
            "description": "Adherence to layering rules, clean abstractions, no circular dependencies",
        },
        "readability": {
            "max": 5.0,
            "description": "Clear naming, code cleanliness, concise self-explanatory structure",
        },
    },
}

QA_TESTING_CONFIG: Dict[str, Any] = {
    "agent_id": "qa_agent",
    "score_type": "testing_reliability",
    "total_points": 100.0,
    "min_evidence_threshold": 1,
    "subscores": {
        "test_coverage": {
            "max": 25.0,
            "description": "Line and branch coverage percentage achieved on modified files",
        },
        "test_completeness": {
            "max": 20.0,
            "description": "Edge case coverage, unit + integration + e2e test completeness",
        },
        "regression_prevention": {
            "max": 20.0,
            "description": "Zero introduced regressions, proactive regression test suite expansion",
        },
        "test_reliability": {
            "max": 15.0,
            "description": "Deterministic test execution, zero flaky tests introduced",
        },
        "test_quality": {
            "max": 10.0,
            "description": "High assertion density, meaningful test suites rather than vanity coverage",
        },
        "defect_prevention": {
            "max": 10.0,
            "description": "Early bug catch rate prior to staging/production releases",
        },
    },
}

DEVOPS_CONFIG: Dict[str, Any] = {
    "agent_id": "devops_agent",
    "score_type": "devops",
    "total_points": 100.0,
    "min_evidence_threshold": 1,
    "subscores": {
        "deployment_reliability": {
            "max": 25.0,
            "description": "Production release success rate and deployment stability",
        },
        "infrastructure_safety": {
            "max": 20.0,
            "description": "IaC hygiene, container security, zero misconfigurations, blast radius control",
        },
        "change_risk_management": {
            "max": 20.0,
            "description": "Safe schema migrations, non-breaking API contracts, phased rollouts",
        },
        "rollback_recovery": {
            "max": 15.0,
            "description": "Safe rollback strategies, rapid MTTR when incidents arise",
        },
        "observability": {
            "max": 10.0,
            "description": "Structured logging, telemetry, metrics, alerts, health check probes",
        },
        "operational_practices": {
            "max": 10.0,
            "description": "Environment isolation, secret management adherence, runbook documentation",
        },
    },
}

CICD_CONFIG: Dict[str, Any] = {
    "agent_id": "cicd_agent",
    "score_type": "cicd",
    "total_points": 100.0,
    "min_evidence_threshold": 1,
    "subscores": {
        "pipeline_reliability": {
            "max": 30.0,
            "description": "Build & test pipeline pass rate for owned/contributed workflows",
        },
        "failure_resolution": {
            "max": 20.0,
            "description": "Speed and effectiveness of fixing broken builds and failed steps",
        },
        "build_test_stability": {
            "max": 20.0,
            "description": "Low flake rate, deterministic exit codes, stable runner executions",
        },
        "pipeline_improvements": {
            "max": 15.0,
            "description": "Optimization of pipeline runtimes, cache efficiency, workflow enhancements",
        },
        "failure_prevention": {
            "max": 15.0,
            "description": "Pre-commit verification, clean dependencies preventing pipeline breaks",
        },
    },
}

MEETING_AGILE_CONFIG: Dict[str, Any] = {
    "agent_id": "meeting_agent",
    "score_type": "agile_collaboration",
    "total_points": 100.0,
    "min_evidence_threshold": 1,
    "subscores": {
        "delivery_reliability": {
            "max": 25.0,
            "description": "Story points delivered vs committed, on-time task completion",
        },
        "sprint_commitment": {
            "max": 20.0,
            "description": "Consistent sprint progress, healthy burndown contribution, low carryover",
        },
        "blocker_management": {
            "max": 20.0,
            "description": "Proactive blocker identification, timely unblocking of team members",
        },
        "action_item_completion": {
            "max": 15.0,
            "description": "Execution of standup and retrospective action items",
        },
        "collaboration_evidence": {
            "max": 10.0,
            "description": "Constructive code reviews, technical pair sessions, cross-functional support",
        },
        "process_participation": {
            "max": 10.0,
            "description": "Timely standup status logs, sprint planning hygiene, board grooming",
        },
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Overall Performance Aggregation & Split:
# Agent Score    = 80 marks
# Superior Score = 20 marks
# -------------------------
# Final Score    = 100 marks
# ─────────────────────────────────────────────────────────────────────────────

AGENT_SCORE_MARKS: float = 80.0
SUPERIOR_SCORE_MARKS: float = 20.0
TOTAL_FINAL_MARKS: float = 100.0

DEFAULT_AGGREGATION_WEIGHTS: Dict[str, float] = {
    "code_quality": 0.25,
    "testing_reliability": 0.20,
    "devops": 0.15,
    "cicd": 0.15,
    "agile_collaboration": 0.25,
}

