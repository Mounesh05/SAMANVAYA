from intelligence.contribution_credit import calculate_contribution_credit, combine_hybrid_credit


def test_credit_is_deterministic_and_uses_observable_evidence():
    evidence = {
        "summary": {"total_commits": 3},
        "commits": [{"sha": "a"}],
        "tasks": [
            {"status": "done", "story_points": 3, "priority": "high"},
            {"status": "in_progress", "story_points": 8, "priority": "critical"},
        ],
        "pull_requests": [{"state": "merged"}],
        "code_reviews": [{"id": "review-1"}],
        "bugs": {"bugs_fixed_count": 1, "bugs_introduced_count": 0},
    }

    result = calculate_contribution_credit(evidence)

    assert result["methodology_version"] == "contribution-v1-objective"
    assert result["score"] == 24.25
    assert result["components"]["delivery"] == 7.5
    assert result["components"]["code_delivery"] == 9.5
    assert result["confidence"] == "high"
    assert result["is_advisory_only"] is True


def test_missing_sources_are_reported_instead_of_being_scored_as_success():
    result = calculate_contribution_credit(
        {
            "summary": {},
            "commits": [],
            "tasks": [],
            "pull_requests": [],
            "code_reviews": [],
            "bugs": {},
        }
    )

    assert result["score"] == 0
    assert result["confidence"] == "low"
    assert set(result["missing_evidence"]) == {
        "pull_requests",
        "code_reviews",
        "bug_tracking",
        "commits",
    }


def test_introduced_bugs_reduce_reliability_points():
    result = calculate_contribution_credit(
        {
            "summary": {},
            "commits": [{"sha": "a"}],
            "tasks": [{"status": "done", "story_points": 1}],
            "pull_requests": [{"state": "merged"}],
            "code_reviews": [],
            "bugs": {"bugs_fixed_count": 0, "bugs_introduced_count": 2},
        }
    )

    assert result["components"]["reliability"] == 0


def test_hybrid_credit_uses_ai_and_normalizes_missing_human_feedback():
    objective = {"score": 50, "components": {}, "missing_evidence": []}

    result = combine_hybrid_credit(objective, ai_score=72)

    assert result["score"] == 60.0
    assert result["components"]["objective_score"] == 50
    assert result["components"]["ai_score"] == 80
    assert result["components"]["human_score"] is None
    assert result["components"]["human_weight"] == 0


def test_hybrid_credit_includes_human_feedback_when_available():
    objective = {"score": 50, "components": {}, "missing_evidence": []}

    result = combine_hybrid_credit(objective, ai_score=72, human_score=100)

    assert result["score"] == 64.0
    assert result["components"]["human_score"] == 100
