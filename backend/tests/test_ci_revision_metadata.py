import json
from pathlib import Path
import runpy

import pytest

from domain.services.qa_workflow_provisioning_service import TEMPLATE_DIR


@pytest.mark.parametrize('generated', [False, True])
def test_uploader_preserves_exact_pr_head_and_workflow_identity(monkeypatch, tmp_path, generated):
    directory = TEMPLATE_DIR if generated else Path(__file__).parents[2] / 'ci'
    namespace = runpy.run_path(str(directory / 'upload_junit_results.py'))
    event = tmp_path / 'event.json'
    event.write_text(json.dumps({'number': 4, 'pull_request': {'number': 4, 'head': {'sha': 'a' * 40, 'ref': 'feature'}, 'base': {'repo': {'full_name': 'owner/repo'}}}}))
    for key, value in {'GITHUB_REPOSITORY': 'owner/repo', 'GITHUB_SHA': 'b' * 40, 'GITHUB_REF_NAME': '4/merge',
                       'GITHUB_EVENT_NAME': 'pull_request', 'GITHUB_EVENT_PATH': str(event),
                       'GITHUB_RUN_ID': '10', 'GITHUB_RUN_ATTEMPT': '2', 'GITHUB_WORKFLOW': 'Unit tests'}.items():
        monkeypatch.setenv(key, value)
    metadata = namespace['_github_metadata']()
    assert metadata['commit_sha'] == 'a' * 40 and metadata['pr_number'] == 4
    assert metadata['workflow_run_id'] == '10' and metadata['run_attempt'] == 2
    assert metadata['branch'] == 'feature' and metadata['source'] == 'github_actions'
