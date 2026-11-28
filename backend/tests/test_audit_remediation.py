"""Regression tests for the SAMANVAYA master-audit findings fixed on fix/audit-remediation.

Each test names the audit ID it guards. Records use plain employee/org IDs.
"""

import json
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError

from core import authorization, database

pytestmark = pytest.mark.anyio


# ── SEC-01: validation errors never echo submitted values ───────────────────

async def test_validation_errors_do_not_echo_or_log_submitted_secrets(caplog):
    import main
    secret = "Sup3r-Secret-Passw0rd!"
    exc = RequestValidationError([{
        "type": "string_too_long", "loc": ("body", "password"), "msg": "String should have at most 256 characters",
        "input": secret, "ctx": {"max_length": 256, "value": secret}, "url": "https://errors.pydantic.dev/x",
    }])
    request = type("R", (), {"url": type("U", (), {"path": "/api/auth/login"})(), "method": "POST"})()
    with caplog.at_level("WARNING"):
        response = await main.validation_exception_handler(request, exc)
    body = json.loads(response.body)
    assert response.status_code == 422
    assert body == {"detail": [{"type": "string_too_long", "loc": ["body", "password"],
                                "msg": "String should have at most 256 characters"}]}
    assert secret not in response.body.decode() and secret not in caplog.text


# ── OPS-01 / OPS-02: readiness reflects the database and required indexes ───

@pytest.fixture
def probes(monkeypatch):
    import main
    from agents import llm_provider
    from core.config import settings
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "")
    monkeypatch.setattr(llm_provider, "check_ollama_connection", lambda: True)
    monkeypatch.setattr(main, "index_failures", set())
    return main


async def test_health_is_503_when_the_database_is_unreachable(probes, monkeypatch):
    class Down:
        async def find_one(self, *args, **kwargs):
            raise ConnectionError("no primary")
    monkeypatch.setattr(probes, "col", lambda name: Down())
    response = await probes.health_check()
    body = json.loads(response.body)
    assert response.status_code == 503
    assert body["status"] == "unhealthy" and body["dependencies"]["database"] == "connection_failed"


async def test_health_is_ready_but_degraded_without_ollama(probes, mock_db, monkeypatch):
    from agents import llm_provider
    monkeypatch.setattr(probes, "col", lambda name: mock_db[name])
    monkeypatch.setattr(llm_provider, "check_ollama_connection", lambda: False)
    response = await probes.health_check()
    assert response.status_code == 200
    assert json.loads(response.body)["status"] == "degraded"
    assert (await probes.liveness_check())["status"] == "alive"


async def test_one_failing_index_initialiser_does_not_skip_the_others(probes, mock_db, monkeypatch):
    calls = []

    def step(name, fail=False):
        async def run():
            calls.append(name)
            if fail:
                raise RuntimeError("index build failed")
        return name, run

    async def initializers():
        return [step("repository_baseline"), step("hitl", fail=True), step("qa"),
                step("token_revocation"), step("blocked_work"), step("release")]
    monkeypatch.setattr(probes, "_index_initializers", initializers)
    monkeypatch.setattr(probes, "col", lambda name: mock_db[name])
    assert await probes.ensure_all_indexes() == {"hitl"}
    assert calls == ["repository_baseline", "hitl", "qa", "token_revocation", "blocked_work", "release"]
    response = await probes.health_check()
    assert response.status_code == 503 and json.loads(response.body)["missing_indexes"] == ["hitl"]


# ── EV-01 / EV-02: evaluation reads stay inside the caller's organisation ───

CEO_A = {"employee_id": "CEO-A", "role": "CEO", "org_id": "ORG-A"}


def _evaluation(evaluation_id, employee_id, org_id):
    return {"evaluation_id": evaluation_id, "employee_id": employee_id, "github_username": "dev", "org_id": org_id,
            "repo_owner": "owner", "repo_name": "repo", "pr_number": 7, "head_commit_sha": "a" * 40,
            "evaluation_focus": "code_quality", "ai_provider": "ollama", "model_name": "llama3.2",
            "created_at": "2026-11-01T00:00:00"}


@pytest.fixture
async def tenants(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    from repositories.project_repository import ProjectRepository
    monkeypatch.setattr(authorization, "_project_repo", ProjectRepository())
    await mock_db.users.insert_many([
        {"employee_id": "CEO-A", "role": "CEO", "org_id": "ORG-A"},
        {"employee_id": "DEV-A", "role": "DEVELOPER", "org_id": "ORG-A"},
        {"employee_id": "DEV-B", "role": "DEVELOPER", "org_id": "ORG-B"},
        {"employee_id": "DEV-X", "role": "DEVELOPER", "org_id": "ORG-A", "organization_id": "ORG-B"},
    ])
    await mock_db.developer_evaluations.insert_many([
        _evaluation("EVAL-A", "DEV-A", "ORG-A"),
        {**_evaluation("EVAL-B", "DEV-B", "ORG-B"), "created_at": "2026-11-20T00:00:00"},
    ])
    return mock_db


async def test_ceo_cannot_read_another_organisations_people(tenants):
    await authorization.verify_can_view_person_evaluations(CEO_A, "DEV-A")
    for outsider in ("DEV-B", "DEV-X"):  # other org, or conflicting organisation alias
        with pytest.raises(HTTPException) as error:
            await authorization.verify_can_view_person_evaluations(CEO_A, outsider)
        assert error.value.status_code == 403
    with pytest.raises(HTTPException):
        await authorization.verify_can_view_person_evaluations({"employee_id": "CEO-N", "role": "CEO"}, "DEV-A")


async def test_ceo_latest_and_by_id_do_not_cross_tenants(tenants):
    from api.routes import evaluation
    latest = await evaluation.get_latest_evaluation(CEO_A)
    assert latest.evaluation_id == "EVAL-A"  # EVAL-B is newer but belongs to ORG-B
    with pytest.raises(HTTPException) as error:
        await evaluation.get_evaluation("EVAL-B", CEO_A)
    assert error.value.status_code in {403, 404}


async def test_ceo_pr_listing_requires_an_in_scope_repository(tenants):
    from api.routes import evaluation
    with pytest.raises(HTTPException) as error:
        await evaluation.list_pr_evaluations("owner", "repo", 7, CEO_A)
    assert error.value.status_code == 403
    await tenants.projects.insert_one({"id": "PRJ-A", "org_id": "ORG-A"})
    await tenants.github_project_configs.insert_one({"project_id": "PRJ-A", "repository_owner": "owner",
                                                     "repository_name": "repo", "org_id": "ORG-A"})
    results = await evaluation.list_pr_evaluations("owner", "repo", 7, CEO_A)
    assert [item.evaluation_id for item in results] == ["EVAL-A"]


# ── EV-03 / EV-04: evaluation receipts ──────────────────────────────────────

async def test_changed_model_or_human_input_is_a_new_evaluation_and_unscored_is_storable(monkeypatch, mock_db):
    from repositories import evaluation_repository
    from test_evaluation_engine import _persistable_evaluation
    monkeypatch.setattr(evaluation_repository, "col", lambda _: mock_db["developer_evaluations"])
    repository = evaluation_repository.EvaluationRepository()
    base = _persistable_evaluation("EVAL-1")
    assert (await repository.create_or_get(base)).evaluation_id == "EVAL-1"
    assert (await repository.create_or_get(base.model_copy(update={"evaluation_id": "EVAL-2"}))).evaluation_id == "EVAL-1"
    other_model = base.model_copy(update={"evaluation_id": "EVAL-3", "model_name": "qwen2.5"})
    assert (await repository.create_or_get(other_model)).evaluation_id == "EVAL-3"
    other_human = base.model_copy(update={"evaluation_id": "EVAL-4", "human_score": 6})
    assert (await repository.create_or_get(other_human)).evaluation_id == "EVAL-4"

    unscored_dims = {name: {"assessment": "insufficient_evidence", "reasoning": "No evidence"} for name in base.dimensions}
    unscored = base.model_copy(update={
        "evaluation_id": "EVAL-5", "overall_score": None, "dimensions": unscored_dims,
        "evidence_manifest": {"files": [{"file": "docs.md"}]},
        "evidence_coverage": {name: "insufficient_evidence" for name in base.dimensions}})
    assert (await repository.create_or_get(unscored)).evaluation_id == "EVAL-5"
    # A score without any scored dimension is still rejected.
    with pytest.raises(ValueError):
        await repository.create_or_get(unscored.model_copy(update={"evaluation_id": "EVAL-6", "overall_score": 5.0}))


async def test_evaluation_internal_errors_are_not_returned_to_the_client(monkeypatch):
    from api.routes import evaluation
    monkeypatch.setattr(evaluation, "verify_can_view_person_evaluations", AsyncMock())
    monkeypatch.setattr(evaluation, "_verify_repository_in_scope", AsyncMock())
    monkeypatch.setattr(evaluation, "_verified_subject_github", AsyncMock(return_value="dev"))
    monkeypatch.setattr(evaluation, "GitHubAPIService", lambda: (_ for _ in ()).throw(RuntimeError("mongodb://user:pw@db")))
    request = evaluation.SimpleEvalRequest(employee_id="DEV-A", github_username="dev", repo_owner="o", repo_name="r", pr_number=1)
    with pytest.raises(HTTPException) as error:
        await evaluation.evaluate_developer_ai(request, CEO_A)
    assert error.value.status_code == 500 and "mongodb" not in error.value.detail


# ── CI-01: CI import never rewrites another tenant's rows ───────────────────

import test_actions_report_import as ci_import_tests  # noqa: E402  (fixture reuse)

importer = ci_import_tests.importer  # the same pytest fixture, registered under its own name here


async def test_ci_import_does_not_take_over_a_foreign_receipt(importer):
    db, service, _ = importer
    receipt = await service.import_run("P", 4, 10, {"employee_id": "L"})
    row_id = receipt["test_run_ids"][0]
    await db.test_runs.create_index("id", unique=True)
    await db.test_runs.update_one({"id": row_id}, {"$set": {"organization_id": "B", "project_id": "OTHER"}})
    with pytest.raises(HTTPException) as error:
        await service.import_run("P", 4, 10, {"employee_id": "L"})
    assert error.value.status_code == 409
    stored = await db.test_runs.find_one({"id": row_id})
    assert stored["organization_id"] == "B" and stored["project_id"] == "OTHER"


async def test_ci_import_keeps_tenant_and_registrant_of_the_source(importer):
    db, service, _ = importer
    await service.import_run("P", 4, 10, {"employee_id": "L"})
    config = await db.qa_ci_configs.find_one({"project_id": "P"})
    assert config["org_id"] == "A" and config["artifact_import_registered_by"] == "L"
    await db.qa_ci_configs.update_one({"project_id": "P"}, {"$set": {"org_id": "B"}})
    with pytest.raises(HTTPException) as error:
        await service.import_run("P", 4, 10, {"employee_id": "L"})
    assert error.value.status_code == 409
    assert (await db.qa_ci_configs.find_one({"project_id": "P"}))["org_id"] == "B"


# ── SEC-02: bcrypt input is never silently truncated ────────────────────────

def test_passwords_longer_than_bcrypt_limit_are_rejected_not_truncated():
    from core.security import hash_password, validate_password_strength, verify_password
    long_password = "Aa1!" + "x" * 80
    ok, message = validate_password_strength(long_password)
    assert not ok and "72 bytes" in message
    with pytest.raises(ValueError):
        hash_password(long_password)
    hashed = hash_password(long_password[:72])
    assert verify_password(long_password[:72], hashed)
    assert not verify_password(long_password, hashed)  # same 72-byte prefix no longer matches


# ── SEC-03: default limits are enforced by middleware ───────────────────────

def test_rate_limit_middleware_is_installed():
    import main
    from slowapi.middleware import SlowAPIMiddleware
    assert any(m.cls is SlowAPIMiddleware for m in main.app.user_middleware)


# ── SEC-04: refreshing rotates the session ──────────────────────────────────

async def test_refresh_revokes_the_presented_token(monkeypatch):
    import httpx
    import main
    from api.routes import auth
    from core.dependencies import get_current_user
    revoked = AsyncMock()
    monkeypatch.setattr(auth, "revoke_token", revoked)
    monkeypatch.setattr(auth.auth_service, "refresh_session", AsyncMock(return_value="new-token"))
    main.app.dependency_overrides[get_current_user] = lambda: {"employee_id": "DEV-A", "jti": "old-jti", "exp": 4102444800}
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
            response = await client.post("/api/auth/refresh")
    finally:
        main.app.dependency_overrides.pop(get_current_user, None)
    assert response.status_code == 200 and response.json() == {"token": "new-token"}
    assert revoked.await_args.args[0] == "old-jti"


# ── SEC-06: AI-run project scope requires a tenant for every role ───────────

async def test_ai_run_scope_requires_tenant_even_for_ceo(mock_db, monkeypatch):
    from domain.services import ai_run_access
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    await mock_db.projects.insert_many([{"id": "PRJ-A", "org_id": "ORG-A"}, {"id": "PRJ-B", "org_id": "ORG-B"},
                                        {"id": "PRJ-X", "org_id": "ORG-A", "organization_id": "ORG-B"}])
    assert await ai_run_access.accessible_projects({"employee_id": "CEO-N", "role": "CEO"}) == []
    rows = await ai_run_access.accessible_projects(CEO_A)
    assert [row["id"] for row in rows] == ["PRJ-A"]


# ── OPS-04: configured pool bounds reach the Mongo client ───────────────────

def test_mongo_client_uses_configured_pool(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, uri, **options):
            captured.update(options)
    monkeypatch.setattr(database, "AsyncIOMotorClient", FakeClient)
    monkeypatch.setattr(database, "_client", None)
    database.get_client()
    from core.config import settings
    assert captured["maxPoolSize"] == settings.DB_MAX_POOL_SIZE
    assert captured["minPoolSize"] == settings.DB_MIN_POOL_SIZE
    monkeypatch.setattr(database, "_client", None)


# ── CQ-01: a PR request without paths uses the PR's changed files ───────────

async def test_pr_paths_come_from_the_connected_pull_request(monkeypatch):
    from api.routes import code_quality
    from domain.services import ai_evidence_service, github_api_service

    class Client:
        async def get_pr_files(self, owner, repo, number):
            assert (owner, repo, number) == ("owner", "repo", 12)
            return [{"filename": "src/app.py", "status": "modified"}, {"filename": "old.py", "status": "removed"},
                    {"filename": "src/app.py", "status": "modified"}, {"filename": "web/view.ts", "status": "added"}]
    monkeypatch.setattr(ai_evidence_service, "_repository", AsyncMock(return_value=("owner", "repo")))
    monkeypatch.setattr(github_api_service, "GitHubAPIService", lambda: type("S", (), {"client": Client()})())
    assert await code_quality._pull_request_paths("PRJ-A", "ORG-A", 12) == ["src/app.py", "web/view.ts"]


async def test_analysis_without_files_needs_a_pr_and_records_the_source(mock_db, monkeypatch):
    from fastapi import BackgroundTasks
    from api.routes import code_quality
    monkeypatch.setattr(code_quality, "col", lambda name: mock_db[name])
    monkeypatch.setattr(code_quality, "verify_project_access", AsyncMock())
    monkeypatch.setattr(code_quality, "_pull_request_paths", AsyncMock(return_value=["src/app.py"]))
    user = {"employee_id": "QA-A", "role": "QA", "org_id": "ORG-A"}
    with pytest.raises(HTTPException) as error:
        await code_quality.start_analysis(code_quality.AnalyzeRequest(repository_id="PRJ-A"), BackgroundTasks(), user)
    assert error.value.status_code == 422
    started = await code_quality.start_analysis(
        code_quality.AnalyzeRequest(repository_id="PRJ-A", pr_number=12), BackgroundTasks(), user)
    run = await mock_db.code_quality_runs.find_one({"run_id": started["run_id"]})
    assert run["changed_files"] == ["src/app.py"] and run["changed_files_source"] == "pull_request"
    assert started["language"] == "python"


# ── CQ-02: deltas only between comparable revisions ─────────────────────────

def _side(**overrides):
    side = {"quality_score": 80, "quality_analysis_status": "available", "policy_digest": "policy-1",
            "tools_executed": ["ruff", "bandit"], "quality_dimensions": {"testing": 70, "complexity": 90, "duplication": None}}
    side.update(overrides)
    return side


@pytest.mark.parametrize("change, reason", [
    ({"quality_score": None}, "score_unavailable"),
    ({"quality_analysis_status": "partial"}, "partial_evidence"),
    ({"policy_digest": "policy-2"}, "policy_changed"),
    ({"tools_executed": ["ruff"]}, "tools_differ"),
    ({"quality_dimensions": {"testing": 70, "complexity": None}}, "dimensions_differ"),
])
def test_incomparable_quality_delta_is_withheld(change, reason):
    from domain.services.pr_quality_comparison import comparable_delta
    assert comparable_delta(_side(), _side(**change)) == {"delta": None, "delta_withheld_reason": reason}


def test_comparable_quality_delta_is_reported_with_its_policy():
    from domain.services.pr_quality_comparison import comparable_delta
    result = comparable_delta(_side(), _side(quality_score=85))
    assert result["delta"] == 5 and result["delta_withheld_reason"] is None and result["policy_digest"] == "policy-1"
    assert comparable_delta(_side(), _side(quality_score=85), truncated=True)["delta"] is None


# ── CQ-04: stored scores carry their effective policy ───────────────────────

async def test_quality_and_risk_results_carry_the_effective_policy():
    from domain.services.quality_run_results import measure_quality, policy_digest
    from test_quality_engine import _make_evidence, TestingEvidenceModel
    evidence = _make_evidence(testing=TestingEvidenceModel(coverage_percentage=90.0), tools_executed=["ruff"])
    result = await measure_quality(evidence, ["src/app.py"])
    assert result["quality_score"] is not None
    assert set(result["quality_policy"]["weights"]) == {"static_security", "testing", "complexity", "architecture", "duplication"}
    assert {"weights", "base_risk", "thresholds"} <= set(result["risk_policy"])
    assert result["policy_digest"] == policy_digest(result["quality_policy"], result["risk_policy"])
    changed = {**result["quality_policy"], "weights": {**result["quality_policy"]["weights"], "testing": 0.99}}
    assert policy_digest(changed, result["risk_policy"]) != result["policy_digest"]


# ── CI-02: several coverage reports map to their own suites ─────────────────

def _coverage(suite, artifact_id, paths, covered, statements):
    return {"coverage_status": "reported", "coverage_percentage": 100 * covered / statements, "covered_lines": covered,
            "statement_lines": statements, "_paths": frozenset(paths), "report_path": "coverage.json",
            "test_suite": suite, "artifact_provenance": {"artifact_id": artifact_id}}


def test_disjoint_coverage_reports_combine_exact_line_counts():
    from domain.services.actions_report_import import combine_coverage
    combined = combine_coverage([_coverage("backend-coverage", 1, ["api.py"], 30, 40),
                                 _coverage("worker-coverage", 2, ["worker.py"], 10, 60)])
    assert (combined["covered_lines"], combined["statement_lines"], combined["coverage_percentage"]) == (40, 100, 40)
    assert [c["test_suite"] for c in combined["components"]] == ["backend-coverage", "worker-coverage"]
    assert "_paths" not in json.dumps(combined, default=str)


def test_overlapping_coverage_reports_are_ambiguous():
    from domain.services.actions_report_import import combine_coverage
    with pytest.raises(HTTPException) as error:
        combine_coverage([_coverage("a", 1, ["api.py"], 3, 4), _coverage("b", 2, ["api.py", "x.py"], 3, 8)])
    assert error.value.status_code == 409


async def test_import_attaches_each_coverage_report_to_its_own_suite(importer):
    import hashlib
    import io
    import zipfile
    db, service, client = importer

    def bundle(junit_name, coverage_path):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive_file:
            archive_file.writestr(junit_name, '<testsuite tests="1"><testcase/></testsuite>')
            archive_file.writestr("coverage.json", json.dumps({
                "totals": {"covered_lines": 1, "num_statements": 2},
                "files": {coverage_path: {"summary": {"covered_lines": 1, "num_statements": 2}}}}))
        return data.getvalue()
    blobs = {21: bundle("backend.xml", "api.py"), 22: bundle("worker.xml", "worker.py")}
    head = client.get_pull_request.return_value["head"]["sha"]
    client.get_workflow_artifacts.return_value = {"total_count": 2, "artifacts": [
        {"id": key, "name": f"suite{key}-test-results", "size_in_bytes": len(raw), "expired": False,
         "digest": "sha256:" + hashlib.sha256(raw).hexdigest(), "workflow_run": {"id": 10, "head_sha": head}}
        for key, raw in blobs.items()]}
    client.download_workflow_artifact.side_effect = lambda owner, repo, key: blobs[key]
    receipt = await service.import_run("P", 4, 10, {"employee_id": "L"})
    assert receipt["reported_coverage"]["statement_lines"] == 4 and receipt["reported_coverage"]["combined_from"] == 2
    rows = await db.test_runs.find({}).to_list(None)
    suites = sorted(row["reported_coverage"]["test_suite"] for row in rows)
    assert suites == ["suite21-test-results", "suite22-test-results"]


# ── OPS-05: high-confidence security and runtime checks block CI ────────────

def test_qa_workflow_blocks_on_high_confidence_findings():
    from pathlib import Path
    yaml = pytest.importorskip("yaml")
    root = Path(__file__).resolve().parents[2]
    steps = yaml.safe_load((root / ".github/workflows/samanvaya-qa.yml").read_text(encoding="utf-8"))["jobs"]["tests"]["steps"]
    blocking = [step for step in steps if not step.get("continue-on-error")]
    assert any("bandit -r . -ll -iii" in step.get("run", "") for step in blocking)
    assert any("ruff check . --select E9,F63,F7,F82" in step.get("run", "") for step in blocking)


def test_junit_uploader_rejects_xml_declarations(tmp_path, monkeypatch):
    import importlib.util
    from pathlib import Path
    script = Path(__file__).resolve().parents[1] / "integrations/github/qa_templates/upload_junit_results.py"
    spec = importlib.util.spec_from_file_location("uploader_template", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = tmp_path / "r.xml"
    report.write_text('<!DOCTYPE x [<!ENTITY a "b">]><testsuite tests="1"><testcase/></testsuite>')
    for key, value in {"SAMANVAYA_API_URL": "https://samanvaya.example", "SAMANVAYA_PROJECT_ID": "P",
                       "SAMANVAYA_TEST_RESULTS_TOKEN": "t", "GITHUB_REPOSITORY": "o/r", "GITHUB_SHA": "a" * 40}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr("sys.argv", ["upload", "--junit", str(report)])
    with pytest.raises(ValueError):
        module.main()


# ── AI-01: model timeout is configurable and the route backstop stays above it ──
def test_ai01_inference_timeout_is_configured_and_backstop_is_larger():
    from core.config import Settings, settings
    from agents import llm_provider
    from api.routes import evaluation as evaluation_routes

    assert llm_provider.INFERENCE_TIMEOUT_SECONDS == settings.OLLAMA_INFERENCE_TIMEOUT_SECONDS
    assert evaluation_routes.MODEL_REQUEST_TIMEOUT_SECONDS > llm_provider.INFERENCE_TIMEOUT_SECONDS
    assert Settings.model_fields["OLLAMA_INFERENCE_TIMEOUT_SECONDS"].default == 120.0


@pytest.mark.parametrize("value", [0, -5, 5000])
def test_ai01_inference_timeout_rejects_out_of_range(value, monkeypatch):
    from pydantic import ValidationError
    from core.config import Settings

    monkeypatch.setenv("OLLAMA_INFERENCE_TIMEOUT_SECONDS", str(value))
    with pytest.raises(ValidationError):
        Settings()
