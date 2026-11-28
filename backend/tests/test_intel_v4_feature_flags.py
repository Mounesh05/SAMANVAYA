"""v4 investigation item 9: the manual-baseline flag is exercised in both states.

Only the disabled path of EVALUATION_HUMAN_BASELINE_ENABLED had a test. The other
intelligence flags (ALGORITHM_BENCHMARK_ENABLED, PR_MULTI_AGENT_INTERNAL_ENABLED,
PR_MULTI_AGENT_MANUAL_ENABLED, VITE_PR_MULTI_AGENT_MANUAL_ENABLED) already have
tests for both states.
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from api.routes import evaluation
from core.config import settings

pytestmark = pytest.mark.anyio
LEAD = {"employee_id": "E4", "role": "LEAD", "org_id": "ORG-A"}


def request(human_score):
    return evaluation.SimpleEvalRequest(employee_id="E5", github_username="dev", repo_owner="o", repo_name="r",
                                        pr_number=1, human_score=human_score)


@pytest.mark.parametrize("enabled,human_score,gate", [
    (False, 8, "policy"), (False, None, "authorization"),
    (True, 8, "authorization"), (True, None, "authorization"),
])
async def test_manual_baseline_gate_in_both_states(monkeypatch, enabled, human_score, gate):
    monkeypatch.setattr(settings, "EVALUATION_HUMAN_BASELINE_ENABLED", enabled)
    verify = AsyncMock(side_effect=HTTPException(403, "Not your team"))
    monkeypatch.setattr(evaluation, "verify_can_view_person_evaluations", verify)
    with pytest.raises(HTTPException) as stopped:
        await evaluation.evaluate_developer_ai(request(human_score), LEAD)
    if gate == "policy":
        assert stopped.value.status_code == 422 and not verify.await_count
    else:
        # Past the policy gate, normal authorization still applies.
        assert stopped.value.status_code == 403 and verify.await_count == 1


def test_enabled_baseline_never_creates_a_score_without_evidence():
    coverage = {name: "insufficient_evidence" for name in evaluation.AI_DIMENSION_WEIGHTS}
    metadata = evaluation._score_coverage_metadata({}, coverage, {}, human_score=9)
    assert metadata["assessed_weight"] == 0
    assert metadata["overall_score"] is None and metadata["calculation"] is None
    assert metadata["normalized_dimension_score"] is None
