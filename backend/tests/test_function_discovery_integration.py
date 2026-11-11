"""Discovery follows existing analysis, authorization and persistence boundaries."""

import base64
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from api.routes import code_quality
from core.dependencies import get_current_user
from domain.services.code_quality_service import CodeQualityService
from domain.services.github_api_service import GitHubAPIService
from domain.services.github_analysis_service import GitHubAnalysisService
from domain.services.github_sync_service import GitHubSyncService
from intelligence.algorithms.discovery.service import discover_sources
from intelligence.evidence.models import CodeQualityEvidence
from repositories.code_quality_repository import CodeQualityRepository

pytestmark = pytest.mark.anyio
SOURCE = "def transform(values):\n    return sorted(values)\n"


async def test_registered_analysis_collects_discovery_without_model(monkeypatch):
    import domain.services.code_quality_service as module
    adapter = SimpleNamespace(analyze=AsyncMock(return_value=CodeQualityEvidence(repository_id="P1", primary_language="python")))
    monkeypatch.setattr(module, "get_analyzers_for_profile", lambda profile: {"python": adapter})
    evidence = await CodeQualityService().analyze_pr(["module.py"], {
        "project_id": "P1", "commit_sha": "sha-1", "source_files": {"module.py": SOURCE},
    })
    adapter.analyze.assert_awaited_once()
    assert evidence.function_discovery.functions[0].possible_task == "collection_ordering"
    assert evidence.function_discovery.source_revision == "sha-1"


async def test_discovery_snapshot_uses_existing_runs_and_authorization(mock_db, monkeypatch):
    import repositories.code_quality_repository as repository
    monkeypatch.setattr(repository, "col", lambda name: mock_db[name])
    monkeypatch.setattr(code_quality, "col", lambda name: mock_db[name])
    report = await discover_sources({"module.py": SOURCE}, "P1", "immutable-head")
    run_id = await CodeQualityRepository().save_discovery("P1", report, 5, "actor")
    user = {"employee_id": "actor", "role": "DEVELOPER"}
    accessible = AsyncMock(return_value=["P1"])
    monkeypatch.setattr(code_quality, "get_accessible_project_ids", accessible)
    app = FastAPI()
    app.include_router(code_quality.router, prefix="/quality")
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/quality/runs/{run_id}/functions?limit=1")
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["functions"][0]["verified_contract"] is None
        assert response.json()["source_revision"] == "immutable-head"
        assert "_id" not in response.json()
        second_page = await client.get(f"/quality/runs/{run_id}/functions?limit=1&skip=1")
        assert second_page.json()["functions"] == []
        accessible.return_value = []
        forbidden = await client.get(f"/quality/runs/{run_id}/functions")
        assert forbidden.status_code == 403
        missing = await client.get("/quality/runs/not-found/functions")
        assert missing.status_code == 404
    saved = await mock_db.code_quality_runs.find_one({"run_id": run_id})
    assert saved["analysis_level"] == "purpose_discovery"
    assert saved["quality_score"] is None and saved["risk_score"] is None


async def test_legacy_run_reports_not_analyzed_instead_of_inventing_evidence(mock_db, monkeypatch):
    monkeypatch.setattr(code_quality, "col", lambda name: mock_db[name])
    monkeypatch.setattr(code_quality, "get_accessible_project_ids", AsyncMock(return_value=["P1"]))
    await mock_db.code_quality_runs.insert_one({"run_id": "old", "repository_id": "P1"})
    data = await code_quality.get_discovered_functions("old", limit=50, skip=0, user={})
    assert data["status"] == "not_analyzed" and data["functions"] == []


async def test_code_quality_background_run_persists_discovery(mock_db, monkeypatch):
    from intelligence.quality_engine import QualityEngine
    from intelligence.risk_engine import RiskEngine
    from intelligence.baselines.repository_baseline import RepositoryBaseline
    report = await discover_sources({"module.py": SOURCE}, "P1", "head")
    evidence = CodeQualityEvidence(repository_id="P1", primary_language="python", function_discovery=report)
    monkeypatch.setattr(code_quality, "col", lambda name: mock_db[name])
    monkeypatch.setattr(code_quality.cq_service, "analyze_pr", AsyncMock(return_value=evidence))
    monkeypatch.setattr(QualityEngine, "calculate", AsyncMock(return_value={"quality_score": 80, "quality_grade": "B", "dimension_scores": {}}))
    monkeypatch.setattr(RiskEngine, "analyze_evidence", AsyncMock(return_value={"risk_score": 20, "risk_level": "low", "risk_factors": [], "dimension_scores": {}}))
    monkeypatch.setattr(RepositoryBaseline, "update_baseline", AsyncMock())
    await mock_db.code_quality_runs.insert_one({"run_id": "run", "repository_id": "P1"})
    body = code_quality.AnalyzeRequest(repository_id="P1", changed_files=["module.py"], use_ai=False)
    await code_quality._run_analysis("run", body, None)
    saved = await mock_db.code_quality_runs.find_one({"run_id": "run"})
    assert saved["status"] == "completed", saved.get("error")
    assert saved["function_discovery"]["functions"][0]["name"] == "transform"


async def test_github_fetches_exact_revision_and_reports_missing_files():
    service = GitHubAPIService()
    async def get_file(owner, repo, path, ref):
        assert ref == "immutable-head"
        if path == "missing.ts":
            return None
        return {"type": "file", "size": len(SOURCE), "encoding": "base64", "content": base64.b64encode(SOURCE.encode()).decode()}
    service.client.get_file = AsyncMock(side_effect=get_file)
    sources, diagnostics = await service.fetch_analysis_sources("owner", "repo", [
        {"filename": "module.py"}, {"filename": "missing.ts"}, {"filename": "../outside.py"},
        {"filename": "removed.py", "status": "removed"}, {"filename": "photo.png"},
    ], "immutable-head")
    assert sources == {"module.py": SOURCE}
    assert diagnostics == [{"path": "missing.ts", "kind": "source_unavailable"}]
    assert service.client.get_file.await_count == 2


async def test_github_includes_unmodified_tests_and_skips_symlinks():
    service = GitHubAPIService()
    service.client.get_source_tree = AsyncMock(return_value={"tree": [
        {"type": "blob", "mode": "100644", "path": "tests/test_module.py"},
        {"type": "blob", "mode": "100644", "path": "caller.ts"},
        {"type": "blob", "mode": "120000", "path": "link.py"},
        {"type": "blob", "mode": "100644", "path": "node_modules/vendor.js"},
    ]})
    service.client.get_file = AsyncMock(return_value={"type": "file", "size": 10, "encoding": "base64", "content": base64.b64encode(SOURCE.encode()).decode()})
    sources, diagnostics = await service.fetch_analysis_sources("o", "r", [{"filename": "module.py"}, {"filename": "link.py"}], "head", include_context=True)
    assert set(sources) == {"module.py", "tests/test_module.py", "caller.ts"}
    assert not diagnostics
    service.client.get_source_tree.assert_awaited_once_with("o", "r", "head")


async def test_connected_code_quality_run_resolves_source_revision(mock_db, monkeypatch):
    monkeypatch.setattr(code_quality, "col", lambda name: mock_db[name])
    await mock_db.github_project_configs.insert_one({"project_id": "P1", "repository_owner": "o", "repository_name": "r", "default_branch": "testing"})
    await mock_db.code_quality_runs.insert_one({"run_id": "run", "repository_id": "P1"})
    github = GitHubAPIService()
    github.client.get_commit = AsyncMock(return_value={"sha": "immutable-head"})
    github.fetch_analysis_sources = AsyncMock(return_value=({"module.py": SOURCE}, []))
    import domain.services.github_api_service as github_module
    monkeypatch.setattr(github_module, "GitHubAPIService", lambda: github)
    # Stop after the actual source-resolution path so unrelated scoring is outside this assertion.
    async def capture(**kwargs):
        assert kwargs["pr_context"]["commit_sha"] == "immutable-head"
        assert kwargs["pr_context"]["source_files"] == {"module.py": SOURCE}
        raise ValueError("Scoring deliberately outside test scope")
    analyze = AsyncMock(side_effect=capture)
    monkeypatch.setattr(code_quality.cq_service, "analyze_pr", analyze)
    body = code_quality.AnalyzeRequest(repository_id="P1", changed_files=["module.py"], use_ai=False)
    await code_quality._run_analysis("run", body, None)
    analyze.assert_awaited_once()
    github.client.get_commit.assert_awaited_once_with("o", "r", "testing")


async def test_ollama_outage_does_not_block_github_structural_analysis(monkeypatch):
    monkeypatch.setitem(sys.modules, "agents.llm_provider", SimpleNamespace(check_ollama_connection=lambda: False))
    result = await GitHubAnalysisService().analyze_with_ai({
        "project_id": "P1", "source_files": {"module.py": SOURCE}, "commit_sha": "head",
    }, {}, use_deep_analysis=True)
    assert result["ai_analysis"]["error"] == "Ollama not available"
    assert result["function_discovery"]["functions"][0]["task_status"] == "INFERRED"
    assert result["function_discovery"]["functions"][0]["verified_contract"] is None


async def test_pr_sync_discovers_and_persists_even_when_ai_disabled(mock_db, monkeypatch):
    import domain.services.github_sync_service as sync_module
    import repositories.code_quality_repository as repository
    monkeypatch.setattr(repository, "col", lambda name: mock_db[name])
    monkeypatch.setattr(sync_module, "PRRepository", lambda: SimpleNamespace(
        store_revision=AsyncMock(side_effect=lambda doc, **kwargs: (doc, True))))
    monkeypatch.setattr(sync_module, "AIRunRepository", lambda: SimpleNamespace(create=AsyncMock()))
    service = GitHubSyncService()
    pr = {"number": 3, "title": "Source update", "state": "open", "user": {"login": "author"},
          "head": {"sha": "head", "ref": "feature"}, "base": {"ref": "main"},
          "created_at": "2026-01-01T00:00:00Z", "html_url": "https://github.com/owner/repo/pull/3", "id": 3}
    service.api_service.fetch_pull_request_data = AsyncMock(return_value={"pr": pr, "files": [{"filename": "module.py"}], "commits": [], "check_runs": {"check_runs": []}})
    service.api_service.fetch_analysis_sources = AsyncMock(return_value=({"module.py": SOURCE}, []))
    service.analysis_service.analyze_risk = AsyncMock(return_value={"risk_score": 20, "risk_level": "low"})
    service.analysis_service.analyze_with_ai = AsyncMock(side_effect=AssertionError("No AI"))
    result = await service.sync_pull_request("owner", "repo", 3, "P1", use_ai=False)
    assert result["discovery_run_id"] and result["function_discovery"]["functions"]
    saved = await mock_db.code_quality_runs.find_one({"run_id": result["discovery_run_id"]})
    assert saved["function_discovery"]["source_revision"] == "head"
    service.analysis_service.analyze_with_ai.assert_not_awaited()
