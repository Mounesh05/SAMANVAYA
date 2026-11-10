"""Real in-memory Mongo/evidence tests; candidate execution is always mocked."""

import asyncio
import copy
import json
from datetime import timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
from pymongo.errors import DuplicateKeyError

from domain.schemas.algorithm_benchmark import BenchmarkRequest
from domain.services import algorithm_benchmark_service as module
from intelligence.algorithms.runner import BenchmarkFailure, BenchmarkUnavailable, DockerBenchmarkRunner

pytestmark = pytest.mark.anyio
USER = {"employee_id": "E1"}


@pytest.fixture
def request_body():
    return BenchmarkRequest.model_validate({
        "project_id": "P1", "language": "python",
        "candidates": [{"name": name, "source": "PRIVATE SOURCE " + name, "entrypoint": "sort"}
                       for name in ("fast", "slow")],
        "sizes": [0, 10], "distributions": ["random", "duplicates"], "repetitions": 2,
    }).model_dump()


def evidence(body):
    return {
        "environment": {"images": {"python": "sha256:test"}, "cpus": 1,
                        "memory_limit_bytes": 536870912, "timing_method": "synthetic",
                        "workers": [{"runtime": "python-test", "platform": "test"}]},
        "tools": {"timing": "synthetic", "memory": "memray"},
        "results": [{"candidate": name, "error": None, "cases": [
            {"size": size, "distribution": distribution, "correct": True, "error": None,
             "timings_seconds": [seconds] * body["repetitions"], "memory_bytes": memory,
             "memory_metric": "memray_peak_tracked_allocations_bytes"}
            for size in body["sizes"] for distribution in body["distributions"]]}
            for name, seconds, memory in (("fast", 0.001, 200), ("slow", 0.002, 100))],
    }


@pytest.fixture
async def service(mock_db, monkeypatch, request_body):
    monkeypatch.setattr(module, "_ENGINE_SLOTS", asyncio.Semaphore(2))
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(
        side_effect=AssertionError("Tests must never launch Docker or execute source")))
    runner = DockerBenchmarkRunner()
    monkeypatch.setattr(runner, "run", AsyncMock(return_value=evidence(request_body)))
    return module.AlgorithmBenchmarkService(mock_db[module.COLLECTION], runner)


async def completed(service, body):
    created = await service.create(body, USER)
    await service.execute(created["run_id"])
    return await service.get(created["run_id"])


async def test_create_lease_indexes_and_partial_unique_exclusivity(service, request_body):
    before = module.utcnow()
    created = await service.create(request_body, USER)
    assert set(created) == {"run_id", "status"}
    assert created["status"] == "pending" and created["run_id"].startswith("ALG-")
    document = await service.get(created["run_id"])
    assert "_id" not in document
    assert document["active"] is True and document["triggered_by"] == "E1"
    from datetime import datetime
    assert before + timedelta(minutes=9) < datetime.fromisoformat(document["lease_expires_at"])
    assert datetime.fromisoformat(document["lease_expires_at"]) <= module.utcnow() + timedelta(minutes=10)
    assert document["source_hashes"] == {
        c["name"]: module.fingerprint(c["source"]) for c in request_body["candidates"]}
    indexes = await service.collection.index_information()
    assert indexes["run_id_1"]["unique"] is True
    partial = indexes["one_active_algorithm_job_per_project"]
    assert partial["unique"] is True and partial["partialFilterExpression"] == {"active": True}
    assert any(index["key"] == [("project_id", 1), ("workload_key", 1), ("created_at", -1)]
               for index in indexes.values())
    with pytest.raises(module.BenchmarkBusy, match="active benchmark"):
        await service.create(request_body, USER)
    # Verify mongomock actually enforces the partial index, not just its metadata.
    with pytest.raises(DuplicateKeyError):
        await service.collection.insert_one({"run_id": "duplicate-active", "project_id": "P1", "active": True})
    for run_id in ("inactive-1", "inactive-2"):
        await service.collection.insert_one({"run_id": run_id, "project_id": "P1", "active": False})
    other = await service.create({**request_body, "project_id": "P2"}, USER)
    assert other["run_id"] != created["run_id"]
    await service._finish(created["run_id"], {"status": "failed"})
    assert (await service.create(request_body, USER))["status"] == "pending"


async def test_index_initialization_is_serialized_and_retries_failure(service, monkeypatch):
    original = service.collection.create_index
    create_index = AsyncMock(wraps=original)
    monkeypatch.setattr(service.collection, "create_index", create_index)
    create_index.side_effect = RuntimeError("temporary index failure")
    with pytest.raises(RuntimeError, match="temporary index failure"):
        await service.ensure_indexes()
    assert service._indexes_ready is False
    create_index.side_effect = None
    await asyncio.gather(service.ensure_indexes(), service.ensure_indexes())
    assert create_index.await_count == 4  # One failed call plus three successful indexes.
    assert service._indexes_ready is True


async def test_execute_success_persists_real_recommendation_and_duplicate_delivery(service, request_body):
    created = await service.create(request_body, USER)

    async def run(body):
        running = await service.get(created["run_id"])
        assert running["status"] == "running" and running["active"] is True
        assert running["started_at"] and running["completed_at"] is None
        await service.execute(created["run_id"])
        return evidence(body)

    service.runner.run.side_effect = run
    await service.execute(created["run_id"])
    document = await service.get(created["run_id"])
    assert document["status"] == "completed" and document["active"] is False
    assert document["completed_at"] and document["error"] is None
    assert document["results"] == evidence(request_body)["results"]
    assert document["tools"] == evidence(request_body)["tools"]
    assert document["environment_key"] == module.environment_key(evidence(request_body))
    recommendation = document["recommendation"]
    assert recommendation["status"] == "recommended" and recommendation["winner"] == "fast"
    assert recommendation["rankings"][0]["timing_score_seconds"] == pytest.approx(0.001)
    assert recommendation["rankings"][0]["peak_memory_bytes"] == 200
    assert "Historical matches are context only" in " ".join(recommendation["limitations"])
    await service.execute(created["run_id"])
    await service.execute("missing")
    assert await service.get(created["run_id"]) == document
    service.runner.run.assert_awaited_once_with(request_body)
    json.dumps(document, allow_nan=False)


@pytest.mark.parametrize("failure,status,error", [
    (BenchmarkUnavailable("Missing local worker image"), "unavailable", "Missing local worker image"),
    (BenchmarkFailure("private worker details"), "failed", "Check worker logs"),
    (RuntimeError("private worker details"), "failed", "Check worker logs"),
    (asyncio.CancelledError(), "failed", "cancelled"),
])
async def test_execute_terminal_failures_release_lease(service, request_body, failure, status, error, caplog):
    created = await service.create(request_body, USER)
    service.runner.run.side_effect = failure
    if isinstance(failure, asyncio.CancelledError):
        with pytest.raises(asyncio.CancelledError):
            await service.execute(created["run_id"])
    else:
        await service.execute(created["run_id"])
    document = await service.get(created["run_id"])
    assert document["status"] == status and document["active"] is False
    assert error in document["error"] and "private worker details" not in document["error"]
    assert document["completed_at"] and document["recommendation"] is None
    assert document["results"] == []
    if isinstance(failure, (BenchmarkFailure, RuntimeError)) and not isinstance(failure, BenchmarkUnavailable):
        assert "Algorithm benchmark failed" in caplog.text
    await service.execute(created["run_id"])
    service.runner.run.assert_awaited_once()
    assert (await service.create(request_body, USER))["status"] == "pending"


async def test_cancel_while_queued_releases_lease(service, request_body, monkeypatch):
    created = await service.create(request_body, USER)
    monkeypatch.setattr(module, "_ENGINE_SLOTS", asyncio.Semaphore(0))
    task = asyncio.create_task(service.execute(created["run_id"]))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    document = await service.get(created["run_id"])
    assert document["status"] == "failed" and document["active"] is False
    assert "cancelled" in document["error"]
    service.runner.run.assert_not_awaited()


async def test_cancel_queued_duplicate_does_not_fail_running_owner(service, request_body, monkeypatch):
    created = await service.create(request_body, USER)
    entered, release = asyncio.Event(), asyncio.Event()
    monkeypatch.setattr(module, "_ENGINE_SLOTS", asyncio.Semaphore(1))

    async def run(body):
        entered.set()
        await release.wait()
        return evidence(body)

    service.runner.run.side_effect = run
    owner = asyncio.create_task(service.execute(created["run_id"]))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        duplicate = asyncio.create_task(service.execute(created["run_id"]))
        await asyncio.sleep(0)
        duplicate.cancel()
        with pytest.raises(asyncio.CancelledError):
            await duplicate
        saved = await service.get(created["run_id"])
        assert saved["status"] == "running" and saved["active"] is True
        assert saved["completed_at"] is None
    finally:
        release.set()
        await asyncio.wait_for(owner, 2)
    assert (await service.get(created["run_id"]))["status"] == "completed"
    service.runner.run.assert_awaited_once()


async def test_expired_running_job_cannot_be_resurrected_by_late_evidence(service, request_body, monkeypatch):
    created = await service.create(request_body, USER)
    now = module.utcnow()

    async def run(body):
        monkeypatch.setattr(module, "utcnow", lambda: now + timedelta(minutes=11))
        await service.expire_jobs()
        return evidence(body)

    service.runner.run.side_effect = run
    await service.execute(created["run_id"])
    saved = await service.get(created["run_id"])
    assert saved["status"] == "failed" and "lease expired" in saved["error"]
    assert saved["results"] == [] and saved["recommendation"] is None


async def test_runner_cannot_overwrite_job_identity_request_or_audit_metadata(service, request_body):
    created = await service.create(request_body, USER)
    forged = {**evidence(request_body), "run_id": "forged", "project_id": "P2",
              "request": {}, "triggered_by": "attacker", "created_at": "2099",
              "source_hashes": {}, "feedback": [{"decision": "accepted"}]}
    service.runner.run.return_value = forged
    await service.execute(created["run_id"])
    saved = await service.get(created["run_id"])
    assert saved["status"] == "completed"
    assert saved["run_id"] == created["run_id"] and saved["project_id"] == "P1"
    assert saved["request"] == request_body and saved["triggered_by"] == "E1"
    assert saved["created_at"] != "2099" and saved["source_hashes"]
    assert "feedback" not in saved


@pytest.mark.parametrize("measurement", [float("nan"), float("inf"), 2**63])
async def test_unserializable_evidence_fails_safely_and_releases_lease(service, request_body, measurement):
    raw = evidence(request_body)
    raw["results"][0]["cases"][0]["memory_bytes"] = measurement
    service.runner.run.return_value = raw
    created = await service.create(request_body, USER)
    await service.execute(created["run_id"])
    saved = await service.get(created["run_id"])
    assert saved["status"] == "failed" and saved["active"] is False
    assert saved["results"] == [] and saved["recommendation"] is None
    assert saved["completed_at"]
    assert (await service.create(request_body, USER))["status"] == "pending"


@pytest.mark.parametrize("reader", ["get", "history", "create", "execute"])
async def test_expired_lease_fails_without_replay(service, request_body, monkeypatch, reader):
    now = module.utcnow()
    created = await service.create(request_body, USER)
    monkeypatch.setattr(module, "utcnow", lambda: now + timedelta(minutes=11))
    if reader == "history":
        await service.history("P1")
    elif reader == "create":
        await service.create(request_body, USER)
    else:
        await getattr(service, reader)(created["run_id"])
    document = await service.get(created["run_id"])
    assert document["status"] == "failed" and document["active"] is False
    assert "lease expired" in document["error"] and document["completed_at"]
    service.runner.run.assert_not_awaited()


async def test_retrieval_scopes_completed_workload_and_history_redacts_sources(service, request_body):
    first = await completed(service, request_body)
    # Source/name are deliberately not part of the workload fingerprint.
    changed_source = copy.deepcopy(request_body)
    changed_source["candidates"][0]["source"] = "OTHER PRIVATE SOURCE"
    assert module.workload_key(changed_source) == first["workload_key"]
    for index in range(7):
        historical = {**copy.deepcopy(first), "run_id": f"old-{index}",
                      "created_at": f"2025-01-{index + 1:02d}T00:00:00+00:00"}
        if index == 6:
            historical["environment_key"] = "different-environment"
        await service.collection.insert_one(historical)
    for change in ({"project_id": "P2"}, {"workload_key": "other-workload"},
                   {"status": "failed"}, {"status": "running"}):
        await service.collection.insert_one({**copy.deepcopy(first), **change,
                                            "run_id": "excluded-" + next(iter(change)) + str(change),
                                            "created_at": "2099-01-01"})
    current = await completed(service, changed_source)
    rows = current["historical_evidence"]
    assert len(rows) == 5 and rows[0]["run_id"] == first["run_id"]
    assert {row["run_id"] for row in rows} == {first["run_id"], "old-6", "old-5", "old-4", "old-3"}
    assert rows[0]["environment_match"] is True and rows[1]["environment_match"] is False
    assert all(row["requires_fresh_benchmark"] and row["winner"] == "fast" for row in rows)
    assert all(set(row) == {"run_id", "created_at", "winner", "reason", "environment_match",
                            "requires_fresh_benchmark", "source_hashes", "feedback"} for row in rows)
    history = await service.history("P1", limit=50)
    assert all(row["project_id"] == "P1" and "_id" not in row for row in history)
    assert all("source" not in c for row in history for c in row["request"]["candidates"])
    assert "PRIVATE SOURCE" not in json.dumps([history, rows])
    assert len(await service.history("P1", limit=2)) == 2
    assert await service.history("missing") == []
    assert await service.get("missing") is None
    assert (await service.get(first["run_id"]))["request"] == request_body


async def test_retrieval_excludes_future_incomplete_and_other_protocol_evidence(service, request_body):
    prior = await completed(service, request_body)
    # Make chronology deterministic even on a low-resolution platform clock.
    now = module.utcnow()
    current = {**copy.deepcopy(prior), "run_id": "current",
               "created_at": (now + timedelta(seconds=1)).isoformat()}
    for index, change in enumerate([
        {"created_at": (now + timedelta(days=1)).isoformat()},
        {"completed_at": (now + timedelta(days=1)).isoformat()},
        {"completed_at": None}, {"protocol": "other-protocol"},
    ]):
        await service.collection.insert_one({**copy.deepcopy(prior), "run_id": f"excluded-{index}", **change})
    rows = await service.retrieve(current, prior["environment_key"])
    assert [item["run_id"] for item in rows] == [prior["run_id"]]
    assert rows[0]["requires_fresh_benchmark"] is True
    rows = await service.retrieve(current, None)
    assert rows[0]["environment_match"] is False


async def test_historical_winner_never_overrides_current_passing_evidence(service, request_body, monkeypatch):
    prior = await completed(service, request_body)
    now = module.utcnow()
    monkeypatch.setattr(module, "utcnow", lambda: now + timedelta(seconds=1))
    fresh = evidence(request_body)
    fresh["results"][0]["cases"][0].update(correct=False, error="Wrong output")
    service.runner.run.return_value = fresh
    current = await completed(service, request_body)
    assert current["historical_evidence"][0]["run_id"] == prior["run_id"]
    assert current["historical_evidence"][0]["winner"] == "fast"
    assert current["recommendation"]["winner"] == "slow"
    assert "No speed comparison" in current["recommendation"]["reason"]
    assert current["results"] == fresh["results"]


def test_workload_and_environment_fingerprints(request_body):
    reordered = {**request_body, "sizes": list(reversed(request_body["sizes"])),
                 "distributions": list(reversed(request_body["distributions"]))}
    assert module.workload_key(reordered) == module.workload_key(request_body)
    for key, value in {"language": "javascript", "seed": 99, "sizes": [1], "repetitions": 3,
                       "objective": "memory", "memory_limit_bytes": 100, "distributions": ["sorted"]}.items():
        assert module.workload_key({**request_body, key: value}) != module.workload_key(request_body)
    original = evidence(request_body)
    changed = copy.deepcopy(original)
    changed["environment"]["images"]["python"] = "sha256:new"
    assert module.environment_key(changed) != module.environment_key(original)


@pytest.mark.parametrize("change", ["docker", "isolation", "profiler", "worker-version", "tools"])
def test_environment_fingerprint_includes_reported_provenance(request_body, change):
    original = evidence(request_body)
    changed = copy.deepcopy(original)
    if change == "worker-version":
        changed["environment"]["workers"][0]["version"] = "different"
    elif change == "tools":
        changed["tools"]["memory"] = "different"
    else:
        changed["environment"][change] = "different"
    assert module.environment_key(changed) != module.environment_key(original)


def test_environment_fingerprint_ignores_only_candidate_labels_order_and_seed(request_body):
    original = evidence(request_body)
    original["environment"]["workers"][0]["candidate"] = "fast"
    changed = copy.deepcopy(original)
    worker = {**changed["environment"]["workers"][0], "candidate": "renamed"}
    changed["environment"]["workers"] = [worker, {**worker, "candidate": "other"}]
    changed["environment"]["seed"] = 99
    assert module.environment_key(changed) == module.environment_key(original)


@pytest.mark.parametrize("missing", ["images", "cpus", "memory_limit_bytes", "timing_method", "workers", "tools"])
def test_incomplete_provenance_has_no_environment_fingerprint(request_body, missing):
    raw = evidence(request_body)
    if missing == "tools":
        del raw[missing]
    else:
        del raw["environment"][missing]
    assert module.environment_key(raw) is None
    assert module.environment_key({}) is None


async def test_feedback_replaces_only_same_users_decision(service, request_body):
    document = await completed(service, request_body)
    await service.feedback(document, {"decision": "accepted", "reason": "Measured advantage"}, USER)
    await service.feedback(document, {"decision": "accepted", "reason": "Useful"}, {"sub": "E2"})
    latest = await service.feedback(document, {"decision": "rejected", "reason": "Need larger sizes"}, USER)
    assert set(latest) == {"decision", "reason", "employee_id", "created_at"}
    assert latest["decision"] == "rejected" and latest["employee_id"] == "E1"
    saved = await service.get(document["run_id"])
    assert len(saved["feedback"]) == 2
    assert {f["employee_id"] for f in saved["feedback"]} == {"E1", "E2"}
    assert next(f for f in saved["feedback"] if f["employee_id"] == "E1") == latest


async def test_concurrent_feedback_uses_one_atomic_literal_safe_update(service, request_body, monkeypatch):
    document = await completed(service, request_body)
    original = service.collection.update_one

    async def update(*args, **kwargs):
        result = await original(*args, **kwargs)
        await asyncio.sleep(0)  # Exposes a split pull/push implementation deterministically.
        return result

    spy = AsyncMock(side_effect=update)
    monkeypatch.setattr(service.collection, "update_one", spy)
    decisions = await asyncio.gather(*[
        service.feedback(document, {"decision": decision, "reason": "$feedback"},
                         {"employee_id": None, "sub": "$user"})
        for decision in ("accepted", "rejected")
    ])
    assert spy.await_count == 2
    assert all(isinstance(call.args[1], list) for call in spy.await_args_list)
    saved = await service.get(document["run_id"])
    assert saved["feedback"] == [decisions[-1]]
    assert saved["feedback"][0]["reason"] == "$feedback"
    assert saved["feedback"][0]["employee_id"] == "$user"


async def test_feedback_rejects_missing_identity_without_modifying_evidence(service, request_body):
    document = await completed(service, request_body)
    with pytest.raises(ValueError, match="identity"):
        await service.feedback(document, {"decision": "accepted", "reason": "Useful"}, {})
    assert "feedback" not in await service.get(document["run_id"])


@pytest.mark.parametrize("selection", [
    None, [], {}, {"statement_ids": []}, {"statement_ids": ["candidate-0"]},
    {"statement_ids": ["current", "invented"]}, {"statement_ids": ["current", "current"]},
    {"statement_ids": ["current", 1]}, {"statement_ids": ["current", {}]},
    {"statement_ids": ["current"] + [f"limit-{i}" for i in range(8)]},
    "invalid-json", "oversized", "missing-response", "model-unavailable", "connection-error",
    {"statement_ids": "current", "explanation": "invented claim"},
])
async def test_explain_invalid_or_unavailable_falls_back(service, request_body, monkeypatch, selection):
    document = await completed(service, request_body)
    real_client = httpx.AsyncClient

    def respond(request):
        if selection == "connection-error":
            raise httpx.ConnectError("offline", request=request)
        if selection == "model-unavailable":
            return httpx.Response(404, json={"error": "model not installed"})
        if selection == "oversized":
            return httpx.Response(200, content=b"x" * 32001)
        if selection == "missing-response":
            return httpx.Response(200, json={})
        return httpx.Response(200, json={"response": "not JSON" if selection == "invalid-json"
                                       else json.dumps(selection)})

    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: real_client(
        transport=httpx.MockTransport(respond), **kwargs))
    result = await service.explain(document)
    assert set(result) == {"status", "explanation", "citations", "error"}
    assert result["status"] == "unavailable" and result["error"]
    assert result["citations"] == [document["run_id"]]
    assert result["explanation"] == (f"[{document['run_id']}] Recommendation: fast. "
                                     + document["recommendation"]["reason"])


async def test_explain_selects_only_existing_statements_and_citations(service, request_body, monkeypatch):
    historical = await completed(service, request_body)
    document = await completed(service, request_body)
    document["feedback"] = [{"reason": "PRIVATE FEEDBACK INJECTION"}]
    selected_ids = ["history-0", "current", "candidate-0", "limit-0"]
    selected_facts = []
    real_client = httpx.AsyncClient

    def respond(request):
        assert request.url.path.endswith("/api/generate")
        payload = json.loads(request.content)
        assert payload["format"] == "json" and payload["stream"] is False
        assert payload["options"]["temperature"] == 0
        assert "PRIVATE SOURCE" not in payload["prompt"] and "PRIVATE FEEDBACK" not in payload["prompt"]
        facts = json.loads(payload["prompt"].split("Facts:\n", 1)[1])
        selected_facts.extend(next(f for f in facts if f["id"] == id_) for id_ in selected_ids)
        return httpx.Response(200, json={"response": json.dumps({
            "statement_ids": selected_ids, "explanation": "UNTRUSTED NEW CLAIM", "citations": ["fake"]})})

    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: real_client(
        transport=httpx.MockTransport(respond), **kwargs))
    result = await service.explain(document)
    assert result == {"status": "generated", "error": None,
                      "explanation": "\n".join(f["text"] for f in selected_facts),
                      "citations": [historical["run_id"], document["run_id"]]}
    assert "UNTRUSTED NEW CLAIM" not in result["explanation"]
