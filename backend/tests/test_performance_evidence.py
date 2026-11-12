"""Canonical evidence fails closed; observations do not establish employee value."""

import importlib
import json
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError


def models():
    return importlib.import_module("domain.models.performance_evidence")


def pipeline():
    return importlib.import_module("intelligence.performance_evidence")


def scope(**changes):
    return models().EvidenceScope(**{**dict(organization_id="O", employee_id="D", project_id="P",
        repository="owner/repo", period_start="2026-07-01T00:00:00Z", period_end="2026-10-01T00:00:00Z"), **changes})


def candidate(**changes):
    return {**dict(kind="pr", origin="pull_requests", external_id="17", organization_id="O", project_id="P",
        repository="owner/repo", occurred_at="2026-08-01T00:00:00Z", source_revision="a" * 40,
        actor_id="D", attribution_basis="EXACT_GITHUB_MAPPING", shared=False,
        facts={"status": "merged", "head_sha": "a" * 40}, parent_source_id=None), **changes}


def build(rows=(), **kwargs):
    return pipeline().build_evidence_snapshot(scope(), rows,
        captured_at=datetime(2026, 11, 12, tzinfo=timezone.utc), **kwargs)


def test_valid_facts_have_versioned_provenance_but_no_performance_points():
    snapshot = build([candidate()])
    assert snapshot.records[0].state == "VERIFIED_SNAPSHOT"
    assert snapshot.records[0].source_revision == "a" * 40
    assert snapshot.records[0].attribution.share is None
    assert snapshot.engineering_score is None and snapshot.combined_score is None
    assert snapshot.coverage.engineering_percent is None and snapshot.is_finalizable is False
    assert all(d.score is None and d.state == "NOT_ASSESSED" for d in snapshot.dimensions)
    assert snapshot.method == "performance-evidence-v1"


@pytest.mark.parametrize("bad", [dict(organization_id="OTHER"), dict(project_id="OTHER"),
    dict(repository="other/repo"), dict(occurred_at="2026-10-01T00:00:00Z"),
    dict(occurred_at="2026-06-30T23:59:59Z"), dict(occurred_at="bad"), dict(occurred_at=None)])
def test_wrong_scope_and_outside_half_open_period_fail_safely(bad):
    snapshot = build([candidate(**bad)])
    assert snapshot.records[0].state == "REJECTED"
    assert snapshot.engineering_score is None
    assert not any(d.verified_source_refs for d in snapshot.dimensions)


@pytest.mark.parametrize("changes,expected", [
    ({"actor_id": None}, "UNVERIFIED"), ({"actor_id": "OTHER"}, "REJECTED"),
    ({"shared": True}, "UNVERIFIED"), ({"source_revision": None}, "UNVERIFIED"),
    ({"disputed": True}, "DISPUTED"), ({"deleted": True}, "REJECTED"),
    ({"current_head_sha": "b" * 40}, "STALE"),
])
def test_uncertain_attribution_and_altered_sources_are_not_scoring_eligible(changes, expected):
    snapshot = build([candidate(**changes)])
    assert snapshot.records[0].state == expected
    assert snapshot.engineering_score is None


def test_counts_and_duplicates_cannot_increase_quality_or_scores():
    one = build([candidate()])
    many = build([candidate()] * 100)
    assert len(many.records) == 1
    assert many.dimensions == one.dimensions and many.coverage == one.coverage
    assert many.engineering_score is None


def test_conflicting_same_source_revisions_remain_visible_and_under_review():
    snapshot = build([candidate(), candidate(source_revision="b" * 40, facts={"status": "merged", "head_sha": "b" * 40})])
    assert len(snapshot.records) == 2 and all(r.state == "DISPUTED" for r in snapshot.records)
    assert snapshot.status == "UNDER_REVIEW"


def test_untrusted_strings_and_authority_claims_do_not_enter_snapshot():
    row = candidate(title="secret-password", description="medical details", approved=True, score=100,
        state="VERIFIED_SNAPSHOT", opportunity="AVAILABLE", facts={"status": "merged", "head_sha": "a" * 40,
        "secret": "secret-password", "story_points": 9999})
    snapshot = build([row])
    encoded = snapshot.model_dump_json()
    assert "secret-password" not in encoded and "medical details" not in encoded
    assert "story_points" not in encoded and snapshot.engineering_score is None
    assert all(d.opportunity == "UNKNOWN" for d in snapshot.dimensions)


def test_test_counts_distinguish_failed_skipped_and_inconsistent_records():
    facts = {"status": "passed", "tests_run": 10, "tests_passed": 7, "tests_failed": 0, "tests_skipped": 3}
    good = build([candidate(kind="test_run", origin="test_runs", facts=facts)])
    assert good.records[0].facts.tests_passed == 7 and good.records[0].facts.tests_skipped == 3
    assert good.engineering_score is None
    for bad in ({**facts, "tests_passed": True}, {**facts, "tests_failed": 2},
                {**facts, "tests_skipped": 8}, {**facts, "tests_passed": "7"}):
        invalid = build([candidate(kind="test_run", origin="test_runs", facts=bad)])
        assert invalid.records[0].state == "REJECTED"


def test_benchmark_and_analyzer_evidence_need_their_own_validation():
    benchmark = build([candidate(kind="benchmark", origin="algorithm_benchmark_runs", facts={"status": "completed"})])
    assert benchmark.records[0].state == "UNVERIFIED"
    analyzer = build([candidate(kind="analysis", origin="code_quality_runs", facts={"status": "completed", "suppressed": True})])
    assert analyzer.records[0].state == "UNVERIFIED"
    assert benchmark.engineering_score is None and analyzer.engineering_score is None


def test_snapshot_digest_is_order_stable_immutable_and_detects_changes_or_deletion():
    first = build([candidate(), candidate(external_id="18")])
    reverse = build([candidate(external_id="18"), candidate()])
    assert pipeline().evidence_digest(first) == pipeline().evidence_digest(reverse)
    restored = models().EvidenceSnapshot.model_validate_json(first.model_dump_json())
    assert pipeline().evidence_digest(restored) == pipeline().evidence_digest(first)
    with pytest.raises(ValidationError):
        first.records[0].facts.status = "closed"
    second = build([candidate(source_revision="b" * 40)])
    changes = pipeline().compare_evidence_snapshots(first, second)
    assert {c.change for c in changes} == {"CHANGED", "MISSING"}
    with pytest.raises(ValueError):
        pipeline().verify_evidence_snapshot(json.loads(second.model_dump_json()), pipeline().evidence_digest(first))


@pytest.mark.parametrize("boundary", ["2026-07-01", "2026-10-01T00:00:00", 1, True])
def test_periods_require_aware_dates_without_numeric_coercion(boundary):
    with pytest.raises(ValidationError):
        scope(period_start=boundary)


@pytest.fixture
async def stored(mock_db, monkeypatch):
    from core import database
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    await mock_db.users.insert_many([
        {"employee_id": "D", "org_id": "O", "role": "DEVELOPER", "is_active": True,
         "project_ids": ["P"], "github_username": "exact-login"},
        {"employee_id": "L", "org_id": "O", "role": "LEAD", "is_active": True, "project_ids": ["P"]},
    ])
    await mock_db.projects.insert_one({"id": "P", "org_id": "O"})
    await mock_db.github_project_configs.insert_one({"project_id": "P", "repository_owner": "owner", "repository_name": "repo"})
    await mock_db.tasks.insert_one({"id": "T1", "project_id": "P", "assignee_id": "D", "status": "done",
        "completed_at": "2026-08-01T00:00:00Z", "updated_at": "2026-08-01T00:00:00Z", "description": "DO NOT EXPORT"})
    await mock_db.pull_requests.insert_one({"id": "PR1", "project_id": "P", "repo_id": "owner/repo", "pr_number": 17,
        "author_login": "exact-login", "status": "merged", "head_sha": "a" * 40, "merged_at": "2026-08-01T00:00:00Z"})
    return mock_db


def request(**changes):
    return models().EvidencePreviewRequest(**{**dict(employee_id="D", project_id="P",
        period_start="2026-07-01T00:00:00Z", period_end="2026-10-01T00:00:00Z"), **changes})


@pytest.mark.anyio
async def test_service_collects_real_stored_shapes_with_no_model_or_database_writes(stored):
    from domain.services.performance_service import PerformanceService
    before = {name: await stored[name].find({}).to_list(None) for name in await stored.list_collection_names()}
    response = await PerformanceService.inspect_evidence(request(), {"employee_id": "L"})
    assert {r.kind for r in response.snapshot.records} == {"task", "pr"}
    # Local records do not establish exclusive ownership or contribution shares.
    assert all(r.state == "UNVERIFIED" and r.attribution.share is None for r in response.snapshot.records)
    assert all("SHARED_CONTRIBUTION_UNRESOLVED" in r.limitations for r in response.snapshot.records)
    assert response.snapshot.engineering_score is None
    assert "DO NOT EXPORT" not in response.model_dump_json()
    after = {name: await stored[name].find({}).to_list(None) for name in await stored.list_collection_names()}
    assert after == before


@pytest.mark.anyio
async def test_preview_does_not_initialize_or_invoke_ollama(stored, monkeypatch):
    from domain.services import performance_service
    def unavailable():
        raise AssertionError("Preview must not initialize an LLM")
    monkeypatch.setattr(performance_service, "PerformanceEvaluationAgent", unavailable)
    result = await performance_service.PerformanceService.inspect_evidence(request(), {"employee_id": "D"})
    assert result.snapshot.engineering_score is None


def test_pr_head_facts_must_agree_with_declared_revision():
    snapshot = build([candidate(facts={"status": "merged", "head_sha": "b" * 40})])
    assert snapshot.records[0].state == "STALE"


def test_snapshot_restoration_rejects_forged_refs_digests_and_coverage():
    snapshot = build([candidate()])
    for mutation in ("digest", "reference", "coverage", "status"):
        payload = json.loads(snapshot.model_dump_json())
        if mutation == "digest":
            payload["records"][0]["facts"]["status"] = "closed"
        elif mutation == "reference":
            payload["dimensions"][0]["verified_source_refs"] = ["f" * 64]
        elif mutation == "coverage":
            payload["coverage"]["engineering_percent"] = 100
        else:
            payload["status"] = "INSUFFICIENT_EVIDENCE"
        with pytest.raises(ValidationError):
            models().EvidenceSnapshot.model_validate(payload)


@pytest.mark.anyio
async def test_optional_source_errors_are_unavailable_and_do_not_leak_details(stored, monkeypatch):
    from domain.services.performance_service import PerformanceService
    from intelligence import performance_evidence_collection as collection
    original = collection.col
    class BrokenSource:
        def find(self, *args, **kwargs):
            raise RuntimeError("mongodb://private-password@host")
        async def find_one(self, *args, **kwargs):
            raise RuntimeError("mongodb://private-password@host")
    monkeypatch.setattr(collection, "col", lambda name: BrokenSource() if name in {"tasks", "qa_ci_configs"} else original(name))
    result = await PerformanceService.inspect_evidence(request(), {"employee_id": "D"})
    assert next(c for c in result.snapshot.connectors if c.origin == "tasks").availability == "UNAVAILABLE"
    assert next(c for c in result.snapshot.connectors if c.origin == "test_runs").availability == "UNAVAILABLE"
    assert "private-password" not in result.model_dump_json()


def test_foreign_rejected_source_cannot_poison_legitimate_source_identity():
    snapshot = build([candidate(), candidate(organization_id="OTHER")])
    assert {r.state for r in snapshot.records} == {"VERIFIED_SNAPSHOT", "REJECTED"}
    assert len({r.source_id for r in snapshot.records}) == 2


@pytest.mark.anyio
async def test_missing_mapping_and_configuration_are_not_no_activity(stored):
    from domain.services.performance_service import PerformanceService
    await stored.users.update_one({"employee_id": "D"}, {"$unset": {"github_username": ""}})
    result = await PerformanceService.inspect_evidence(request(), {"employee_id": "D"})
    connector = next(c for c in result.snapshot.connectors if c.origin == "pull_requests")
    assert connector.availability == "UNAVAILABLE" and connector.fetched_count == 0
    await stored.github_project_configs.delete_many({})
    result = await PerformanceService.inspect_evidence(request(), {"employee_id": "D"})
    assert next(c for c in result.snapshot.connectors if c.origin == "pull_requests").availability == "NOT_CONFIGURED"


@pytest.mark.anyio
async def test_unrelated_author_runs_and_cross_org_rows_are_not_attributed(stored):
    from domain.services.performance_service import PerformanceService
    await stored.tasks.insert_many([
        {"id": "OTHER-ORG-TASK", "project_id": "P", "org_id": "OTHER", "assignee_id": "D"},
        {"id": "OTHER-PROJECT-TASK", "project_id": "Q", "assignee_id": "D"},
    ])
    await stored.pull_requests.insert_one({"id": "OTHER-AUTHOR-PR", "project_id": "P", "repo_id": "owner/repo",
        "pr_number": 18, "author_login": "different-login", "head_sha": "b" * 40})
    await stored.code_quality_runs.insert_one({"run_id": "OTHER-RUN", "repository_id": "P", "pr_number": 18,
        "triggered_by": "D", "commit_sha": "b" * 40, "status": "completed"})
    result = await PerformanceService.inspect_evidence(request(), {"employee_id": "D"})
    assert len(result.snapshot.records) == 2


@pytest.mark.anyio
async def test_ci_revision_link_detects_rebase_and_skipped_tests_stay_observations(stored):
    from domain.services.performance_service import PerformanceService
    await stored.qa_ci_configs.insert_one({"project_id": "P", "repository": "owner/repo"})
    await stored.test_runs.insert_one({"id": "CI1", "project_id": "P", "repository": "owner/repo", "pr_number": 17,
        "commit_sha": "b" * 40, "status": "passed", "tests_run": 10, "tests_passed": 7, "tests_failed": 0,
        "tests_skipped": 3, "created_at": "2026-08-01T00:00:00Z"})
    result = await PerformanceService.inspect_evidence(request(), {"employee_id": "D"})
    run = next(r for r in result.snapshot.records if r.kind == "test_run")
    assert run.state == "STALE" and run.facts.tests_skipped == 3
    assert run.parent_source_id in {r.source_id for r in result.snapshot.records}
    assert result.snapshot.coverage.engineering_percent is None


@pytest.mark.anyio
async def test_unrelated_ci_configuration_is_not_a_trusted_source(stored):
    from domain.services.performance_service import PerformanceService
    await stored.qa_ci_configs.insert_one({"project_id": "P", "org_id": "OTHER", "repository": "owner/repo"})
    result = await PerformanceService.inspect_evidence(request(), {"employee_id": "D"})
    assert next(c for c in result.snapshot.connectors if c.origin == "test_runs").availability == "NOT_CONFIGURED"


@pytest.mark.anyio
async def test_actual_qa_defect_status_is_preserved_without_claiming_a_validated_fix(stored):
    from domain.services.performance_service import PerformanceService
    await stored.qa_defects.insert_one({"id": "DEFECT-1", "project_id": "P", "assignee_id": "D", "status": "FIXED",
        "updated_at": "2026-08-01T00:00:00Z", "created_at": "2026-08-01T00:00:00Z"})
    result = await PerformanceService.inspect_evidence(request(), {"employee_id": "D"})
    defect = next(r for r in result.snapshot.records if r.kind == "defect")
    assert defect.facts.status == "fixed"
    assert defect.state == "UNVERIFIED" and "INVALID_SOURCE_FACTS" not in defect.limitations
    assert result.snapshot.engineering_score is None


@pytest.mark.anyio
async def test_truncation_is_reported_and_never_means_complete_coverage(stored, monkeypatch):
    from domain.services.performance_service import PerformanceService
    from intelligence import performance_evidence_collection
    monkeypatch.setattr(performance_evidence_collection, "LIMIT", 1)
    await stored.tasks.insert_one({"id": "T2", "project_id": "P", "assignee_id": "D"})
    result = await PerformanceService.inspect_evidence(request(), {"employee_id": "D"})
    connector = next(c for c in result.snapshot.connectors if c.origin == "tasks")
    assert connector.availability == "PARTIAL" and "COLLECTION_TRUNCATED" in connector.limitations
    assert result.snapshot.coverage.engineering_percent is None


@pytest.mark.anyio
async def test_http_uses_current_account_and_exact_scope_before_fetching_evidence(stored):
    from api.routes import performance as routes
    from core.dependencies import get_current_user
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/performance")
    # Forged stale token claims cannot grant access: database role is DEVELOPER.
    actor = {"employee_id": "D", "role": "CEO", "org_id": "OTHER", "is_admin": True}
    app.dependency_overrides[get_current_user] = lambda: actor
    body = request().model_dump(mode="json")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        result = await client.post("/api/performance/evidence/preview", json=body)
        assert result.status_code == 200
        assert result.json()["snapshot"]["engineering_score"] is None
        forbidden = await client.post("/api/performance/evidence/preview", json={**body, "employee_id": "L"})
        assert forbidden.status_code == 403
        forged = await client.post("/api/performance/evidence/preview", json={**body, "approved": True, "score": 100})
        assert forged.status_code == 422
        await stored.users.update_one({"employee_id": "D"}, {"$set": {"org_id": "OTHER"}})
        assert (await client.post("/api/performance/evidence/preview", json=body)).status_code == 403


@pytest.mark.anyio
@pytest.mark.parametrize("actor_change", [{"role": "HR"}, {"role": "CEO"}, {"is_active": False},
    {"project_ids": []}, {"org_id": None}])
async def test_new_preview_denies_unqualified_inactive_and_unscoped_actors(stored, actor_change):
    from domain.services.performance_service import PerformanceService
    from fastapi import HTTPException
    await stored.users.update_one({"employee_id": "L"}, {"$set": actor_change})
    with pytest.raises(HTTPException) as error:
        await PerformanceService.inspect_evidence(request(), {"employee_id": "L", "is_admin": True})
    assert error.value.status_code == 403
