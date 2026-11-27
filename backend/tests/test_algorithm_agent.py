"""Pure validation and evidence projection tests; live Ollama is separately required."""
import pytest
from agents.algorithm_agent import validate_advisory, report_evidence, deterministic_complete


def response():
    return {"summary": "Check assumptions before choosing an implementation.", "suggestions": [
        {"type": "TEST_PROPOSAL", "why": "Boundary behavior remains unclear.", "action": "Review empty input behavior.",
         "evidence_refs": ["function-1"]}], "limitations": ["Finite evidence only."]}


def test_valid_advice_and_unknown_reference():
    assert validate_advisory(response(), {"function-1"})["suggestions"]
    with pytest.raises(ValueError):
        validate_advisory(response(), {"foreign"})


@pytest.mark.parametrize("summary", ["O(n) is proven.", "Winner is candidate.", "Latency is 5 ms.", "See https://example.com"])
def test_rejects_new_factual_claims(summary):
    value = response()
    value["summary"] = summary
    with pytest.raises(ValueError):
        validate_advisory(value, {"function-1"})


def test_no_source_or_user_text_in_advisory_context():
    doc = {"functions": [{"current": {"function_id": "id", "source": "SECRET"}, "static": {"patterns": ["recursion"], "test_expectations": ["SECRET"]}, "complexity": {"time_complexity": "O(n)"}}]}
    assert "SECRET" not in str(report_evidence(doc, "pr"))


def test_deterministic_blocker_prevents_complete_status():
    doc = {"status": "completed", "functions": [{"status": "analyzed", "benchmark_status": "blocked"}]}
    assert not deterministic_complete(doc, "pr")
