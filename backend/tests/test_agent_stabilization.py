"""F03–F06 real factory, strict legacy contracts and persistence regressions."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from agents import code_agent, hr_agent, qa_agent, devops_agent, meeting_agent, cicd_agent, supervisor
from agents import llm_provider, parsers
from core.permissions import Permission


TASKS = {
    "code_review": code_agent, "qa_analysis": qa_agent, "devops_risk": devops_agent,
    "meeting_insights": meeting_agent, "cicd_analysis": cicd_agent, "hr_assistant": hr_agent,
}
COMMON = {"analysis": "Synthetic advisory analysis", "recommendations": ["Review cited evidence"],
          "risk_level": "low", "confidence": 0.8}
CICD = {"root_cause": "Synthetic build failure", "affected_component": "test runner",
        "fix_recommendations": ["Check the cited failing assertion"], "prevention": "Retain regression coverage",
        "urgency": "high", "confidence": 0.8}


def state(role="LEAD"):
    return {"evidence": {}, "context": {}, "agent_history": [], "errors": [],
            "user_context": {"role": role, "permissions": [Permission.VIEW_AI_EVALUATION.value,
                                                           Permission.VIEW_EMPLOYEE_DIRECTORY.value]}}


def response(task):
    if task == "cicd_analysis":
        return dict(CICD)
    return {**COMMON, **({"quality_score": 88, "failure_risk": 12} if task == "code_review" else {})}


def test_real_factory_keeps_documented_arguments_and_configures_both_transports():
    llm = llm_provider.get_ollama_llm("synthetic-model", 0.2, "http://127.0.0.1:1")
    assert llm.format == "json" and llm.model == "synthetic-model" and llm.temperature == 0.2
    for client in (llm._client._client, llm._async_client._client):
        assert all(getattr(client.timeout, field) == 120 for field in ("connect", "read", "write", "pool"))
    assert llm_provider.get_ollama_llm().format == "json"


@pytest.mark.parametrize("task", TASKS)
def test_six_actual_nodes_with_real_factory_and_mocked_transport(monkeypatch, task):
    # Mock beneath the factory: unsupported factory kwargs must fail this test.
    def factory(*args, **kwargs):
        llm = llm_provider.get_ollama_llm(*args, **kwargs)
        llm._client.generate = Mock(return_value=iter([{"response": json.dumps(response(task)), "done": True}]))
        return llm
    monkeypatch.setattr(TASKS[task], "get_ollama_llm", factory)
    original = state("HR" if task == "hr_assistant" else "LEAD")
    result = supervisor.invoke_agent(task, original)
    assert result["errors"] == [] and result["analysis"]
    assert len(result["agent_history"]) == 1 and original["agent_history"] == []
    assert result["next_agent"] is None


@pytest.mark.parametrize("task", TASKS)
@pytest.mark.parametrize("payload", ["not-json", "{}", "[]", "null", "", "x" * 65537,
    '{"analysis":"x","analysis":"y","recommendations":[],"risk_level":"low","confidence":0.8}',
    json.dumps({**COMMON, "confidence": float("nan")}),
    json.dumps({**COMMON, "verification_state": "VERIFIED"}),
    json.dumps({**COMMON, "confidence": 2}),
    json.dumps({**COMMON, "risk_level": "invented"}),
    {"analysis": "unsupported object"}, SimpleNamespace(content=[{"text": "unsupported content"}])],
    ids=["malformed", "empty-object", "array", "null", "empty", "oversized", "duplicate-key", "nan",
         "forged-verification", "range", "enum", "object", "non-text-content"])
def test_invalid_responses_fail_with_no_stale_or_fabricated_analysis(monkeypatch, task, payload):
    llm = Mock()
    llm.invoke.return_value = payload
    monkeypatch.setattr(TASKS[task], "get_ollama_llm", lambda **kwargs: llm)
    result = supervisor.invoke_agent(task, {**state(), "analysis": "stale success", "quality_score": 100})
    assert result["errors"] and "INVALID_MODEL_RESPONSE" in result["errors"][0]
    assert result["analysis"] is None and result["quality_score"] is None and result["confidence"] is None
    assert "unsupported object" not in str(result["errors"])


@pytest.mark.parametrize("task", TASKS)
@pytest.mark.parametrize("error,code", [(httpx.ReadTimeout("SYNTHETIC_PRIVATE_PAYLOAD"), "MODEL_TIMEOUT"),
                                      (ConnectionError("SYNTHETIC_PRIVATE_PAYLOAD"), "MODEL_UNAVAILABLE")])
def test_provider_failures_remain_explicit_and_do_not_echo_payload(monkeypatch, task, error, code):
    llm = Mock()
    llm.invoke.side_effect = error
    monkeypatch.setattr(TASKS[task], "get_ollama_llm", lambda **kwargs: llm)
    result = supervisor.invoke_agent(task, state())
    assert code in result["errors"][0] and result["analysis"] is None
    assert "SYNTHETIC_PRIVATE_PAYLOAD" not in str(result["errors"])


def test_cicd_preserves_valid_legacy_sections_without_fabricated_confidence():
    text = """ROOT_CAUSE: Synthetic build failure
AFFECTED_COMPONENT: test runner
FIX_RECOMMENDATIONS:
- Check the cited failing assertion
PREVENTION: Retain regression coverage
URGENCY: High
CONFIDENCE: 0.8
"""
    assert cicd_agent._parse_cicd_response(text) == CICD
    with pytest.raises(ValueError):
        cicd_agent._parse_cicd_response("ROOT_CAUSE: unsupported incomplete report")


@pytest.mark.parametrize("extra", [{"confidence": True}, {"confidence": "0.8"}, {"analysis": "   "},
                                   {"recommendations": ["x"] * 33}, {"analysis": "x" * 16001}],
                         ids=["bool", "coercion", "blank", "long-list", "long-text"])
def test_strict_parser_rejects_coercion_and_unbounded_fields(extra):
    with pytest.raises(ValueError):
        parsers.safe_parse(json.dumps({**COMMON, **extra}), parsers.AgentAnalysisResult)


@pytest.mark.parametrize("wrap", [lambda s: s, lambda s: "```json\n" + s + "\n```", lambda s: "Analysis follows:\n" + s,
                                lambda s: s + "\nAdvisory only.", lambda s: SimpleNamespace(content=s)])
def test_supported_json_wrappers_retain_legacy_fields(wrap):
    parsed = parsers.safe_parse(wrap(json.dumps(COMMON)), parsers.AgentAnalysisResult)
    assert parsed.analysis == COMMON["analysis"] and parsed.confidence == 0.8


def test_code_and_hr_permission_checks_precede_provider(monkeypatch):
    for module, node in [(code_agent, code_agent.code_analysis_node), (hr_agent, hr_agent.hr_assistant_node)]:
        provider = Mock(side_effect=AssertionError("Provider must not run"))
        monkeypatch.setattr(module, "get_ollama_llm", provider)
        result = node({**state(), "user_context": {"role": "HR", "permissions": []}})
        assert "Insufficient permissions" in result["errors"][0]
        provider.assert_not_called()


def test_hr_forced_routing_still_excludes_technical_prompt_content(monkeypatch):
    llm = Mock()
    llm.invoke.return_value = json.dumps(COMMON)
    monkeypatch.setattr(hr_agent, "get_ollama_llm", lambda **kwargs: llm)
    code = Mock(side_effect=AssertionError("HR must not invoke code node"))
    monkeypatch.setitem(supervisor.AGENT_REGISTRY, "code_review", code)
    result = supervisor.invoke_agent("code_review", {**state("HR"), "evidence": {
        "github_data": {"pr_diffs": "SYNTHETIC_PRIVATE_CODE"}, "performance_summary": {"overall_score": 85}}})
    assert result["errors"] == [] and result["agent_history"] == ["hr_assistant"]
    assert "SYNTHETIC_PRIVATE_CODE" not in llm.invoke.call_args.args[0]
    code.assert_not_called()


@pytest.mark.parametrize("task", TASKS)
@pytest.mark.parametrize("change", [{"quality_score": float("inf")}, {"quality_score": -1},
    {"quality_breakdown": {"testing": 16}}, {"quality_breakdown": {"architecture": True}},
    {"quality_breakdown": {"unexpected": 2}}, {"schema_version": "unsupported-v2"}])
def test_unknown_versions_and_unsupported_numerical_fields_cannot_succeed(monkeypatch, task, change):
    llm = Mock()
    llm.invoke.return_value = json.dumps({**response(task), **change})
    monkeypatch.setattr(TASKS[task], "get_ollama_llm", lambda **kwargs: llm)
    result = supervisor.invoke_agent(task, state())
    assert result["errors"] and result["analysis"] is None


def test_deep_or_multiple_json_objects_and_fallback_cannot_invent_results():
    for raw in ['{"nested":' * 20 + '{}' + '}' * 20, json.dumps(COMMON) + json.dumps(COMMON),
                json.dumps({**COMMON, "confidence": None})]:
        with pytest.raises(ValueError):
            parsers.safe_parse(raw, parsers.AgentAnalysisResult)
    with pytest.raises(ValueError):
        parsers.safe_parse('{}', parsers.AgentAnalysisResult, parsers.AgentAnalysisResult(**COMMON))


def test_missing_optional_code_numbers_stay_unknown_and_real_zero_is_preserved(monkeypatch):
    llm = Mock()
    llm.invoke.return_value = json.dumps(COMMON)
    monkeypatch.setattr(code_agent, "get_ollama_llm", lambda **kwargs: llm)
    result = supervisor.invoke_agent("code_review", state())
    assert result["errors"] == []
    assert all(result[name] is None for name in ("quality_score", "failure_risk", "evidence_risk_score", "evidence_quality_score"))
    llm.invoke.return_value = json.dumps({**COMMON, "quality_score": 0, "failure_risk": 0})
    result = supervisor.invoke_agent("code_review", state())
    assert result["quality_score"] == 0 and result["failure_risk"] == 0


def test_registry_identifiers_remain_exactly_the_six_legacy_tasks():
    assert set(supervisor.AGENT_REGISTRY) == set(TASKS)
