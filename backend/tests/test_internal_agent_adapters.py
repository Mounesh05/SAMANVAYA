"""F07/F08 boundaries through the real internal adapters and persistence paths."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import json
from pydantic import ValidationError

from agents import code_agent, llm_provider
from api.routes import code_quality, cicd_logs
from core import database
from domain.models.code_quality_report import CodeQualityReport, QualityBreakdown
from domain.services.github_analysis_service import GitHubAnalysisService
from intelligence.evidence.models import CodeQualityEvidence
from intelligence.quality_engine import QualityEngine
from intelligence.risk_engine import RiskEngine
ORIGINAL_QUALITY_CALCULATE = QualityEngine.calculate
ORIGINAL_CODE_NODE = code_agent.code_analysis_node

pytestmark = pytest.mark.anyio
REVISION = "a" * 40
QUALITY = {"quality_score": 83, "quality_grade": "B", "dimension_scores": {
    "static_security": 90, "testing": 80, "complexity": 70, "architecture": 100, "duplication": 75},
    "penalties": {"static_security": 10.0, "testing": 20.0, "complexity": 30.0, "architecture": 0.0, "duplication": 25.0}}
RISK = {"risk_score": 27, "risk_level": "low", "risk_factors": ["Observed change"], "dimension_scores": {"size": 12}}
VALID = {"analysis": "Advisory review", "recommendations": ["Inspect evidence"], "risk_level": "high",
         "confidence": 0.8, "critical_issues": [], "review_focus": None,
         "quality_score": 1, "failure_risk": 99, "affected_component": "runner", "prevention": "Retain regression tests", "urgency": "high"}
PR = {"pr_id": "PR1", "pr_number": 7, "title": "Review", "author": "developer", "repo": "owner/repo",
      "project_id": "P1", "commit_sha": REVISION, "changed_files": ["example.py"],
      "source_files": {"example.py": "def explore(x):\n    return x\n"}}


@pytest.fixture
async def environment(mock_db, monkeypatch):
    monkeypatch.setattr(database, "get_db", lambda: mock_db)
    user = {"employee_id": "A", "role": "DEVELOPER", "org_id": "O1", "project_ids": ["P1"],
            "email": "a@example.invalid", "is_active": True}
    await mock_db.users.insert_one(dict(user))
    await mock_db.projects.insert_many([{"id": "P1", "org_id": "O1"}, {"id": "P2", "org_id": "O2"}])
    await mock_db.github_project_configs.insert_one({"project_id": "P1", "repository_owner": "owner", "repository_name": "repo"})
    monkeypatch.setattr(llm_provider, "check_ollama_connection", lambda: True)
    node = Mock(return_value=deepcopy(VALID))
    monkeypatch.setattr(code_agent, "code_analysis_node", node)
    evidence = CodeQualityEvidence(repository_id="P1", primary_language="python", files_analyzed=1)
    monkeypatch.setattr(QualityEngine, "calculate", AsyncMock(return_value=deepcopy(QUALITY)))
    monkeypatch.setattr(RiskEngine, "analyze_evidence", AsyncMock(return_value=deepcopy(RISK)))
    from intelligence.analyzers import registry
    monkeypatch.setattr(registry, "get_analyzers_for_profile", lambda profile: {
        "python": SimpleNamespace(analyze=AsyncMock(return_value=evidence))})
    return mock_db, user, node, evidence


@pytest.mark.parametrize("deep", [False, True])
async def test_missing_authorization_never_becomes_completed_analysis(environment, deep):
    _, _, node, _ = environment
    result = await GitHubAnalysisService().analyze_with_ai(dict(PR), dict(RISK), use_deep_analysis=deep)
    assert result["ai_analysis"]["status"] == "failed"
    assert result.get("ai_run_data") is None
    node.assert_not_called()


@pytest.mark.parametrize("deep", [False, True])
async def test_user_authority_and_server_scope_reach_real_adapter(environment, deep):
    _, user, node, _ = environment
    result = await GitHubAnalysisService().analyze_with_ai(dict(PR), dict(RISK), use_deep_analysis=deep, authorization=user)
    assert result["ai_analysis"]["status"] == "completed"
    state = node.call_args.args[0]
    assert "VIEW_AI_EVALUATION" in state["user_context"]["permissions"]
    assert state["context"]["project_id"] == "P1"
    run = result["ai_run_data"]
    assert (run["owner_id"], run["project_id"], run["organization_id"]) == ("A", "P1", "O1")
    assert run["provenance"]["model_interpretation"] == "ADVISORY"
    assert run["access_version"] == "ai-run-access-v1"
    if deep:
        report = result["code_quality_report"]
        assert report.quality_score == 83 and report.failure_risk == 27
        assert report.quality_breakdown is None
        assert report.quality_representation == "quality-engine-v1"
        assert report.engine_quality.model_dump(exclude={"schema_version"}) == QUALITY
        assert report.engine_risk == RISK


@pytest.mark.parametrize("failure", ["errors", "empty", "invalid", "exception", "unavailable", "missing-evidence"])
@pytest.mark.parametrize("deep", [False, True])
async def test_failed_model_cannot_erase_measurements_or_create_completed_run(environment, failure, deep, monkeypatch):
    _, user, node, evidence = environment
    if failure == "errors":
        node.return_value = {**VALID, "errors": ["MODEL_TIMEOUT"]}
    elif failure == "empty":
        node.return_value = {**VALID, "analysis": ""}
    elif failure == "invalid":
        node.return_value = {**VALID, "confidence": float("nan")}
    elif failure == "exception":
        node.side_effect = RuntimeError("PRIVATE_PROVIDER_DATA")
    elif failure == "unavailable":
        monkeypatch.setattr(llm_provider, "check_ollama_connection", lambda: False)
    elif deep:
        evidence.files_analyzed = 0
    risk = {} if failure == "missing-evidence" and not deep else dict(RISK)
    result = await GitHubAnalysisService().analyze_with_ai(dict(PR), risk, use_deep_analysis=deep, authorization=user)
    assert result["ai_analysis"]["status"] in {"failed", "unavailable"}
    assert result["ai_run_data"]["status"] == "failed"
    assert result["ai_analysis"]["analysis"] is None
    assert "PRIVATE_PROVIDER_DATA" not in str(result)
    if deep:
        assert result["code_quality_report"].quality_score == QUALITY["quality_score"]
        assert result["code_quality_report"].failure_risk == RISK["risk_score"]


@pytest.mark.parametrize("change", [{"role": "HR"}, {"org_id": "O2"}, {"project_ids": []}, {"is_active": False}])
async def test_current_permissions_override_old_user_context(environment, change):
    db, user, node, _ = environment
    await db.users.update_one({"employee_id": "A"}, {"$set": change})
    result = await GitHubAnalysisService().analyze_with_ai(dict(PR), dict(RISK), authorization=user)
    assert result["ai_analysis"]["status"] == "failed"
    assert result.get("ai_run_data") is None
    node.assert_not_called()


async def test_server_owned_automation_is_exactly_project_repo_revision_scoped(environment):
    from domain.services.internal_agent_adapter import GitHubAutomation
    _, _, node, _ = environment
    job = GitHubAutomation("P1", "owner/repo", REVISION)
    result = await GitHubAnalysisService().analyze_with_ai(dict(PR), dict(RISK), authorization=job)
    assert result["ai_analysis"]["status"] == "completed"
    state = node.call_args.args[0]
    assert state["user_context"]["employee_id"] == "github-automation:P1"
    assert state["user_context"]["permissions"] == ["VIEW_AI_EVALUATION"]
    assert result["ai_run_data"]["owner_id"] == "github-automation:P1"
    changed = {**PR, "commit_sha": "b" * 40}
    denied = await GitHubAnalysisService().analyze_with_ai(changed, dict(RISK), authorization=job)
    assert denied["ai_analysis"]["status"] == "failed"
    assert node.call_count == 1


@pytest.mark.parametrize("failure", ["project", "repository", "revision", "missing-tenant", "inactive-project", "missing-mapping", "ambiguous-mapping"])
async def test_automation_review_rejects_unestablished_authority(environment, failure):
    from domain.services.internal_agent_adapter import GitHubAutomation
    db, _, node, _ = environment
    project, repository, revision = "P1", "owner/repo", REVISION
    if failure == "project":
        project = "P2"
    elif failure == "repository":
        repository = "other/repository"
    elif failure == "revision":
        revision = "main"
    elif failure == "missing-tenant":
        await db.projects.update_one({"id": "P1"}, {"$unset": {"org_id": ""}})
    elif failure == "inactive-project":
        await db.projects.update_one({"id": "P1"}, {"$set": {"status": "archived"}})
    elif failure == "missing-mapping":
        await db.github_project_configs.delete_many({})
    else:
        await db.github_project_configs.insert_one({"project_id": "P2", "repository_owner": "owner", "repository_name": "repo"})
    result = await GitHubAnalysisService().analyze_with_ai(dict(PR), dict(RISK),
        authorization=GitHubAutomation(project, repository, revision))
    assert result["ai_analysis"]["status"] == "failed"
    assert result.get("ai_run_data") is None
    node.assert_not_called()


async def test_caller_dictionary_cannot_impersonate_internal_automation(environment):
    _, _, node, _ = environment
    forged = {"employee_id": "github-automation:P1", "role": "AUTOMATION", "permissions": ["VIEW_AI_EVALUATION"]}
    result = await GitHubAnalysisService().analyze_with_ai(dict(PR), dict(RISK), authorization=forged)
    assert result["ai_analysis"]["status"] == "failed"
    node.assert_not_called()


async def test_operator_dictionary_is_not_an_authenticated_employee_identity(environment):
    _, _, node, _ = environment
    result = await GitHubAnalysisService().analyze_with_ai(dict(PR), dict(RISK), authorization={"employee_id": {"$ne": None}})
    assert result["ai_analysis"]["status"] == "failed"
    node.assert_not_called()


async def test_historical_report_keeps_legacy_point_units():
    breakdown = QualityBreakdown(correctness=20, maintainability=20, security=20, testing=15,
                                 performance=10, architecture=10, readability=5)
    old = {"pr_id": "old", "pr_number": 1, "pr_title": "old", "author": "A", "quality_score": 100,
           "quality_breakdown": breakdown.model_dump(), "failure_risk": 10, "risk_level": "low"}
    report = CodeQualityReport.model_validate(old)
    assert report.quality_breakdown.total == 100
    assert report.engine_quality is None
    assert report.quality_representation == "legacy-advisory-v1"


@pytest.mark.parametrize("change", [{"testing": 101}, {"architecture": True}, {"complexity": "70"}, {"unexpected": 1}])
async def test_engine_dimension_contract_rejects_incompatible_values_without_conversion(change):
    from domain.models.code_quality_report import EngineQualityV1
    value = deepcopy(QUALITY)
    value["dimension_scores"].update(change)
    with pytest.raises(ValidationError):
        EngineQualityV1.model_validate(value)


@pytest.mark.parametrize("failed", [False, True])
async def test_background_adapter_records_ai_status_independently(environment, monkeypatch, failed):
    db, _, node, evidence = environment
    await db.users.update_one({"employee_id": "A"}, {"$set": {"role": "QA"}})
    await db.code_quality_runs.insert_one({"run_id": "run"})
    monkeypatch.setattr(code_quality.cq_service, "analyze_pr", AsyncMock(return_value=evidence))
    from intelligence.baselines.repository_baseline import RepositoryBaseline
    monkeypatch.setattr(RepositoryBaseline, "update_baseline", AsyncMock())
    if failed:
        node.return_value = {"errors": ["MODEL_TIMEOUT"]}
    body = code_quality.AnalyzeRequest(repository_id="P1", changed_files=["example.py"], pr_context={"source_files": PR["source_files"]})
    await code_quality._run_analysis("run", body, None, actor_id="A")
    stored = await db.code_quality_runs.find_one({"run_id": "run"})
    assert stored["status"] == "completed"
    assert stored["quality_score"] == 83 and stored["risk_score"] == 27
    assert stored["ai_status"] == ("failed" if failed else "completed")
    assert stored["ai_analysis"]["status"] == stored["ai_status"]


@pytest.mark.parametrize("result", [{"errors": ["MODEL_TIMEOUT"]}, {"analysis": ""}, {**VALID, "confidence": 2}, VALID])
async def test_cicd_persistence_requires_valid_analysis(environment, monkeypatch, result):
    db, user, _, _ = environment
    monkeypatch.setattr(cicd_logs, "check_ollama_connection", lambda: True)
    monkeypatch.setattr(cicd_logs, "invoke_agent", Mock(return_value=result))
    response = await cicd_logs.analyze_cicd_log(cicd_logs.LogAnalysisRequest(log_content="ERROR: build failed", log_type="build"), user)
    stored = await db.ai_runs.find_one({"id": response.ai_run_id})
    assert stored["owner_id"] == "A" and stored["provenance"]["model_interpretation"] == "ADVISORY"
    assert stored["status"] == ("completed" if result == VALID else "failed")
    assert bool(stored["error_message"]) == (result != VALID)


async def test_agent_input_mutation_cannot_override_engine_measurements(environment):
    _, user, node, _ = environment
    def mutate(state):
        state["quality_result"]["quality_score"] = 0
        state["risk_result"]["risk_score"] = 100
        state["user_context"]["permissions"].clear()
        return dict(VALID)
    node.side_effect = mutate
    result = await GitHubAnalysisService().analyze_with_ai(dict(PR), dict(RISK), use_deep_analysis=True, authorization=user)
    assert result["code_quality_report"].quality_score == 83
    assert result["code_quality_report"].failure_risk == 27
    assert result["code_quality_report"].engine_risk == RISK


async def test_unrecognized_engine_dimensions_remain_available_as_raw_measurements(environment, monkeypatch):
    _, user, node, _ = environment
    changed = deepcopy(QUALITY)
    changed["dimension_scores"]["future_dimension"] = 17
    monkeypatch.setattr(QualityEngine, "calculate", AsyncMock(return_value=changed))
    result = await GitHubAnalysisService().analyze_with_ai(dict(PR), dict(RISK), use_deep_analysis=True, authorization=user)
    assert result["ai_analysis"]["error"] == "ENGINE_SCHEMA_INCOMPATIBLE"
    assert result["code_quality_report"] is None
    assert result["quality_result"] == changed and result["risk_result"] == RISK
    assert result["ai_run_data"]["status"] == "failed"
    node.assert_not_called()


@pytest.mark.parametrize("automation", [False, True])
@pytest.mark.parametrize("failed", [False, True])
async def test_real_github_sync_persists_scoped_success_or_failure(environment, monkeypatch, automation, failed):
    from domain.services.github_sync_service import GitHubSyncService
    import domain.services.github_sync_service as module
    db, user, node, _ = environment
    monkeypatch.setattr(module, "PRRepository", lambda: SimpleNamespace(
        store_revision=AsyncMock(side_effect=lambda doc, **kwargs: (doc, True))))
    service = GitHubSyncService()
    pr = {"number": 7, "title": "Review", "state": "open", "user": {"login": "author"},
          "head": {"sha": REVISION, "ref": "feature"}, "base": {"ref": "main"},
          "created_at": "2026-01-01T00:00:00Z", "html_url": "https://github.com/owner/repo/pull/7", "id": 7}
    service.api_service.fetch_pull_request_data = AsyncMock(return_value={"pr": pr,
        "files": [{"filename": "example.py"}], "commits": [], "check_runs": {"check_runs": []}})
    service.api_service.fetch_analysis_sources = AsyncMock(return_value=(PR["source_files"], []))
    service.analysis_service.analyze_risk = AsyncMock(return_value=deepcopy(RISK))
    if failed:
        node.return_value = {"errors": ["MODEL_TIMEOUT"]}
    result = await service.sync_pull_request("owner", "repo", 7, "P1", actor=None if automation else user)
    stored = await db.ai_runs.find_one({"id": result["ai_run_id"]})
    assert stored["status"] == ("failed" if failed else "completed")
    assert stored["owner_id"] == ("github-automation:P1" if automation else "A")
    assert stored["organization_id"] == "O1" and stored["project_id"] == "P1"
    assert result["risk_analysis"] == RISK
    assert stored["provenance"]["model_interpretation"] == "ADVISORY"


@pytest.mark.parametrize("actor", [None, "A"])
async def test_background_missing_or_revoked_authorization_keeps_static_results(environment, monkeypatch, actor):
    db, _, node, evidence = environment
    await db.users.update_one({"employee_id": "A"}, {"$set": {"role": "HR", "is_admin": True}})
    monkeypatch.setattr(code_quality.cq_service, "analyze_pr", AsyncMock(return_value=evidence))
    from intelligence.baselines.repository_baseline import RepositoryBaseline
    monkeypatch.setattr(RepositoryBaseline, "update_baseline", AsyncMock())
    await db.code_quality_runs.insert_one({"run_id": "no-authority"})
    body = code_quality.AnalyzeRequest(repository_id="P1", changed_files=["example.py"], pr_context={"source_files": PR["source_files"]})
    await code_quality._run_analysis("no-authority", body, None, actor_id=actor)
    stored = await db.code_quality_runs.find_one({"run_id": "no-authority"})
    assert stored["status"] == "completed" and stored["quality_score"] == 83
    assert stored["ai_status"] == "failed" and stored["ai_analysis"]["analysis"] is None
    node.assert_not_called()


async def test_cicd_uncaught_provider_error_is_sanitized_and_retains_log_measurements(environment, monkeypatch):
    _, user, _, _ = environment
    monkeypatch.setattr(cicd_logs, "check_ollama_connection", lambda: True)
    monkeypatch.setattr(cicd_logs, "invoke_agent", Mock(side_effect=RuntimeError("PRIVATE_PROVIDER_DATA")))
    response = await cicd_logs.analyze_cicd_log(cicd_logs.LogAnalysisRequest(log_content="ERROR: failed", log_type="build"), user)
    assert response.ai_status == "failed" and response.ai_run_id is None
    assert response.ai_analysis is None and "PRIVATE_PROVIDER_DATA" not in str(response)
    baseline = await cicd_logs.analyze_cicd_log(cicd_logs.LogAnalysisRequest(log_content="ERROR: failed", log_type="build", use_ai=False), user)
    assert (response.error_count, response.risk_score, response.risk_level) == (baseline.error_count, baseline.risk_score, baseline.risk_level)


@pytest.mark.parametrize("field", ["testing", "architecture"])
async def test_versioned_engine_units_allow_100_where_legacy_units_reject_it(field):
    from domain.models.code_quality_report import EngineQualityV1
    value = deepcopy(QUALITY)
    value["dimension_scores"][field] = 100
    result = EngineQualityV1.model_validate(value)
    assert getattr(result.dimension_scores, field) == 100
    legacy = dict(correctness=0, maintainability=0, security=0, testing=0, performance=0, architecture=0, readability=0)
    with pytest.raises(ValidationError):
        QualityBreakdown(**{**legacy, field: 100})


async def test_real_quality_engine_output_roundtrips_exactly_in_v1(environment):
    from domain.models.code_quality_report import EngineQualityV1
    _, _, _, evidence = environment
    result = await ORIGINAL_QUALITY_CALCULATE(QualityEngine(), evidence)
    parsed = EngineQualityV1.model_validate(result)
    assert parsed.model_dump(exclude={"schema_version"}) == result
    assert set(result["dimension_scores"]) == {"static_security", "testing", "complexity", "architecture", "duplication"}


@pytest.mark.parametrize("automation", [False, True])
async def test_real_code_guard_accepts_only_scoped_permissions(environment, monkeypatch, automation):
    from domain.services.internal_agent_adapter import GitHubAutomation, resolve_code_authority, interpret_code
    _, user, _, _ = environment
    monkeypatch.setattr(code_agent, "code_analysis_node", ORIGINAL_CODE_NODE)
    llm = Mock()
    llm.invoke.return_value = json.dumps({key: VALID[key] for key in ("analysis", "recommendations", "risk_level", "confidence")})
    factory = Mock(return_value=llm)
    monkeypatch.setattr(code_agent, "get_ollama_llm", factory)
    authorization = GitHubAutomation("P1", "owner/repo", REVISION) if automation else user
    authority = await resolve_code_authority(authorization, PR)
    result = await interpret_code({"evidence_summary": "Observed inputs"}, PR, authority)
    assert result["status"] == "completed"
    authority.user_context["permissions"] = []
    denied = await interpret_code({"evidence_summary": "Observed inputs"}, PR, authority)
    assert denied["status"] == "failed"
    assert factory.call_count == 1


async def test_cicd_upload_shared_path_rejects_hr_technical_ai(environment, monkeypatch):
    import io
    from fastapi import UploadFile, HTTPException
    _, user, _, _ = environment
    user.update(role="HR", is_admin=True)
    model = Mock(side_effect=AssertionError("HR must not invoke technical analysis"))
    monkeypatch.setattr(cicd_logs, "invoke_agent", model)
    with pytest.raises(HTTPException) as error:
        await cicd_logs.analyze_log_file(UploadFile(filename="example.log", file=io.BytesIO(b"ERROR: failed")), current_user=user)
    assert error.value.status_code == 403
    model.assert_not_called()


async def test_cicd_persistence_failure_clears_interpretation_fields(environment, monkeypatch):
    _, user, _, _ = environment
    monkeypatch.setattr(cicd_logs, "check_ollama_connection", lambda: True)
    monkeypatch.setattr(cicd_logs, "invoke_agent", Mock(return_value=VALID))
    monkeypatch.setattr(cicd_logs, "AIRunRepository", lambda: SimpleNamespace(create=AsyncMock(side_effect=RuntimeError("PRIVATE_DB_DATA"))))
    response = await cicd_logs.analyze_cicd_log(cicd_logs.LogAnalysisRequest(log_content="ERROR: failed", log_type="build"), user)
    assert response.ai_status == "failed" and response.ai_run_id is None
    assert response.root_cause is None and response.confidence is None and response.affected_component is None
    assert response.fix_recommendations == [] and "PRIVATE_DB_DATA" not in str(response)


@pytest.mark.parametrize("viewer,visible", [
    ({"employee_id": "A", "role": "DEVELOPER", "org_id": "O1", "project_ids": ["P1"]}, True),
    ({"employee_id": "B", "role": "HR", "is_admin": True, "org_id": "O1", "project_ids": ["P1"]}, False),
    ({"employee_id": "B", "role": "PM", "org_id": "O2"}, False),
])
async def test_code_quality_reads_apply_ai_scope_even_if_legacy_project_helper_allows(environment, monkeypatch, viewer, visible):
    db, _, _, _ = environment
    monkeypatch.setattr(code_quality, "get_accessible_project_ids", AsyncMock(return_value=["P1"]))
    await db.code_quality_runs.insert_one({"run_id": "readable-static", "repository_id": "P1", "status": "completed",
        "quality_score": 83, "created_at": "2026-11-13", "ai_analysis": {"analysis": "PRIVATE_AI_TEXT", "nested": {"secret": "PRIVATE_AI_TEXT"}},
        "ai_status": "completed", "ai_authorization_scope": {"access_version": "ai-run-access-v1", "owner_id": "A", "project_id": "P1", "organization_id": "O1"}})
    for result in [await code_quality.get_run("readable-static", viewer), await code_quality.get_latest_run("P1", viewer)]:
        assert result["quality_score"] == 83
        assert ("PRIVATE_AI_TEXT" in str(result)) is visible
        if not visible:
            assert result["ai_status"] == "unavailable" and result["ai_authorization_scope"] is None


async def test_unprovenanced_legacy_code_quality_ai_text_is_withheld(environment, monkeypatch):
    db, user, _, _ = environment
    monkeypatch.setattr(code_quality, "get_accessible_project_ids", AsyncMock(return_value=["P1"]))
    await db.code_quality_runs.insert_one({"run_id": "legacy", "repository_id": "P1", "status": "completed",
        "ai_analysis": {"analysis": "PRIVATE_LEGACY_TEXT"}, "quality_score": 83})
    result = await code_quality.get_run("legacy", user)
    assert result["quality_score"] == 83 and "PRIVATE_LEGACY_TEXT" not in str(result)
    assert result["ai_status"] == "unavailable"


async def test_code_quality_unknown_scope_is_withheld_and_skipped_state_is_preserved(environment):
    _, user, _, _ = environment
    legacy = {"repository_id": "P1", "ai_analysis": {"analysis": "PRIVATE"}, "ai_authorization_scope": "UNTRUSTED"}
    denied = await code_quality._visible_ai_result(legacy, user)
    assert denied["ai_status"] == "unavailable" and "PRIVATE" not in str(denied)
    skipped = await code_quality._visible_ai_result({**legacy, "ai_status": "skipped"}, user)
    assert skipped["ai_status"] == "skipped" and "PRIVATE" not in str(skipped)
