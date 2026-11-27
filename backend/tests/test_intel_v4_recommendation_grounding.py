"""v4 investigation item 6 / REC-13: model advice is not stored as verified, prioritised fact.

The webhook pipeline turned the code agent's free-text output into pending PR
recommendations. The agent reply carries no evidence references, yet:
- "critical_issues" became CRITICAL recommendations titled "Critical: ...";
- priority came from wording ("must", "immediately" -> CRITICAL);
- the model's own confidence (or a 0.7 default) was stored as confidence;
- rule-generated advice carried fixed confidences (0.95 / 0.9) that nothing measured;
- nothing distinguished model advice from rule output (both "recommendation-engine").
"""

import pytest

from domain.models.recommendation import RecommendationPriority
from domain.services.recommendation_engine import RecommendationEngine

pytestmark = pytest.mark.anyio

HIGH_RISK = {"risk_level": "high", "risk_score": 80, "risk_factors": ["Large PR (>20 files)", "3 failing tests"]}
AI = {"status": "completed", "confidence": 0.93,
      "recommendations": ["You must rewrite the parser immediately", "Consider adding a docstring"],
      "critical_issues": ["SQL injection in login handler"]}


class Repo:
    def __init__(self):
        self.rows = []

    async def insert(self, row):
        self.rows.append(row)
        return row["id"]


@pytest.fixture
def engine():
    instance = RecommendationEngine.__new__(RecommendationEngine)
    instance.repo = Repo()
    return instance


async def test_model_advice_is_marked_unverified_and_not_escalated(engine):
    await engine.generate_pr_recommendations("PR-1", {"author": "octo"}, {"risk_level": "low"}, ai_analysis=AI,
                                             project_id="P1")
    rows = engine.repo.rows
    assert len(rows) == 3
    for row in rows:
        assert row["generated_by"] == "code-agent"
        assert row["evidence_ids"] == [] and row["confidence"] is None
        assert row["priority"] == RecommendationPriority.INFO
        assert "Unverified model suggestion" in row["reasoning"]
        assert not row["title"].startswith("Critical")


async def test_rule_advice_does_not_carry_an_invented_confidence(engine):
    await engine.generate_pr_recommendations("PR-1", {"author": "octo"}, HIGH_RISK, project_id="P1",
                                             code_quality_report={"security_findings": {"critical_count": 2}})
    rows = engine.repo.rows
    assert {row["generated_by"] for row in rows} == {"recommendation-engine"}
    assert all(row["confidence"] is None for row in rows)
    # Rule priority still follows the measured risk and the measured findings.
    assert {row["title"]: row["priority"] for row in rows} == {
        "Request senior engineer review": RecommendationPriority.HIGH,
        "Add unit tests before merge": RecommendationPriority.HIGH,
        "Fix 2 critical security issue(s)": RecommendationPriority.CRITICAL,
    }
    tests = next(row for row in rows if row["title"] == "Add unit tests before merge")
    assert tests["description"] == "Risk analysis reported: 3 failing tests"  # no coverage claim


async def test_failed_or_unavailable_model_creates_no_advice(engine):
    failed = {"status": "failed", "recommendations": [], "critical_issues": [], "confidence": None}
    await engine.generate_pr_recommendations("PR-1", {"author": "octo"}, {"risk_level": "low"}, ai_analysis=failed)
    assert engine.repo.rows == []
