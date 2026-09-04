"""
Tests for the Risk Engine.
"""

import pytest
from intelligence.risk_engine import RiskEngine
from intelligence.rules.risk_rules import RiskRules


class TestRiskClassification:
    """Test risk level classification."""

    def test_classify_critical(self):
        assert RiskRules.classify_risk_level(70) == "CRITICAL"
        assert RiskRules.classify_risk_level(100) == "CRITICAL"

    def test_classify_high(self):
        assert RiskRules.classify_risk_level(50) == "HIGH"
        assert RiskRules.classify_risk_level(69) == "HIGH"

    def test_classify_medium(self):
        assert RiskRules.classify_risk_level(30) == "MEDIUM"
        assert RiskRules.classify_risk_level(49) == "MEDIUM"

    def test_classify_low(self):
        assert RiskRules.classify_risk_level(0) == "LOW"
        assert RiskRules.classify_risk_level(29) == "LOW"


class TestAggregateRiskScores:
    """Test risk score aggregation."""

    def test_equal_weights(self):
        scores = [80, 40, 60]
        result = RiskRules.aggregate_risk_scores(scores)
        assert result == 60

    def test_custom_weights(self):
        scores = [80, 40]
        weights = [0.7, 0.3]
        result = RiskRules.aggregate_risk_scores(scores, weights)
        # 80*0.7 + 40*0.3 = 56 + 12 = 68
        assert result == 68

    def test_empty_scores(self):
        assert RiskRules.aggregate_risk_scores([]) == 0

    def test_single_score(self):
        assert RiskRules.aggregate_risk_scores([75]) == 75

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError, match="same length"):
            RiskRules.aggregate_risk_scores([1, 2], [1.0])


class TestDetermineActionRequired:
    """Test action determination based on risk level."""

    def test_critical_pr_actions(self):
        result = RiskRules.determine_action_required("CRITICAL", "pull_request")
        assert result["urgency"] == "immediate"
        assert result["requires_approval"] is True
        assert len(result["actions"]) > 0

    def test_low_sprint_actions(self):
        result = RiskRules.determine_action_required("LOW", "sprint")
        assert result["urgency"] == "normal"
        assert result["requires_approval"] is False

    def test_unknown_entity_type(self):
        result = RiskRules.determine_action_required("HIGH", "unknown_type")
        assert result["actions"] == []


class TestPRRisk:
    """Test PR risk evidence building."""

    @pytest.fixture
    def engine(self):
        return RiskEngine()

    def test_large_pr_risk(self, engine):
        import asyncio
        result = asyncio.run(engine._build_simple_pr_evidence(
            pr_id="PR-1",
            files_changed=25,
            lines_added=100,
            lines_deleted=50,
            commit_count=5,
        ))
        assert result["risk_score"] > 20
        assert any("Large PR" in f for f in result["risk_factors"])

    def test_small_pr_no_size_penalty(self, engine):
        import asyncio
        result = asyncio.run(engine._build_simple_pr_evidence(
            pr_id="PR-2",
            files_changed=2,
            lines_added=10,
            lines_deleted=5,
            commit_count=1,
        ))
        assert not any("Large PR" in f or "Medium PR" in f for f in result["risk_factors"])

    def test_failing_tests_high_risk(self, engine):
        import asyncio
        result = asyncio.run(engine._build_simple_pr_evidence(
            pr_id="PR-3",
            files_changed=3,
            lines_added=20,
            lines_deleted=10,
            commit_count=1,
            tests_failed=5,
        ))
        assert result["risk_score"] >= 25
        assert any("failing tests" in f for f in result["risk_factors"])

    def test_coverage_decrease_risk(self, engine):
        import asyncio
        result = asyncio.run(engine._build_simple_pr_evidence(
            pr_id="PR-4",
            files_changed=3,
            lines_added=20,
            lines_deleted=10,
            commit_count=1,
            previous_coverage=80.0,
            current_coverage=70.0,
        ))
        assert any("Coverage decreased" in f for f in result["risk_factors"])

    def test_stale_pr_risk(self, engine):
        import asyncio
        result = asyncio.run(engine._build_simple_pr_evidence(
            pr_id="PR-5",
            files_changed=3,
            lines_added=20,
            lines_deleted=10,
            commit_count=1,
            pr_age_hours=200,
        ))
        assert any("stale" in f for f in result["risk_factors"])


class TestSprintRisk:
    """Test sprint risk evidence building."""

    @pytest.fixture
    def engine(self):
        return RiskEngine()

    def test_blocked_sprint_high_risk(self, engine):
        result = engine._build_simple_sprint_evidence(
            sprint_id="S-1",
            total_stories=10,
            completed_stories=2,
            in_progress_stories=3,
            blocked_stories=3,
            total_points=50,
            completed_points=10,
            original_points=50,
            days_elapsed=7,
            sprint_duration_days=14,
        )
        assert result["risk_score"] >= 15
        assert any("blocked" in f for f in result["risk_factors"])

    def test_on_track_sprint_low_risk(self, engine):
        result = engine._build_simple_sprint_evidence(
            sprint_id="S-2",
            total_stories=10,
            completed_stories=5,
            in_progress_stories=3,
            blocked_stories=0,
            total_points=50,
            completed_points=25,
            original_points=50,
            days_elapsed=7,
            sprint_duration_days=14,
        )
        assert result["risk_score"] < 30
        assert result["risk_level"] in ["LOW", "MEDIUM"]
