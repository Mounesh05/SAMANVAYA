"""Repros for integration invariants missing from the initial Phase 1–5 suite."""

import copy
from unittest.mock import AsyncMock

import pytest

from intelligence.algorithms.decision import evaluate_decision
from intelligence.algorithms.discovery.service import discover_sources
from domain.services.pr_algorithm_intelligence_service import changed_functions
from repositories.recommendation_repository import RecommendationRepository
from test_pr_algorithm_intelligence import workflow, contract, run
from test_requirement_discovery import requirements, request, publish, source, declaration
from test_behavioral_compatibility import passing_evidence, approved, body, AUTHOR, REVIEWER, proposal
from domain.services.algorithm_benchmark_service import AlgorithmBenchmarkService
from domain.services.behavioral_compatibility_service import BehavioralCompatibilityService
from types import SimpleNamespace
from pathlib import Path
import re
import httpx
from fastapi import FastAPI

pytestmark = pytest.mark.anyio


async def test_manual_discovered_prefix_constraint_is_not_silently_discarded(requirements):
    payload = request()
    payload["decision_policy"] = {"id": "manual-policy", "version": "1", "objective": "MINIMIZE_TIME", "constraints": [{
        "id": "discovered-user-budget", "type": "MAX_LATENCY", "threshold": 0.001, "unit": "seconds",
        "metric": "elapsed_invocation_seconds", "evaluation_policy": "MAX_OBSERVED_INVOCATION", "source_reference": "user/explicit-budget"}]}
    prepared = await requirements.prepare(payload)
    result = evaluate_decision(prepared, passing_evidence(prepared), prepared["decision_policy"])
    assert all(row["task_eligibility"] == "INELIGIBLE" for row in result["candidates"])
    assert any(c["id"] == "discovered-user-budget" for c in prepared["decision_policy"]["constraints"])


async def test_user_unknown_requirement_with_discovered_prefix_remains_unknown(requirements):
    payload = request()
    payload["decision_policy"] = {"id": "manual", "version": "1", "unknown_requirements": [{"id": "discovered-user-order", "description": "Required traversal order is unknown"}]}
    prepared = await requirements.prepare(payload)
    assert any(r["id"] == "discovered-user-order" for r in prepared["decision_policy"]["unknown_requirements"])


async def test_supersession_chain_does_not_reactivate_an_ancestor_after_partial_write(requirements):
    one = await publish(requirements)
    two = await publish(requirements, source(declaration(value=0.2), source_revision="two", supersedes=one["source_id"]))
    # Approved replacement persisted, but updating its predecessor was interrupted.
    await requirements.collection("algorithm_requirement_sources").update_one({"source_id": one["source_id"]}, {"$set": {"status": "APPROVED"}})
    await publish(requirements, source(declaration(value=0.3), source_revision="three", supersedes=two["source_id"]))
    report = await requirements.discover("P1")
    assert [r["value"] for r in report["established"]] == [0.3]


async def test_superseded_manifest_invalidates_recommendations_before_pr_metadata_updates(workflow, monkeypatch):
    await contract(workflow)
    result = await run(workflow)
    import repositories.recommendation_repository as module
    monkeypatch.setattr(module, "db", workflow.db)
    repository = RecommendationRepository()
    assert await repository.find_by_entity("pr", "PR1", "pending")
    # A live revision check detects stale work before another sync updates the PR.
    await workflow.db.code_quality_runs.update_one({"run_id": result["run_id"]}, {"$set": {"status": "superseded"}})
    assert await repository.find_by_entity("pr", "PR1", "pending") == []


async def test_expired_queued_job_is_failed_when_claimed_without_a_history_read(workflow):
    created = await workflow.service.enqueue("P1", "o/r", workflow.pr, [{"filename": "module.py"}], "PR1", launch=False)
    await workflow.db.code_quality_runs.update_one({"run_id": created["run_id"]}, {"$set": {"lease_expires_at": "2000-01-01T00:00:00+00:00"}})
    await workflow.service.execute(created["run_id"])
    doc = await workflow.db.code_quality_runs.find_one({"run_id": created["run_id"]})
    pr = await workflow.db.pull_requests.find_one({"id": "PR1"})
    assert doc["status"] == "failed"
    assert pr["algorithm_intelligence_status"] == "failed"
    workflow.runner.run.assert_not_awaited()


async def test_history_labels_superseded_manifest_as_historical_before_pr_catches_up(workflow, monkeypatch):
    from api.routes import algorithms
    result = await run(workflow)
    await workflow.db.code_quality_runs.update_one({"run_id": result["run_id"]}, {"$set": {"status": "superseded"}})
    monkeypatch.setattr(algorithms, "col", lambda name: workflow.db[name])
    monkeypatch.setattr(algorithms.ProjectRepository, "find_by_id", AsyncMock(return_value={"id": "P1", "org_id": "org"}))
    history = await algorithms.pr_intelligence_history("P1", None, {"employee_id": "dev", "role": "DEVELOPER", "org_id": "org", "project_ids": ["P1"]})
    assert history["analyses"][0]["historical_only"]


@pytest.mark.parametrize("extension,before,after", [
    ("py", "a = lambda x: x; b = lambda y: y\n", "a = lambda x: x + 1; b = lambda y: y\n"),
    ("js", "function a(x){return x;} function b(y){return y;}", "function a(x){return x+1;} function b(y){return y;}"),
    ("ts", "const a = (x: number) => x; const b = (y: number) => y;", "const a = (x: number) => x+1; const b = (y: number) => y;"),
    ("py", "label='é'; a=lambda x:x; b=lambda y:y\n", "label='é'; a=lambda x:x+1; b=lambda y:y\n"),
    ("js", "const label='🙂'; function a(x){return x;} function b(y){return y;}", "const label='🙂'; function a(x){return x+1;} function b(y){return y;}"),
])
async def test_adjacent_function_change_does_not_mark_unchanged_sibling(extension, before, after):
    path = "module." + extension
    base = (await discover_sources({path: before}, "P1", "base")).model_dump()
    head = (await discover_sources({path: after}, "P1", "head")).model_dump()
    rows = changed_functions(base, head, [{"filename": path}], {path: before}, {path: after})
    assert [row["current"]["qualified_name"] for row in rows] == ["a"]


async def test_decorator_change_is_a_changed_python_implementation():
    before = "@first\ndef solve(x):\n    return x\n"
    after = "@second\ndef solve(x):\n    return x\n"
    base = (await discover_sources({"module.py": before}, "P1", "base")).model_dump()
    head = (await discover_sources({"module.py": after}, "P1", "head")).model_dump()
    rows = changed_functions(base, head, [{"filename": "module.py"}], {"module.py": before}, {"module.py": after})
    assert [row["current"]["qualified_name"] for row in rows] == ["solve"]


async def test_unverified_revision_label_cannot_exclude_an_approved_requirement(requirements):
    await publish(requirements, source(declaration(scope={"source_revision": "approved-revision"})))
    payload = request()
    discovery = (await discover_sources({"module.py": payload["candidates"][0]["source"]}, "P1", "client-claimed-other-revision")).model_dump()
    await requirements.collection("code_quality_runs").insert_one({"run_id": "unverified", "repository_id": "P1", "function_discovery": discovery})
    payload["requirement_context"] = {"discovery_run_ids": ["unverified"]}
    prepared = await requirements.prepare(payload)
    assert any(r["applicability_status"] == "UNRESOLVED" for r in prepared["requirements_discovery"]["established"])
    assert prepared["requirements_discovery"]["conflicts"]


async def test_function_contract_approval_from_a_different_current_organization_is_not_resolved(requirements):
    doc = await approved(requirements.contracts)
    await requirements.collection("projects").insert_one({"id": "P1", "org_id": "different-organization"})
    resolution = await requirements.contracts.resolve("P1", [doc["contract_id"]])
    assert resolution["status"] != "APPROVED"


async def test_requirement_approval_from_a_different_current_organization_is_not_enforced(requirements):
    await publish(requirements)
    await requirements.collection("projects").insert_one({"id": "P1", "org_id": "different-organization"})
    report = await requirements.discover("P1")
    assert not report["established"]
    assert report["conflicts"]


async def test_nested_function_reference_cannot_bind_a_different_module_entrypoint(requirements):
    code = "def solve(xs): return xs\nclass Other:\n    def solve(self, xs): return list(reversed(xs))\n"
    discovery = (await discover_sources({"module.py": code}, "P1", "revision")).model_dump()
    nested = next(fn for fn in discovery["functions"] if fn["qualified_name"] == "Other.solve")
    await requirements.collection("code_quality_runs").insert_one({"run_id": "R1", "repository_id": "P1", "function_discovery": discovery})
    contract_doc = await approved(requirements.contracts)
    benchmarks = AlgorithmBenchmarkService(requirements.collection("algorithm_benchmark_runs"), SimpleNamespace(run=AsyncMock()))
    service = BehavioralCompatibilityService(benchmarks, requirements.contracts)
    payload = body([contract_doc["contract_id"]])
    payload["previous"].update(source=code, function_reference={"run_id": "R1", "function_id": nested["function_id"]})
    result = await service.create(payload, AUTHOR)
    assert result["status"] == "completed"
    record = await benchmarks.get(result["run_id"])
    assert record["behavioral_compatibility"]["status"] == "UNVERIFIED"
    assert record["request"]["compatibility_context"]["context_errors"]


async def test_partial_discovery_is_visible_on_completed_pr_analysis(workflow):
    await contract(workflow)
    workflow.snapshots["head"]["broken.py"] = "def incomplete("
    result = await run(workflow, [{"filename": "module.py"}, {"filename": "broken.py"}])
    assert result["status"] == "completed"
    assert result["function_discovery"]["status"] == "partial"
    assert result["analysis_truncated"]


async def test_one_worker_failure_does_not_make_the_entire_pr_analysis_completed(workflow):
    workflow.snapshots["base"]["module.py"] += "\ndef other(xs): return xs\n"
    workflow.snapshots["head"]["module.py"] += "\ndef other(xs): return list(xs)\n"
    await contract(workflow)
    payload = proposal(name="other-operation")
    payload["automatic_scope"] = {"repository": "o/r", "path": "module.py", "qualified_name": "other"}
    await approved(workflow.service.contracts, payload)
    count = 0
    async def worker(request):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError("Second worker stopped")
        return passing_evidence(request)
    workflow.runner.run.side_effect = worker
    result = await run(workflow)
    assert result["status"] == "failed"
    assert {r["status"] for r in result["functions"]} == {"completed", "failed"}


async def test_superseded_worker_event_does_not_generate_new_risk_recommendations():
    from domain.services.webhook_event_processor import WebhookEventProcessor
    from domain.models.webhook_event import WebhookEvent
    processor = WebhookEventProcessor.__new__(WebhookEventProcessor)
    processor.github_service = SimpleNamespace(sync_pull_request=AsyncMock(return_value={"pr": {"id": "PR1"},
        "risk_analysis": {"risk_score": 90, "risk_level": "high"}, "revision_superseded": True}))
    processor.traceability_service = SimpleNamespace(link_pr_to_tasks=AsyncMock(return_value=[]))
    processor.recommendation_engine = SimpleNamespace(generate_pr_recommendations=AsyncMock(return_value=["stale-recommendation"]))
    processor._notify_pr_risks = AsyncMock(return_value=[])
    result = await processor._handle_pull_request_event(WebhookEvent(id="WH", event_type="pull_request", event_action="synchronize",
        project_id="P1", repository="o/r", payload={"pull_request": {"number": 7}, "repository": {"full_name": "o/r"}}))
    assert not result["recommendations_created"]
    processor.recommendation_engine.generate_pr_recommendations.assert_not_awaited()
    processor._notify_pr_risks.assert_not_awaited()


async def test_superseded_sync_does_not_attach_old_ai_results_to_current_pr(mock_db, monkeypatch):
    from domain.services.github_sync_service import GitHubSyncService
    from integrations.github.normalizer import GitHubNormalizer
    import repositories.code_quality_repository as quality
    monkeypatch.setattr(quality, "col", lambda name: mock_db[name])
    raw = {"number": 7, "title": "old snapshot", "state": "open", "user": {"login": "dev"}, "head": {"sha": "old", "ref": "branch"},
        "base": {"sha": "base", "ref": "testing"}, "created_at": "2026-11-01T10:00:00Z", "html_url": "https://github.com/o/r/pull/7", "id": 7}
    service = GitHubSyncService.__new__(GitHubSyncService)
    service.normalizer = GitHubNormalizer()
    service.pr_repo = SimpleNamespace(store_revision=AsyncMock(return_value=({"id": "PR1", "project_id": "P1", "head_sha": "new", "risk_score": 0, "risk_level": "low"}, False)))
    service.api_service = SimpleNamespace(fetch_pull_request_data=AsyncMock(return_value={"pr": raw, "files": [], "commits": [], "check_runs": {"check_runs": []}}),
        fetch_analysis_sources=AsyncMock(return_value=({}, [])))
    service.analysis_service = SimpleNamespace(analyze_risk=AsyncMock(return_value={"risk_score": 90, "risk_level": "high"}),
        analyze_with_ai=AsyncMock(return_value={"ai_analysis": {"analysis": "outdated"}}))
    result = await service.sync_pull_request("o", "r", 7, "P1")
    assert result["revision_superseded"]
    assert result["ai_analysis"] is None and result["risk_analysis"]["risk_score"] == 0
    service.analysis_service.analyze_with_ai.assert_not_awaited()


async def test_reevaluation_retires_superseded_workload_coverage_without_removing_manual_checks(requirements):
    old = await publish(requirements, source(declaration("WORKLOAD", {"required_dataset_ids": ["old-fixture"]})))
    runner = SimpleNamespace(run=AsyncMock(side_effect=passing_evidence))
    benchmarks = AlgorithmBenchmarkService(requirements.collection("algorithm_benchmark_runs"), runner, requirements)
    payload = request()
    payload["decision_policy"] = {"id": "explicit-manual", "version": "1", "required_dataset_ids": ["empty"]}
    created = await benchmarks.create(payload, AUTHOR)
    await benchmarks.execute(created["run_id"])
    previous = await benchmarks.get(created["run_id"])
    await publish(requirements, source(declaration("WORKLOAD", {"required_dataset_ids": ["required"]}), supersedes=old["source_id"], source_revision="replacement"))
    policy = previous["decision"]["policy_snapshot"]
    decision = await benchmarks.reevaluate(created["run_id"], policy, REVIEWER)
    assert decision["policy_snapshot"]["required_dataset_ids"] == ["empty", "required"]
    assert "old-fixture" not in decision["candidates"][0]["missing_required_dataset_ids"]


async def test_trusted_single_candidate_revision_can_establish_requirement_scope(requirements):
    payload = request()
    payload["candidates"] = payload["candidates"][:1]
    await requirements.collection("github_project_configs").insert_one({"project_id": "P1", "repository_owner": "o", "repository_name": "r"})
    discovery = (await discover_sources({"module.py": payload["candidates"][0]["source"]}, "P1", "revision-1")).model_dump()
    await requirements.collection("code_quality_runs").insert_one({"run_id": "trusted", "repository_id": "P1", "commit_sha": "revision-1",
        "source_provenance": {"method": "github-exact-revision", "repository": "o/r", "revision": "revision-1"}, "function_discovery": discovery})
    await publish(requirements, source(declaration(scope={"source_revision": "revision-1"})))
    payload["requirement_context"] = {"discovery_run_ids": ["trusted"]}
    prepared = await requirements.prepare(payload)
    assert prepared["requirements_discovery"]["established"][0]["applicability_status"] == "APPLIES"


async def test_one_bound_candidate_cannot_establish_an_excluding_revision_for_unbound_candidate(requirements):
    payload = request()
    await requirements.collection("github_project_configs").insert_one({"project_id": "P1", "repository_owner": "o", "repository_name": "r"})
    discovery = (await discover_sources({"module.py": payload["candidates"][0]["source"]}, "P1", "revision-1")).model_dump()
    await requirements.collection("code_quality_runs").insert_one({"run_id": "trusted", "repository_id": "P1", "commit_sha": "revision-1",
        "source_provenance": {"method": "github-exact-revision", "repository": "o/r", "revision": "revision-1"}, "function_discovery": discovery})
    await publish(requirements, source(declaration(scope={"source_revision": "revision-2"})))
    payload["requirement_context"] = {"discovery_run_ids": ["trusted"]}
    prepared = await requirements.prepare(payload)
    assert any(r["applicability_status"] == "UNRESOLVED" for r in prepared["requirements_discovery"]["established"])


def test_existing_qa_workflow_is_parseable_and_preserves_multilanguage_checks():
    text = (Path(__file__).resolve().parents[2] / ".github/workflows/samanvaya-qa.yml").read_text(encoding="utf-8")
    assert not re.search(r"^(<<<<<<<|=======|>>>>>>>)", text, re.MULTILINE), "Unresolved merge markers prevent GitHub from loading the QA workflow"
    yaml = pytest.importorskip("yaml")
    workflow = yaml.safe_load(text)
    steps = workflow["jobs"]["tests"]["steps"]
    assert any(step.get("uses", "").startswith("actions/setup-python@") for step in steps)
    assert any(step.get("uses", "").startswith("actions/setup-node@") for step in steps)
    assert any(step.get("run") == "bash ci/run_tests.sh" for step in steps)
    upload = next(step for step in steps if step.get("name") == "Upload results to Samanvaya")
    assert upload["if"] == "always() && github.event_name != 'pull_request'"
    final = next(step for step in steps if step.get("name") == "Fail workflow when tests fail")
    assert final["if"] == "always()" and "TEST_EXIT_CODE" in final["run"]


def test_qa_workflow_bootstraps_existing_static_parser_before_python_tests():
    yaml = pytest.importorskip("yaml")
    root = Path(__file__).resolve().parents[2]
    steps = yaml.safe_load((root / ".github/workflows/samanvaya-qa.yml").read_text(encoding="utf-8"))["jobs"]["tests"]["steps"]
    node_setup = next(i for i, step in enumerate(steps) if step.get("uses", "").startswith("actions/setup-node@"))
    tests = next(i for i, step in enumerate(steps) if step.get("run") == "bash ci/run_tests.sh")
    installs = [i for i, step in enumerate(steps) if "npm ci --prefix backend/benchmark_worker" in step.get("run", "")]
    assert installs, "The parser requires the pinned backend TypeScript package, which is absent in a fresh CI checkout"
    assert node_setup < installs[0] < tests


@pytest.mark.parametrize("surface", ["pending_recommendations", "pr_summary"])
async def test_new_decision_revision_cannot_leave_old_pr_finding_authoritative(workflow, monkeypatch, surface):
    from api.routes import algorithms
    import repositories.recommendation_repository as module
    await contract(workflow)
    result = await run(workflow)
    child_id = result["functions"][0]["benchmark_run_id"]
    decision = await workflow.benchmarks.reevaluate(child_id, {"id": "revised", "version": "1", "constraints": [{
        "id": "new-latency", "type": "MAX_LATENCY", "threshold": 0, "unit": "seconds", "metric": "elapsed_invocation_seconds",
        "evaluation_policy": "MAX_OBSERVED_INVOCATION", "source_reference": "review/revised-policy"}]}, REVIEWER)
    assert decision["task_suitability"]["status"] == "NO_ELIGIBLE_IMPLEMENTATION"
    if surface == "pending_recommendations":
        monkeypatch.setattr(module, "db", workflow.db)
        assert await RecommendationRepository().find_by_entity("pr", "PR1", "pending") == []
    else:
        monkeypatch.setattr(algorithms, "col", lambda name: workflow.db[name])
        monkeypatch.setattr(algorithms.ProjectRepository, "find_by_id", AsyncMock(return_value={"id": "P1", "org_id": "org"}))
        history = await algorithms.pr_intelligence_history("P1", None, {"employee_id": "dev", "role": "DEVELOPER", "org_id": "org", "project_ids": ["P1"]})
        assert history["analyses"][0]["functions"][0]["finding_status"] == "CONSTRAINT_FAILURE"
        assert history["analyses"][0]["functions"][0]["current_decision_reference"] == child_id + "/" + decision["revision_id"]


async def test_existing_recommendation_api_serializes_persisted_algorithm_findings(workflow, monkeypatch):
    from api.routes import recommendations
    from core.dependencies import get_current_user
    from domain.services.recommendation_engine import RecommendationEngine
    from repositories.pr_repository import PRRepository
    from repositories.project_repository import ProjectRepository
    import repositories.recommendation_repository as module
    await contract(workflow)
    await run(workflow)
    monkeypatch.setattr(module, "db", workflow.db)
    engine = RecommendationEngine.__new__(RecommendationEngine)
    engine.repo = RecommendationRepository()
    from fastapi.encoders import jsonable_encoder
    try:
        jsonable_encoder(await engine.get_recommendations_for_entity("pr", "PR1"))
    except ValueError as error:
        pytest.fail("Persisted recommendation cannot be JSON encoded: " + str(error))
    monkeypatch.setattr(recommendations, "engine", engine)
    monkeypatch.setattr(PRRepository, "find_by_id", AsyncMock(return_value={"id": "PR1", "project_id": "P1"}))
    monkeypatch.setattr(ProjectRepository, "find_by_id", AsyncMock(return_value={"id": "P1", "org_id": "org"}))
    app = FastAPI()
    app.include_router(recommendations.router)
    app.dependency_overrides[get_current_user] = lambda: {"employee_id": "dev", "role": "DEVELOPER", "org_id": "org", "project_ids": ["P1"]}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as client:
        response = await client.get("/entity/pr/PR1")
    assert response.status_code == 200, response.text
    assert response.json()["recommendations"][0]["finding_status"] == "CONDITIONAL_FINDING"


@pytest.mark.parametrize("role", ["DEVELOPER", "PM", "CEO"])
@pytest.mark.parametrize("surface", ["entity", "item", "accept", "reject", "implement"])
async def test_legacy_recommendation_route_cannot_bypass_algorithm_organization_scope(workflow, monkeypatch, role, surface):
    from api.routes import recommendations
    from core.dependencies import get_current_user
    from domain.services.recommendation_engine import RecommendationEngine
    from repositories.pr_repository import PRRepository
    from repositories.project_repository import ProjectRepository
    import repositories.recommendation_repository as module
    await contract(workflow)
    result = await run(workflow)
    monkeypatch.setattr(module, "db", workflow.db)
    engine = RecommendationEngine.__new__(RecommendationEngine)
    engine.repo = RecommendationRepository()
    monkeypatch.setattr(recommendations, "engine", engine)
    monkeypatch.setattr(PRRepository, "find_by_id", AsyncMock(return_value={"id": "PR1", "project_id": "P1"}))
    monkeypatch.setattr(ProjectRepository, "find_by_id", AsyncMock(return_value={"id": "P1", "org_id": "org"}))
    app = FastAPI()
    app.include_router(recommendations.router)
    app.dependency_overrides[get_current_user] = lambda: {"employee_id": "other", "role": role, "org_id": "foreign", "project_ids": ["P1"]}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as client:
        rec_id = result["recommendation_ids"][0]
        if surface == "entity":
            response = await client.get("/entity/pr/PR1")
        elif surface == "item":
            response = await client.get("/" + rec_id)
        else:
            response = await client.post("/" + rec_id + "/" + surface)
    assert response.status_code == 403
    assert (await workflow.db.recommendations.find_one({"id": rec_id}))["status"] == "pending"


@pytest.mark.parametrize("action,expected", [("accept", "accepted"), ("reject", "rejected"), ("implement", "implemented")])
async def test_authorized_existing_pm_recommendation_actions_remain_available(workflow, monkeypatch, action, expected):
    from api.routes import recommendations
    from domain.services.recommendation_engine import RecommendationEngine
    from repositories.project_repository import ProjectRepository
    import repositories.recommendation_repository as module
    await contract(workflow)
    result = await run(workflow)
    monkeypatch.setattr(module, "db", workflow.db)
    engine = RecommendationEngine.__new__(RecommendationEngine)
    engine.repo = RecommendationRepository()
    monkeypatch.setattr(recommendations, "engine", engine)
    monkeypatch.setattr(ProjectRepository, "find_by_id", AsyncMock(return_value={"id": "P1", "org_id": "org"}))
    rec_id = result["recommendation_ids"][0]
    user = {"employee_id": "pm", "role": "PM", "org_id": "org"}
    if action == "accept":
        response = await recommendations.accept_recommendation(rec_id, None, user)
    elif action == "reject":
        response = await recommendations.reject_recommendation(rec_id, None, user)
    else:
        response = await recommendations.mark_recommendation_implemented(rec_id, None, user)
    assert response["success"] and response["status"] == expected
    assert (await workflow.db.recommendations.find_one({"id": rec_id}))["status"] == expected
