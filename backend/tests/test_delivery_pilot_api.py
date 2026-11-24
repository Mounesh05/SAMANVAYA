"""Release review through the production router registrations and ingestion contracts."""

import pytest
from httpx import ASGITransport, AsyncClient

from core import authorization, database
from core.ci_credentials import project_ci_token
from core.config import settings
from core.dependencies import get_current_user
from repositories.project_repository import ProjectRepository


@pytest.mark.anyio
async def test_release_review_through_mounted_api(mock_db, monkeypatch):
    from main import app
    from core.audit import audit_logger

    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    monkeypatch.setattr(authorization, "_project_repo", ProjectRepository())
    monkeypatch.setattr(audit_logger, "collection", mock_db.audit_logs)
    monkeypatch.setattr(settings, "QA_TEST_RESULTS_TOKEN", "test-ingestion-only")
    actor = {"employee_id": "ops", "role": "DEVOPS", "org_id": "pilot", "project_ids": ["P"]}
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: dict(actor))
    task_id = "TSK-12345678"
    repository = "pilot/service"
    merge = "b" * 40
    await mock_db.projects.insert_one({"id": "P", "org_id": "pilot"})
    await mock_db.tasks.insert_one({"id": task_id, "project_id": "P", "status": "done", "title": "Search"})
    await mock_db.github_project_configs.insert_one({"project_id": "P", "repository_owner": "pilot", "repository_name": "service"})
    await mock_db.qa_ci_configs.insert_one({"project_id": "P", "repository": repository, "enabled": True})
    await mock_db.pull_requests.insert_one({"id": "pr", "pr_number": 7, "title": task_id, "repo_id": repository,
        "status": "merged", "head_sha": "a" * 40, "merge_commit_sha": merge, "project_id": "P"})
    url = f"/api/tasks/{task_id}"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        control = "/api/projects/P/release-gate"
        issue = {"action": "issue", "version": 0, "repository": repository}
        issued = await client.post(control, json=issue)
        assert issued.status_code == 200 and issued.headers["cache-control"] == "no-store"
        token = issued.json()["token"]
        assert token not in (await client.get(control)).text
        assert token not in str(await mock_db.project_release_gates.find_one({}))
        assert (await client.post(control, json=issue)).status_code == 409

        async def gate(credential):
            return await client.post("/api/release-gates/check", headers={"X-Release-Gate-Token": credential},
                json={"project_id": "P", "repository": repository, "task_id": task_id,
                      "revision": merge, "environment": "production"})

        async def read():
            response = await client.get(url + "/delivery")
            assert response.status_code == 200, response.text
            return response.json()

        async def decide(action, state):
            return await client.post(url + "/release-decisions", json={
                "decision": action, "decision_version": state["decision_version"], "revision": state["revision"],
                "reason": "Reviewed search acceptance tests and release criteria.",
            })

        async def report(attempt, failed, token=None):
            return await client.post("/api/qa/test-runs",
                headers={"X-Test-Results-Token": token or project_ci_token("P", repository)},
                json={"project_id": "P", "branch": "main", "repository": repository, "commit_sha": merge,
                      "workflow_run_id": "42", "test_suite": "acceptance", "run_attempt": attempt,
                      "tests_run": 1, "tests_passed": 1 - failed, "tests_failed": failed,
                      "status": "failed" if failed else "passed"})

        assert (await report(1, 1, project_ci_token("P2", repository))).status_code == 401
        assert (await report(1, 1)).status_code == 201
        failed = await read()
        assert failed["implementation"]["status"] == "merged"
        assert failed["qa"]["status"] == "failed" and failed["production"]["status"] == "unknown"
        assert (await decide("approve", failed)).status_code == 409
        assert (await decide("hold", failed)).status_code == 200
        assert (await gate(token)).status_code == 409
        assert (await report(2, 0)).status_code == 201
        actor.update(employee_id="qa", role="QA")
        assert (await client.post(control, json={**issue, "version": 1})).status_code == 403
        passing = await read()
        assert passing["can_verify_qa"] and not passing["can_decide"]
        assert (await decide("verify_qa", passing)).status_code == 200
        actor.update(employee_id="ops", role="DEVOPS")
        verified = await read()
        assert verified["can_approve"]
        assert (await decide("approve", verified)).status_code == 200
        permitted = await gate(token)
        assert permitted.status_code == 200 and permitted.json()["allowed"] is True
        rotated = await client.post(control, json={**issue, "version": 1})
        assert rotated.status_code == 200 and (await gate(token)).status_code == 403
        token = rotated.json()["token"]
        assert (await gate(token)).status_code == 200
        approved = await read()
        assert approved["release_decision"]["is_current"] and approved["production"]["status"] == "unknown"
        assert (await report(2, 0)).status_code == 201
        assert (await read())["decision_version"] == approved["decision_version"]
        assert (await report(2, 1)).status_code == 409
        assert (await report(3, 1)).status_code == 201
        revoked = await read()
        assert not revoked["qa_verification"]["is_current"] and not revoked["release_decision"]["is_current"]
        assert (await decide("approve", approved)).status_code == 409
        assert (await gate(token)).status_code == 409
        assert (await client.post(control, json={"action": "revoke", "repository": repository, "version": 2})).status_code == 200
        assert (await gate(token)).status_code == 403
        actor["org_id"] = "elsewhere"
        assert (await client.get(url + "/delivery")).status_code in (403, 404)
        assert (await client.get(control)).status_code in (403, 404)
