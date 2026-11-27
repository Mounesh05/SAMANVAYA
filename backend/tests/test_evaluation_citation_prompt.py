"""Regression for literal placeholder filenames copied by live evaluation models."""
import json
from unittest.mock import Mock

import pytest

from api.routes import evaluation
from test_evaluation_engine import _evidence, _model_response


@pytest.mark.asyncio
async def test_model_selects_real_server_citations_without_placeholder_paths(monkeypatch):
    model = Mock()
    response = json.loads(_model_response())

    def infer(prompt, **kwargs):
        assert 'path/to/changed-file' not in prompt
        assert 'Copy source_id from the citation catalog' in prompt
        example = json.loads(prompt.split('Return JSON only with this exact shape:\n', 1)[1].strip())
        assert set(example['dimensions']) == set(response['dimensions'])
        manifest = evaluation._build_evidence_manifest('owner', 'repo', 1, _evidence())
        catalog = evaluation._citation_catalog(manifest)
        shape = kwargs['format']
        assert kwargs['options']['num_predict'] == 2048
        assert kwargs['options']['num_ctx'] == 16384
        assert shape['properties']['recommendations']['items']['type'] == 'string'
        assert shape['properties']['evidence']['items']['properties']['source_id']['enum'] == [row['source_id'] for row in catalog]
        delivery = shape['properties']['dimensions']['properties']['delivery']['properties']['evidence']['items']
        assert delivery['properties']['source_id']['enum'] == [row['source_id'] for row in catalog if 'commit_sha' in row['reference']]
        assert shape['properties']['dimensions']['properties']['delivery']['properties']['evidence']['maxItems'] == 1
        for refs in [response['evidence'], *(d['evidence'] for d in response['dimensions'].values())]:
            for ref in refs:
                match = next(row for row in catalog if all(ref.get(key) == value for key, value in row['reference'].items()))
                reason, recommendation = ref['reason'], ref.get('recommendation')
                ref.clear()
                ref.update(source_id=match['source_id'], reason=reason)
                if recommendation:
                    ref['recommendation'] = recommendation
        return json.dumps(response)

    model.invoke.side_effect = infer
    monkeypatch.setattr(evaluation, 'check_ollama_connection', lambda: True)
    monkeypatch.setattr(evaluation, 'get_ollama_llm', lambda **kwargs: model)
    result = await evaluation._run_ai_evaluation('developer', {'owner': 'owner', 'name': 'repo'}, _evidence(), 'code_quality')
    assert result['evidence'][0]['file'] == 'backend/app/routes/events.py'
    assert result['evidence'][0]['excerpt'] == 'def create_event():'
    assert result['dimensions']['code_quality']['score'] == 7


def test_unknown_or_mixed_citation_ids_fail_closed():
    catalog = [{'source_id': 'SRC-1', 'reference': {'file': 'real.py', 'line': 2, 'excerpt': 'return 1'}}]
    for ref in [{'source_id': 'unknown', 'reason': 'x'},
                {'source_id': 'SRC-1', 'file': 'invented.py', 'reason': 'x'}]:
        with pytest.raises(evaluation.ModelResponseValidationError):
            evaluation._resolve_citation_ids({'evidence': [ref], 'dimensions': {}}, catalog)


def test_catalog_keeps_exact_added_line_numbers_and_never_invents_missing_source():
    manifest = {'files': [{'file': 'real.py', 'patch': '@@ -10,2 +10,3 @@\n unchanged\n-old\n+new_value = 2\n+return new_value'}]}
    rows = evaluation._citation_catalog(manifest)
    assert [r['reference'] for r in rows] == [
        {'file': 'real.py', 'line': 11, 'excerpt': 'new_value = 2'},
        {'file': 'real.py', 'line': 12, 'excerpt': 'return new_value'}]
    assert evaluation._citation_catalog({'files': []}) == []


@pytest.mark.asyncio
async def test_one_semantically_unrelated_dimension_can_be_rechecked_against_exact_source(monkeypatch):
    first = json.loads(_model_response())
    first['dimensions']['delivery']['reasoning'] = 'Beautiful colors and layout.'
    catalog = evaluation._citation_catalog(evaluation._build_evidence_manifest('owner', 'repo', 1, _evidence()))
    commit = next(row for row in catalog if 'commit_sha' in row['reference'])
    corrected = {'score': 7, 'reasoning': 'Commit abc123 records Add events.',
                 'evidence': [{'source_id': commit['source_id'], 'reason': 'The commit records Add events.'}]}
    model = Mock()
    model.invoke.side_effect = [json.dumps(first), json.dumps(corrected)]
    monkeypatch.setattr(evaluation, 'check_ollama_connection', lambda: True)
    monkeypatch.setattr(evaluation, 'get_ollama_llm', lambda **kwargs: model)
    result = await evaluation._run_ai_evaluation('developer', {'name': 'repo'}, _evidence(), 'code_quality')
    assert result['dimensions']['delivery']['evidence'][0]['commit_sha'] == 'abc123'
    assert result['dimensions']['delivery']['reasoning'] == corrected['reasoning']
    assert model.invoke.call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('bad', ['unknown_source', 'invalid_score', 'unrelated_reason'])
async def test_corrective_model_call_cannot_bypass_existing_validation(monkeypatch, bad):
    first = json.loads(_model_response())
    first['dimensions']['delivery']['reasoning'] = 'Beautiful colors and layout.'
    catalog = evaluation._citation_catalog(evaluation._build_evidence_manifest('owner', 'repo', 1, _evidence()))
    commit = next(row for row in catalog if 'commit_sha' in row['reference'])
    revised = {'score': 7, 'reasoning': 'Commit records Add events.',
               'evidence': [{'source_id': commit['source_id'], 'reason': 'Recorded commit change'}]}
    if bad == 'unknown_source':
        revised['evidence'][0]['source_id'] = 'invented'
    elif bad == 'invalid_score':
        revised['score'] = 100
    else:
        revised['reasoning'] = 'Beautiful colors and layout.'
    model = Mock()
    model.invoke.side_effect = [json.dumps(first), json.dumps(revised)]
    monkeypatch.setattr(evaluation, 'check_ollama_connection', lambda: True)
    monkeypatch.setattr(evaluation, 'get_ollama_llm', lambda **kwargs: model)
    with pytest.raises(evaluation.ModelResponseValidationError):
        await evaluation._run_ai_evaluation('developer', {'name': 'repo'}, _evidence(), 'code_quality')
    assert model.invoke.call_count == 2
