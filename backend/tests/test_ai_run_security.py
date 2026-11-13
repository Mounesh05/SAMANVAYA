"""F01/F02 authorization and provenance through the actual HTTP routes and Mongo queries."""

import base64
import hashlib
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import FastAPI

from api.routes import ai
from core import database
from core.dependencies import get_current_user
from core.security import create_access_token, revoke_token, decode_token
from domain.models.performance_claims import PROTECTED_RUN_TYPES
from domain.services.auth_service import AuthService
from integrations.github.client import GitHubClient

pytestmark = pytest.mark.anyio
REVISION = "a" * 40
SOURCE = b"def explore(items):\n    return list(items)\n"
SHA256 = hashlib.sha256(SOURCE).hexdigest()
BLOB_SHA = hashlib.sha1(b"blob " + str(len(SOURCE)).encode() + b"\0" + SOURCE).hexdigest()


@pytest.fixture
async def endpoint(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    actor = {"employee_id": "A", "email": "a@example.invalid", "role": "LEAD", "org_id": "O1",
             "team_id": "T1", "project_ids": ["P1"], "is_active": True}
    await mock_db.projects.insert_many([
        {"id": "P1", "org_id": "O1", "team_id": "T1"},
        {"id": "P2", "org_id": "O1", "team_id": "T2"},
        {"id": "P3", "org_id": "O2", "team_id": "T1"},
        {"id": "UNKNOWN_ORG", "team_id": "T1"},
    ])
    monkeypatch.setattr(ai, "check_ollama_connection", lambda: True)
    invoke = Mock(return_value={"analysis": "Advisory result", "recommendations": [], "risk_level": "low",
                                "confidence": 0.8, "errors": [], "agent_history": ["qa_agent"]})
    monkeypatch.setattr(ai, "invoke_agent", invoke)
    app = FastAPI()
    app.include_router(ai.router, prefix="/api/ai")
    app.dependency_overrides[get_current_user] = lambda: actor
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, mock_db, actor, invoke, app


def document(key, owner="A", project=None, org="O1", **extra):
    now = datetime.now(timezone.utc).isoformat()
    return {"id": key, "agent_type": "qa_analysis", "owner_id": owner, "project_id": project,
            "organization_id": org, "access_version": "ai-run-access-v1",
            "triggered_by": "a@example.invalid", "status": "completed", "created_at": now,
            "updated_at": now, "input_data": {"context": {"project_id": project}},
            "output_data": {"analysis": "PRIVATE", "nested": {"source_code": "SECRET"}}, **extra}


async def invoke(client, **changes):
    return await client.post("/api/ai/invoke", json={"task_type": "qa_analysis", "evidence": {}, **changes})


@pytest.mark.parametrize("role", ["LEAD", "DEVELOPER", "PM", "CEO", "HR"])
async def test_private_runs_are_owner_only_even_for_privileged_roles(endpoint, role):
    client, db, actor, _, _ = endpoint
    actor["role"] = role
    await db.ai_runs.insert_many([document("own"), document("other", owner="B")])
    assert (await client.get("/api/ai/runs/own")).status_code == 200
    assert (await client.get("/api/ai/runs/other")).status_code == 404
    assert [row["id"] for row in (await client.get("/api/ai/runs")).json()] == ["own"]


@pytest.mark.parametrize("role,project,org,status", [
    ("LEAD", "P1", "O1", 200), ("DEVELOPER", "P1", "O1", 200),
    ("LEAD", "P2", "O1", 404), ("LEAD", "P3", "O2", 404),
    ("PM", "P2", "O1", 200), ("PM", "P3", "O2", 404),
    ("CEO", "P3", "O2", 200), ("HR", "P1", "O1", 200),
    ("LEAD", "P1", "O2", 404), ("CEO", "P1", "O2", 404),
    ("CEO", "MISSING", "O1", 404), ("CEO", "UNKNOWN_ORG", None, 404),
])
async def test_scoped_reads_resolve_current_project_and_organization(endpoint, role, project, org, status):
    client, db, actor, _, _ = endpoint
    actor["role"] = role
    await db.ai_runs.insert_one(document("scoped", owner="B", project=project, org=org))
    assert (await client.get("/api/ai/runs/scoped")).status_code == status
    listed = (await client.get("/api/ai/runs")).json()
    assert len(listed) == (1 if status == 200 else 0)


@pytest.mark.parametrize("missing", ["owner_id", "organization_id", "access_version"])
async def test_historical_scoped_records_without_provenance_are_hidden(endpoint, missing):
    client, db, _, _, _ = endpoint
    row = document("legacy", project="P1")
    row.pop(missing)
    await db.ai_runs.insert_one(row)
    assert (await client.get("/api/ai/runs/legacy")).status_code == 404
    assert (await client.get("/api/ai/runs")).json() == []


async def test_old_email_and_client_context_cannot_supply_ownership(endpoint):
    client, db, _, _, _ = endpoint
    row = document("legacy")
    row.pop("owner_id")
    row["input_data"] = {"context": {"owner_id": "A", "project_id": "P1", "org_id": "O1"}}
    await db.ai_runs.insert_one(row)
    assert (await client.get("/api/ai/runs/legacy")).status_code == 404


async def test_filter_precedes_pagination_and_count(endpoint, monkeypatch):
    from repositories.base import BaseRepository
    client, db, _, _, _ = endpoint
    await db.ai_runs.insert_many([document("hidden-" + str(i), owner="B", created_at="2099-01-01") for i in range(5)]
                                + [document("visible-" + str(i), created_at="2026-01-0" + str(i + 1)) for i in range(3)])
    original = BaseRepository.find_many
    counts = []
    async def page(repository, *args, **kwargs):
        result = await original(repository, *args, **kwargs)
        counts.append(result["total"])
        return result
    monkeypatch.setattr(BaseRepository, "find_many", page)
    result = await client.get("/api/ai/runs?limit=1&skip=1")
    assert [row["id"] for row in result.json()] == ["visible-1"]
    assert counts == [3]


@pytest.mark.parametrize("query", ["limit=0", "limit=-1", "limit=501", "skip=-1"])
async def test_pagination_is_bounded(endpoint, query):
    assert (await endpoint[0].get("/api/ai/runs?" + query)).status_code == 422


async def test_hr_allowlist_removes_arbitrary_nested_context_and_model_prose(endpoint):
    client, db, actor, _, _ = endpoint
    actor.update(role="HR", is_admin=True)
    await db.ai_runs.insert_one(document("hr", project="P1", input_data={
        "evidence": {"unknown": {"secret": "SECRET"}},
        "context": {"employee_name": {"code": "SECRET"}, "custom": "SECRET"}},
        output_data={"analysis": "SECRET", "recommendations": ["SECRET"], "summary": {"new": "SECRET"}},
        error_message="SECRET", model_name="SECRET"))
    for result in [await client.get("/api/ai/runs/hr"), await client.get("/api/ai/runs")]:
        assert result.status_code == 200
        assert "SECRET" not in result.text
    body = (await client.get("/api/ai/runs/hr")).json()
    assert body["input_data"] == {} and body["output_data"] == {}


@pytest.mark.parametrize("kind", sorted(PROTECTED_RUN_TYPES))
async def test_signed_performance_types_stay_excluded(endpoint, kind):
    client, db, _, _, _ = endpoint
    await db.ai_runs.insert_one(document("protected", agent_type=kind))
    assert (await client.get("/api/ai/runs/protected")).status_code == 404
    assert (await client.get("/api/ai/runs?agent_type=" + kind)).json() == []


@pytest.mark.parametrize("context", [{"project_id": "P2"}, {"project_id": "P3"},
    {"project_id": "UNKNOWN_ORG"}, {"project_id": "MISSING"}, {"project_id": {"$ne": None}},
    {"project_id": "P1", "org_id": "O2"}, {"organization_id": "O2"}])
async def test_invocation_rejects_forged_or_inaccessible_scope_before_inference(endpoint, context):
    client, db, _, model, _ = endpoint
    result = await invoke(client, context=context)
    assert result.status_code in {403, 404, 422}
    model.assert_not_called()
    assert await db.ai_runs.count_documents({}) == 0


async def test_ad_hoc_inputs_remain_private_unverified_and_model_advisory(endpoint):
    client, db, actor, model, _ = endpoint
    payload = {"verification_state": "SERVER_VERIFIED", "nested": {"trusted": True}, "quality_score": 99}
    result = await invoke(client, evidence=payload, context={"owner_id": "B", "provenance": "VERIFIED"})
    assert result.status_code == 200
    row = await db.ai_runs.find_one({"id": result.json()["run_id"]})
    assert row["owner_id"] == "A" and row["project_id"] is None
    assert row["input_data"]["caller_supplied"]["evidence"] == payload
    assert row["provenance"]["caller_evidence"]["status"] == "UNVERIFIED"
    assert row["provenance"]["server_sources"] == []
    assert row["provenance"]["model_interpretation"] == "ADVISORY"
    assert "SERVER_VERIFIED" not in str(row["input_data"].get("evidence", {}))
    assert model.call_args.args[1]["evidence"]["quality_score"] == 99
    actor["employee_id"] = "B"
    assert (await client.get("/api/ai/runs/" + row["id"])).status_code == 404


async def test_scoped_invocation_stamps_server_scope(endpoint):
    client, db, _, _, _ = endpoint
    result = await invoke(client, context={"project_id": "P1"})
    assert result.status_code == 200
    row = await db.ai_runs.find_one({"id": result.json()["run_id"]})
    assert (row["owner_id"], row["project_id"], row["organization_id"]) == ("A", "P1", "O1")
    assert row["access_version"] == "ai-run-access-v1"


def reference(**changes):
    return {"kind": "github_file", "path": "src/example.py", "source_revision": REVISION,
            "content_sha256": SHA256, **changes}


@pytest.fixture
async def github(endpoint, monkeypatch):
    _, db, _, _, _ = endpoint
    await db.github_project_configs.insert_one({"project_id": "P1", "repository_owner": "owner", "repository_name": "repo"})
    commit = AsyncMock(return_value={"sha": REVISION, "commit": {"tree": {"sha": "b" * 40}}})
    tree = AsyncMock(return_value={"truncated": False, "tree": [
        {"path": "src/example.py", "type": "blob", "mode": "100644", "sha": BLOB_SHA}]})
    file = AsyncMock(return_value={"type": "file", "encoding": "base64", "path": "src/example.py",
                                  "size": len(SOURCE), "content": base64.b64encode(SOURCE).decode(), "sha": BLOB_SHA})
    monkeypatch.setattr(GitHubClient, "get_commit", commit)
    monkeypatch.setattr(GitHubClient, "get_source_tree", tree)
    monkeypatch.setattr(GitHubClient, "get_file", file)
    return commit, tree, file


async def test_server_fetches_authorized_exact_revision_and_checks_content_hash(endpoint, github):
    client, db, _, model, _ = endpoint
    result = await invoke(client, task_type="code_review", context={"project_id": "P1"}, evidence_sources_v1=[reference()])
    assert result.status_code == 200, result.text
    row = await db.ai_runs.find_one({"id": result.json()["run_id"]})
    source = row["provenance"]["server_sources"][0]
    assert source["status"] == "SERVER_VERIFIED" and source["source_revision"] == REVISION
    assert source["content_sha256"] == SHA256 and source["repository"] == "owner/repo"
    assert source["verification_scope"] == "GITHUB_BLOB_AT_COMMIT"
    github[0].assert_awaited_once_with("owner", "repo", REVISION)
    github[2].assert_awaited_once_with("owner", "repo", "src/example.py", ref=REVISION)
    assert json.dumps(SOURCE.decode())[1:-1] in model.call_args.args[1]["evidence"]["evidence_summary"]


@pytest.mark.parametrize("failure", ["hash", "revision", "blob", "path", "size", "symlink", "truncated", "outage", "timeout", "ambiguous", "case-ambiguity", "foreign-config"])
async def test_unverifiable_sources_fail_before_inference_or_persistence(endpoint, github, failure):
    client, db, _, model, _ = endpoint
    ref = reference()
    if failure == "hash":
        ref["content_sha256"] = "0" * 64
    elif failure == "revision":
        github[0].return_value["sha"] = "c" * 40
    elif failure in {"blob", "path", "size"}:
        github[2].return_value[{"blob": "sha", "path": "path", "size": "size"}[failure]] = {
            "blob": "0" * 40, "path": "other.py", "size": len(SOURCE) + 1}[failure]
    elif failure == "symlink":
        github[1].return_value["tree"][0]["mode"] = "120000"
    elif failure == "truncated":
        github[1].return_value["truncated"] = True
    elif failure == "outage":
        github[0].side_effect = httpx.ConnectError("PRIVATE_TOKEN")
    elif failure == "timeout":
        github[0].side_effect = TimeoutError("PRIVATE_TOKEN")
    elif failure in {"ambiguous", "case-ambiguity"}:
        await db.github_project_configs.insert_one({"project_id": "P2", "repository_owner": "Owner" if failure == "case-ambiguity" else "owner", "repository_name": "repo"})
    else:
        await db.github_project_configs.update_one({"project_id": "P1"}, {"$set": {"org_id": "O2"}})
    result = await invoke(client, task_type="code_review", context={"project_id": "P1"}, evidence_sources_v1=[ref])
    assert result.status_code in {409, 503}, result.text
    assert "PRIVATE_TOKEN" not in result.text
    model.assert_not_called()
    assert await db.ai_runs.count_documents({}) == 0


@pytest.mark.parametrize("change", [{"source_revision": "main"}, {"path": "../secret"}, {"path": "src/a.py?ref=main"},
    {"kind": "performance_evidence_snapshot"}, {"status": "SERVER_VERIFIED"}, {"content_sha256": "bad"}])
async def test_unsupported_reference_labels_paths_and_revisions_rejected(endpoint, change):
    result = await invoke(endpoint[0], task_type="code_review", context={"project_id": "P1"}, evidence_sources_v1=[reference(**change)])
    assert result.status_code == 422
    endpoint[3].assert_not_called()


async def test_hr_cannot_fetch_technical_evidence_even_with_admin(endpoint, github):
    client, _, actor, model, _ = endpoint
    actor.update(role="HR", is_admin=True)
    result = await invoke(client, task_type="code_review", context={"project_id": "P1"}, evidence_sources_v1=[reference()])
    assert result.status_code == 403
    github[0].assert_not_awaited()
    model.assert_not_called()


async def test_real_session_rechecks_current_account_and_assignments(endpoint):
    client, db, actor, _, app = endpoint
    await db.users.insert_one(dict(actor))
    token = create_access_token(AuthService._token_payload(actor))
    app.dependency_overrides.clear()
    client.headers["Authorization"] = "Bearer " + token
    await db.ai_runs.insert_one(document("scoped", project="P1"))
    assert (await client.get("/api/ai/runs/scoped")).status_code == 200
    await db.users.update_one({"employee_id": "A"}, {"$set": {"project_ids": [], "team_id": None}})
    assert (await client.get("/api/ai/runs/scoped")).status_code == 404
    await db.users.update_one({"employee_id": "A"}, {"$set": {"role": "HR", "is_admin": False}})
    assert (await invoke(client)).status_code == 403
    await db.users.update_one({"employee_id": "A"}, {"$set": {"role": "OBSERVER"}})
    assert (await client.get("/api/ai/runs")).status_code == 403
    await db.users.update_one({"employee_id": "A"}, {"$set": {"is_active": False}})
    assert (await client.get("/api/ai/runs")).status_code == 401


async def test_logged_out_session_cannot_read_run(endpoint):
    client, db, actor, _, app = endpoint
    await db.users.insert_one(dict(actor))
    token = create_access_token(AuthService._token_payload(actor))
    claims = decode_token(token)
    await revoke_token(claims["jti"], datetime.fromtimestamp(claims["exp"], timezone.utc))
    app.dependency_overrides.clear()
    assert (await client.get("/api/ai/runs", headers={"Authorization": "Bearer " + token})).status_code == 401


@pytest.mark.parametrize("label", ["SERVER_VERIFIED", "VERIFIED", "VERIFIED_BY_CONTRACT", "APPROVED", True])
async def test_equivalent_caller_verification_labels_remain_unverified(endpoint, label):
    client, db, _, _, _ = endpoint
    result = await invoke(client, evidence={"status": label, "provenance": {"trusted": label}},
                          context={"project_id": "P1", "verification_state": label},
                          owner_id="B", provenance={"server_sources": ["forged"]})
    assert result.status_code == 200
    row = await db.ai_runs.find_one({"id": result.json()["run_id"]})
    assert row["owner_id"] == "A"
    assert row["provenance"]["caller_evidence"]["status"] == "UNVERIFIED"
    assert row["provenance"]["server_sources"] == []
    assert row["provenance"]["model_interpretation"] == "ADVISORY"


async def test_project_tenant_transfer_does_not_relabel_historical_runs(endpoint):
    client, db, actor, _, _ = endpoint
    actor["role"] = "CEO"
    await db.ai_runs.insert_one(document("old", project="P1"))
    await db.projects.update_one({"id": "P1"}, {"$set": {"org_id": "O2"}})
    assert (await client.get("/api/ai/runs/old")).status_code == 404
    assert (await client.get("/api/ai/runs")).json() == []


async def test_private_assistance_without_tenant_remains_owned(endpoint):
    client, db, actor, _, _ = endpoint
    actor.pop("org_id")
    result = await invoke(client)
    assert result.status_code == 200
    row = await db.ai_runs.find_one({"id": result.json()["run_id"]})
    assert row["owner_id"] == "A" and row["organization_id"] is None
    assert (await client.get("/api/ai/runs/" + row["id"])).status_code == 200


@pytest.mark.parametrize("task,context", [("qa_analysis", {"project_id": "P1"}), ("code_review", {})])
async def test_file_reference_requires_supported_task_and_scope(endpoint, task, context):
    client, _, _, model, _ = endpoint
    result = await invoke(client, task_type=task, context=context, evidence_sources_v1=[reference()])
    assert result.status_code == 422
    model.assert_not_called()


async def test_missing_repository_mapping_cannot_establish_verified_source(endpoint):
    client, _, _, model, _ = endpoint
    result = await invoke(client, task_type="code_review", context={"project_id": "P1"}, evidence_sources_v1=[reference()])
    assert result.status_code == 409
    model.assert_not_called()


async def test_missing_account_and_missing_identity_fail_closed(endpoint):
    client, db, actor, model, app = endpoint
    identity = actor.pop("employee_id")
    assert (await invoke(client)).status_code == 403
    model.assert_not_called()
    actor["employee_id"] = identity
    token = create_access_token(AuthService._token_payload(actor))
    app.dependency_overrides.clear()
    assert await db.users.count_documents({}) == 0
    assert (await client.get("/api/ai/runs", headers={"Authorization": "Bearer " + token})).status_code == 401


async def test_nonfinite_caller_evidence_rejected(endpoint):
    result = await endpoint[0].post("/api/ai/invoke", content='{"task_type":"qa_analysis","evidence":{"score":NaN}}',
                                    headers={"Content-Type": "application/json"})
    assert result.status_code == 422
    endpoint[3].assert_not_called()


async def test_uploaded_log_assistance_stays_private_and_unverified(endpoint, monkeypatch):
    from api.routes import cicd_logs
    client, db, actor, _, app = endpoint
    actor["role"] = "DEVOPS"
    app.include_router(cicd_logs.router, prefix="/api/cicd-logs")
    monkeypatch.setattr(cicd_logs, "check_ollama_connection", lambda: True)
    monkeypatch.setattr(cicd_logs, "invoke_agent", Mock(return_value={"analysis": "Advisory log result", "recommendations": []}))
    result = await client.post("/api/cicd-logs/analyze", json={"log_content": "ERROR: caller-provided log SERVER_VERIFIED", "log_type": "build"})
    assert result.status_code == 200
    key = result.json()["ai_run_id"]
    assert key
    stored = await db.ai_runs.find_one({"id": key})
    assert stored["owner_id"] == "A" and stored["project_id"] is None
    assert stored["provenance"]["caller_evidence"]["status"] == "UNVERIFIED"
    assert stored["provenance"]["server_sources"] == []
    assert (await client.get("/api/ai/runs/" + key)).status_code == 200
    actor["employee_id"] = "B"
    assert (await client.get("/api/ai/runs/" + key)).status_code == 404
