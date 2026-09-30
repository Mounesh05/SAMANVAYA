"""Deterministic, auditable developer contribution scoring.

This module deliberately does not use an LLM.  It turns available activity
evidence into a bounded score and reports which evidence was unavailable.
"""

from typing import Any, Dict


METHODOLOGY_VERSION = "contribution-v2-hybrid"
OBJECTIVE_WEIGHT = 0.60
AI_WEIGHT = 0.30
HUMAN_WEIGHT = 0.10


def _completed(status: Any) -> bool:
    return str(status or "").lower() in {"done", "completed", "closed", "resolved", "merged"}


def _priority_weight(priority: Any) -> float:
    return {
        "critical": 1.5,
        "urgent": 1.5,
        "high": 1.25,
        "medium": 1.0,
        "low": 0.75,
    }.get(str(priority or "medium").lower(), 1.0)


def calculate_contribution_credit(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate a transparent 0-100 contribution score from observed evidence.

    The score is a contribution signal, not a compensation or promotion
    decision. Missing integrations reduce confidence and are recorded rather
    than silently treated as positive evidence.
    """
    summary = evidence.get("summary", {})
    tasks = evidence.get("tasks", [])
    prs = evidence.get("pull_requests", [])
    reviews = evidence.get("code_reviews", [])
    bugs = evidence.get("bugs", {}) or {}

    completed_tasks = [task for task in tasks if _completed(task.get("status"))]
    delivery_units = sum(
        max(float(task.get("story_points") or 1), 1.0) * _priority_weight(task.get("priority"))
        for task in completed_tasks
    )
    delivery_points = min(30.0, delivery_units * 2.0)

    merged_prs = [
        pr for pr in prs
        if (
            str(pr.get("state") or "").lower() == "merged"
            or pr.get("merged_at")
            or pr.get("merged") is True
        )
    ]
    commit_count = int(summary.get("total_commits", 0) or 0)
    code_points = min(30.0, len(merged_prs) * 8.0 + min(commit_count, 10) * 0.5)

    collaboration_points = min(15.0, len(reviews) * 3.0)

    bugs_fixed = int(bugs.get("bugs_fixed_count", 0) or 0)
    bugs_introduced = int(bugs.get("bugs_introduced_count", 0) or 0)
    reliability_points = min(15.0, bugs_fixed * 3.0)
    reliability_points = max(0.0, reliability_points - bugs_introduced * 3.0)

    impact_points = min(
        10.0,
        sum(_priority_weight(task.get("priority")) for task in completed_tasks),
    )

    score = round(
        delivery_points
        + code_points
        + collaboration_points
        + reliability_points
        + impact_points,
        2,
    )

    missing_evidence = []
    if not prs:
        missing_evidence.append("pull_requests")
    if not reviews:
        missing_evidence.append("code_reviews")
    if not bugs.get("bug_tracking_available", False):
        missing_evidence.append("bug_tracking")
    if not evidence.get("commits"):
        missing_evidence.append("commits")

    observed_sources = 5 - len(missing_evidence)
    confidence = "high" if observed_sources >= 4 else "medium" if observed_sources >= 2 else "low"

    return {
        "methodology_version": "contribution-v1-objective",
        "score": score,
        "confidence": confidence,
        "components": {
            "delivery": round(delivery_points, 2),
            "code_delivery": round(code_points, 2),
            "collaboration": round(collaboration_points, 2),
            "reliability": round(reliability_points, 2),
            "impact": round(impact_points, 2),
        },
        "evidence_counts": {
            "tasks_completed": len(completed_tasks),
            "merged_pull_requests": len(merged_prs),
            "code_reviews": len(reviews),
            "bugs_fixed": bugs_fixed,
            "bugs_introduced": bugs_introduced,
            "commits": int(summary.get("total_commits", 0) or 0),
        },
        "missing_evidence": missing_evidence,
        "evidence_availability": {
            "bug_tracking": bool(bugs.get("bug_tracking_available", False)),
        },
        "is_advisory_only": True,
    }


def combine_hybrid_credit(
    objective_credit: Dict[str, Any],
    ai_score: float,
    human_score: float | None = None,
    ai_available: bool = True,
) -> Dict[str, Any]:
    """Combine objective evidence, AI interpretation, and optional human input.

    Missing optional sources are excluded from the denominator and the
    remaining weights are normalized. This avoids penalizing a developer just
    because a review or AI service was unavailable.
    """
    objective_score = max(0.0, min(100.0, float(objective_credit.get("score", 0))))
    normalized_ai = max(0.0, min(100.0, float(ai_score))) / 90.0 * 100.0
    human_available = human_score is not None

    weighted = [(objective_score, OBJECTIVE_WEIGHT, True)]
    if ai_available:
        weighted.append((normalized_ai, AI_WEIGHT, True))
    if human_available:
        weighted.append((max(0.0, min(100.0, float(human_score))), HUMAN_WEIGHT, True))

    denominator = sum(weight for _, weight, _ in weighted)
    final_score = round(sum(score * weight for score, weight, _ in weighted) / denominator, 2)

    components = dict(objective_credit.get("components", {}))
    components.update({
        "objective_score": round(objective_score, 2),
        "ai_score": round(normalized_ai, 2),
        "human_score": round(float(human_score), 2) if human_available else None,
        "objective_weight": OBJECTIVE_WEIGHT / denominator,
        "ai_weight": AI_WEIGHT / denominator if ai_available else 0,
        "human_weight": HUMAN_WEIGHT / denominator if human_available else 0,
    })

    result = dict(objective_credit)
    result.update({
        "methodology_version": METHODOLOGY_VERSION,
        "score": final_score,
        "components": components,
        "is_advisory_only": True,
    })
    return result
