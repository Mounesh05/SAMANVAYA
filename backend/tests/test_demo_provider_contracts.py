"""Provider requests must use the existing strict response schema, not input state."""
import json
from unittest.mock import AsyncMock, Mock

import pytest

from agents import cicd_agent, llm_provider, pr_multi_agent
from domain.models.pr_multi_agent import SpecialistReply, SpecialistView, PRScope


@pytest.mark.anyio
async def test_pr_provider_requests_existing_reply_schema(monkeypatch):
    model = Mock(ainvoke=AsyncMock(return_value='{}'))
    monkeypatch.setattr(llm_provider, 'get_ollama_llm', lambda **kwargs: model)
    view = SpecialistView(specialist='code_analysis', snapshot_id='a' * 64,
        scope=PRScope(owner_id='A', organization_id='O', project_id='P', repository='example/service',
                      pr_number=1, head_sha='a' * 40, base_sha='b' * 40), references=(), observations=())
    await pr_multi_agent._model_reply(view)
    prompt = model.ainvoke.call_args.args[0]
    assert '"schema_version":"pr-specialist-v1"' in prompt and '"claims":[' in prompt
    assert 'never the input state or a JSON Schema' in prompt
    assert 'Return the pr-specialist-v1 response object with summary, claims and limitations. Do not return an observation, input state or schema.' in prompt
    assert model.ainvoke.call_args.kwargs['options']['num_ctx'] == 8192
    shape = model.ainvoke.call_args.kwargs['format']
    assert shape['$defs']['ClaimDraft']['properties']['kind']['enum'] == ['OBSERVATION', 'INTERPRETATION']
    assert shape['additionalProperties'] is False
    assert 'maxLength' not in json.dumps(shape)
    assert 'maxLength' in json.dumps(SpecialistReply.model_json_schema())


def test_cicd_provider_requests_existing_reply_schema(monkeypatch):
    model = Mock()
    model.invoke.return_value = json.dumps({'root_cause': 'Synthetic compile error',
        'affected_component': 'compiler', 'fix_recommendations': ['Review the missing name'],
        'prevention': 'Retain compiler checks', 'urgency': 'high', 'confidence': 0.8})
    monkeypatch.setattr(cicd_agent, 'get_ollama_llm', lambda **kwargs: model)
    result = cicd_agent.cicd_analysis_node({'evidence': {}, 'context': {}, 'agent_history': [], 'errors': []})
    assert not result['errors']
    assert 'exactly one lowercase string' in model.invoke.call_args.args[0]


def test_generation_compatibility_does_not_relax_authoritative_reply_bounds():
    from agents.parsers import AgentResponseError, safe_parse
    claim = {'kind': 'INTERPRETATION', 'statement': 'Synthetic proposal', 'topic': 'review'}
    with pytest.raises(AgentResponseError):
        safe_parse(json.dumps({'summary': 'Synthetic', 'claims': [claim] * 13}), SpecialistReply)
    with pytest.raises(AgentResponseError):
        safe_parse(json.dumps({'summary': 'Synthetic', 'claims': [claim], 'authoritative_score': 100}), SpecialistReply)
