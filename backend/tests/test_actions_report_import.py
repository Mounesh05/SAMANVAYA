import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from core import database, authorization
from repositories.project_repository import ProjectRepository
from domain.services.actions_report_import import ActionsReportImporter
from test_actions_test_artifacts import archive

pytestmark = pytest.mark.anyio
HEAD = 'a' * 40


@pytest.fixture
async def importer(mock_db, monkeypatch):
    monkeypatch.setattr(database, 'get_db', lambda: mock_db)
    monkeypatch.setattr(authorization, '_project_repo', ProjectRepository())
    await mock_db.users.insert_one({'employee_id': 'L', 'role': 'LEAD', 'org_id': 'A', 'team_id': 'T', 'project_ids': ['P'], 'is_active': True})
    await mock_db.projects.insert_one({'id': 'P', 'org_id': 'A', 'team_id': 'T'})
    await mock_db.github_project_configs.insert_one({'project_id': 'P', 'repository_owner': 'owner', 'repository_name': 'repo'})
    data = archive('pytest-results.xml', '<testsuite tests="2"><testcase/><testcase/></testsuite>')
    client = SimpleNamespace(get_pull_request=AsyncMock(return_value={'number': 4, 'head': {'sha': HEAD}, 'base': {'sha': 'b' * 40, 'repo': {'full_name': 'owner/repo'}}}),
        get_workflow_run=AsyncMock(return_value={'id': 10, 'run_attempt': 1, 'head_sha': HEAD, 'status': 'completed', 'conclusion': 'success', 'head_branch': 'feature', 'repository': {'full_name': 'owner/repo'}}),
        get_workflow_artifacts=AsyncMock(return_value={'total_count': 1, 'artifacts': [{'id': 20, 'name': 'backend-test-results', 'size_in_bytes': len(data), 'expired': False, 'digest': 'sha256:' + hashlib.sha256(data).hexdigest(), 'workflow_run': {'id': 10, 'head_sha': HEAD}}]}),
        download_workflow_artifact=AsyncMock(return_value=data))
    return mock_db, ActionsReportImporter(client), client


async def test_import_is_exact_revision_idempotent_and_eligible_as_reported_qa(importer):
    db, service, _ = importer
    first = await service.import_run('P', 4, 10, {'employee_id': 'L'})
    second = await service.import_run('P', 4, 10, {'employee_id': 'L'})
    assert first['test_run_ids'] == second['test_run_ids']
    assert await db.test_runs.count_documents({}) == 1
    row = await db.test_runs.find_one({})
    assert row['commit_sha'] == HEAD and row['tests_run'] == row['tests_passed'] == 2
    assert row['artifact_provenance']['verification_scope'] == 'GITHUB_ARTIFACT_BYTES_AT_RUN'
    assert first['coverage_status'] == 'missing'


@pytest.mark.parametrize('case', ['foreign_org', 'inactive', 'revoked_permission', 'stale_revision', 'wrong_repository', 'digest', 'expired', 'attempt_changed'])
async def test_scope_integrity_or_permission_failure_never_imports(importer, case):
    db, service, client = importer
    if case == 'foreign_org':
        await db.projects.update_one({'id': 'P'}, {'$set': {'org_id': 'B'}})
    elif case == 'inactive':
        await db.users.update_one({'employee_id': 'L'}, {'$set': {'is_active': False}})
    elif case == 'revoked_permission':
        await db.users.update_one({'employee_id': 'L'}, {'$set': {'role': 'DEVELOPER'}})
    elif case == 'stale_revision':
        client.get_workflow_run.return_value['head_sha'] = 'c' * 40
    elif case == 'wrong_repository':
        client.get_workflow_run.return_value['repository']['full_name'] = 'foreign/repo'
    elif case == 'digest':
        client.get_workflow_artifacts.return_value['artifacts'][0]['digest'] = 'sha256:' + '0' * 64
    elif case == 'expired':
        client.get_workflow_artifacts.return_value['artifacts'][0]['expired'] = True
    else:
        first = dict(client.get_workflow_run.return_value)
        client.get_workflow_run.side_effect = [first, {**first, 'run_attempt': 2}]
    with pytest.raises(HTTPException):
        await service.import_run('P', 4, 10, {'employee_id': 'L'})
    assert await db.test_runs.count_documents({}) == 0


async def test_import_of_actual_merge_commit_and_legacy_provenance_refresh(importer):
    db, service, client = importer
    merge = 'c' * 40
    pr = client.get_pull_request.return_value
    pr.update(merge_commit_sha=merge, state='open', merged=False)
    client.get_workflow_run.return_value['head_sha'] = merge
    client.get_workflow_artifacts.return_value['artifacts'][0]['workflow_run']['head_sha'] = merge
    with pytest.raises(HTTPException):
        await service.import_run('P', 4, 10, {'employee_id': 'L'})
    pr.update(state='closed', merged=True)
    receipt = await service.import_run('P', 4, 10, {'employee_id': 'L'})
    query = {'id': receipt['test_run_ids'][0]}
    row = await db.test_runs.find_one(query)
    assert row['commit_sha'] == merge
    assert row['artifact_provenance']['revision_kind'] == 'merge_commit'
    await db.test_runs.update_one(query, {'$unset': {'artifact_provenance.workflow_conclusion': ''}})
    await service.import_run('P', 4, 10, {'employee_id': 'L'})
    refreshed = await db.test_runs.find_one(query)
    assert refreshed['received_at'] == row['received_at']
    assert refreshed['artifact_provenance']['workflow_conclusion'] == 'success'
