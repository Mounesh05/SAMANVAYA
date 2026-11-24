"""Explicit Phase 0 characterization; passing probes do NOT mean bugs are fixed.

Run from backend/ with its configured Python environment. No live inference,
GitHub calls, real Mongo writes, production configuration or runtime patches.
Temporary mocks are process-local and use synthetic accounts and evidence.
"""

import asyncio
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
os.environ.update(SECRET_KEY="phase0-synthetic-secret-never-production-12345",
                  DB_NAME="phase0_synthetic", OLLAMA_BASE_URL="http://localhost:11434")

import httpx  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from mongomock_motor import AsyncMongoMockClient  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from agents import code_agent, hr_agent, qa_agent, cicd_agent, supervisor  # noqa: E402
from agents.llm_provider import get_ollama_llm  # noqa: E402
from agents.parsers import CodeAnalysisResult  # noqa: E402
from api.routes import ai  # noqa: E402
from core import authorization, database  # noqa: E402
from core.dependencies import get_current_user  # noqa: E402
from core.permissions import Permission  # noqa: E402
from domain.models.ai_run import AIRun  # noqa: E402
from domain.services.github_analysis_service import GitHubAnalysisService  # noqa: E402
from domain.models.risk_configuration import RiskConfiguration  # noqa: E402
from intelligence.evidence.models import CodeQualityEvidence, SecurityEvidence, TestingEvidence, ArchitectureEvidence  # noqa: E402
from intelligence.quality_engine import QualityEngine  # noqa: E402
from intelligence.risk_engine import RiskEngine  # noqa: E402
from repositories.ai_run_repository import AIRunRepository  # noqa: E402
from repositories.project_repository import ProjectRepository  # noqa: E402


def state(role="LEAD"):
    return {"evidence": {}, "context": {}, "errors": [], "agent_history": [],
            "user_context": {"role": role, "permissions": [
                Permission.VIEW_AI_EVALUATION.value, Permission.VIEW_EMPLOYEE_DIRECTORY.value]}}


async def main():
    checks = []
    snapshots = {}
    for node, role in [(code_agent.code_analysis_node, "LEAD"), (hr_agent.hr_assistant_node, "HR")]:
        with patch("agents.llm_provider.OllamaLLM") as constructor:
            result = node(state(role))
        assert "unexpected keyword argument 'response_format'" in result["errors"][0]
        constructor.assert_not_called()
        checks.append(node.__name__ + ": real provider signature fails before network")
    llm = get_ollama_llm()
    assert "timeout" not in type(llm).model_fields
    assert llm._client._client.timeout.read is None
    assert llm._async_client._client.timeout.read is None
    assert llm.format == "json"
    checks.append("real provider clients: JSON mode, unbounded read timeout")

    for task in supervisor.AGENT_REGISTRY:
        calls = []
        nodes = {name: (lambda s, name=name: calls.append(name) or {
            "analysis": "Synthetic advisory", "agent_history": [name]}) for name in supervisor.AGENT_REGISTRY}
        with patch.dict(supervisor.AGENT_REGISTRY, nodes):
            result = supervisor.invoke_agent(task, state())
        assert calls == [task] and not result["errors"]
    calls = []
    with patch.dict(supervisor.AGENT_REGISTRY, {"hr_assistant": lambda s: calls.append("hr_assistant") or {"analysis": "HR only"}}):
        supervisor.invoke_agent("code_review", state("HR"))
    assert calls == ["hr_assistant"]
    checks.append("six legacy routes: one selected specialist; HR forced to HR")

    fake_llm = Mock()
    fake_llm.invoke.return_value = json.dumps({"root_cause": "Synthetic cause", "confidence": 0.9})
    with patch.object(cicd_agent, "get_ollama_llm", return_value=fake_llm):
        result = supervisor.invoke_agent("cicd_analysis", state())
    assert "no validated analysis" in result["errors"][0] and result["analysis"] is None
    checks.append("CI/CD valid JSON cannot be parsed by line-based legacy parser")
    fake_llm.invoke.return_value = "malformed model output"
    with patch.object(code_agent, "get_ollama_llm", return_value=fake_llm):
        result = supervisor.invoke_agent("code_review", state())
    assert not result["errors"] and result["analysis"] == "Failed to parse AI response"
    assert result["quality_score"] == 0.0
    checks.append("after bypassing known signature bug: code parse fallback is successful zero-score output")
    parsed = CodeAnalysisResult.model_validate({"analysis": "Synthetic", "quality_score": float("nan"),
                                                "confidence": 999, "risk_level": "invented"})
    assert parsed.confidence == 999 and parsed.quality_score != parsed.quality_score
    checks.append("legacy parser accepts NaN, out-of-range confidence and arbitrary risk label")
    simple = await GitHubAnalysisService()._analyze_simple({"project_id": "P1", "title": "Synthetic"}, {}, "synthetic")
    assert simple["ai_analysis"]["analysis"] is None and simple["ai_run_data"]["status"] == "completed"
    assert "project_id" not in simple["ai_run_data"]["input_data"]["context"]
    checks.append("GitHub simple adapter: missing permissions yields completed null analysis and unscoped run")

    # Existing engine formulas run unmodified; only configuration/analyzer I/O
    # and the advisory model are synthetic. No repository or model execution.
    evidence = CodeQualityEvidence(repository_id="P1", primary_language="python", detected_languages=["python"],
                                   security=SecurityEvidence(critical_count=1))
    config = SimpleNamespace(get_configuration=AsyncMock(return_value=RiskConfiguration(name="Synthetic defaults", created_by="audit")))
    analyzer = SimpleNamespace(analyze=AsyncMock(return_value=evidence))
    with patch("intelligence.quality_engine.get_risk_config_service", return_value=config), patch(
            "domain.services.risk_config_service.get_risk_config_service", return_value=config), patch(
            "intelligence.analyzers.registry.get_analyzers_for_profile", return_value={"python": analyzer}), patch.object(
            code_agent, "code_analysis_node", return_value={"analysis": "Synthetic model claims perfection", "quality_score": 0,
                "failure_risk": 0, "risk_level": "low", "confidence": 1}):
        pr = {"pr_id": "SYNTHETIC", "pr_number": 1, "repo": "synthetic/repo", "project_id": "P1", "changed_files": ["module.py"]}
        try:
            await GitHubAnalysisService()._analyze_deep(pr, {}, "audit")
        except ValidationError as error:
            assert {e["loc"] for e in error.errors()} == {("testing",), ("architecture",)}
        else:
            raise AssertionError("Expected legacy quality-breakdown unit mismatch")
        checks.append("deep report nominal engine dimensions exceed legacy testing/architecture point caps")
        # A second, explicitly degraded synthetic case fits the legacy caps;
        # this permits testing authority separately from that confirmed defect.
        evidence = evidence.model_copy(update={"testing": TestingEvidence(coverage_percentage=0),
            "architecture": ArchitectureEvidence(layer_violations=[{"from": "x", "to": "y"}] * 10)})
        analyzer.analyze.return_value = evidence
        expected_quality = await QualityEngine().calculate(evidence)
        expected_risk = await RiskEngine().analyze_evidence(evidence)
        result = await GitHubAnalysisService()._analyze_deep(pr, {}, "audit")
    report = result["code_quality_report"]
    assert report.quality_score == expected_quality["quality_score"]
    assert report.failure_risk == expected_risk["risk_score"] and report.risk_level == expected_risk["risk_level"]
    snapshots["deterministic_authority"] = {"quality_score": report.quality_score, "risk_score": report.failure_risk,
                                            "risk_level": report.risk_level, "model_quality_and_risk": [0, 0]}
    checks.append("real quality/risk formulas survive conflicting synthetic model numbers in deep PR report")

    client = AsyncMongoMockClient()
    db = client.phase0_synthetic
    actor = {"employee_id": "A", "email": "a@synthetic.invalid", "role": "LEAD", "org_id": "O1", "project_ids": ["P1"]}
    app = FastAPI()
    app.include_router(ai.router, prefix="/api/ai")
    app.dependency_overrides[get_current_user] = lambda: actor
    with patch.object(database, "get_db", return_value=db), patch.object(authorization, "_project_repo", ProjectRepository()):
        # Rebind the repository after the database patch: no real project query.
        authorization._project_repo = ProjectRepository()
        await db.projects.insert_many([{"id": "P1", "org_id": "O1"}, {"id": "P2", "org_id": "O2"}])
        repo = AIRunRepository()
        private = await repo.create(AIRun(agent_type="cicd_analysis", triggered_by="b@synthetic.invalid",
            input_data={"evidence": {"log_excerpt": "SYNTHETIC_PRIVATE_LOG"}, "context": {"note": "SYNTHETIC_CONTEXT"}},
            output_data={"analysis": "Synthetic private summary"}, status="completed"))
        foreign = await repo.create(AIRun(agent_type="qa_analysis", triggered_by="b@synthetic.invalid",
            input_data={"context": {"project_id": "P2", "organization_id": "O2"}}, output_data={}, status="completed"))
        protected = await repo.create(AIRun(agent_type="performance_calibration_draft", triggered_by="synthetic",
                                           input_data={}, output_data={}))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://audit.invalid") as api:
            actor.update(role="DEVELOPER", project_ids=["P1"])
            response = await api.get("/api/ai/runs/" + private)
            assert response.status_code == 200 and "SYNTHETIC_PRIVATE_LOG" in response.text
            listing = await api.get("/api/ai/runs")
            assert private in [r["id"] for r in listing.json()]
            denied = await api.get("/api/ai/runs/" + foreign)
            assert denied.status_code == 403
            assert (await api.get("/api/ai/runs/" + protected)).status_code == 404
            snapshots["run_scope"] = {"unowned_unscoped": response.status_code, "unrelated_project": denied.status_code,
                                      "protected_scoring_artifact": 404}
            checks.append("AI-run HTTP reads: unowned unscoped allowed; unrelated scoped denied; protected artifacts hidden")
            actor.update(role="PM", org_id="O1")
            assert (await api.get("/api/ai/runs/" + foreign)).status_code == 200
            assert set(await authorization.get_accessible_project_ids(actor)) == {"P1", "P2"}
            await authorization.verify_project_access(actor, "P2")
            checks.append("PM role bypass and shared authorization helper cross organization boundaries")
            actor.update(role="HR")
            response = await api.get("/api/ai/runs/" + private)
            assert response.status_code == 200
            assert "evidence" not in response.json()["input_data"]
            assert response.json()["input_data"]["context"]["note"] == "SYNTHETIC_CONTEXT"
            checks.append("HR redaction removes input evidence but preserves arbitrary context and generated summary")
            actor.update(role="LEAD")
            fake_llm.invoke.return_value = json.dumps({"analysis": "Synthetic advisory", "risk_level": "low", "confidence": 0.5})
            body = {"task_type": "qa_analysis", "evidence": {"verification_state": "SERVER_VERIFIED", "test_coverage_pct": 100},
                    "context": {"project_id": "P2", "organization_id": "O2"}, "save_run": True}
            with patch.object(ai, "check_ollama_connection", return_value=True), patch.object(qa_agent, "get_ollama_llm", return_value=fake_llm):
                response = await api.post("/api/ai/invoke", json=body)
            assert response.status_code == 200 and response.json()["errors"] == []
            saved = await repo.get_by_id(response.json()["run_id"])
            assert saved.input_data["evidence"]["verification_state"] == "SERVER_VERIFIED"
            assert saved.input_data["context"]["project_id"] == "P2" and saved.status == "completed"
            assert "verification_state" not in response.json()
            snapshots["invoke_success_keys"] = sorted(response.json())
            checks.append("foreign project and caller verification flag persist unchanged; response has no trusted verification field")
            with patch.object(ai, "check_ollama_connection", return_value=False):
                response = await api.post("/api/ai/invoke", json=body)
            assert response.status_code == 503
            snapshots["model_unavailable"] = response.json()
            actor.update(role="DEVELOPER")
            response = await api.post("/api/ai/invoke", json=body)
            assert response.status_code == 403
            snapshots["permission_denied"] = response.json()
            response = await api.post("/api/ai/invoke", json={**body, "task_type": "unregistered"})
            assert response.status_code == 422
            snapshots["invalid_task_status"] = response.status_code
            checks.append("existing HTTP status contracts: invoke permission 403, model down 503, unknown task 422")
            app.dependency_overrides.clear()
            missing = await api.get("/api/ai/runs")
            invalid = await api.get("/api/ai/runs", headers={"Authorization": "Bearer not-a-jwt"})
            assert missing.status_code == 422 and invalid.status_code == 401
            snapshots["authentication"] = {"missing_header": missing.status_code, "invalid_token": invalid.status_code}
            checks.append("real auth dependency rejects missing header and invalid JWT without a DB lookup")
    client.close()
    print(json.dumps({"characterizations": len(checks), "checks": checks, "snapshots": snapshots}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
