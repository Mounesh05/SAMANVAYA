"""Scoped internal interpretation adapters. Model output remains advisory."""

import asyncio
import re
from dataclasses import dataclass
from copy import deepcopy

from fastapi import HTTPException

from agents.parsers import CICDFailureResult, CodeAnalysisResult
from agents.state import AgentState
from core.permissions import Permission
from domain.models.performance_evidence import canonical_digest
from domain.services.ai_evidence_service import _repository
from domain.services.ai_run_access import ACCESS_VERSION, invocation_scope, permissions
from domain.services.auth_service import AuthService
from repositories.project_repository import ProjectRepository
from repositories.user_repository import UserRepository


@dataclass(frozen=True)
class GitHubAutomation:
    """Server-constructed job identity, bound to one fetched PR revision."""
    project_id: str
    repository: str
    revision: str


@dataclass(frozen=True)
class CodeAuthority:
    scope: dict
    user_context: dict
    basis: str


async def resolve_code_authority(authorization, context, operation="github_sync"):
    project_id = context.get("project_id")
    if isinstance(authorization, GitHubAutomation):
        if (operation != "github_sync" or authorization.project_id != project_id
                or authorization.repository != context.get("repo") or authorization.revision != context.get("commit_sha")
                or not re.fullmatch(r"[a-fA-F0-9]{40}", authorization.revision or "")):
            raise HTTPException(403, "AUTOMATION_SCOPE_MISMATCH")
        project = await ProjectRepository().find_by_id(project_id)
        if (not project or not isinstance(project.get("org_id"), str) or not project["org_id"]
                or project.get("status", "active") != "active"):
            raise HTTPException(403, "AUTOMATION_PROJECT_UNAVAILABLE")
        owner, repo = await _repository(project_id, project["org_id"])
        if (owner + "/" + repo).casefold() != authorization.repository.casefold():
            raise HTTPException(403, "AUTOMATION_REPOSITORY_MISMATCH")
        identity = "github-automation:" + project_id
        scope = dict(access_version=ACCESS_VERSION, owner_id=identity, project_id=project_id, organization_id=project["org_id"])
        return CodeAuthority(scope, {"employee_id": identity, "role": "AUTOMATION",
            "permissions": [Permission.VIEW_AI_EVALUATION.value], "accessible_project_ids": [project_id]},
            "SERVER_OWNED_GITHUB_REVISION")
    if (not isinstance(authorization, dict) or not isinstance(authorization.get("employee_id"), str)
            or not authorization["employee_id"]):
        raise HTTPException(403, "AUTHORIZATION_MISSING")
    account = await UserRepository().find_by_employee_id(authorization["employee_id"])
    if not account or not account.get("is_active", True):
        raise HTTPException(403, "CURRENT_ACCOUNT_UNAVAILABLE")
    user = AuthService._token_payload(account)
    user.update(role=user["organizational_role"], is_admin=user["system_access"] == "ADMIN")
    allowed = permissions(user)
    if (user["role"] == "HR" or Permission.VIEW_AI_EVALUATION not in allowed
            or operation == "code_quality" and Permission.TRIGGER_CODE_ANALYSIS not in allowed
            or operation == "github_sync" and Permission.SYNC_PR not in allowed and user["role"] not in {"LEAD", "PM"}):
        raise HTTPException(403, "CODE_INTERPRETATION_FORBIDDEN")
    scope = await invocation_scope(user, {"project_id": project_id})
    if not project_id:
        raise HTTPException(403, "PROJECT_SCOPE_REQUIRED")
    if context.get("repo"):
        owner, repo = await _repository(project_id, scope["organization_id"])
        if (owner + "/" + repo).casefold() != context["repo"].casefold():
            raise HTTPException(403, "REPOSITORY_SCOPE_MISMATCH")
    return CodeAuthority(scope, {"employee_id": scope["owner_id"], "role": user["role"],
        "permissions": [permission.value for permission in allowed], "accessible_project_ids": [project_id]},
        "CURRENT_AUTHENTICATED_ACCOUNT")


def failed_interpretation(code, unavailable=False):
    return {"status": "unavailable" if unavailable else "failed", "analysis": None,
            "recommendations": [], "critical_issues": [], "review_focus": None, "confidence": None,
            "risk_level": None, "error": code, "errors": [code]}


def validated_interpretation(result, kind="code"):
    if not isinstance(result, dict):
        return failed_interpretation("INVALID_AGENT_RESULT")
    if result.get("errors"):
        errors = str(result["errors"])
        code = next((value for value in ("MODEL_TIMEOUT", "MODEL_UNAVAILABLE", "INVALID_MODEL_RESPONSE") if value in errors), "AGENT_FAILED")
        return failed_interpretation(code, unavailable=code == "MODEL_UNAVAILABLE")
    model: type[CodeAnalysisResult] | type[CICDFailureResult] = CodeAnalysisResult if kind == "code" else CICDFailureResult
    values = {key: result[key] for key in model.model_fields if key != "schema_version" and key in result}
    if kind == "cicd":
        values.update(root_cause=result.get("analysis"), fix_recommendations=result.get("recommendations"))
    try:
        parsed = model.model_validate(values)
    except ValueError:
        return failed_interpretation("INVALID_AGENT_RESULT")
    if isinstance(parsed, CICDFailureResult):
        return {"status": "completed", "analysis": parsed.root_cause, "recommendations": parsed.fix_recommendations,
                "confidence": parsed.confidence, "urgency": parsed.urgency, "affected_component": parsed.affected_component,
                "prevention": parsed.prevention, "errors": []}
    return {"status": "completed", "analysis": parsed.analysis, "recommendations": parsed.recommendations,
            "confidence": parsed.confidence, "risk_level": parsed.risk_level,
            "critical_issues": getattr(parsed, "critical_issues", []), "review_focus": getattr(parsed, "review_focus", None),
            "errors": []}


async def interpret_code(evidence, context, authority, evidence_available=True, quality_result=None, risk_result=None):
    from agents.code_agent import code_analysis_node
    from agents.llm_provider import check_ollama_connection
    if not isinstance(authority, CodeAuthority) or authority.scope["project_id"] != context.get("project_id"):
        return failed_interpretation("AUTHORIZATION_MISSING")
    if not evidence or not evidence_available:
        return failed_interpretation("MISSING_EVIDENCE")
    try:
        if not await asyncio.to_thread(check_ollama_connection):
            return failed_interpretation("MODEL_UNAVAILABLE", unavailable=True)
        state: AgentState = {
            "task_type": "code_review", "evidence": evidence, "context": context,
            "user_context": authority.user_context, "agent_history": [], "errors": [],
            "quality_result": quality_result, "risk_result": risk_result}
        result = await asyncio.to_thread(code_analysis_node, deepcopy(state))
        interpretation = validated_interpretation(result)
        findings = evidence.get("static_analysis", {}).get("findings")
        if isinstance(findings, list) and interpretation["status"] == "completed":
            citations = {f"[{f.get('file')}:{f.get('line')} {f.get('rule_id')}]" for f in findings[:20]
                         if isinstance(f, dict) and f.get("file") and f.get("line") and f.get("rule_id")}
            for field in ("recommendations", "critical_issues"):
                interpretation[field] = [text for text in interpretation[field] if any(c in text for c in citations)]
        return interpretation
    except Exception:
        return failed_interpretation("MODEL_UNAVAILABLE", unavailable=True)


def internal_run(authority, kind, evidence, context, interpretation, triggered_by):
    """Record scope and observation provenance independently of interpretation success."""
    observation = {"evidence": evidence, "context": context}
    return {**authority.scope, "agent_type": kind,
            "input_data": {"server_observed": {"evidence": evidence}, "caller_supplied": {"context": context}},
            "provenance": {"schema_version": "ai-internal-observation-v1", "model_interpretation": "ADVISORY",
                "source": {"status": "SERVER_OBSERVED", "content_sha256": canonical_digest(observation),
                           "source_revision": context.get("commit_sha")}, "caller_context_status": "UNVERIFIED",
                "authorization_basis": authority.basis},
            "output_data": interpretation, "status": "completed" if interpretation["status"] == "completed" else "failed",
            "error_message": "; ".join(interpretation.get("errors", [])) or None,
            "model_name": "ollama", "triggered_by": triggered_by}
