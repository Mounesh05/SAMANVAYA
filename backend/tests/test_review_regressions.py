"""Exercise previously untested HR and seed migration branches."""

import pytest
from core import database
from domain.models.hr_performance import HRAssessmentCreate, HRAssessmentDimensionItem
from domain.services.hr_performance_service import HRPerformanceService
from migrations.seed_risk_configurations import seed_example_project_configs

pytestmark = pytest.mark.anyio


@pytest.fixture
async def store(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    await mock_db.users.insert_one({"employee_id": "REVIEW-DEV", "role": "DEVELOPER", "name": "Developer"})
    return mock_db


async def test_first_hr_assessment_cannot_fabricate_engineering_evaluation(store):
    from domain.services.performance_human_service import HumanScoringPending
    with pytest.raises(HumanScoringPending):
        await HRPerformanceService().submit_hr_assessment("REVIEW-DEV", HRAssessmentCreate(
            dimensions={"professional_conduct": HRAssessmentDimensionItem(dimension="professional_conduct", rating=3)}
        ), {"employee_id": "REVIEW-HR", "role": "HR", "name": "Evaluator"})
    assert await store.developer_performances.count_documents({}) == 0
    assert await store.hr_assessments.count_documents({}) == 0


async def test_completeness_before_first_performance_does_not_invent_required_roles(store):
    result = await HRPerformanceService().check_human_evaluation_completeness("REVIEW-DEV")
    assert result.is_complete is False and result.human_score is None
    assert result.pending_roles == [] and result.required_roles == []
    assert result.details["status"] == "POLICY_PENDING"
    assert await store.developer_performances.count_documents({}) == 0


async def test_example_risk_seed_creates_valid_configurations(store, capsys):
    assert await seed_example_project_configs()
    configs = await store.risk_configurations.find({}).to_list(None)
    assert len(configs) == 2
    assert all(c["base_risk"] == 10.0 for c in configs)
    assert not await seed_example_project_configs()


async def test_lifespan_starts_recovery_and_preserves_departments(store, monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    import main
    from api.routes import webhooks
    from domain.services.hitl_workflow_service import hitl_service
    from intelligence.baselines.repository_baseline import RepositoryBaseline
    from test_webhook_recovery import processor, event
    monkeypatch.setattr(RepositoryBaseline, "ensure_index", AsyncMock())
    monkeypatch.setattr(hitl_service, "_ensure_indexes", AsyncMock())
    await store.users.insert_one({"employee_id": "CEO", "role": "CEO", "dept": "Custom department"})
    await event(store)
    worker = processor(store, AsyncMock(return_value={}))
    monkeypatch.setattr(webhooks, "event_processor", worker)
    async with main.lifespan(main.app):
        for _ in range(100):
            saved = await worker.event_repo.find_by_id("WH-1")
            if saved["status"] == "completed":
                break
            await asyncio.sleep(0.01)
        assert saved["status"] == "completed"
        assert (await store.users.find_one({"employee_id": "CEO"}))["dept"] == "Custom department"
    assert worker._recovery_task.done()
