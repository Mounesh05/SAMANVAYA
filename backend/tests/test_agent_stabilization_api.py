"""Existing /ai/invoke schema and failed-run persistence, not F01/F02 fixes."""

from unittest.mock import AsyncMock, Mock
import json

import httpx
import pytest
from fastapi import FastAPI

from api.routes import ai
from core import database
from core.dependencies import get_current_user
from test_agent_stabilization import TASKS, response

pytestmark = pytest.mark.anyio
RESPONSE_KEYS = {"run_id", "task_type", "analysis", "recommendations", "risk_level", "confidence",
                 "agent_history", "errors", "execution_time_ms"}


@pytest.fixture
async def endpoint(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    monkeypatch.setattr(ai, "get_accessible_project_ids", AsyncMock(return_value=["P1"]))
    monkeypatch.setattr(ai, "check_ollama_connection", lambda: True)
    actor = {"employee_id": "SYNTHETIC", "email": "synthetic@example.invalid", "role": "CEO", "org_id": "O1"}
    app = FastAPI()
    app.include_router(ai.router, prefix="/api/ai")
    app.dependency_overrides[get_current_user] = lambda: actor
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client, mock_db, actor


@pytest.mark.parametrize("task", TASKS)
@pytest.mark.parametrize("save", [True, False])
async def test_six_tasks_preserve_success_response_and_optional_persistence(endpoint, monkeypatch, task, save):
    client, db, actor = endpoint
    if task == "hr_assistant":
        actor.update(role="HR", is_admin=True)
    llm = Mock()
    llm.invoke.return_value = json.dumps(response(task))
    monkeypatch.setattr(TASKS[task], "get_ollama_llm", lambda **kwargs: llm)
    result = await client.post("/api/ai/invoke", json={"task_type": task, "evidence": {}, "context": {"project_id": "P1"}, "save_run": save})
    assert result.status_code == 200
    body = result.json()
    assert set(body) == RESPONSE_KEYS and body["errors"] == [] and body["analysis"]
    assert len(body["agent_history"]) == 1 and body["task_type"] == task
    if save:
        saved = await db.ai_runs.find_one({"id": body["run_id"]})
        assert saved["status"] == "completed" and saved["error_message"] is None
        assert "verification_state" not in saved["output_data"]
    else:
        assert body["run_id"] is None and await db.ai_runs.count_documents({}) == 0


@pytest.mark.parametrize("task", TASKS)
@pytest.mark.parametrize("failure", ["malformed", "unsupported", "forged-state", "outage", "timeout"])
async def test_invalid_or_unavailable_models_persist_failed_not_completed(endpoint, monkeypatch, task, failure):
    client, db, actor = endpoint
    if task == "hr_assistant":
        actor.update(role="HR", is_admin=True)
    llm = Mock()
    if failure == "timeout":
        llm.invoke.side_effect = httpx.ReadTimeout("SYNTHETIC_PRIVATE_LOG")
    elif failure == "outage":
        llm.invoke.side_effect = ConnectionError("SYNTHETIC_PRIVATE_LOG")
    else:
        llm.invoke.return_value = {"malformed": "not json", "unsupported": {"analysis": "not text"},
            "forged-state": json.dumps({**response(task), "verification_state": "VERIFIED"})}[failure]
    monkeypatch.setattr(TASKS[task], "get_ollama_llm", lambda **kwargs: llm)
    result = await client.post("/api/ai/invoke", json={"task_type": task, "evidence": {}, "save_run": True})
    assert result.status_code == 200  # Existing errors-in-body public contract.
    body = result.json()
    assert set(body) == RESPONSE_KEYS and body["errors"] and body["analysis"] is None
    expected = {"timeout": "MODEL_TIMEOUT", "outage": "MODEL_UNAVAILABLE"}.get(failure, "INVALID_MODEL_RESPONSE")
    assert expected in body["errors"][0]
    assert body["confidence"] is None and "SYNTHETIC_PRIVATE_LOG" not in result.text
    saved = await db.ai_runs.find_one({"id": body["run_id"]})
    assert saved["status"] == "failed" and saved["error_message"]
    assert saved["output_data"]["analysis"] is None and saved["output_data"]["confidence"] is None
    assert "verification_state" not in saved["output_data"]


async def test_existing_permission_validation_and_model_health_statuses(endpoint, monkeypatch):
    client, db, actor = endpoint
    body = {"task_type": "qa_analysis", "evidence": {}}
    actor["role"] = "DEVELOPER"
    result = await client.post("/api/ai/invoke", json=body)
    assert result.status_code == 403 and result.json() == {"detail": "Insufficient permissions"}
    actor["role"] = "CEO"
    monkeypatch.setattr(ai, "check_ollama_connection", lambda: False)
    assert (await client.post("/api/ai/invoke", json=body)).status_code == 503
    assert (await client.post("/api/ai/invoke", json={**body, "task_type": "unsupported"})).status_code == 422
    assert await db.ai_runs.count_documents({}) == 0
