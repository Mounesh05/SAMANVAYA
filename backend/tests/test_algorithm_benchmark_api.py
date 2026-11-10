"""Standalone router contracts: no application startup, Docker, or host source execution."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

from api.routes import algorithms
from core.dependencies import get_current_user
from domain.schemas.algorithm_benchmark import BenchmarkFeedback, BenchmarkRequest
from domain.services.algorithm_benchmark_service import AlgorithmBenchmarkService
from intelligence.algorithms.runner import BenchmarkUnavailable, DockerBenchmarkRunner

pytestmark = pytest.mark.anyio


@pytest.fixture
def body():
    return {"project_id": "P1", "language": "python",
            "candidates": [{"name": name, "source": "PRIVATE SOURCE " + name, "entrypoint": "sort"}
                           for name in ("fast", "slow")],
            "sizes": [0, 10], "distributions": ["random"], "repetitions": 2}


@pytest.fixture
async def api(mock_db, monkeypatch):
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(
        side_effect=AssertionError("No Docker or source execution permitted")))
    runner = DockerBenchmarkRunner()
    monkeypatch.setattr(runner, "run", AsyncMock(side_effect=BenchmarkUnavailable("Worker image missing")))
    monkeypatch.setattr(runner, "availability", AsyncMock(return_value={
        "available": False, "environment": {}, "error": "Worker image missing"}))
    service = AlgorithmBenchmarkService(mock_db.algorithm_benchmark_runs, runner)
    monkeypatch.setattr(algorithms, "service", service)
    monkeypatch.setattr(algorithms.settings, "ALGORITHM_BENCHMARK_ENABLED", True)
    projects = {"P1": {"id": "P1", "org_id": "O1"},
                "unassigned": {"id": "unassigned", "org_id": "O1"},
                "foreign": {"id": "foreign", "org_id": "O2"}}
    lookup = AsyncMock(side_effect=lambda project_id: projects.get(project_id))
    # Both route-level existence/org checks and the shared assignment helper remain real.
    monkeypatch.setattr(algorithms.ProjectRepository, "find_by_id", lookup)
    user = {"employee_id": "E1", "role": "DEVELOPER", "org_id": "O1", "project_ids": ["P1"]}
    app = FastAPI()
    app.include_router(algorithms.router, prefix="/algorithms")
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield SimpleNamespace(client=client, app=app, user=user, service=service, lookup=lookup)


async def seed_run(api, body, status="completed"):
    created = await api.service.create(BenchmarkRequest.model_validate(body).model_dump(), api.user)
    await api.service._finish(created["run_id"], {
        "status": status,
        "recommendation": {"status": "recommended", "winner": "fast", "reason": "Measured advantage",
                           "rankings": [], "limitations": []} if status == "completed" else None,
    })
    return created["run_id"]


async def test_developer_start_background_execution_get_and_history_contract(api, body):
    response = await api.client.post("/algorithms/runs", json=body)
    assert response.status_code == 202, response.text
    started = response.json()
    assert set(started) == {"run_id", "status"} and started["status"] == "pending"
    api.service.runner.run.assert_awaited_once_with(BenchmarkRequest.model_validate(body).model_dump())
    response = await api.client.get(f"/algorithms/runs/{started['run_id']}")
    assert response.status_code == 200, response.text
    run = response.json()
    assert run["status"] == "unavailable" and run["error"] == "Worker image missing"
    assert run["run_id"] == started["run_id"] and run["project_id"] == "P1"
    assert run["request"]["objective"] == "time" and run["request"]["seed"] == 42
    assert run["request"]["repetitions"] == 2
    assert run["results"] == [] and run["recommendation"] is None
    assert run["historical_evidence"] == [] and run["environment"] == {} and run["tools"] == {}
    assert run["created_at"] and run["completed_at"] and "_id" not in run
    response = await api.client.get("/algorithms/projects/P1/history?limit=1")
    assert response.status_code == 200, response.text
    history = response.json()
    assert set(history) == {"history"} and len(history["history"]) == 1
    assert history["history"][0]["run_id"] == started["run_id"]
    assert "PRIVATE SOURCE" not in response.text
    assert all("source" not in c for c in history["history"][0]["request"]["candidates"])


@pytest.mark.parametrize("role", ["DEVELOPER", "LEAD", "PM", "CEO", "QA", "DEVOPS", "developer"])
async def test_engineering_roles_can_submit(api, body, role):
    api.user["role"] = role
    assert (await api.client.post("/algorithms/runs", json=body)).status_code == 202


async def test_org_role_fallback_and_admin_can_submit(api, body):
    del api.user["role"]
    api.user["organizational_role"] = "DEVELOPER"
    assert (await api.client.post("/algorithms/runs", json=body)).status_code == 202
    api.user.update(role="HR", is_admin=True)
    assert (await api.client.post("/algorithms/runs", json=body)).status_code == 202


@pytest.mark.parametrize("endpoint", ["start", "feedback", "explanation"])
async def test_hr_cannot_mutate_engineering_evidence(api, body, endpoint):
    run_id = await seed_run(api, body)
    api.user["role"] = "HR"
    path, payload = {
        "start": ("/algorithms/runs", body),
        "feedback": (f"/algorithms/runs/{run_id}/feedback", {"decision": "accepted", "reason": "Useful"}),
        "explanation": (f"/algorithms/runs/{run_id}/explanation", None),
    }[endpoint]
    response = await api.client.post(path, json=payload)
    assert response.status_code == 403 and "Engineering" in response.json()["detail"]
    api.service.runner.run.assert_not_awaited()
    assert "feedback" not in await api.service.get(run_id)


@pytest.mark.parametrize("method,path", [
    ("GET", "/algorithms/availability"), ("POST", "/algorithms/runs"),
    ("GET", "/algorithms/runs/missing"), ("GET", "/algorithms/projects/P1/history"),
    ("POST", "/algorithms/runs/missing/feedback"), ("POST", "/algorithms/runs/missing/explanation"),
])
async def test_all_endpoints_require_authenticated_dependency(api, body, method, path):
    async def unauthenticated():
        raise HTTPException(status_code=401, detail="Authentication required")

    api.app.dependency_overrides[get_current_user] = unauthenticated
    payload = {"decision": "accepted", "reason": "Useful"} if path.endswith("feedback") else body
    response = await api.client.request(method, path, json=payload)
    assert response.status_code == 401
    assert await api.service.collection.count_documents({}) == 0
    api.lookup.assert_not_awaited()


@pytest.mark.parametrize("project_id,status,detail", [
    ("unassigned", 403, "don't have access"), ("missing", 404, "Project not found"),
    ("foreign", 403, "different organization"),
])
@pytest.mark.parametrize("endpoint", ["start", "history", "get", "feedback", "explanation"])
async def test_project_authorization_on_all_evidence_paths(api, body, project_id, status, detail, endpoint):
    foreign_body = {**body, "project_id": project_id}
    if endpoint in {"get", "feedback", "explanation"}:
        run_id = await seed_run(api, foreign_body)
        path = f"/algorithms/runs/{run_id}" + ("" if endpoint == "get" else "/" + endpoint)
        method = "GET" if endpoint == "get" else "POST"
        payload = {"decision": "accepted", "reason": "Useful"} if endpoint == "feedback" else None
    elif endpoint == "start":
        method, path, payload = "POST", "/algorithms/runs", foreign_body
    else:
        method, path, payload = "GET", f"/algorithms/projects/{project_id}/history", None
    response = await api.client.request(method, path, json=payload)
    assert response.status_code == status, response.text
    assert detail in response.json()["detail"]
    assert "PRIVATE SOURCE" not in response.text
    api.service.runner.run.assert_not_awaited()


@pytest.mark.parametrize("role,project_id,status", [("CEO", "missing", 404), ("PM", "foreign", 403)])
async def test_privileged_roles_do_not_bypass_existence_or_org(api, body, role, project_id, status):
    api.user["role"] = role
    response = await api.client.post("/algorithms/runs", json={**body, "project_id": project_id})
    assert response.status_code == status


@pytest.mark.parametrize("role", ["PM", "CEO", "DEVELOPER"])
@pytest.mark.parametrize("org_id", [None, "", "missing"])
@pytest.mark.parametrize("endpoint", ["start", "history", "get", "feedback", "explanation"])
async def test_missing_user_org_cannot_access_tenant_evidence(api, body, role, org_id, endpoint):
    run_id = await seed_run(api, body)
    api.user["role"] = role
    if org_id == "missing":
        api.user.pop("org_id")
    else:
        api.user["org_id"] = org_id
    if endpoint == "start":
        method, path, payload = "POST", "/algorithms/runs", body
    elif endpoint == "history":
        method, path, payload = "GET", "/algorithms/projects/P1/history", None
    else:
        method = "GET" if endpoint == "get" else "POST"
        path = f"/algorithms/runs/{run_id}" + ("" if endpoint == "get" else "/" + endpoint)
        payload = {"decision": "accepted", "reason": "Useful"} if endpoint == "feedback" else None
    response = await api.client.request(method, path, json=payload)
    assert response.status_code == 403
    assert "PRIVATE SOURCE" not in response.text
    api.service.runner.run.assert_not_awaited()


@pytest.mark.parametrize("user_org", ["O1", None])
async def test_missing_project_org_fails_closed(api, body, user_org):
    api.lookup.side_effect = lambda project_id: {"id": project_id}
    api.user.update(role="CEO", org_id=user_org)
    assert (await api.client.post("/algorithms/runs", json=body)).status_code == 403
    assert (await api.client.get("/algorithms/projects/P1/history")).status_code == 403
    api.service.runner.run.assert_not_awaited()


@pytest.mark.parametrize("role", [None, 123, [], {}])
async def test_malformed_role_is_not_a_server_error(api, body, role):
    api.user["role"] = role
    assert (await api.client.post("/algorithms/runs", json=body)).status_code == 403
    assert (await api.client.get("/algorithms/projects/P1/history")).status_code == 200


@pytest.mark.parametrize("identity", [None, "", 123])
async def test_mutations_require_a_stable_authenticated_identity(api, body, identity):
    api.user["employee_id"] = identity
    assert (await api.client.post("/algorithms/runs", json=body)).status_code == 403
    api.service.runner.run.assert_not_awaited()


@pytest.mark.parametrize("language", ["python", "javascript", "typescript"])
async def test_all_supported_languages_submit_canonical_async_contract(api, body, language):
    body["language"] = language
    api.user.update(employee_id=None, sub="E1")
    response = await api.client.post("/algorithms/runs", json=body)
    assert response.status_code == 202
    api.service.runner.run.assert_awaited_once_with(BenchmarkRequest.model_validate(body).model_dump())
    saved = await api.service.get(response.json()["run_id"])
    assert saved["triggered_by"] == "E1"


@pytest.mark.parametrize("suffix", ["", "/feedback", "/explanation"])
async def test_missing_run_returns_404(api, suffix):
    path = "/algorithms/runs/missing" + suffix
    response = (await api.client.post(path, json={"decision": "accepted", "reason": "Useful"})
                if suffix else await api.client.get(path))
    assert response.status_code == 404 and response.json()["detail"] == "Benchmark run not found"


@pytest.mark.parametrize("status", ["pending", "running", "failed", "unavailable"])
@pytest.mark.parametrize("endpoint", ["feedback", "explanation"])
async def test_unfinished_run_rejects_feedback_and_explanation(api, body, status, endpoint):
    run_id = await seed_run(api, body, status)
    response = await api.client.post(f"/algorithms/runs/{run_id}/{endpoint}",
                                     json={"decision": "accepted", "reason": "Useful"})
    assert response.status_code == 409


async def test_feedback_and_explanation_return_frontend_contract(api, body, monkeypatch):
    run_id = await seed_run(api, body)
    response = await api.client.post(f"/algorithms/runs/{run_id}/feedback",
                                     json={"decision": "accepted", "reason": "  Useful evidence  "})
    assert response.status_code == 200, response.text
    saved = response.json()
    assert set(saved) == {"decision", "reason", "employee_id", "created_at"}
    assert saved["decision"] == "accepted" and saved["reason"] == "Useful evidence"
    assert saved["employee_id"] == "E1" and saved["created_at"]
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
            "response": '{"statement_ids": ["current"]}'})), **kwargs))
    response = await api.client.post(f"/algorithms/runs/{run_id}/explanation")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "generated", "error": None,
                               "explanation": f"[{run_id}] Recommendation: fast. Measured advantage",
                               "citations": [run_id]}


@pytest.mark.parametrize("payload", [
    {"decision": "maybe", "reason": "Useful"}, {"decision": "accepted", "reason": "   "},
    {"decision": "accepted", "reason": "x" * 2001}, {"decision": "accepted"},
    {"decision": "accepted", "reason": "Useful", "employee_id": "spoofed"},
])
async def test_invalid_feedback_is_rejected(api, body, payload):
    run_id = await seed_run(api, body)
    with pytest.raises(ValidationError):
        BenchmarkFeedback.model_validate(payload)
    response = await api.client.post(f"/algorithms/runs/{run_id}/feedback", json=payload)
    assert response.status_code == 422
    assert "feedback" not in await api.service.get(run_id)


@pytest.mark.parametrize("key,value", [
    ("project_id", " "), ("project_id", "x" * 201), ("language", "shell"),
    ("candidates", []), ("candidates", [{"name": "only", "source": "x", "entrypoint": "sort"}]),
    ("sizes", []), ("sizes", [True]), ("sizes", ["10"]), ("sizes", [1.5]),
    ("sizes", [-1]), ("sizes", [10001]), ("sizes", [10, 10]), ("sizes", list(range(17))),
    ("distributions", []), ("distributions", ["unknown"]), ("distributions", ["random", "random"]),
    ("repetitions", 0), ("repetitions", 11), ("repetitions", True), ("repetitions", "2"),
    ("seed", -1), ("seed", 2**32), ("seed", True), ("objective", "energy"),
    ("memory_limit_bytes", 0), ("memory_limit_bytes", 536870913), ("memory_limit_bytes", True),
    ("memory_limit_bytes", "100"), ("image", "untrusted:latest"),
])
async def test_request_schema_and_api_reject_invalid_bounds(api, body, key, value):
    payload = {**body, key: value}
    with pytest.raises(ValidationError):
        BenchmarkRequest.model_validate(payload)
    response = await api.client.post("/algorithms/runs", json=payload)
    assert response.status_code == 422
    assert await api.service.collection.count_documents({}) == 0
    api.service.runner.run.assert_not_awaited()


@pytest.mark.parametrize("field,value", [
    ("source", ""), ("source", " \n\t"), ("source", "x" * 200001), ("source", "é" * 100001),
    ("name", "  "), ("name", "x" * 201), ("name", "bad\x00key"), ("entrypoint", "sort();evil()"),
    ("entrypoint", "class"), ("entrypoint", "$sort"), ("entrypoint", "x" * 129),
    ("image", "untrusted:latest"),
], ids=["empty-source", "blank-source", "long-source", "utf8-source", "blank-name",
        "long-name", "nul-name", "expression-entrypoint", "keyword-entrypoint", "python-dollar",
        "long-entrypoint", "custom-image"])
async def test_invalid_sources_and_candidate_contract(api, body, field, value):
    body["candidates"][0][field] = value
    with pytest.raises(ValidationError):
        BenchmarkRequest.model_validate(body)
    assert (await api.client.post("/algorithms/runs", json=body)).status_code == 422
    api.service.runner.run.assert_not_awaited()


def test_candidate_name_must_be_valid_utf8(body):
    body["candidates"][0]["name"] = "bad\ud800key"
    with pytest.raises(ValidationError):
        BenchmarkRequest.model_validate(body)


@pytest.mark.parametrize("mutation", ["duplicates", "too-many"])
async def test_candidate_names_unique_and_count_bounded(api, body, mutation):
    if mutation == "duplicates":
        body["candidates"][1]["name"] = " fast "
    else:
        body["candidates"] = [{**body["candidates"][0], "name": str(i)} for i in range(6)]
    assert (await api.client.post("/algorithms/runs", json=body)).status_code == 422


@pytest.mark.parametrize("language", ["javascript", "typescript"])
@pytest.mark.parametrize("constraint", [{"objective": "memory"}, {"memory_limit_bytes": 100}])
async def test_node_peak_memory_constraints_unsupported(api, body, language, constraint):
    payload = {**body, "language": language, **constraint}
    with pytest.raises(ValidationError, match="Node heap delta"):
        BenchmarkRequest.model_validate(payload)
    assert (await api.client.post("/algorithms/runs", json=payload)).status_code == 422


@pytest.mark.parametrize("language", ["python", "javascript", "typescript"])
def test_valid_boundary_contract_and_defaults(body, language):
    body.update(language=language, project_id=" P1 ", sizes=[0, 10000], repetitions=10, seed=2**32 - 1)
    body["candidates"][0].update(name=" fast ", source="é" * 100000)
    if language == "python":
        body.update(objective="memory", memory_limit_bytes=536870912)
    else:
        body["candidates"][0]["entrypoint"] = "$sort"
    parsed = BenchmarkRequest.model_validate(body)
    assert parsed.project_id == "P1" and parsed.candidates[0].name == "fast"
    defaults = BenchmarkRequest.model_validate({key: body[key] for key in ("project_id", "language", "candidates")})
    assert defaults.sizes == [100, 1000] and defaults.repetitions == 5 and defaults.seed == 42
    assert defaults.distributions == ["random", "sorted", "reversed", "duplicates"]
    assert defaults.objective == "time" and defaults.memory_limit_bytes is None


async def test_disabled_feature_is_503_and_does_not_probe_worker(api, body, monkeypatch):
    monkeypatch.setattr(algorithms.settings, "ALGORITHM_BENCHMARK_ENABLED", False)
    response = await api.client.post("/algorithms/runs", json=body)
    assert response.status_code == 503 and "disabled" in response.json()["detail"]
    availability = await api.client.get("/algorithms/availability")
    assert availability.status_code == 200
    assert availability.json()["available"] is False and availability.json()["environment"] == {}
    assert "disabled" in availability.json()["error"]
    api.service.runner.availability.assert_not_awaited()
    api.service.runner.run.assert_not_awaited()
    assert await api.service.collection.count_documents({}) == 0
    assert (await api.client.get("/algorithms/projects/P1/history")).json() == {"history": []}


async def test_enabled_availability_false_is_an_explicit_flag(api):
    response = await api.client.get("/algorithms/availability")
    assert response.status_code == 200
    assert response.json() == {"available": False, "environment": {}, "error": "Worker image missing"}
    api.service.runner.availability.assert_awaited_once_with()
    api.service.runner.run.assert_not_awaited()


async def test_active_project_conflict_is_409_without_execution(api, body):
    await api.service.create(BenchmarkRequest.model_validate(body).model_dump(), api.user)
    response = await api.client.post("/algorithms/runs", json=body)
    assert response.status_code == 409 and "active benchmark" in response.json()["detail"]
    api.service.runner.run.assert_not_awaited()


@pytest.mark.parametrize("limit", ["0", "51", "-1", "1.5", "not-an-integer"])
async def test_history_limit_validation(api, limit):
    response = await api.client.get(f"/algorithms/projects/P1/history?limit={limit}")
    assert response.status_code == 422


@pytest.mark.parametrize("limit", [1, 50])
async def test_history_limit_boundaries(api, limit):
    response = await api.client.get(f"/algorithms/projects/P1/history?limit={limit}")
    assert response.status_code == 200 and response.json() == {"history": []}
