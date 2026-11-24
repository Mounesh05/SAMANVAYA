"""Exact target-run report checks using the production artifact parser."""
import hashlib
from io import BytesIO
from unittest.mock import AsyncMock
from zipfile import ZipFile

import pytest

from core import database
from core.config import settings
from domain.services import release_test_evidence as qa


@pytest.mark.anyio
async def test_release_evidence_reuses_bounded_junit_parser_and_rejects_newer_evidence(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    monkeypatch.setattr(settings, "RELEASE_REQUIRED_TEST_SUITES", "suite/junit.xml,missing/junit.xml")
    target = "b" * 40
    run = {"id": 10, "workflow_id": 20, "run_number": 1, "head_branch": "main", "head_sha": target,
           "event": "push", "run_attempt": 1, "status": "completed", "conclusion": "success"}
    manifest = {"repository": "pilot/service", "repository_id": 30, "project_id": "P", "organization_id": "O",
                "target_sha": target, "artifact": {"id": 40, "digest": "d" * 64, "run_id": 10,
                    "run_attempt": 1, "workflow_id": 20, "workflow_sha256": "f" * 64}}
    with BytesIO() as output:
        with ZipFile(output, "w") as archive:
            archive.writestr("junit.xml", '<testsuite tests="1"><testcase name="passed"/></testsuite>')
        archive_bytes = output.getvalue()
    metadata = [{"id": 40, "digest": "d" * 64, "name": "samanvaya-candidate-10-1"},
                {"id": 41, "digest": hashlib.sha256(archive_bytes).hexdigest(),
                 "size_bytes": len(archive_bytes), "name": "suite-10-1"}]
    client = AsyncMock()
    client.list_workflow_runs.return_value = {"total_count": 1, "workflow_runs": [run]}
    client.download_workflow_artifact.return_value = archive_bytes
    client.get_workflow_run.return_value = run
    monkeypatch.setattr(qa, "GitHubClient", lambda: client)
    monkeypatch.setattr(qa, "verify_trusted_run", AsyncMock(return_value=(run, "f" * 64)))
    monkeypatch.setattr(qa, "artifact_inventory", AsyncMock(return_value=metadata))
    assert (await qa.release_tests(manifest))["qa"]["status"] == "unknown"
    monkeypatch.setattr(settings, "RELEASE_REQUIRED_TEST_SUITES", "suite/junit.xml")
    current = await qa.release_tests(manifest)
    assert current["qa"]["status"] == "passed" and current["qa"]["runs"][0]["tests_passed"] == 1
    assert current["coverage_status"] == "missing"
    monkeypatch.setattr(settings, "RELEASE_MIN_COVERAGE_PERCENT", 80)
    missing_coverage = await qa.release_tests(manifest)
    assert missing_coverage["qa"]["status"] == "unknown" and missing_coverage["coverage_status"] == "missing"
    monkeypatch.setattr(settings, "RELEASE_MIN_COVERAGE_PERCENT", 0)
    client.list_workflow_runs.return_value = {"total_count": 2, "workflow_runs": [
        run, {**run, "id": 11, "run_number": 2, "conclusion": "failure"}]}
    assert (await qa.release_tests(manifest))["qa"]["status"] == "failed"
    client.list_workflow_runs.return_value = {"total_count": 1, "workflow_runs": [run]}
    await mock_db.webhook_events.insert_one({"event_type": "workflow_run", "source": "github", "project_id": "P",
        "payload": {"repository": {"id": 30}, "workflow_run": {"id": 10, "head_sha": target, "run_attempt": 2}}})
    assert (await qa.release_tests(manifest))["qa"]["status"] == "unknown"
