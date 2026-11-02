import asyncio
import hashlib
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
        }, {
            "filename": "backend/tests/test_events.py",
            "patch": "@@ -1 +1 @@\n+def test_create_event():",
            "status": "added",
            "additions": 1,
            "deletions": 0,
        }],
        "commits": [{"sha": "abc123", "commit": {"message": "Add events"}}],
        "check_runs": [{"name": "backend-tests", "conclusion": "success"}],
        "reviews": [],
        "comments": [],
    }


def _model_response():
    coverage, _ = evaluation._determine_dimension_eligibility(
        _evidence(),
        "code_quality",
    )
    evidence_by_dimension = {
        "code_quality": [{
            "file": "backend/app/routes/events.py",
            "line": 1,
            "excerpt": "def create_event():",
            "reason": "The changed handler is the implementation being assessed.",
        }],
        "delivery": [{
            "commit_sha": "abc123",
            "reason": "The retrieved commit records this submitted contribution.",
        }],
        "reliability": [{
            "check_name": "backend-tests",
            "reason": "This check run is the retrieved CI evidence.",
        }],
        "engineering_judgment": [{
            "file": "backend/tests/test_events.py",
            "line": 1,
            "excerpt": "def test_create_event():",
            "reason": "The paired test change shows the tested implementation behavior.",
        }],
    }
    dimensions = {
        name: {
            "score": 7,
            "reasoning": {
                "code_quality": "The create_event handler implements event creation.",
                "delivery": "Commit abc123 records Add events.",
                "reliability": "The backend-tests check passed.",
                "engineering_judgment": "test_create_event covers create_event.",
            }[name],
            "evidence": evidence_by_dimension[name],
        }
        for name in evaluation.AI_DIMENSION_WEIGHTS
        if coverage[name] in {"assessed", "partially_assessable"}
    }
    return json.dumps({
        "dimensions": dimensions,
        "analysis": "The change is supported by the PR evidence.",
        "strengths": ["The API has focused scope."],
        "weaknesses": ["Additional edge-case coverage is needed."],
        "recommendations": ["Add malformed input validation to create_event."],
        "evidence": [{
            "file": "backend/app/routes/events.py",
            "line": 1,
            "excerpt": "def create_event():",
            "reason": "The changed route implements event creation.",
            "recommendation": "Add malformed input validation to create_event.",
        }],
        "confidence": 0.8,
    })


def _response_with_code_quality_score(score):
    response = json.loads(_model_response())
    response["dimensions"]["code_quality"]["score"] = score
    return json.dumps(response)


def _persistable_evaluation(evaluation_id, head_commit_sha="abc123"):
    coverage, reasons = evaluation._determine_dimension_eligibility(
        _evidence(),
        "code_quality",
    )
    dimensions = {}
    for name in evaluation.AI_DIMENSION_WEIGHTS:
        if coverage[name] in {"assessed", "partially_assessable"}:
            dimensions[name] = {
                "score": 7,
                "assessment": coverage[name],
                "reasoning": f"Evidence for {name}",
            }
        else:
            dimensions[name] = {
                "assessment": coverage[name],
                "reasoning": reasons[name],
            }
    weights = evaluation._normalized_score_weights(dimensions, coverage)
    return DeveloperEvaluation(
        evaluation_id=evaluation_id,
        employee_id="DEMO-DEV",
        github_username="developer",
        repo_owner="owner",
        repo_name="repo",
        pr_number=1,
        head_commit_sha=head_commit_sha,
        evaluation_focus="code_quality",
        ai_provider="ollama",
        model_name="llama3.2",
        overall_score=evaluation._calculate_focus_score(dimensions, coverage),
        dimensions=dimensions,
        evidence_manifest={"files": [{"file": "events.py"}]},
        evidence_coverage=coverage,
        evidence_coverage_reasons=reasons,
        score_dimensions=list(weights),
        score_weights=weights,
        schema_validated=True,
        evidence_validated=True,
        is_preliminary=False,
    )


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
        {
            "name": "repo",
            "owner": {"login": "owner", "repo": {"full_name": "owner/repo"}},
            "permissions": {"admin": True},
        },
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
    assert "Every scored dimension must cite one or more exact sources" in prompt
    assert "Do not claim delivery was on time" in prompt
    assert "does not establish production reliability" in prompt
    assert "This is a PR-scoped evaluation" in prompt
    assert "preliminary PR evaluation" not in prompt
    assert '"collaboration": {' not in prompt
    assert '"dimension": "collaboration"' in prompt
    assert "No pull request reviews or comments were retrieved." in prompt
    assert '"engineering_impact": {' not in prompt
    assert '"engineering_judgment": {' in prompt
    assert '"repo": {' not in prompt
    assert '"permissions":' not in prompt
    assert len(prompt.encode("utf-8")) <= evaluation.MAX_MODEL_PROMPT_BYTES
    assert result["dimensions"]["code_quality"]["score"] == 7


@pytest.mark.asyncio
async def test_oversized_manifest_is_rejected_before_model_call(monkeypatch):
    llm = Mock()
    monkeypatch.setattr(evaluation, "MAX_EVIDENCE_MANIFEST_BYTES", 1)
    monkeypatch.setattr(evaluation, "check_ollama_connection", lambda: True)
    monkeypatch.setattr(evaluation, "get_ollama_llm", lambda **_: llm)

    with pytest.raises(evaluation.EvidenceUnavailableError, match="manifest exceeds"):
        await evaluation._run_ai_evaluation(
            "developer",
            {"name": "repo"},
            _evidence(),
            "code_quality",
        )
    llm.invoke.assert_not_called()


@pytest.mark.asyncio
async def test_oversized_prompt_is_rejected_before_model_call(monkeypatch):
    llm = Mock()
    monkeypatch.setattr(evaluation, "MAX_MODEL_PROMPT_BYTES", 1)
    monkeypatch.setattr(evaluation, "check_ollama_connection", lambda: True)
    monkeypatch.setattr(evaluation, "get_ollama_llm", lambda **_: llm)

    with pytest.raises(evaluation.EvidenceUnavailableError, match="prompt exceeds"):
        await evaluation._run_ai_evaluation(
            "developer",
            {"name": "repo"},
            _evidence(),
            "code_quality",
        )
    llm.invoke.assert_not_called()


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
async def test_scored_dimension_requires_grounded_evidence_citation(monkeypatch):
    response = json.loads(_model_response())
    response["dimensions"]["code_quality"]["evidence"] = []

    with pytest.raises(evaluation.ModelResponseValidationError, match="cite at least one evidence source"):
        await _run_model_response(monkeypatch, json.dumps(response))


@pytest.mark.asyncio
async def test_unsupported_deadline_claim_is_rejected(monkeypatch):
    response = json.loads(_model_response())
    response["dimensions"]["delivery"]["reasoning"] = (
        "The contribution was delivered on time."
    )

    with pytest.raises(evaluation.ModelResponseValidationError, match="deadline claim"):
        await _run_model_response(monkeypatch, json.dumps(response))


@pytest.mark.asyncio
async def test_ci_does_not_support_production_reliability_claim(monkeypatch):
    response = json.loads(_model_response())
    response["dimensions"]["reliability"]["reasoning"] = (
        "Successful CI proves production reliability."
    )

    with pytest.raises(evaluation.ModelResponseValidationError, match="production reliability"):
        await _run_model_response(monkeypatch, json.dumps(response))


@pytest.mark.asyncio
async def test_security_claim_without_retrieved_security_evidence_is_rejected(monkeypatch):
    response = json.loads(_model_response())
    response["dimensions"]["code_quality"]["reasoning"] = (
        "The change introduces a security vulnerability."
    )

    with pytest.raises(evaluation.ModelResponseValidationError, match="security claim"):
        await _run_model_response(monkeypatch, json.dumps(response))


@pytest.mark.asyncio
async def test_performance_claim_without_measurement_is_rejected(monkeypatch):
    response = json.loads(_model_response())
    response["dimensions"]["code_quality"]["reasoning"] = (
        "The implementation creates a performance bottleneck."
    )

    with pytest.raises(evaluation.ModelResponseValidationError, match="performance claim"):
        await _run_model_response(monkeypatch, json.dumps(response))


@pytest.mark.asyncio
async def test_dimension_reference_to_non_manifest_file_is_rejected(monkeypatch):
    response = json.loads(_model_response())
    response["dimensions"]["code_quality"]["evidence"][0]["file"] = "backend/missing.py"

    with pytest.raises(evaluation.ModelResponseValidationError, match="not present in the manifest"):
        await _run_model_response(monkeypatch, json.dumps(response))


@pytest.mark.asyncio
async def test_score_reasoning_unrelated_to_its_citation_is_rejected(monkeypatch):
    response = json.loads(_model_response())
    response["dimensions"]["code_quality"]["reasoning"] = (
        "The payment gateway retries failed transactions."
    )

    with pytest.raises(evaluation.ModelResponseValidationError, match="not connected"):
        await _run_model_response(monkeypatch, json.dumps(response))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "recommendation",
    [
        "Consider using a more modern Python framework.",
        "Implement security measures for this application.",
        "Add retry logic to the unrelated payment gateway.",
    ],
)
async def test_generic_or_unrelated_recommendation_is_rejected(monkeypatch, recommendation):
    response = json.loads(_model_response())
    response["recommendations"] = [recommendation]
    response["evidence"][0]["recommendation"] = recommendation

    with pytest.raises(evaluation.ModelResponseValidationError, match="recommendation"):
        await _run_model_response(monkeypatch, json.dumps(response))


@pytest.mark.asyncio
async def test_missing_collaboration_and_impact_evidence_excludes_scores(monkeypatch):
    result = await _run_model_response(monkeypatch, _model_response())

    assert "collaboration" not in result["dimensions"]
    assert "engineering_impact" not in result["dimensions"]


@pytest.mark.asyncio
async def test_missing_assessed_score_is_rejected(monkeypatch):
    response = json.loads(_model_response())
    del response["dimensions"]["code_quality"]["score"]
    with pytest.raises(evaluation.ModelResponseValidationError, match="missing score"):
        await _run_model_response(monkeypatch, json.dumps(response))


@pytest.mark.asyncio
async def test_insufficient_evidence_dimension_may_omit_score(monkeypatch):
    result = await _run_model_response(monkeypatch, _model_response())
    assert "collaboration" not in result["dimensions"]


@pytest.mark.asyncio
async def test_score_for_insufficient_evidence_dimension_is_rejected(monkeypatch):
    response = json.loads(_model_response())
    response["dimensions"]["collaboration"] = {
        "score": 0,
        "reasoning": "No collaboration evidence supports this score.",
    }
    with pytest.raises(evaluation.ModelResponseValidationError, match="unsupported dimension"):
        await _run_model_response(monkeypatch, json.dumps(response))


def test_score_aggregation_excludes_unsupported_dimensions():
    dimensions = {
        "code_quality": {"score": 8, "assessment": "assessed"},
        "delivery": {"score": 6, "assessment": "assessed"},
        "collaboration": {"assessment": "insufficient_evidence"},
        "reliability": {"score": 9, "assessment": "assessed"},
        "engineering_impact": {"assessment": "insufficient_evidence"},
        "engineering_judgment": {"assessment": "insufficient_evidence"},
    }
    coverage = {name: value["assessment"] for name, value in dimensions.items()}
    assert evaluation._calculate_focus_score(dimensions, coverage) == 7.58


def test_overall_score_unavailable_when_no_dimensions_are_eligible():
    coverage = {
        name: "insufficient_evidence"
        for name in evaluation.AI_DIMENSION_WEIGHTS
    }
    assert evaluation._calculate_focus_score({}, coverage) is None


def test_dimension_eligibility_is_derived_from_current_pr_evidence():
    coverage, reasons = evaluation._determine_dimension_eligibility(
        _evidence(),
        "code_quality",
    )

    assert coverage["code_quality"] == "assessed"
    assert coverage["collaboration"] == "insufficient_evidence"
    assert coverage["engineering_impact"] == "insufficient_evidence"
    assert coverage["engineering_judgment"] == "partially_assessable"
    assert coverage["delivery"] == "partially_assessable"
    assert coverage["reliability"] == "partially_assessable"
    assert "No pull request reviews or comments" in reasons["collaboration"]
    assert "long-term impact" in reasons["engineering_impact"]
    assert "production reliability" in reasons["reliability"]


def test_different_evidence_changes_the_eligibility_set():
    evidence = _evidence()
    evidence["reviews"] = [{"id": 1, "state": "APPROVED"}]
    evidence["impact_metrics"] = [
        {"metric": "latency_ms", "baseline": 100, "observed": 80}
    ]

    coverage, _ = evaluation._determine_dimension_eligibility(
        evidence,
        "code_quality",
    )

    assert coverage["collaboration"] == "partially_assessable"
    assert coverage["engineering_impact"] == "partially_assessable"


def test_evaluation_result_identifies_duplicate_responses():
    result = evaluation._result_from_evaluation(
        _persistable_evaluation("EVAL-EXISTING"),
        duplicate=True,
    )
    assert result.duplicate is True
    assert result.evaluation_id == "EVAL-EXISTING"


def test_completed_result_replaces_legacy_preliminary_wording_without_mutation():
    legacy_wording = (
        "Preliminary pull-request evaluation; not a complete performance assessment."
    )
    item = _persistable_evaluation("EVAL-COMPLETED").model_copy(
        update={
            "limitations": [
                legacy_wording,
                "Historical result is preliminary because no evidence manifest was recorded.",
            ],
            "status": "completed",
        }
    )
    saved_record = item.model_dump(mode="json")

    result = evaluation._result_from_evaluation(item)
    serialized_limitations = " ".join(result.limitations).lower()
    calculated_score = sum(
        result.ai_analysis["dimensions"][name]["score"] * result.score_weights[name]
        for name in result.score_dimensions
    )

    assert result.status == "completed"
    assert result.is_preliminary is False
    assert "preliminary" not in serialized_limitations
    assert "pr-scoped evaluation of the available evidence for pr #1" in serialized_limitations
    assert "not a complete assessment" in serialized_limitations
    assert result.overall_score == 7
    assert round(calculated_score, 2) == result.overall_score
    assert "score" not in result.ai_analysis["dimensions"]["collaboration"]
    assert "score" not in result.ai_analysis["dimensions"]["engineering_impact"]
    assert item.model_dump(mode="json") == saved_record


def test_preliminary_result_retains_warning_and_pr_scope():
    item = _persistable_evaluation("EVAL-PRELIMINARY").model_copy(
        update={
            "status": "processing",
            "is_preliminary": True,
            "limitations": [
                "Preliminary pull-request evaluation; not a complete performance assessment."
            ],
        }
    )

    result = evaluation._result_from_evaluation(item)

    assert result.is_preliminary is True
    assert any("preliminary pr-scoped evaluation" in item.lower() for item in result.limitations)
    assert any("not a complete assessment" in item.lower() for item in result.limitations)


def test_historical_result_without_manifest_remains_readable_without_false_warning():
    item = _persistable_evaluation("EVAL-HISTORICAL").model_copy(
        update={"evidence_manifest": {}, "status": "completed"}
    )

    result = evaluation._result_from_evaluation(item)

    assert result.evaluation_id == "EVAL-HISTORICAL"
    assert result.status == "completed"
    assert result.overall_score == 7
    assert any(
        "predates evidence-manifest validation" in limitation
        for limitation in result.limitations
    )
    assert all("preliminary" not in limitation.lower() for limitation in result.limitations)


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
async def test_non_object_model_json_is_rejected(monkeypatch):
    with pytest.raises(evaluation.ModelResponseValidationError, match="JSON object"):
        await _run_model_response(monkeypatch, "[]")


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
    assert persisted[0].schema_validated is True
    assert persisted[0].evidence_validated is True
    assert persisted[0].is_preliminary is False
    assert persisted[0].score_coverage["assessed_weight"] == 65
    assert persisted[0].score_coverage["coverage_percentage"] == 65
    assert persisted[0].score_coverage["calculation"].endswith("= 7.00")
    assert persisted[0].dimensions["code_quality"]["evidence"]


@pytest.mark.asyncio
async def test_evaluation_rejects_scores_for_dimensions_without_evidence(monkeypatch):
    service = Mock()
    service.get_repository_info = AsyncMock(return_value={"name": "repo", "owner": "owner"})
    service.fetch_pull_request_evidence = AsyncMock(return_value=_evidence())
    monkeypatch.setattr(evaluation, "GitHubAPIService", lambda: service)
    monkeypatch.setattr(evaluation, "check_ollama_connection", lambda: True)
    response = json.loads(_model_response())
    response["dimensions"]["collaboration"] = {
        "score": 4,
        "assessment": "assessed",
        "reasoning": "No collaboration evidence supports this score.",
    }
    llm = Mock()
    llm.invoke.return_value = json.dumps(response)
    monkeypatch.setattr(evaluation, "get_ollama_llm", lambda **_: llm)

    persisted = []

    class FakeRepository:
        async def create_or_get(self, item):
            persisted.append(item)
            return item

    monkeypatch.setattr(evaluation, "EvaluationRepository", FakeRepository)
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
    assert error.value.status_code == 502
    assert persisted == []


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
    item = _persistable_evaluation("EVAL-1")

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
        {"is_preliminary": True},
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
    existing = _persistable_evaluation("EVAL-HISTORICAL").model_copy(
        update=existing_updates
    )
    await collection.insert_one(existing.model_dump(mode="json"))
    historical_before = await collection.find_one({"evaluation_id": "EVAL-HISTORICAL"})
    candidate = _persistable_evaluation("EVAL-NEW").model_copy(
        update={"head_commit_sha": existing.head_commit_sha}
    )

    saved = await repository.create_or_get(candidate)

    assert saved.evaluation_id == "EVAL-NEW"
    assert await collection.count_documents({}) == 2
    assert await collection.find_one({"evaluation_id": "EVAL-HISTORICAL"}) == historical_before
    client.close()


@pytest.mark.asyncio
async def test_scored_insufficient_legacy_record_does_not_block_new_key_contract(monkeypatch):
    client = AsyncMongoMockClient()
    collection = client["evaluation_test"]["developer_evaluations"]
    monkeypatch.setattr(evaluation_repository, "col", lambda _: collection)
    repository = evaluation_repository.EvaluationRepository()
    existing = _persistable_evaluation("EVAL-HISTORICAL")
    invalid_dimensions = {
        **existing.dimensions,
        "collaboration": {
            "score": 4,
            "assessment": "insufficient_evidence",
            "reasoning": "Unsupported historical score",
        },
    }
    legacy_identity = json.dumps(
        (
            "score-contract-v2",
            existing.employee_id,
            existing.repo_owner,
            existing.repo_name,
            str(existing.pr_number),
            existing.head_commit_sha,
            existing.evaluation_focus,
        ),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    existing = existing.model_copy(
        update={
            "dimensions": invalid_dimensions,
            "duplicate_key": hashlib.sha256(legacy_identity.encode("utf-8")).hexdigest(),
        }
    )
    await collection.insert_one(existing.model_dump(mode="json"))

    saved = await repository.create_or_get(
        _persistable_evaluation("EVAL-NEW")
    )

    assert saved.evaluation_id == "EVAL-NEW"
    assert await collection.count_documents({}) == 2
    client.close()


@pytest.mark.asyncio
async def test_different_head_sha_gets_distinct_evaluation(monkeypatch):
    client = AsyncMongoMockClient()
    collection = client["evaluation_test"]["developer_evaluations"]
    monkeypatch.setattr(evaluation_repository, "col", lambda _: collection)
    repository = evaluation_repository.EvaluationRepository()
    base = _persistable_evaluation("EVAL-ONE")

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
    item = _persistable_evaluation("EVAL-CONCURRENT")

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


def test_fabricated_evidence_excerpt_is_rejected():
    manifest = evaluation._build_evidence_manifest("owner", "repo", 1, _evidence())
    invalid = evaluation._validate_evidence_references(
        [{
            "file": "backend/app/routes/events.py",
            "line": 1,
            "excerpt": "def delete_everything():",
            "reason": "Fabricated excerpt.",
        }],
        manifest,
    )

    assert invalid and "does not match" in invalid[0]["reason"]


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


def test_partial_score_coverage_reports_65_percent_and_normalized_formula():
    coverage, reasons = evaluation._determine_dimension_eligibility(
        _evidence(),
        "code_quality",
    )
    dimensions = {
        name: {"score": score}
        for name, score in {
            "code_quality": 8,
            "delivery": 6,
            "reliability": 7,
            "engineering_judgment": 5,
        }.items()
    }

    metadata = evaluation._score_coverage_metadata(
        dimensions,
        coverage,
        reasons,
    )

    assert metadata["configured_total_weight"] == 100
    assert metadata["defined_dimension_weight"] == 90
    assert metadata["unallocated_weight"] == 10
    assert metadata["assessed_weight"] == 65
    assert metadata["coverage_percentage"] == 65
    assert metadata["included_dimensions"] == [
        "code_quality",
        "delivery",
        "reliability",
        "engineering_judgment",
    ]
    assert {item["dimension"] for item in metadata["excluded_dimensions"]} == {
        "collaboration",
        "engineering_impact",
    }
    assert metadata["normalized_weights"] == {
        "code_quality": 0.384615,
        "delivery": 0.307692,
        "reliability": 0.230769,
        "engineering_judgment": 0.076923,
    }
    assert metadata["configured_weights"] == {
        "code_quality": 25,
        "delivery": 20,
        "reliability": 15,
        "engineering_judgment": 5,
    }
    assert metadata["calculation"].endswith("= 6.92")
    assert metadata["normalized_dimension_score"] == 6.92
    assert metadata["overall_score"] == 6.92


def test_reference_evaluation_scores_and_coverage_remain_compatible():
    base = _persistable_evaluation("EVAL-REFERENCE")
    item = base.model_copy(
        update={
            "overall_score": 6.92,
            "dimensions": {
                **base.dimensions,
                "code_quality": {
                    "score": 8,
                    "assessment": "assessed",
                    "reasoning": "Existing saved reasoning.",
                },
                "delivery": {
                    "score": 6,
                    "assessment": "partially_assessable",
                    "reasoning": "Existing saved reasoning.",
                },
                "reliability": {
                    "score": 7,
                    "assessment": "partially_assessable",
                    "reasoning": "Existing saved reasoning.",
                },
                "engineering_judgment": {
                    "score": 5,
                    "assessment": "partially_assessable",
                    "reasoning": "Existing saved reasoning.",
                },
            },
            "score_coverage": {},
        }
    )

    result = evaluation._result_from_evaluation(item)

    assert result.overall_score == 6.92
    assert result.score_coverage["assessed_weight"] == 65
    assert result.score_coverage["coverage_percentage"] == 65
    assert result.score_coverage["calculation"].endswith("= 6.92")
    assert "score" not in result.ai_analysis["dimensions"]["collaboration"]
    assert "score" not in result.ai_analysis["dimensions"]["engineering_impact"]


def test_full_dimension_evidence_reports_all_defined_weight_as_assessed():
    dimensions = {
        name: {"score": 7}
        for name in evaluation.AI_DIMENSION_WEIGHTS
    }
    coverage = {name: "assessed" for name in evaluation.AI_DIMENSION_WEIGHTS}
    reasons = {name: "Evidence available" for name in evaluation.AI_DIMENSION_WEIGHTS}

    metadata = evaluation._score_coverage_metadata(dimensions, coverage, reasons)

    assert metadata["assessed_weight"] == sum(evaluation.AI_DIMENSION_WEIGHTS.values())
    assert metadata["coverage_percentage"] == 90
    assert metadata["included_dimensions"] == list(evaluation.AI_DIMENSION_WEIGHTS)
    assert metadata["excluded_dimensions"] == []


def test_human_baseline_formula_matches_existing_score_policy():
    coverage = {name: "assessed" for name in evaluation.AI_DIMENSION_WEIGHTS}
    dimensions = {
        "code_quality": {"score": 8},
        "delivery": {"score": 6},
        "reliability": {"score": 7},
        "engineering_judgment": {"score": 5},
    }

    metadata = evaluation._score_coverage_metadata(
        dimensions,
        coverage,
        {},
        human_score=8,
    )

    assert metadata["normalized_dimension_score"] == 6.92
    assert metadata["overall_score"] == 7.03
    assert metadata["calculation"].endswith("= 7.03")


def test_historical_evaluation_serialization_derives_missing_score_coverage():
    result = evaluation._result_from_evaluation(
        _persistable_evaluation("EVAL-LEGACY").model_copy(
            update={"score_coverage": {}}
        )
    )

    assert result.score_coverage["assessed_weight"] == 65
    assert result.score_coverage["coverage_percentage"] == 65
