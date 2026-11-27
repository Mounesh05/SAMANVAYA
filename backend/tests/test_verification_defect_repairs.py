"""Security/correctness reproductions use mock databases and trusted temp source."""
import hashlib
import json
import os
import shutil
import subprocess
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from core import database
from core.security import create_access_token
from domain.services.auth_service import AuthService
from api.routes import code_quality

pytestmark = pytest.mark.anyio


@pytest.fixture
async def quality_api(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    from core import authorization
    from repositories.project_repository import ProjectRepository
    monkeypatch.setattr(authorization, "_project_repo", ProjectRepository())
    await mock_db.projects.insert_many([
        {"id": "OWN", "org_id": "A", "team_id": "T"},
        {"id": "FOREIGN", "org_id": "B", "team_id": "T"},
        {"id": "LEGACY", "team_id": "T"},
    ])
    for project in ["OWN", "FOREIGN", "LEGACY"]:
        await mock_db.code_quality_runs.insert_one({"run_id": project, "repository_id": project,
            "status": "completed", "created_at": "2026-01-01", "function_discovery": {
                "status": "available", "functions": [{"qualified_name": "PRIVATE_EVIDENCE"}]}})
        await mock_db.code_quality_findings.insert_one({"run_id": project, "message": "PRIVATE_EVIDENCE"})
    app = FastAPI()
    app.include_router(code_quality.router, prefix="/quality")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, mock_db


def endpoints(project):
    return [f"/quality/runs/{project}", f"/quality/runs/{project}/functions",
            f"/quality/runs/{project}/findings", f"/quality/repositories/{project}/history",
            f"/quality/repositories/{project}/latest", f"/quality/projects/{project}/config"]


async def headers(db, role, org="A", projects=None, team="T"):
    account = {"employee_id": "ACTOR", "role": role, "org_id": org, "team_id": team,
               "project_ids": ["OWN"] if projects is None else projects, "is_active": True}
    await db.users.replace_one({"employee_id": "ACTOR"}, account, upsert=True)
    return {"Authorization": "Bearer " + create_access_token(AuthService._token_payload(account))}


@pytest.mark.parametrize("role", ["CEO", "LEAD", "PM", "DEVELOPER", "QA", "HR"])
async def test_foreign_quality_evidence_denied_on_every_read(quality_api, role):
    client, db = quality_api
    auth = await headers(db, role, projects=["OWN", "FOREIGN"])
    for path in endpoints("FOREIGN"):
        response = await client.get(path, headers=auth)
        assert response.status_code == 403, (path, response.text)
        assert "PRIVATE_EVIDENCE" not in response.text


@pytest.mark.parametrize("role", ["CEO", "LEAD", "PM", "DEVELOPER", "QA"])
async def test_same_org_authorized_quality_reads_remain_available(quality_api, role):
    client, db = quality_api
    auth = await headers(db, role)
    for path in endpoints("OWN"):
        assert (await client.get(path, headers=auth)).status_code == 200


@pytest.mark.parametrize("case", ["missing-user-org", "legacy-project", "hr", "unassigned", "unauthenticated", "missing-run-project"])
async def test_unknown_provenance_and_unauthorized_reads_are_closed(quality_api, case):
    client, db = quality_api
    project = "LEGACY" if case == "legacy-project" else "OWN"
    role = "HR" if case == "hr" else "DEVELOPER" if case == "unassigned" else "CEO"
    auth = await headers(db, role, org=None if case == "missing-user-org" else "A",
                         projects=[] if case == "unassigned" else None,
                         team=None if case == "unassigned" else "T")
    if case == "unauthenticated":
        auth = {}
    if case == "missing-run-project":
        await db.code_quality_runs.update_one({"run_id": "OWN"}, {"$unset": {"repository_id": ""}})
    paths = endpoints(project)[:3] if case == "missing-run-project" else endpoints(project)
    for path in paths:
        response = await client.get(path, headers=auth)
        assert response.status_code in (401, 403, 422), (case, path, response.text)
        assert "PRIVATE_EVIDENCE" not in response.text


async def test_shared_project_enumeration_is_tenant_scoped(quality_api):
    _, _db = quality_api
    from core.authorization import get_accessible_project_ids
    for role in ["CEO", "LEAD", "PM", "DEVELOPER"]:
        user = {"role": role, "org_id": "A", "team_id": "T", "project_ids": ["OWN", "FOREIGN", "LEGACY"]}
        assert await get_accessible_project_ids(user) == ["OWN"]
        assert await get_accessible_project_ids({**user, "org_id": None}) == []


@pytest.mark.parametrize("context", [
    {"repo_path": "C:/private-foreign-project"},
    {"source_files": {"module.py": "def forged(): return 1"}, "commit_sha": "a" * 40},
])
async def test_public_quality_submission_cannot_select_host_source_or_forge_snapshot(quality_api, monkeypatch, context):
    client, db = quality_api
    worker = AsyncMock()
    monkeypatch.setattr(code_quality, "_run_analysis", worker)
    before = await db.code_quality_runs.count_documents({})
    response = await client.post("/quality/analyze", headers=await headers(db, "QA"), json={
        "repository_id": "OWN", "changed_files": ["module.py"], "use_ai": False, "pr_context": context})
    assert response.status_code == 422
    assert await db.code_quality_runs.count_documents({}) == before
    worker.assert_not_called()


@pytest.mark.parametrize("metadata", [{"org_id": "B"}, {"organization_id": "B"}, {"org_id": "A", "organization_id": "B"},
    {"org_id": ["A", "B"]}, {"organization_id": ["A", "B"]}])
async def test_conflicting_run_tenant_is_denied_and_filtered(quality_api, metadata):
    client, db = quality_api
    await db.code_quality_runs.update_one({"run_id": "OWN"}, {"$set": metadata})
    auth = await headers(db, "CEO")
    for path in endpoints("OWN")[:3]:
        response = await client.get(path, headers=auth)
        assert response.status_code == 403
        assert "PRIVATE_EVIDENCE" not in response.text
    history = await client.get('/quality/repositories/OWN/history', headers=auth)
    assert history.json()["count"] == 0
    assert (await client.get('/quality/repositories/OWN/latest', headers=auth)).status_code == 404


async def test_revoked_permissions_and_unassigned_lead_cannot_read(quality_api):
    client, db = quality_api
    auth = await headers(db, "LEAD")
    await db.users.update_one({"employee_id": "ACTOR"}, {"$set": {"role": "HR"}})
    assert (await client.get('/quality/runs/OWN', headers=auth)).status_code == 403
    auth = await headers(db, "LEAD", team="OTHER", projects=[])
    assert (await client.get('/quality/runs/OWN', headers=auth)).status_code == 403
    auth = await headers(db, "LEAD", team="OTHER", projects=["OWN"])
    assert (await client.get('/quality/runs/OWN', headers=auth)).status_code == 200


async def test_conflicting_finding_metadata_is_filtered(quality_api):
    client, db = quality_api
    await db.code_quality_findings.insert_many([
        {"run_id": "OWN", "repository_id": "FOREIGN", "message": "FOREIGN_FINDING"},
        {"run_id": "OWN", "organization_id": "B", "message": "FOREIGN_FINDING"},
        {"run_id": "OWN", "organization_id": ["A", "B"], "message": "FOREIGN_FINDING"},
        {"run_id": "OWN", "repository_id": ["OWN", "FOREIGN"], "message": "FOREIGN_FINDING"},
        {"run_id": ["OWN", "FOREIGN"], "message": "FOREIGN_FINDING"}])
    response = await client.get('/quality/runs/OWN/findings', headers=await headers(db, "CEO"))
    assert response.status_code == 200 and response.json()["total"] == 1
    assert "FOREIGN_FINDING" not in response.text


async def test_array_project_reference_is_not_a_valid_run_scope(quality_api):
    client, db = quality_api
    await db.code_quality_runs.update_one({"run_id": "OWN"}, {"$set": {"repository_id": ["OWN", "FOREIGN"]}})
    auth = await headers(db, "CEO")
    assert (await client.get('/quality/runs/OWN', headers=auth)).status_code == 403
    assert (await client.get('/quality/repositories/OWN/history', headers=auth)).json()["count"] == 0
    assert (await client.get('/quality/repositories/OWN/latest', headers=auth)).status_code == 404


async def test_conflicting_configuration_tenant_is_denied(quality_api):
    client, db = quality_api
    await db.project_configs.insert_one({"project_id": "OWN", "organization_id": "B", "private_setting": "PRIVATE_EVIDENCE"})
    response = await client.get('/quality/projects/OWN/config', headers=await headers(db, "CEO"))
    assert response.status_code == 403 and "PRIVATE_EVIDENCE" not in response.text


async def test_ambiguous_configuration_project_is_not_exposed(quality_api):
    client, db = quality_api
    await db.project_configs.insert_one({"project_id": ["OWN", "FOREIGN"], "private_setting": "PRIVATE_EVIDENCE"})
    response = await client.get('/quality/projects/OWN/config', headers=await headers(db, "CEO"))
    assert response.status_code == 200 and "PRIVATE_EVIDENCE" not in response.text


@pytest.mark.parametrize("source_case", ["no-worktree", "missing-file", "snapshot-only", "unrelated-worktree", "server-cwd"])
async def test_deep_github_analysis_without_source_never_scores(mock_db, monkeypatch, tmp_path, source_case):
    from domain.services.github_analysis_service import GitHubAnalysisService
    from intelligence.quality_engine import QualityEngine
    from intelligence.risk_engine import RiskEngine
    from agents import llm_provider
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    from core import authorization
    from repositories.project_repository import ProjectRepository
    monkeypatch.setattr(authorization, "_project_repo", ProjectRepository())
    monkeypatch.setattr(llm_provider, "check_ollama_connection", lambda: False)
    await mock_db.users.insert_one({"employee_id": "DEV", "role": "DEVELOPER", "org_id": "A", "project_ids": ["P"], "is_active": True})
    await mock_db.projects.insert_one({"id": "P", "org_id": "A"})
    await mock_db.github_project_configs.insert_one({"project_id": "P", "repository_owner": "example", "repository_name": "fixture"})
    quality, risk = AsyncMock(), AsyncMock()
    monkeypatch.setattr(QualityEngine, "calculate", quality)
    monkeypatch.setattr(RiskEngine, "analyze_evidence", risk)
    data = {"project_id": "P", "repo": "example/fixture", "commit_sha": "a" * 40, "changed_files": ["module.py"]}
    if source_case == "server-cwd":
        data["changed_files"] = ["main.py"]
        data["source_files"] = {"main.py": "def trusted(x): return x"}
    if source_case in ("missing-file", "unrelated-worktree"):
        data["repo_path"] = str(tmp_path)
    if source_case in ("snapshot-only", "unrelated-worktree"):
        data["source_files"] = {"module.py": "def trusted(x): return x"}
    if source_case == "unrelated-worktree":
        (tmp_path / "module.py").write_text("def unrelated(x): return x + 1")
    result = await GitHubAnalysisService().analyze_with_ai(data, {}, use_deep_analysis=True, authorization={"employee_id": "DEV"})
    quality.assert_not_awaited()
    risk.assert_not_awaited()
    assert result["code_quality_report"] is None
    assert result["ai_analysis"]["status"] != "completed"
    assert result.get("quality_analysis_status") == "failed"
    assert not result.get("engine_results_v1")
    assert result["ai_run_data"]["status"] == "failed"


async def test_valid_local_source_preserves_real_partial_analysis(mock_db, monkeypatch, tmp_path):
    from domain.services.github_analysis_service import GitHubAnalysisService
    from agents import llm_provider
    from core import authorization
    from repositories.project_repository import ProjectRepository
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    monkeypatch.setattr(authorization, "_project_repo", ProjectRepository())
    monkeypatch.setattr(llm_provider, "check_ollama_connection", lambda: False)
    await mock_db.users.insert_one({"employee_id": "DEV", "role": "DEVELOPER", "org_id": "A", "project_ids": ["P"], "is_active": True})
    await mock_db.projects.insert_one({"id": "P", "org_id": "A"})
    await mock_db.github_project_configs.insert_one({"project_id": "P", "repository_owner": "example", "repository_name": "fixture"})
    source = "def trusted(x): return x\n"
    (tmp_path / "module.py").write_bytes(source.encode())
    result = await GitHubAnalysisService().analyze_with_ai({"project_id": "P", "repo": "example/fixture",
        "commit_sha": "a" * 40, "changed_files": ["module.py"], "source_files": {"module.py": source},
        "repo_path": str(tmp_path), "pr_id": "PR", "pr_number": 1}, {}, use_deep_analysis=True,
        authorization={"employee_id": "DEV"})
    assert result["code_quality_report"] is not None
    assert result["code_quality_report"].quality_score == result["engine_results_v1"]["quality"]["quality_score"]
    assert result["code_quality_report"].confidence < 1
    assert result["ai_analysis"]["status"] == "unavailable"
    assert result["ai_analysis"]["quality_analysis_status"] == "partial"
    assert result["ai_analysis"]["tools_skipped"]


def generate_coverage(tmp_path):
    binary = shutil.which("coverage")
    if not binary:
        pytest.skip("Real coverage CLI unavailable")
    source = tmp_path / "trusted.py"
    source.write_text("value = sum([1, 2, 3])\n", encoding="utf-8")
    result = subprocess.run([binary, "run", "--rcfile=" + os.devnull,
        "--data-file=" + str(tmp_path / ".coverage"), str(source)], cwd=tmp_path,
        capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    return source


async def test_real_coverage_export_preserves_percentage_and_provenance(tmp_path):
    from intelligence.analyzers.python.analyzer import PythonAnalyzer
    from intelligence.evidence.models import CodeQualityEvidence
    source = generate_coverage(tmp_path)
    original_data = (tmp_path / ".coverage").read_bytes()
    evidence = CodeQualityEvidence(repository_id="fixture", primary_language="python")
    testing = await PythonAnalyzer()._testing(str(tmp_path), evidence)
    assert testing.coverage_percentage == 100.0
    assert testing.coverage_status == "available"
    assert testing.coverage_provenance["source_hashes"]["trusted.py"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert testing.coverage_provenance["data_sha256"]
    assert testing.coverage_provenance["data_sha256"] == hashlib.sha256(original_data).hexdigest()
    assert (tmp_path / ".coverage").read_bytes() == original_data
    assert not (tmp_path / "coverage.json").exists()


async def test_mixed_language_merge_preserves_coverage_sources():
    from intelligence.evidence.models import TestingEvidence
    from intelligence.evidence.merger import EvidenceMerger
    python = TestingEvidence(total_tests=1, coverage_percentage=100, coverage_status="available",
        coverage_provenance={"data_sha256": "fixture-digest"})
    merged = EvidenceMerger._merge_testing([python, TestingEvidence(test_framework="jest")])
    assert merged.coverage_percentage == 100  # Existing aggregation policy is unchanged.
    assert merged.coverage_status == "partial"
    assert merged.coverage_provenance["sources"][0]["provenance"]["data_sha256"] == "fixture-digest"


async def test_unsupported_coverage_command_output_is_not_a_success(monkeypatch):
    import intelligence.analyzers.python.analyzer as module
    from types import SimpleNamespace
    process = SimpleNamespace(returncode=1, communicate=AsyncMock(return_value=(b"Unsupported command", b"")))
    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    assert await module._run(["coverage", "json", "-o", "-"], require_success=True) is None


@pytest.mark.parametrize("case", ["missing-data", "invalid-json", "invalid-report", "unavailable", "export-failed"])
async def test_coverage_failures_never_invent_percentages(tmp_path, monkeypatch, case):
    import intelligence.analyzers.python.analyzer as module
    from intelligence.evidence.models import CodeQualityEvidence
    analyzer = module.PythonAnalyzer()
    monkeypatch.setattr(analyzer, "_tool_available", lambda _: case != "unavailable")
    if case != "missing-data":
        (tmp_path / ".coverage").write_bytes(b"fixture data")
    output = {"invalid-json": "not json", "invalid-report": json.dumps({"totals": {}})}.get(case)
    monkeypatch.setattr(module, "_run", AsyncMock(return_value=output))
    evidence = CodeQualityEvidence(repository_id="fixture", primary_language="python")
    result = await analyzer._testing(str(tmp_path), evidence)
    assert result.coverage_percentage is None
    assert result.coverage_status == case
    assert result.coverage_unavailable_reason
