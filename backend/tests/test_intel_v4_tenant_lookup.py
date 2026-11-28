"""v4 BASE-04 / investigation item 5: code-quality run reads are scoped to the
caller's organisation *before* any lookup, so another tenant's run is
indistinguishable from a missing one (same 404, no existence oracle)."""

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.anyio

LEAD_A = {"employee_id": "QA-LEAD-A", "role": "LEAD", "org_id": "ORG-QA-A", "permissions": []}


@pytest.fixture
async def runs(mock_db, monkeypatch):
    from api.routes import code_quality
    from core import authorization
    monkeypatch.setattr(code_quality, "col", lambda name: mock_db[name])

    async def projects(user):
        return ["PRJ-A"] if user.get("org_id") == "ORG-QA-A" else ["PRJ-B"]
    monkeypatch.setattr(authorization, "get_accessible_project_ids", projects)
    await mock_db.code_quality_runs.insert_many([
        {"run_id": "RUN-OWN", "repository_id": "PRJ-A", "org_id": "ORG-QA-A", "status": "completed"},
        {"run_id": "RUN-FOREIGN", "repository_id": "PRJ-B", "org_id": "ORG-QA-B", "status": "completed",
         "function_discovery": {"functions": [{"name": "secret"}]}},
        {"run_id": "RUN-FOREIGN-ORGANIZATION", "repository_id": "PRJ-B", "organization_id": "ORG-QA-B"},
    ])
    await mock_db.code_quality_findings.insert_one({"run_id": "RUN-FOREIGN", "org_id": "ORG-QA-B", "message": "x"})
    return code_quality


async def _status(call):
    try:
        await call
    except HTTPException as error:
        return error.status_code, error.detail
    return 200, None


@pytest.mark.parametrize("reader", ["get_run", "get_run_findings", "get_discovered_functions"])
@pytest.mark.parametrize("run_id", ["RUN-FOREIGN", "RUN-FOREIGN-ORGANIZATION"])
async def test_foreign_run_looks_exactly_like_a_missing_run(runs, reader, run_id):
    read = getattr(runs, reader)
    extra = {"severity": None, "category": None, "limit": 50, "skip": 0} if reader == "get_run_findings" else (
        {"limit": 50, "skip": 0} if reader == "get_discovered_functions" else {})
    foreign = await _status(read(run_id, user=LEAD_A, **extra))
    missing = await _status(read("RUN-DOES-NOT-EXIST", user=LEAD_A, **extra))
    assert foreign == missing == (404, "Run not found")


async def test_own_run_is_still_readable(runs):
    run = await runs.get_run("RUN-OWN", user=LEAD_A)
    assert run["run_id"] == "RUN-OWN"
