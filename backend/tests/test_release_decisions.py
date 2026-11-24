import asyncio
from copy import deepcopy

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from domain.services import release_decision_service as decisions
from domain.services.release_decision_service import DecisionRequest, decision_context, record_decision


DEVOPS = {"role": "DEVOPS", "org_id": "org", "employee_id": "ops1", "name": "Ravi"}
QA = {"role": "QA", "org_id": "org", "employee_id": "qa1", "name": "Leena"}


@pytest.fixture
def status():
    return {
        "organization_id": "org", "project_id": "project", "task_id": "task", "revision": "a" * 40,
        "revision_kind": "merge_commit",
        "implementation": {"status": "merged", "pull_requests": [{"number": 17, "repository": "test/catalog"}]},
        "qa": {"status": "passed", "runs": [{"id": "test-1", "run_attempt": 2, "tests_passed": 10}]},
        "readiness": {"status": "awaiting_review"},
    }


@pytest.fixture
async def db(mock_db, monkeypatch):
    monkeypatch.setattr(decisions, "col", lambda name: mock_db[name])
    return mock_db


def request(action, version, status):
    return DecisionRequest(decision=action, reason="Reviewed acceptance tests for catalog search.",
                           revision=status["revision"], decision_version=version)


@pytest.mark.anyio
async def test_independent_qa_and_devops_history_and_retries(status, db):
    before = await decision_context(status, DEVOPS)
    assert before["can_decide"] and not before["can_approve"]
    verify = request("verify_qa", before["decision_version"], status)
    after_qa = await record_decision(status, QA, verify)
    assert after_qa["qa_verification"]["is_current"]
    assert not after_qa["can_approve"] and not after_qa["can_verify_qa"]
    assert await record_decision(status, QA, verify) == after_qa
    ops = await decision_context(status, DEVOPS)
    assert ops["can_approve"]
    approve = request("approve", ops["decision_version"], status)
    result = await record_decision(status, DEVOPS, approve)
    assert result["release_decision"]["actor_name"] == "Ravi"
    assert result["release_decision"]["decision"] == "approve"
    assert result["release_decision"]["is_current"]
    assert await record_decision(status, DEVOPS, approve) == result
    held = await record_decision(status, DEVOPS, request("hold", result["decision_version"], status))
    assert held["release_decision"]["decision"] == "hold"
    with pytest.raises(HTTPException) as exc:
        await record_decision(status, DEVOPS, approve)
    assert exc.value.status_code == 409
    assert await db.release_decisions.count_documents({}) == 3


@pytest.mark.anyio
async def test_approval_expires_when_evidence_changes_at_same_revision(status, db):
    base = await decision_context(status, QA)
    result = await record_decision(status, QA, request("verify_qa", base["decision_version"], status))
    await record_decision(status, DEVOPS, request("approve", result["decision_version"], status))
    status["qa"]["runs"][0]["run_attempt"] = 3
    current = await decision_context(status, DEVOPS)
    assert not current["can_approve"]
    assert not current["qa_verification"]["is_current"]
    assert not current["release_decision"]["is_current"]


@pytest.mark.parametrize("qa_status", ["unknown", "failed", "passed"])
@pytest.mark.anyio
async def test_missing_failing_or_unverified_evidence_supports_hold_only(status, qa_status, db):
    status["qa"] = {"status": qa_status, "runs": []}
    ops = await decision_context(status, DEVOPS)
    for user, action in ((QA, "verify_qa"), (DEVOPS, "approve")):
        with pytest.raises(HTTPException) as exc:
            await record_decision(status, user, request(action, ops["decision_version"], status))
        assert exc.value.status_code == 409
    held = await record_decision(status, DEVOPS, request("hold", ops["decision_version"], status))
    assert held["release_decision"]["decision"] == "hold"


@pytest.mark.anyio
async def test_wrong_actor_project_org_and_revision(status, db):
    authorized = await decision_context(status, DEVOPS)
    action = request("hold", authorized["decision_version"], status)
    for user in ({**DEVOPS, "role": "CEO", "is_admin": True}, {**DEVOPS, "org_id": "other"}, QA):
        with pytest.raises(HTTPException) as exc:
            await record_decision(status, user, action)
        assert exc.value.status_code == 403
    for change in ({"project_id": "other"}, {"revision": "b" * 40}):
        with pytest.raises(HTTPException) as exc:
            await record_decision({**status, **change}, DEVOPS, action)
        assert exc.value.status_code == 409
    other_org = await decision_context({**status, "organization_id": "other"}, {**DEVOPS, "org_id": "other"})
    assert other_org["decision_version"] != authorized["decision_version"]


@pytest.mark.anyio
async def test_stale_concurrent_approval_and_hold_cannot_both_commit(status, db):
    version = (await decision_context(status, QA))["decision_version"]
    version = (await record_decision(status, QA, request("verify_qa", version, status)))["decision_version"]
    writes = await asyncio.gather(*[
        record_decision(status, DEVOPS, request(action, version, status))
        for action in ["hold", "approve"]
    ], return_exceptions=True)
    assert sum(isinstance(value, HTTPException) and value.status_code == 409 for value in writes) == 1
    assert await db.release_decisions.count_documents({}) == 2


@pytest.mark.anyio
async def test_order_independent_fingerprint_and_invalidation_on_new_revision(status, db):
    status["qa"]["runs"].append({"id": "suite-2"})
    result = await decision_context(status, QA)
    verified = await record_decision(status, QA, request("verify_qa", result["decision_version"], status))
    reordered = deepcopy(status)
    reordered["qa"]["runs"].reverse()
    reordered["qa"]["runs"][0]["received_at"] = "2026-11-23T08:00:00Z"
    assert (await decision_context(reordered, DEVOPS))["decision_version"] == verified["decision_version"]
    reordered["revision"] = "b" * 40
    assert not (await decision_context(reordered, DEVOPS))["qa_verification"]["is_current"]


@pytest.mark.parametrize("fields", [{"reason": "  "}, {"revision": "abc1234"}, {"actor_id": "someone-else"}])
def test_request_rejects_unusable_reason_revision_or_spoofed_identity(fields):
    with pytest.raises(ValidationError):
        DecisionRequest(**{"decision": "hold", "revision": "a" * 40, "decision_version": "b" * 64,
                           "reason": "Investigating the result", **fields})
