import asyncio
import json
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from mongomock_motor import AsyncMongoMockClient

from api.routes import evaluation
from domain.models.developer_evaluation import DeveloperEvaluation
from repositories import evaluation_repository


def _evidence():
    return {
        "pr": {
            "number": 1,
            "title": "Add events",
            "body": "Adds event creation and listing.",
            "user": {"login": "developer"},
            "head": {"ref": "feature/events", "sha": "abc123"},
            "base": {"ref": "main"},
        },
        "files": [{
            "filename": "backend/app/routes/events.py",
            "patch": "@@ -1 +1 @@\n+def create_event():",
            "status": "modified",
            "additions": 1,
            "deletions": 0,
        }],
        "commits": [{"sha": "abc123", "commit": {"message": "Add events"}}],
        "check_runs": [{"name": "backend-tests", "conclusion": "success"}],
        "reviews": [],
        "comments": [],
    }


def _model_response():
    dimensions = {
        name: {
            "score": 7,
            "assessment": "assessed",
            "reasoning": f"Evidence for {name}",
        }
        for name in evaluation.AI_DIMENSION_WEIGHTS
    }
    return json.dumps({
        "dimensions": dimensions,
        "analysis": "The change is supported by the PR evidence.",
        "strengths": ["The API has focused scope."],
        "weaknesses": ["Additional edge-case coverage is needed."],
        "recommendations": ["Add validation for malformed event payloads."],
        "evidence": [{
            "file": "backend/app/routes/events.py",
            "reason": "The changed route implements event creation.",
            "recommendation": "Add malformed payload tests.",
        }],
        "confidence": 0.8,
    })


def _response_with_code_quality_score(score):
    response = json.loads(_model_response())
    response["dimensions"]["code_quality"]["score"] = score
    return json.dumps(response)


async def _run_model_response(monkeypatch, response):
    llm = Mock()
    llm.invoke.return_value = response
    monkeypatch.setattr(evaluation, "check_ollama_connection", lambda: True)
    monkeypatch.setattr(evaluation, "get_ollama_llm", lambda **_: llm)
    return await evaluation._run_ai_evaluation(
        "developer",
        {"name": "repo"},
        _evidence(),
        "code_quality",
    )


@pytest.mark.asyncio
async def test_ai_prompt_contains_actual_pr_evidence(monkeypatch):
    llm = Mock()
    llm.invoke.return_value = _model_response()
    monkeypatch.setattr(evaluation, "check_ollama_connection", lambda: True)
    monkeypatch.setattr(evaluation, "get_ollama_llm", lambda **_: llm)

    result = await evaluation._run_ai_evaluation(
        "developer",
        {"name": "repo", "owner": "owner"},
        _evidence(),
        "code_quality",
    )

    prompt = llm.invoke.call_args.args[0]
    assert "backend/app/routes/events.py" in prompt
    assert "Add events" in prompt
    assert "backend-tests" in prompt
    assert "0 to 10 inclusive" in prompt
    assert "Never return percentages or a 0-100 score" in prompt
    assert "do not invent a score" in prompt
    assert '"repo": {' not in prompt
    assert result["dimensions"]["code_quality"]["score"] == 7


@pytest.mark.asyncio
@pytest.mark.parametrize("score", [8.2, 0, 10])
async def test_numeric_scores_inclusive_zero_to_ten_are_accepted(monkeypatch, score):
    result = await _run_model_response(
        monkeypatch,
        _response_with_code_quality_score(score),
    )
    assert result["dimensions"]["code_quality"]["score"] == score


@pytest.mark.asyncio
@pytest.mark.parametrize("score", [-1, 10.1, 80, "8.2"])
async def test_invalid_score_values_are_rejected_without_normalization(monkeypatch, score):
    with pytest.raises(evaluation.ModelResponseValidationError, match="between 0 and 10"):
        await _run_model_response(
            monkeypatch,
            _response_with_code_quality_score(score),
        )


@pytest.mark.asyncio
async def test_missing_assessed_score_is_rejected(monkeypatch):
    response = json.loads(_model_response())
    del response["dimensions"]["code_quality"]["score"]
    with pytest.raises(evaluation.ModelResponseValidationError, match="missing score"):
        await _run_model_response(monkeypatch, json.dumps(response))


@pytest.mark.asyncio
async def test_insufficient_evidence_dimension_may_omit_score(monkeypatch):
    response = json.loads(_model_response())
    dimension = response["dimensions"]["collaboration"]
    dimension.pop("score")
    dimension["assessment"] = "insufficient_evidence"
    result = await _run_model_response(monkeypatch, json.dumps(response))
    assert "score" not in result["dimensions"]["collaboration"]


@pytest.mark.asyncio
async def test_unsupported_dimension_is_rejected(monkeypatch):
    response = json.loads(_model_response())
    response["dimensions"]["unsupported"] = response["dimensions"]["code_quality"]
    with pytest.raises(evaluation.ModelResponseValidationError, match="unsupported dimensions"):
        await _run_model_response(monkeypatch, json.dumps(response))


@pytest.mark.asyncio
async def test_missing_evidence_stops_before_model(monkeypatch):
    llm = Mock()
    monkeypatch.setattr(evaluation, "check_ollama_connection", lambda: True)
    monkeypatch.setattr(evaluation, "get_ollama_llm", lambda **_: llm)

    incomplete = _evidence()
    incomplete["files"] = []
    with pytest.raises(evaluation.EvidenceUnavailableError):
        await evaluation._run_ai_evaluation(
            "developer",
            {"name": "repo"},
            incomplete,
            "code_quality",
        )
    llm.invoke.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_model_json_is_rejected(monkeypatch):
    llm = Mock()
    llm.invoke.return_value = "not json"
    monkeypatch.setattr(evaluation, "check_ollama_connection", lambda: True)
    monkeypatch.setattr(evaluation, "get_ollama_llm", lambda **_: llm)

    with pytest.raises(evaluation.ModelResponseValidationError):
        await evaluation._run_ai_evaluation(
            "developer",
            {"name": "repo"},
            _evidence(),
            "code_quality",
        )


@pytest.mark.asyncio
async def test_ollama_connection_closed_is_reported_without_persistence(monkeypatch):
    llm = Mock()
    llm.invoke.side_effect = ConnectionError("connection closed during generation")
    monkeypatch.setattr(evaluation, "check_ollama_connection", lambda: True)
    monkeypatch.setattr(evaluation, "get_ollama_llm", lambda **_: llm)

    with pytest.raises(evaluation.EvaluationProcessingError, match="AI evaluation failed"):
        await evaluation._run_ai_evaluation(
            "developer",
            {"name": "repo"},
            _evidence(),
            "code_quality",
        )


@pytest.mark.asyncio
async def test_ollama_timeout_is_reported(monkeypatch):
    async def stalled_call(*_args):
        await asyncio.sleep(1)

    monkeypatch.setattr(evaluation, "MODEL_REQUEST_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(evaluation.asyncio, "to_thread", stalled_call)
    monkeypatch.setattr(evaluation, "check_ollama_connection", lambda: True)
    monkeypatch.setattr(evaluation, "get_ollama_llm", lambda **_: Mock())

    with pytest.raises(evaluation.EvaluationProcessingError, match="timed out"):
        await evaluation._run_ai_evaluation(
            "developer",
            {"name": "repo"},
            _evidence(),
            "code_quality",
        )


@pytest.mark.asyncio
async def test_backend_path_remains_usable_after_model_failure(monkeypatch):
    llm = Mock()
    llm.invoke.side_effect = ConnectionError("connection closed")
    monkeypatch.setattr(evaluation, "check_ollama_connection", lambda: True)
    monkeypatch.setattr(evaluation, "get_ollama_llm", lambda **_: llm)

    with pytest.raises(evaluation.EvaluationProcessingError):
        await evaluation._run_ai_evaluation(
            "developer",
            {"name": "repo"},
            _evidence(),
            "code_quality",
        )

    llm.invoke.side_effect = None
    llm.invoke.return_value = _model_response()
    result = await evaluation._run_ai_evaluation(
        "developer",
        {"name": "repo"},
        _evidence(),
        "code_quality",
    )
    assert result["dimensions"]["code_quality"]["score"] == 7


@pytest.mark.asyncio
async def test_evaluation_persists_employee_and_pr_association(monkeypatch):
    service = Mock()
    service.get_repository_info = AsyncMock(return_value={
        "name": "repo",
        "owner": "owner",
        "language": "Python",
    })
    service.fetch_pull_request_evidence = AsyncMock(return_value=_evidence())
    monkeypatch.setattr(evaluation, "GitHubAPIService", lambda: service)
    monkeypatch.setattr(evaluation, "check_ollama_connection", lambda: True)
    llm = Mock()
    llm.invoke.return_value = _model_response()
    monkeypatch.setattr(evaluation, "get_ollama_llm", lambda **_: llm)

    persisted = []

    class FakeRepository:
        async def create_or_get(self, item):
            persisted.append(item)
            return item

    monkeypatch.setattr(evaluation, "EvaluationRepository", FakeRepository)
    result = await evaluation.evaluate_developer_ai(
        evaluation.SimpleEvalRequest(
            employee_id="DEMO-DEV",
            github_username="developer",
            repo_owner="owner",
            repo_name="repo",
            pr_number=1,
        ),
        {"employee_id": "DEMO-LEAD", "role": "LEAD"},
    )

    assert result.employee_id == "DEMO-DEV"
    assert result.pr_number == 1
    assert result.head_commit_sha == "abc123"
    assert persisted[0].repo_name == "repo"
    assert persisted[0].status == "completed"


@pytest.mark.asyncio
async def test_author_mismatch_is_not_a_successful_evaluation(monkeypatch):
    service = Mock()
    service.get_repository_info = AsyncMock(return_value={"name": "repo"})
    evidence = _evidence()
    evidence["pr"]["user"]["login"] = "different-user"
    service.fetch_pull_request_evidence = AsyncMock(return_value=evidence)
    monkeypatch.setattr(evaluation, "GitHubAPIService", lambda: service)

    with pytest.raises(HTTPException) as error:
        await evaluation.evaluate_developer_ai(
            evaluation.SimpleEvalRequest(
                employee_id="DEMO-DEV",
                github_username="developer",
                repo_owner="owner",
                repo_name="repo",
                pr_number=1,
            ),
            {"employee_id": "DEMO-LEAD", "role": "LEAD"},
        )
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_repository_round_trip_and_duplicate_handling(monkeypatch):
    client = AsyncMongoMockClient()
    collection = client["evaluation_test"]["developer_evaluations"]
    monkeypatch.setattr(evaluation_repository, "col", lambda _: collection)
    repository = evaluation_repository.EvaluationRepository()
    item = DeveloperEvaluation(
        evaluation_id="EVAL-1",
        employee_id="DEMO-DEV",
        github_username="developer",
        repo_owner="owner",
        repo_name="repo",
        pr_number=1,
        head_commit_sha="abc123",
        evaluation_focus="code_quality",
        ai_provider="ollama",
        model_name="llama3.2",
        overall_score=7,
        evidence_manifest={"files": [{"file": "events.py"}]},
    )

    first = await repository.create_or_get(item)
    second = await repository.create_or_get(item.model_copy(update={"evaluation_id": "EVAL-2"}))
    fetched = await repository.get_by_id("EVAL-1")

    assert first.evaluation_id == "EVAL-1"
    assert second.evaluation_id == "EVAL-1"
    assert fetched and fetched.employee_id == "DEMO-DEV"
    client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "existing_updates",
    [
        {"evidence_manifest": {}},
        {"evidence_manifest": {"files": [{"file": "events.py"}]}, "unsupported_references": [{"file": "fake.py"}]},
        {"status": "failed", "evidence_manifest": {"files": [{"file": "events.py"}]}},
    ],
)
async def test_invalid_existing_evaluation_does_not_block_new_attempt(
    monkeypatch,
    existing_updates,
):
    client = AsyncMongoMockClient()
    collection = client["evaluation_test"]["developer_evaluations"]
    monkeypatch.setattr(evaluation_repository, "col", lambda _: collection)
    repository = evaluation_repository.EvaluationRepository()
    existing = DeveloperEvaluation(
        evaluation_id="EVAL-HISTORICAL",
        employee_id="DEMO-DEV",
        github_username="developer",
        repo_owner="owner",
        repo_name="repo",
        pr_number=1,
        head_commit_sha="abc123",
        evaluation_focus="code_quality",
        ai_provider="ollama",
        model_name="llama3.2",
        overall_score=7,
        **existing_updates,
    )
    await collection.insert_one(existing.model_dump(mode="json"))
    candidate = existing.model_copy(
        update={"evaluation_id": "EVAL-NEW", "status": "completed"}
    )

    saved = await repository.create_or_get(candidate)

    assert saved.evaluation_id == "EVAL-NEW"
    assert await collection.count_documents({}) == 2
    client.close()


@pytest.mark.asyncio
async def test_different_head_sha_gets_distinct_evaluation(monkeypatch):
    client = AsyncMongoMockClient()
    collection = client["evaluation_test"]["developer_evaluations"]
    monkeypatch.setattr(evaluation_repository, "col", lambda _: collection)
    repository = evaluation_repository.EvaluationRepository()
    base = DeveloperEvaluation(
        evaluation_id="EVAL-ONE",
        employee_id="DEMO-DEV",
        github_username="developer",
        repo_owner="owner",
        repo_name="repo",
        pr_number=1,
        head_commit_sha="abc123",
        evaluation_focus="code_quality",
        ai_provider="ollama",
        model_name="llama3.2",
        overall_score=7,
        evidence_manifest={"files": [{"file": "events.py"}]},
    )

    first = await repository.create_or_get(base)
    second = await repository.create_or_get(
        base.model_copy(
            update={"evaluation_id": "EVAL-TWO", "head_commit_sha": "def456"}
        )
    )

    assert first.evaluation_id == "EVAL-ONE"
    assert second.evaluation_id == "EVAL-TWO"
    assert await collection.count_documents({}) == 2
    client.close()


@pytest.mark.asyncio
async def test_concurrent_valid_duplicates_return_one_persisted_result(monkeypatch):
    client = AsyncMongoMockClient()
    collection = client["evaluation_test"]["developer_evaluations"]
    monkeypatch.setattr(evaluation_repository, "col", lambda _: collection)
    repository = evaluation_repository.EvaluationRepository()
    item = DeveloperEvaluation(
        evaluation_id="EVAL-CONCURRENT",
        employee_id="DEMO-DEV",
        github_username="developer",
        repo_owner="owner",
        repo_name="repo",
        pr_number=1,
        head_commit_sha="abc123",
        evaluation_focus="code_quality",
        ai_provider="ollama",
        model_name="llama3.2",
        overall_score=7,
        evidence_manifest={"files": [{"file": "events.py"}]},
    )

    results = await asyncio.gather(
        repository.create_or_get(item),
        repository.create_or_get(item.model_copy(update={"evaluation_id": "EVAL-OTHER"})),
    )

    assert len({result.evaluation_id for result in results}) == 1
    assert await collection.count_documents({}) == 1
    client.close()


def test_unknown_evidence_reference_is_rejected():
    manifest = evaluation._build_evidence_manifest(
        "owner",
        "repo",
        1,
        _evidence(),
    )
    invalid = evaluation._validate_evidence_references(
        [{"file": "github-api-client.py", "reason": "not in PR"}],
        manifest,
    )
    assert invalid and "Unknown file" in invalid[0]["reason"]


@pytest.mark.parametrize(
    "reference",
    [
        {"commit_sha": "fabricated"},
        {"check_name": "fabricated-check"},
        {"file": "backend/app/routes/events.py", "line": 999},
    ],
)
def test_fabricated_commit_check_and_line_references_are_rejected(reference):
    manifest = evaluation._build_evidence_manifest("owner", "repo", 1, _evidence())
    invalid = evaluation._validate_evidence_references([reference], manifest)
    assert invalid


def test_score_uses_only_assessable_dimensions():
    dimensions = {
        name: {
            "score": 8,
            "assessment": "assessed",
            "reasoning": "supported",
        }
        for name in evaluation.AI_DIMENSION_WEIGHTS
    }
    coverage = {name: "insufficient_evidence" for name in dimensions}
    coverage["code_quality"] = "assessed"
    assert evaluation._calculate_focus_score(dimensions, coverage) == 8
