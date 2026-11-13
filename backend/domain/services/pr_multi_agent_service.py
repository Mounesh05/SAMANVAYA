"""Manual internal entry point. No HTTP route, persistence, worker or automatic trigger."""

import asyncio

import httpx
from fastapi import HTTPException

from agents.pr_multi_agent import PRMultiAgentGraph, PRWorkflowState, code_specialist, qa_specialist
from core.config import settings
from domain.models.pr_multi_agent import ManualPRRequest
from domain.services.github_api_service import GitHubAPIService
from domain.services.pr_multi_agent_evidence import PREvidenceResolver, pr_revisions


class ManualPRWorkflowService:
    def __init__(self, api=None, code_specialist=code_specialist, qa_specialist=qa_specialist):
        self.resolver = PREvidenceResolver(api or GitHubAPIService())
        self.code_specialist = code_specialist
        self.qa_specialist = qa_specialist
        self.model_name = settings.OLLAMA_MODEL
        self.graph = PRMultiAgentGraph(self).compiled

    @staticmethod
    def check_enabled():
        if not settings.PR_MULTI_AGENT_INTERNAL_ENABLED or settings.ENVIRONMENT not in {"development", "test"}:
            raise HTTPException(404, "The internal manual PR workflow is disabled")

    async def authorize_snapshot(self, state, check_revision=False):
        self.check_enabled()
        scope = state["snapshot"].scope
        access, owner, repo = await self.resolver.authorize({"employee_id": state["actor_id"]}, state["request"])
        if (access["owner_id"] != scope.owner_id or access["organization_id"] != scope.organization_id
                or owner + "/" + repo != scope.repository):
            raise HTTPException(403, "Snapshot authority changed")
        if not check_revision:
            return True
        pr = await self.resolver.api.client.get_pull_request(owner, repo, scope.pr_number)
        return pr_revisions(pr, scope.repository, scope.pr_number) == (scope.head_sha, scope.base_sha)

    async def run(self, request, current_user):
        self.check_enabled()
        request = request if isinstance(request, ManualPRRequest) else ManualPRRequest.model_validate(request)
        identity = current_user.get("employee_id") if isinstance(current_user, dict) else None
        if not isinstance(identity, str) or not identity:
            raise HTTPException(403, "An authenticated account is required")
        try:
            async with asyncio.timeout(180):
                initial: PRWorkflowState = {"actor_id": identity, "request": request}
                state = await self.graph.ainvoke(initial, config={"recursion_limit": 10})
                return state["report"]
        except (TimeoutError, httpx.HTTPError):
            raise HTTPException(503, "Pinned PR evidence is unavailable or the internal execution deadline expired") from None
