"""Targeted provenance, role routing and prompt regressions from live failures."""
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from agents.code_agent import _build_evidence_text
from api.routes import evaluation
from core import authorization, database
from test_ai_run_security import endpoint
from test_evaluation_engine import _evidence

pytestmark = pytest.mark.anyio


def actions_evidence():
    value = _evidence()
    value['pr']['head']['sha'] = 'a' * 40
    value['pr']['base']['repo'] = {'full_name': 'example/service'}
    value['check_runs'] = {'check_runs': [], 'evidence_status': 'unavailable'}
    run = {'run_id': 99, 'run_attempt': 2, 'repository': 'example/service', 'commit_sha': 'a' * 40,
           'name': 'Backend CI', 'status': 'completed', 'conclusion': 'success', 'jobs': []}
    value['actions_ci'] = {'status': 'available', 'runs': [run]}
    return value


def test_actions_are_grounded_separate_sources_not_fabricated_checks():
    evidence = actions_evidence()
    manifest = evaluation._build_evidence_manifest('example', 'service', 1, evidence)
    assert manifest['check_runs'] == [] and manifest['workflow_runs'][0]['run_id'] == 99
    catalog = evaluation._citation_catalog(manifest)
    choices = evaluation._dimension_citation_choices('reliability', catalog)
    assert choices and all('workflow_run_id' in row['reference'] for row in choices)
    assert not evaluation._validate_evidence_references([{'workflow_run_id': 99, 'reason': 'Exact CI outcome'}], manifest)
    assert evaluation._validate_evidence_references([{'workflow_run_id': 100}], manifest)
    evaluation._validate_dimension_reasoning_sources({'reliability': {
        'reasoning': 'Backend CI run 99 reported success.', 'evidence': [{'workflow_run_id': 99}]}}, manifest)


@pytest.mark.parametrize('key,value', [('repository', 'foreign/service'), ('commit_sha', 'b' * 40)])
def test_actions_foreign_or_stale_identity_never_becomes_evaluation_evidence(key, value):
    evidence = actions_evidence()
    evidence['actions_ci']['runs'][0][key] = value
    assert evaluation._actions_observations(evidence) == ([], [])


def test_legacy_prompt_does_not_turn_missing_measurements_into_zero():
    assert 'Files changed: Unknown' in _build_evidence_text({}, {})
    text = _build_evidence_text({'changed_files': ['example.py'], 'diff': 'return value + 1',
                                 'tests': {'coverage': {'line_coverage': 0}}}, {})
    assert 'Files changed: 1' in text and 'return value + 1' in text and 'Test Coverage: 0%' in text


async def test_hr_can_use_only_private_hr_assistance_without_technical_permission(endpoint):
    client, _, actor, invoke, _ = endpoint
    actor.update(role='HR', designation='HR_MANAGER', project_ids=[])
    response = await client.post('/api/ai/invoke', json={'task_type': 'hr_assistant', 'evidence': {}, 'save_run': False})
    assert response.status_code == 200
    assert invoke.call_args.args[0] == 'hr_assistant'
    assert 'TRIGGER_AI_EVALUATION' not in invoke.call_args.args[1]['user_context']['permissions']
    for task in ('code_review', 'qa_analysis', 'devops_risk', 'cicd_analysis'):
        assert (await client.post('/api/ai/invoke', json={'task_type': task, 'evidence': {}})).status_code == 403
    assert (await client.post('/api/ai/invoke', json={'task_type': 'hr_assistant', 'evidence': {},
                                                  'context': {'project_id': 'P1'}})).status_code == 403


@pytest.mark.parametrize('case', ['valid', 'missing', 'conflicting', 'unapproved', 'array-tenant'])
async def test_employee_github_binding_uses_authorized_stored_metadata(mock_db, monkeypatch, case):
    monkeypatch.setattr(database, 'get_db', lambda: mock_db)
    monkeypatch.setattr(authorization, 'get_accessible_project_ids', AsyncMock(return_value=['P']))
    await mock_db.users.insert_one({'employee_id': 'DEV', 'org_id': ['O', 'FOREIGN'] if case == 'array-tenant' else 'O',
                                   'is_active': True})
    config = {'project_id': 'P', 'org_id': 'O', 'repository_owner': 'example', 'repository_name': 'service',
              'validated_by': 'manager', 'identity_binding_authority': 'PROJECT_REPOSITORY_MANAGER',
              'developer_mappings': [{'employee_id': 'DEV', 'github_username': 'author'}]}
    if case == 'missing':
        config['developer_mappings'] = []
    if case == 'conflicting':
        config['developer_mappings'].append({'employee_id': 'OTHER', 'github_username': 'author'})
    if case == 'unapproved':
        del config['identity_binding_authority']
    await mock_db.github_project_configs.insert_one(deepcopy(config))
    actor = {'employee_id': 'lead', 'role': 'LEAD', 'org_id': 'O'}
    if case == 'valid':
        assert await evaluation._verified_subject_github(actor, 'DEV', 'example', 'service') == 'author'
    else:
        with pytest.raises(HTTPException) as error:
            await evaluation._verified_subject_github(actor, 'DEV', 'example', 'service')
        assert error.value.status_code in {403, 409}
