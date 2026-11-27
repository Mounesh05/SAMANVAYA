"""Regression tests for evidence and identity at the connected quality boundary."""
import base64
import hashlib
from unittest.mock import AsyncMock

import pytest

from domain.services.github_api_service import GitHubAPIService
from domain.services.quality_run_results import measure_quality
from intelligence.analyzers.common import complexity
from intelligence.evidence.models import CodeQualityEvidence


@pytest.mark.anyio
async def test_fetch_by_git_tree_id_and_verify_contents_at_commit():
    api = GitHubAPIService()
    revision, tree_id = "a" * 40, "b" * 40
    content = b"print(1)"
    blob = hashlib.sha1(b"blob 8\0" + content).hexdigest()
    api.client.get_commit = AsyncMock(return_value={"sha":revision, "commit":{"tree":{"sha":tree_id}}})
    api.client.get_source_tree = AsyncMock(return_value={"sha":tree_id,"truncated":False,
        "tree":[{"mode":"100644","type":"blob","path":"a.py","sha":blob}]})
    api.client.get_file = AsyncMock(return_value={"type":"file","encoding":"base64","size":8,
        "path":"a.py","sha":blob,"content":base64.b64encode(content).decode()})
    sources, diagnostics = await api.fetch_analysis_sources("o","r",[{"filename":"a.py"}],revision,True,True)
    assert sources == {"a.py":"print(1)"} and diagnostics == []
    api.client.get_source_tree.assert_awaited_once_with("o","r",tree_id)
    api.client.get_file.assert_awaited_once_with("o","r","a.py",ref=revision)


@pytest.mark.anyio
async def test_lizard_reads_ccn_instead_of_tokens_and_respects_quoted_commas(monkeypatch):
    raw = '12,10,72,2,15,"a@1-15@module,one.py","module,one.py","a","a(x,y)",1,15\n'
    monkeypatch.setattr(complexity,"_run",AsyncMock(return_value=raw))
    result = await complexity._run_lizard(["module,one.py"])
    assert result["average_complexity"] == result["max_complexity"] == 10
    assert result["lines_of_code"] == 12
    assert result["high_complexity_functions"][0]["file"] == "module,one.py"
    assert result["high_complexity_functions"][0]["function"] == "a"


@pytest.mark.anyio
@pytest.mark.parametrize("path,state", [("missing.py","failed"),("README.md","unsupported")])
async def test_file_count_and_discovery_do_not_generate_scores(path, state):
    evidence = CodeQualityEvidence(repository_id="P", primary_language="unknown",files_analyzed=1,tools_executed=["ast-test-discovery"])
    result = await measure_quality(evidence,[path])
    assert result["status"] == state
    assert result["quality_score"] is None and result["risk_score"] is None


@pytest.mark.anyio
async def test_pr_quality_delta_uses_each_revision_and_replays_without_work(mock_db, monkeypatch):
    from domain.services import pr_quality_comparison as comparison
    from domain.services import internal_agent_adapter

    base, head = "1" * 40, "2" * 40
    pr = {"number": 7, "base": {"sha": base}, "head": {"sha": head}}
    files = [{"filename": "new.py", "previous_filename": "old.py", "status": "renamed"}]
    monkeypatch.setattr(comparison, "col", mock_db.get_collection)
    authority = internal_agent_adapter.CodeAuthority({"organization_id": "O"}, {}, "test")
    monkeypatch.setattr(internal_agent_adapter, "resolve_code_authority", AsyncMock(return_value=authority))

    async def fetch(owner, repo, selected, revision, **options):
        path = "old.py" if revision == base else "new.py"
        assert selected == [{"filename": path}]
        assert options["verified_snapshot"]
        return {path: "def report(): return 1"}, []

    api = GitHubAPIService()
    api.fetch_analysis_sources = AsyncMock(side_effect=fetch)

    async def analyze(service, paths, context):
        return CodeQualityEvidence(repository_id="P", commit_sha=context["commit_sha"],
                                   primary_language="python", files_analyzed=1, tools_executed=["ruff"])

    async def measure(evidence, paths):
        score = 72 if evidence.commit_sha == base else 86
        return {"status": "completed", "quality_analysis_status": "available", "quality_score": score,
                "function_discovery": evidence.function_discovery.model_dump(mode="json")}

    monkeypatch.setattr(comparison.CodeQualityService, "analyze_pr", analyze)
    monkeypatch.setattr(comparison, "measure_quality", measure)
    parent, _ = await comparison.compare_revisions(api, "P", "owner", "repo", pr, files, "actor")
    again, replay = await comparison.compare_revisions(api, "P", "owner", "repo", pr, files, "actor")
    # CQ-02: comparable sides also record why no delta was withheld and the shared policy.
    assert parent["quality_comparison"] == {"base_score": 72, "head_score": 86, "delta": 14,
                                            "delta_withheld_reason": None, "policy_digest": None,
                                            "base_status": "available", "head_status": "available"}
    assert parent["score_basis"] == parent["child_run_ids"]["head"]
    assert parent["run_id"] == again["run_id"] and replay.commit_sha == head
    assert api.fetch_analysis_sources.await_count == 2
    assert await mock_db.code_quality_runs.count_documents({"org_id": "O"}) == 3

    claim = {"run_id": "RUN-MANUAL", "status": "running", "claimed_by": "worker"}
    await mock_db.code_quality_runs.insert_one({**claim, "repository_id": "P", "org_id": "O"})
    await comparison.compare_revisions(
        api, "P", "owner", "repo", pr, files, "actor", claimed_run=claim, expected_org="O",
    )
    manual = await mock_db.code_quality_runs.find_one({"run_id": "RUN-MANUAL"})
    assert manual["kind"] == "pr_quality_comparison"
    assert manual["quality_comparison"]["delta"] == 14
    assert manual["child_run_ids"] == {"base": "RUN-MANUAL-base", "head": "RUN-MANUAL-head"}
    auto_replay, _ = await comparison.compare_revisions(api, "P", "owner", "repo", pr, files, "actor")
    assert auto_replay["run_id"] == parent["run_id"]



@pytest.mark.anyio
async def test_risk_level_uses_the_adjusted_score(monkeypatch):
    from domain.models.risk_configuration import RiskConfiguration
    from domain.services.risk_config_service import get_risk_config_service
    from intelligence.risk_engine import RiskEngine

    config = RiskConfiguration(base_risk=28, name="test", created_by="test")
    monkeypatch.setattr(get_risk_config_service(), "get_configuration", AsyncMock(return_value=config))
    evidence = CodeQualityEvidence(repository_id="P", primary_language="python")
    evidence.analysis_quality.confidence = 0.5
    evidence.testing.coverage_percentage = 90
    result = await RiskEngine().analyze_evidence(evidence)
    assert result["risk_score"] == 33
    assert result["risk_level"] == "MEDIUM"


@pytest.mark.anyio
async def test_repository_analysis_discovers_verified_tree_and_expands_directories():
    api = GitHubAPIService()
    revision, tree_id = "a" * 40, "b" * 40
    api.client.get_commit = AsyncMock(return_value={"sha": revision, "commit": {"tree": {"sha": tree_id}}})
    api.client.get_source_tree = AsyncMock(return_value={
        "sha": tree_id, "truncated": False,
        "tree": [
            {"path": "src/app.py", "mode": "100644", "type": "blob"},
            {"path": "src/web/App.tsx", "mode": "100644", "type": "blob"},
            {"path": "vendor/third_party.py", "mode": "100644", "type": "blob"},
            {"path": "README.md", "mode": "100644", "type": "blob"},
            {"path": "src/link.py", "mode": "120000", "type": "blob"},
        ],
    })
    summary = await api.list_repository_tree_summary("owner", "repo", revision, excluded_paths=["vendor"])
    assert summary["files"] == ["src/app.py", "src/web/App.tsx"]
    assert summary["directories"] == ["src", "src/web"]
    assert summary["unsupported_files_count"] == 1
    assert await api.expand_selected_paths("owner", "repo", revision, ["src/web/"]) == ["src/web/App.tsx"]

    api.client.get_source_tree.return_value["truncated"] = True
    with pytest.raises(ValueError, match="Exact regular-file tree required"):
        await api.list_repository_tree_summary("owner", "repo", revision)
