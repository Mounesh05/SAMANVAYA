"""Legacy API values remain legacy; read metadata cannot approve or backfill them."""

import copy
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import FastAPI

from api.routes import performance as routes
from core import audit, database
from core.dependencies import get_current_user
from domain.models.developer_performance import AIEvaluation, DeveloperPerformance, PerformanceBreakdown, RoleEvaluation
from domain.models.hr_performance import HRAssessmentCreate, HRAssessmentDimensionItem, HRDimensionKey
from domain.services.hr_performance_service import HRPerformanceService
from domain.schemas.hr_views import PerformanceOutcomeHR
from domain.services.performance_service import PerformanceService
from repositories.performance_repository import PerformanceRepository

pytestmark = pytest.mark.anyio


def assessment():
    return DeveloperPerformance(developer_id="AUDIT-DEV", developer_name="Synthetic employee", project_id="AUDIT-PROJECT",
        period_type="quarter", period_start=datetime(2026, 7, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 10, 1, tzinfo=timezone.utc), period_label="2026-Q3",
        ai_evaluation=AIEvaluation(score=77.4, breakdown=PerformanceBreakdown(
            code_quality=0, delivery=0, collaboration=0, reliability=0, engineering_impact=0, engineering_judgment=0),
            reasoning="Synthetic legacy fixture", confidence="low"),
        role_evaluation=RoleEvaluation(), final_score=85.4, grade="B+", confidence_level="low", confidence_reason="Fixture")


def hr_data():
    return HRAssessmentCreate(dimensions={key.value: HRAssessmentDimensionItem(
        dimension=key.value, rating=4 if index == 0 else 3) for index, key in enumerate(HRDimensionKey)})


def assert_legacy_metadata(value):
    assert value["mode"] == "LEGACY_READ_ONLY" and value["status"] == "LEGACY_UNVERIFIABLE"
    assert value["engineering_score"] is None and value["human_score"] is None and value["combined_score"] is None
    assert value["approved_score"] is None and value["is_finalizable"] is False
    assert value["snapshot"] is None and value["policy"] is None and value["rubric"] is None
    assert value["coverage"]["engineering_percent"] is None
    assert value["coverage"]["human_completeness"] == "UNKNOWN"


def test_old_model_values_are_preserved_and_missing_methodology_stays_unknown():
    record = assessment().model_dump()
    record.pop("scoring", None)
    loaded = DeveloperPerformance(**record)
    serialized = loaded.model_dump(mode="json")
    assert serialized["final_score"] == 85.4 and serialized["ai_evaluation"]["score"] == 77.4
    assert serialized["grade"] == "B+"
    assert_legacy_metadata(serialized["scoring"])
    assert serialized["scoring"]["legacy_methodology_version"] is None
    assert serialized["scoring"]["source_units"]["ai_evaluation_score"] == "LEGACY_AI_0_90"


def test_input_scoring_claims_do_not_promote_a_legacy_record():
    record = assessment().model_dump()
    record["scoring"] = {"status": "APPROVED", "combined_score": 100, "is_finalizable": True}
    loaded = DeveloperPerformance(**record)
    assert loaded.final_score == 85.4
    assert_legacy_metadata(loaded.model_dump(mode="json")["scoring"])


def test_hr_serializer_preserves_values_and_excludes_raw_evidence():
    record = assessment().model_dump()
    record["raw_evidence"] = {"private": "not for this response"}
    view = PerformanceOutcomeHR.from_performance(record).model_dump(mode="json")
    assert view["overall_score"] == 85.4 and view["ai_score_summary"] == 77.4
    assert "raw_evidence" not in view
    assert_legacy_metadata(view["scoring"])


@pytest.fixture
async def stored(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    monkeypatch.setattr(audit.audit_logger, "collection", mock_db.audit_logs)
    await mock_db.users.insert_one({"employee_id": "AUDIT-DEV", "role": "DEVELOPER", "team_id": "T1", "org_id": "O1"})
    # Emulate an old stored document, not a reserialized new model.
    record = assessment().model_dump()
    record.pop("scoring", None)
    record["contribution_credit"] = {"methodology_version": "contribution-v2-hybrid", "score": 85.4,
        "confidence": "low", "components": {}, "evidence_counts": {}, "missing_evidence": []}
    await mock_db.developer_performances.insert_one(record)
    return mock_db


async def test_reads_annotate_legacy_data_without_writing_a_backfill(stored):
    before = await stored.developer_performances.find_one({})
    service = PerformanceService()
    result = await service.get_developer_performance("AUDIT-DEV")
    assert result.scoring.legacy_methodology_version == "contribution-v2-hybrid"
    assert_legacy_metadata(result.model_dump(mode="json")["scoring"])
    assert_legacy_metadata((await service.get_performance_trend("AUDIT-DEV"))[0]["scoring"])
    assert_legacy_metadata((await service.get_team_performance("AUDIT-PROJECT", "2026-Q3"))[0]["scoring"])
    after = await stored.developer_performances.find_one({})
    assert after == before and "scoring" not in after


@pytest.mark.parametrize("role", ["DEVELOPER", "HR"])
async def test_legacy_detail_dashboard_and_trend_api_contracts(stored, role):
    user = {"employee_id": "AUDIT-DEV" if role == "DEVELOPER" else "HR-1", "role": role,
            "designation": "HR_MANAGER" if role == "HR" else None, "is_admin": False, "org_id": "O1"}
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/performance")
    app.dependency_overrides[get_current_user] = lambda: user
    before = copy.deepcopy(await stored.developer_performances.find_one({}))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        detailed = await client.get("/api/performance/developer/AUDIT-DEV")
        assert detailed.status_code == 200
        assert_legacy_metadata(detailed.json()["scoring"])
        dashboard = await client.get("/api/performance/dashboard/AUDIT-DEV")
        assert dashboard.status_code == 200
        current = dashboard.json()["current_performance"]
        assert current["overall_score"] == 85.4
        assert_legacy_metadata(current["scoring"])
        assert_legacy_metadata(dashboard.json()["historical_trend"][0]["scoring"])
        trend = await client.get("/api/performance/developer/AUDIT-DEV/trend")
        assert trend.status_code == 200 and trend.json()["current_score"] == 85.4
        assert_legacy_metadata(trend.json()["history"][0]["scoring"])
    assert await stored.developer_performances.find_one({}) == before


async def test_team_api_keeps_legacy_values_and_metadata(stored):
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/performance")
    app.dependency_overrides[get_current_user] = lambda: {"employee_id": "HR-1", "role": "HR", "org_id": "O1"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/performance/team/AUDIT-PROJECT/2026-Q3")
    assert response.status_code == 200
    row = response.json()[0]
    assert row["overall_score"] == 85.4
    assert_legacy_metadata(row["scoring"])
    assert row["scoring"]["legacy_methodology_version"] == "contribution-v2-hybrid"


async def test_read_only_metadata_is_not_persisted_on_legacy_writes(stored):
    model = assessment()
    assert "scoring" in model.model_dump()
    repository = PerformanceRepository()
    created = await repository.create(model.model_dump())
    assert "scoring" not in await repository.get_by_id(created)
    await repository.update(created, model.model_dump())
    assert "scoring" not in await repository.get_by_id(created)


async def test_hr_submission_preserves_historical_values_without_recalculation(stored):
    from domain.services.performance_human_service import HumanScoringPending
    before = await stored.developer_performances.find_one({})
    with pytest.raises(HumanScoringPending):
        await HRPerformanceService().submit_hr_assessment("AUDIT-DEV", hr_data(), {"employee_id": "HR-1", "role": "HR"})
    assert await stored.developer_performances.find_one({}) == before
    assert_legacy_metadata(DeveloperPerformance(**before).model_dump(mode="json")["scoring"])
