"""Regression tests for the second set of audit findings:
OPS-03, CQ-05, CQ-03, AI-02, EV-05, SEC-05 and AI-01.

Each test names the audit ID it guards.
"""

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.anyio

TOKEN = "t" * 40


# ── OPS-03: worker broker and broker-aware runners ─────────────────────────

def _snapshot_context():
    source = "def increment(value):\n    return value + 1\n"
    return {"project_id": "P", "commit_sha": "a" * 40, "organization_id": "ORG-A", "source_files": {"module.py": source},
            "source_provenance": {"method": "github-contents-v1", "project_id": "P", "repository": "example/service",
                                  "organization_id": "ORG-A", "revision": "a" * 40,
                                  "source_hashes": {"module.py": hashlib.sha256(source.encode()).hexdigest()}}}


def _broker_client():
    from fastapi.testclient import TestClient
    from worker_broker.app import create_app
    return TestClient(create_app(token=TOKEN))


def _headers(token=TOKEN):
    return {"Authorization": f"Bearer {token}", "X-Worker-Protocol": "samanvaya-worker-broker-v1"}


def test_ops03_broker_requires_token_and_protocol():
    client = _broker_client()
    assert client.get("/v1/health").status_code == 200
    assert client.post("/v1/quality/analyze", json={}).status_code == 401
    assert client.post("/v1/quality/analyze", json={}, headers=_headers("x" * 40)).status_code == 401
    assert client.post("/v1/quality/analyze", json={},
                       headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 422


def test_ops03_broker_refuses_short_tokens():
    from worker_broker.app import create_app
    with pytest.raises(RuntimeError):
        create_app(token="short")


def test_ops03_broker_never_lets_callers_choose_internal_operations(monkeypatch):
    from intelligence.algorithms.runner import DockerBenchmarkRunner
    run = AsyncMock(return_value={"results": []})
    monkeypatch.setattr(DockerBenchmarkRunner, "run", run)
    response = _broker_client().post("/v1/benchmark/run", json={"payload": {"operation": "structure"}}, headers=_headers())
    assert response.status_code == 422
    run.assert_not_awaited()


def test_ops03_broker_runs_quality_and_maps_unavailable(monkeypatch):
    from intelligence.algorithms.runner import BenchmarkUnavailable
    from intelligence.analyzers.isolated import DockerQualityRunner
    from intelligence.evidence.models import CodeQualityEvidence
    evidence = CodeQualityEvidence(repository_id="P", commit_sha="a" * 40, primary_language="python")
    monkeypatch.setattr(DockerQualityRunner, "analyze", AsyncMock(return_value=evidence))
    client = _broker_client()
    ok = client.post("/v1/quality/analyze", json={"changed_files": ["module.py"], "context": {}}, headers=_headers())
    assert ok.status_code == 200 and ok.json()["evidence"]["commit_sha"] == "a" * 40
    monkeypatch.setattr(DockerQualityRunner, "analyze", AsyncMock(side_effect=BenchmarkUnavailable("Missing image")))
    down = client.post("/v1/quality/analyze", json={"changed_files": ["module.py"], "context": {}}, headers=_headers())
    assert down.status_code == 503 and "Missing image" in down.json()["detail"]


async def test_ops03_api_rechecks_broker_quality_results():
    from integrations.worker_broker import BrokerQualityRunner
    from intelligence.evidence.models import CodeQualityEvidence
    data = _snapshot_context()
    good = CodeQualityEvidence(repository_id="P", commit_sha="a" * 40, primary_language="python", files_analyzed=1)
    good.execution_provenance = {**data["source_provenance"], "method": "quality-snapshot-v1", "network": "none",
                                 "host_source_execution": False}

    class Client:
        def __init__(self, evidence):
            self.evidence, self.sent = evidence, None

        async def request(self, method, path, body=None):
            self.sent = (method, path, body)
            return {"protocol": "samanvaya-worker-broker-v1", "evidence": self.evidence.model_dump(mode="json")}

    client = Client(good)
    result = await BrokerQualityRunner(client=client).analyze(["module.py"], data)
    assert result.commit_sha == "a" * 40 and client.sent[1] == "/v1/quality/analyze"
    forged = good.model_copy(deep=True)
    forged.execution_provenance = {**good.execution_provenance, "network": "bridge"}
    with pytest.raises(ValueError):
        await BrokerQualityRunner(client=Client(forged)).analyze(["module.py"], data)
    foreign = good.model_copy(update={"repository_id": "OTHER"})
    with pytest.raises(ValueError):
        await BrokerQualityRunner(client=Client(foreign)).analyze(["module.py"], data)


def test_ops03_runner_selection_follows_the_broker_setting(monkeypatch):
    from core.config import settings
    from integrations import worker_broker
    from intelligence.algorithms.runner import DockerBenchmarkRunner
    from intelligence.analyzers.isolated import DockerQualityRunner
    monkeypatch.setattr(settings, "WORKER_BROKER_URL", "")
    assert isinstance(worker_broker.benchmark_runner(), DockerBenchmarkRunner)
    assert isinstance(worker_broker.quality_runner(), DockerQualityRunner)
    monkeypatch.setattr(settings, "WORKER_BROKER_URL", "http://worker-broker:8090")
    assert isinstance(worker_broker.benchmark_runner(), worker_broker.BrokerBenchmarkRunner)
    assert isinstance(worker_broker.quality_runner(), worker_broker.BrokerQualityRunner)


def test_ops03_broker_url_requires_a_strong_token_in_production(monkeypatch):
    from core.config import Settings
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("WORKER_BROKER_URL", "http://worker-broker:8090")
    monkeypatch.setenv("WORKER_BROKER_TOKEN", "short")
    errors = Settings().validate_production_settings()
    assert any("WORKER_BROKER_TOKEN" in error for error in errors)


def test_ops03_api_image_has_pinned_parser_and_no_docker_client():
    from pathlib import Path
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(encoding="utf-8")
    assert "node:22.14.0-bookworm-slim" in dockerfile and "npm ci --omit=dev" in dockerfile
    assert "docker" not in dockerfile.replace("Docker", "").split("FROM python", 1)[1].lower().replace(
        "docker client or socket", "")


# ── CQ-05: durable intake and recovery ─────────────────────────────────────

def _iso(delta_seconds=0):
    return (datetime.now(timezone.utc) + timedelta(seconds=delta_seconds)).isoformat()


async def test_cq05_only_one_process_claims_a_run(mock_db):
    from domain.services import code_quality_jobs as jobs
    runs = mock_db.code_quality_runs
    await runs.insert_one({"run_id": "R1", "status": "pending", "work_deadline": _iso(600)})
    assert await jobs.claim(runs, "R1") is True
    assert await jobs.claim(runs, "R1") is False
    stored = await runs.find_one({"run_id": "R1"})
    assert stored["status"] == "running" and stored["claimed_by"] == jobs.INSTANCE_ID and stored["lease_expires_at"]


async def test_cq05_expired_pending_run_is_never_claimed(mock_db):
    from domain.services import code_quality_jobs as jobs
    runs = mock_db.code_quality_runs
    await runs.insert_one({"run_id": "R2", "status": "pending", "work_deadline": _iso(-5)})
    assert await jobs.claim(runs, "R2") is False


async def test_cq05_recovery_fails_interrupted_runs_and_restarts_unclaimed_ones(mock_db):
    from domain.services import code_quality_jobs as jobs
    runs = mock_db.code_quality_runs
    await runs.insert_many([
        {"run_id": "DEAD", "status": "running", "claimed_by": "other-process", "lease_expires_at": _iso(-10),
         "work_deadline": _iso(600)},
        {"run_id": "LIVE", "status": "running", "claimed_by": "other-process", "lease_expires_at": _iso(60),
         "work_deadline": _iso(600)},
        {"run_id": "WAITING", "status": "pending", "request": {"body": {}}, "created_at": _iso(-120),
         "work_deadline": _iso(600)},
        {"run_id": "FRESH", "status": "pending", "request": {"body": {}}, "created_at": _iso(),
         "work_deadline": _iso(600)},
        {"run_id": "LATE", "status": "pending", "request": {"body": {}}, "created_at": _iso(-900),
         "work_deadline": _iso(-1)},
        {"run_id": "OTHER-KIND", "kind": "pr_quality_head", "status": "running", "claimed_by": "x",
         "lease_expires_at": _iso(-10)},
    ])
    started = []
    result = await jobs.recover_once(runs, lambda run: started.append(run["run_id"]))
    assert started == ["WAITING"]
    assert result == {"interrupted": 1, "expired": 1, "restarted": 1}
    dead = await runs.find_one({"run_id": "DEAD"})
    assert dead["status"] == "failed" and "not replayed" in dead["error"]
    assert (await runs.find_one({"run_id": "LIVE"}))["status"] == "running"
    assert (await runs.find_one({"run_id": "LATE"}))["status"] == "failed"
    assert (await runs.find_one({"run_id": "OTHER-KIND"}))["status"] == "running"


async def test_cq05_lost_lease_stops_the_work(mock_db, monkeypatch):
    from domain.services import code_quality_jobs as jobs
    runs = mock_db.code_quality_runs
    await runs.insert_one({"run_id": "R3", "status": "pending", "work_deadline": _iso(600)})
    assert await jobs.claim(runs, "R3")
    monkeypatch.setattr(jobs, "HEARTBEAT_SECONDS", 0.01)
    await runs.update_one({"run_id": "R3"}, {"$set": {"status": "failed"}})  # recovered elsewhere

    async def work():
        await asyncio.sleep(5)

    with pytest.raises(asyncio.CancelledError):
        await jobs.run_with_lease(runs, "R3", work)


async def test_cq05_results_from_a_lost_claim_are_not_written(mock_db, monkeypatch):
    from api.routes import code_quality
    monkeypatch.setattr(code_quality, "col", lambda name: mock_db[name])
    await mock_db.code_quality_runs.insert_one({"run_id": "R4", "status": "failed", "error": "recovered"})
    body = code_quality.AnalyzeRequest(repository_id="P1", changed_files=["module.py"], use_ai=False)
    analyze = AsyncMock()
    monkeypatch.setattr(code_quality.cq_service, "analyze_pr", analyze)
    await code_quality._run_analysis("R4", body, None)
    analyze.assert_not_awaited()
    assert (await mock_db.code_quality_runs.find_one({"run_id": "R4"}))["error"] == "recovered"


async def test_cq05_intake_is_bounded_per_organisation_and_stores_the_request(mock_db, monkeypatch):
    from fastapi import BackgroundTasks
    from api.routes import code_quality
    from core.config import settings
    monkeypatch.setattr(code_quality, "col", lambda name: mock_db[name])
    monkeypatch.setattr(code_quality, "verify_project_access", AsyncMock())
    monkeypatch.setattr(settings, "CODE_QUALITY_MAX_PENDING_PER_ORG", 1)
    user = {"employee_id": "QA-A", "role": "QA", "org_id": "ORG-A"}
    body = code_quality.AnalyzeRequest(repository_id="PRJ-A", changed_files=["src/app.py"])
    started = await code_quality.start_analysis(body, BackgroundTasks(), user)
    stored = await mock_db.code_quality_runs.find_one({"run_id": started["run_id"]})
    assert stored["request"]["body"]["changed_files"] == ["src/app.py"]
    assert stored["request"]["expected_org"] == "ORG-A"
    with pytest.raises(HTTPException) as error:
        await code_quality.start_analysis(body, BackgroundTasks(), user)
    assert error.value.status_code == 429
    other = {**user, "org_id": "ORG-B"}
    assert (await code_quality.start_analysis(body, BackgroundTasks(), other))["status"] == "pending"


# ── CQ-03: finding identity and new / existing / resolved ──────────────────

def _finding(file_path, line, rule="E501", message="Line too long (120 > 88)", snippet="x = 1", tool="ruff"):
    from intelligence.evidence.models import Finding
    return Finding(file_path=file_path, line_number=line, rule_id=rule, category="maintainability",
                   severity="low", source_tool=tool, message=message, code_snippet=snippet)


def test_cq03_identity_ignores_line_moves_and_follows_renames():
    from domain.services.pr_quality_comparison import finding_fingerprints
    before = _finding("old.py", 10)
    moved = _finding("new.py", 42, message="Line too long (131 > 88)")
    a = finding_fingerprints([before], {"old.py": "new.py"})[before.id]
    b = finding_fingerprints([moved])[moved.id]
    assert a == b
    other = _finding("new.py", 42, snippet="y = 2")
    assert finding_fingerprints([other])[other.id] != b


def test_cq03_classifies_new_existing_and_resolved():
    from domain.services.pr_quality_comparison import classify_findings, rename_map
    files = [{"filename": "new.py", "previous_filename": "old.py", "status": "renamed"}]
    kept_base, kept_head = _finding("old.py", 3), _finding("new.py", 9)
    fixed = _finding("old.py", 20, rule="B101", tool="bandit", message="Use of assert", snippet="assert x")
    added = _finding("new.py", 30, rule="F401", message="os imported but unused", snippet="import os")
    summary, identities = classify_findings([kept_base, fixed], [kept_head, added], rename_map(files))
    assert summary["counts"] == {"new": 1, "existing": 1, "resolved": 1}
    assert summary["new"][0]["rule_id"] == "F401"
    assert summary["resolved"][0]["rule_id"] == "B101" and summary["resolved"][0]["file_path"] == "new.py"
    assert identities["new"] and identities["resolved"]


def test_cq03_duplicates_are_counted_not_collapsed():
    from domain.services.pr_quality_comparison import classify_findings
    one = _finding("a.py", 1)
    two = [_finding("a.py", 1), _finding("a.py", 5)]
    summary, _ = classify_findings([one], two, {})
    assert summary["counts"] == {"new": 1, "existing": 1, "resolved": 0}


def test_cq03_partial_evidence_withholds_the_classification():
    from domain.services.pr_quality_comparison import classify_findings
    summary, identities = classify_findings([_finding("a.py", 1)], [], {}, head_available=False)
    assert summary["status"] == "unavailable" and summary["reason"] == "partial_evidence" and identities is None


async def test_cq03_classification_is_stored_on_findings():
    from domain.services.pr_quality_comparison import _mark_findings, finding_fingerprints
    head = [_finding("a.py", 1), _finding("a.py", 2, rule="F401", snippet="import os")]

    class Findings:  # installed mongomock cannot apply pymongo 4.9+ UpdateOne; record and apply here
        def __init__(self):
            self.rows = {f.id: {"run_id": "H", "id": f.id} for f in head}

        async def bulk_write(self, operations, ordered=True):
            for op in operations:
                assert op._filter["run_id"] == "H"
                self.rows[op._filter["id"]].update(op._doc["$set"])

    collection = Findings()
    fingerprints = finding_fingerprints(head)
    await _mark_findings(collection, "H", fingerprints, {fingerprints[head[1].id]}, "new")
    stored = collection.rows
    assert stored[head[0].id]["comparison_status"] == "existing"
    assert stored[head[1].id]["comparison_status"] == "new"
    assert stored[head[1].id]["fingerprint"] == fingerprints[head[1].id]


# ── AI-02: cancellation with fencing, and quotas ───────────────────────────

class _Repository:
    def __init__(self, status="RUNNING", counts=None):
        self.status, self.counts, self.cancelled = status, counts or {"actor": 0, "organization": 0, "total": 0}, []

    async def header(self, key):
        return {"_id": key, "status": self.status, "scope": {}, "request": {}}

    async def cancel(self, key, actor):
        self.cancelled.append((key, actor))
        return True

    async def active_counts(self, owner, org):
        return self.counts


def _service(repository):
    from domain.services.pr_workflow_durable import DurablePRWorkflowService
    manual = type("Manual", (), {"check_enabled": staticmethod(lambda: None)})()
    service = DurablePRWorkflowService(manual=manual, repository=repository)
    scope = type("Scope", (), {"owner_id": "E5", "organization_id": "ORG-A"})()
    service.authorize_header = AsyncMock(return_value=(scope, None))
    service.get = AsyncMock(return_value={"status": "CANCELLED"})
    return service, scope


async def test_ai02_requester_can_cancel_an_active_job():
    repository = _Repository("RUNNING")
    service, _ = _service(repository)
    assert (await service.cancel("job", {"employee_id": "E5"}))["status"] == "CANCELLED"
    assert repository.cancelled == [("job", "E5")]


async def test_ai02_finished_jobs_cannot_be_cancelled():
    service, _ = _service(_Repository("FINALIZED"))
    with pytest.raises(HTTPException) as error:
        await service.cancel("job", {"employee_id": "E5"})
    assert error.value.status_code == 409


@pytest.mark.parametrize("counts, status", [
    ({"actor": 3, "organization": 0, "total": 0}, 429),
    ({"actor": 0, "organization": 20, "total": 0}, 429),
    ({"actor": 0, "organization": 0, "total": 100}, 503),
])
async def test_ai02_quotas_bound_the_queue(counts, status):
    service, scope = _service(_Repository(counts=counts))
    with pytest.raises(HTTPException) as error:
        await service._enforce_quota(scope)
    assert error.value.status_code == status


async def test_ai02_cancel_fences_the_running_worker(mock_db, monkeypatch):
    """After cancel, the old worker's lease guard no longer matches its job."""
    from mongomock_motor import AsyncMongoMockCollection
    from repositories.pr_workflow_repository import JOB_VERSION, PRWorkflowRepository

    def with_options(collection, **options):  # same test shim as test_pr_workflow_durability
        delegate = AsyncMongoMockCollection.__getattr__(collection, "with_options")(**options)
        return AsyncMongoMockCollection(collection.database, delegate)
    monkeypatch.setattr(AsyncMongoMockCollection, "with_options", with_options, raising=False)
    clock = lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)  # noqa: E731
    repository = PRWorkflowRepository(mock_db.pr_multi_agent_jobs, clock=clock)
    await mock_db.pr_multi_agent_jobs.insert_one({"_id": "job", "schema_version": JOB_VERSION, "status": "RUNNING",
                                                   "generation": 1, "attempts": 1, "worker_id": "w1"})
    try:
        cancelled = await repository.cancel("job", "E5")
    except NotImplementedError:
        pytest.skip("mongomock lacks pipeline updates; covered by the Mongo integration suite")
    assert cancelled is True
    row = await mock_db.pr_multi_agent_jobs.find_one({"_id": "job"})
    assert row["status"] == "CANCELLED" and row["generation"] == 2
    assert row["last_error"]["code"] == "CANCELLED_BY_REQUESTER"
    assert await repository.cancel("job", "E5") is False


def test_ai02_cancelled_jobs_project_as_skipped():
    from domain.schemas.pr_workflow_api import status_projection
    row = {"job_id": "a" * 64, "status": "CANCELLED", "snapshot_id": "b" * 64,
           "checkpoint": {"outcomes": {}}, "step_results": [],
           "scope": {"project_id": "P", "repository": "o/r", "pr_number": 1, "head_sha": "c" * 40, "base_sha": "d" * 40},
           "snapshot": {"limitations": []}, "last_error": {"code": "CANCELLED_BY_REQUESTER"}}
    status = status_projection(row)
    assert status.status == "CANCELLED" and status.failure_reason == "CANCELLED_BY_REQUESTER"
    assert {step.status for step in status.specialists} <= {"SKIPPED", "WAITING"}


def test_ai02_cancel_route_is_registered():
    from api.routes.pr_workflows import router
    assert any(route.path == "/jobs/{job_id}/cancel" and "POST" in route.methods for route in router.routes)


# ── EV-05: manual scores are off by policy; score is labelled PR-only ──────

async def test_ev05_manual_score_rejected_while_policy_disabled(monkeypatch):
    from api.routes import evaluation
    from core.config import settings
    monkeypatch.setattr(settings, "EVALUATION_HUMAN_BASELINE_ENABLED", False)
    request = evaluation.SimpleEvalRequest(employee_id="E5", github_username="dev", repo_owner="o", repo_name="r",
                                           pr_number=1, human_score=8)
    verify = AsyncMock()
    monkeypatch.setattr(evaluation, "verify_can_view_person_evaluations", verify)
    with pytest.raises(HTTPException) as error:
        await evaluation.evaluate_developer_ai(request, {"employee_id": "E4", "role": "LEAD", "org_id": "ORG-A"})
    assert error.value.status_code == 422
    verify.assert_not_awaited()


async def test_ev05_health_reports_policy_and_scope(monkeypatch):
    from api.routes import evaluation
    from integrations.github import client as github_client
    monkeypatch.setattr(github_client.GitHubClient, "check_token_validity", AsyncMock(return_value=False))
    monkeypatch.setattr(evaluation, "check_ollama_connection", lambda: False)
    health = await evaluation.evaluation_health()
    assert health["human_baseline_enabled"] is False and health["score_scope"] == "pr_advisory"
    assert "recent_latency" in health["model"]


# ── SEC-05: HttpOnly cookie sessions with CSRF protection ──────────────────

def test_sec05_session_cookie_is_httponly_and_strict():
    from fastapi import Response
    from core.session_cookies import set_session_cookies, clear_session_cookies
    response = Response()
    set_session_cookies(response, "jwt-value")
    cookies = response.headers.getlist("set-cookie")
    session = next(c for c in cookies if c.startswith("samanvaya_session="))
    csrf = next(c for c in cookies if c.startswith("samanvaya_csrf="))
    assert "HttpOnly" in session and "samesite=strict" in session.lower()
    assert "HttpOnly" not in csrf and "samesite=strict" in csrf.lower()
    cleared = Response()
    clear_session_cookies(cleared)
    assert all("Max-Age=0" in c or "expires=" in c.lower() for c in cleared.headers.getlist("set-cookie"))


def test_sec05_csrf_double_submit():
    from core.session_cookies import csrf_valid
    assert csrf_valid("GET", None, None)
    assert not csrf_valid("POST", "abc", None)
    assert not csrf_valid("POST", "abc", "abd")
    assert csrf_valid("POST", "abc", "abc")


def _request(method, cookies, headers=None):
    from starlette.requests import Request
    cookie = "; ".join(f"{k}={v}" for k, v in cookies.items())
    raw = [(b"cookie", cookie.encode())] + [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "method": method, "path": "/api/x", "headers": raw, "query_string": b""})


async def test_sec05_cookie_session_requires_csrf_for_changes():
    from core.dependencies import get_current_user
    cookies = {"samanvaya_session": "not-a-jwt", "samanvaya_csrf": "c1"}
    with pytest.raises(HTTPException) as error:
        await get_current_user(None, _request("POST", cookies))
    assert error.value.status_code == 403
    # With the CSRF header (or on a GET) the cookie token is used, and an invalid one is a 401.
    with pytest.raises(HTTPException) as error:
        await get_current_user(None, _request("POST", cookies, {"X-CSRF-Token": "c1"}))
    assert error.value.status_code == 401
    with pytest.raises(HTTPException) as error:
        await get_current_user(None, _request("GET", cookies))
    assert error.value.status_code == 401


async def test_sec05_no_credentials_is_401():
    from core.dependencies import get_current_user, get_current_user_optional
    with pytest.raises(HTTPException) as error:
        await get_current_user(None, _request("GET", {}))
    assert error.value.status_code == 401
    assert await get_current_user_optional(None, _request("GET", {})) is None


async def test_sec05_login_sets_the_session_cookie(monkeypatch):
    from fastapi import Response
    from api.routes import auth
    result = type("R", (), {"token": "jwt-value"})()
    monkeypatch.setattr(auth, "_sign_in", AsyncMock(return_value=result))
    response = Response()
    request = _request("POST", {})
    await auth.login.__wrapped__(request, response, None) if hasattr(auth.login, "__wrapped__") else \
        await auth.login(request, response, None)
    assert any(c.startswith("samanvaya_session=jwt-value") and "HttpOnly" in c
               for c in response.headers.getlist("set-cookie"))


# ── AI-01: configurable timeouts and recorded latency ──────────────────────

def test_ai01_specialist_timeout_and_execution_budget_follow_settings():
    from agents import pr_multi_agent
    from core.config import settings
    from domain.services import pr_workflow_durable
    assert pr_multi_agent.SPECIALIST_TIMEOUT_SECONDS == settings.PR_AGENT_SPECIALIST_TIMEOUT_SECONDS
    assert pr_workflow_durable.EXECUTION_SECONDS >= 2 * settings.PR_AGENT_SPECIALIST_TIMEOUT_SECONDS + 60


async def test_ai01_model_latency_is_recorded_without_content():
    from core import model_metrics
    model_metrics.reset()
    with model_metrics.measure("developer_evaluation"):
        pass
    with pytest.raises(TimeoutError):
        with model_metrics.measure("developer_evaluation"):
            raise TimeoutError
    summary = model_metrics.summary()["developer_evaluation"]
    assert summary["calls"] == 2 and summary["ok"] == 1 and summary["timeouts"] == 1
    assert set(summary) == {"calls", "ok", "timeouts", "errors", "p50_seconds", "p95_seconds", "max_seconds"}
    model_metrics.reset()
