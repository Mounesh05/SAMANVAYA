"""Explicit internal start/read/pump operations. No routes, startup hooks or automatic triggers."""

import asyncio
import re
from uuid import uuid4

import httpx
from fastapi import HTTPException
from pymongo.errors import PyMongoError

from agents.pr_multi_agent_durable import DurablePRGraph, RetryableInference
from core.config import settings
from core.database import col
from domain.models.pr_multi_agent import ManualPRRequest, PRScope
from domain.services.pr_multi_agent_service import ManualPRWorkflowService
from domain.services.pr_multi_agent_evidence import pr_revisions
from repositories.pr_repository import PRRepository
from repositories.pr_workflow_repository import JOB_VERSION, PRWorkflowRepository, LeaseLost, InvalidWorkflowRecord, parse

HEARTBEAT_SECONDS = 20
# AI-01: two sequential specialists plus evidence work must fit in one execution.
EXECUTION_SECONDS = max(180, 2 * settings.PR_AGENT_SPECIALIST_TIMEOUT_SECONDS + 60)


class DurablePRWorkflowService:
    def __init__(self, manual=None, repository=None):
        self.manual = manual if manual is not None else ManualPRWorkflowService()
        self.repository = repository if repository is not None else PRWorkflowRepository()
        self.worker_id = uuid4().hex
        self._slot = asyncio.Lock()

    async def authorize_header(self, header, user):
        self.manual.check_enabled()
        identity = user.get("employee_id") if isinstance(user, dict) else None
        if header is None or not isinstance(identity, str) or identity != header["scope"].get("owner_id"):
            raise HTTPException(404, "Workflow not available")
        scope, request = parse(PRScope, header["scope"]), parse(ManualPRRequest, header["request"])
        if request.project_id != scope.project_id or request.pr_number != scope.pr_number or request.expected_head_sha != scope.head_sha:
            raise InvalidWorkflowRecord("Stored request conflicts with scope")
        access, owner, repo = await self.manual.resolver.authorize({"employee_id": identity}, request)
        if (access["owner_id"] != scope.owner_id or access["organization_id"] != scope.organization_id
                or owner + "/" + repo != scope.repository):
            raise HTTPException(403, "Workflow scope is no longer authorized")
        return scope, request

    @staticmethod
    def summary(row):
        return {"job_id": row["job_id"], "status": row["status"], "snapshot_id": row["snapshot_id"]}

    async def start(self, request, current_user):
        self.manual.check_enabled()
        request = request if isinstance(request, ManualPRRequest) else ManualPRRequest.model_validate(request)
        async with asyncio.timeout(75):
            access, owner, repo = await self.manual.resolver.authorize(current_user, request)
            pr = await self.manual.resolver.api.client.get_pull_request(owner, repo, request.pr_number)
            head, base = pr_revisions(pr, owner + "/" + repo, request.pr_number)
            if request.expected_head_sha is not None and request.expected_head_sha != head:
                raise HTTPException(409, "Requested PR revision changed")
            scope = PRScope(owner_id=access["owner_id"], organization_id=access["organization_id"], project_id=request.project_id,
                            repository=owner + "/" + repo, pr_number=request.pr_number, head_sha=head, base_sha=base)
            key = self.repository.identity(scope)
            if await self.repository.header(key) is not None:
                return self.summary(await self.get(key, current_user))
            await self._enforce_quota(scope)
            pinned = ManualPRRequest(project_id=request.project_id, pr_number=request.pr_number, expected_head_sha=head)
            snapshot = await self.manual.resolver.resolve(current_user, pinned)
            if snapshot.scope != scope:
                raise HTTPException(409, "PR scope changed during job creation")
            await self.manual.authorize_snapshot({"actor_id": scope.owner_id, "request": pinned, "snapshot": snapshot})
            await self.repository.ensure_indexes()
            key = await self.repository.create(pinned, snapshot)
            return self.summary(await self.get(key, current_user))

    async def _enforce_quota(self, scope):
        """AI-02: bounded queue with per-requester and per-organisation limits."""
        counts = await self.repository.active_counts(scope.owner_id, scope.organization_id)
        if counts["actor"] >= settings.PR_WORKFLOW_MAX_ACTIVE_PER_ACTOR:
            raise HTTPException(429, "You already have the maximum number of advisory analyses in progress. "
                                     "Wait for one to finish or cancel it.")
        if counts["organization"] >= settings.PR_WORKFLOW_MAX_ACTIVE_PER_ORG:
            raise HTTPException(429, "Your organisation has the maximum number of advisory analyses in progress. Retry later.")
        if counts["total"] >= settings.PR_WORKFLOW_MAX_ACTIVE_TOTAL:
            raise HTTPException(503, "The advisory analysis queue is full. Retry later.")

    async def cancel(self, key, current_user):
        """AI-02: the requester stops their own queued or running analysis."""
        self.manual.check_enabled()
        header = await self.repository.header(key)
        scope, _ = await self.authorize_header(header, current_user)
        if header["status"] not in ("PENDING", "RUNNING", "RETRY_WAIT"):
            raise HTTPException(409, "This analysis has already finished")
        if not await self.repository.cancel(key, scope.owner_id):
            raise HTTPException(409, "This analysis has already finished")
        return await self.get(key, current_user)

    async def get(self, key, current_user):
        self.manual.check_enabled()
        header = await self.repository.header(key)
        scope, _ = await self.authorize_header(header, current_user)
        # Authorization is resolved from current account data before reading any evidence/model fields.
        row = await self.repository.collection.find_one({"_id": key,
            **{"scope." + field: value for field, value in scope.model_dump(mode="json").items()}})
        if row is None:
            raise HTTPException(404, "Workflow not available")
        self.repository.validate(row)
        await self.authorize_header(header, current_user)
        return {key: value for key, value in row.items() if key != "_id"}

    async def lookup_report(self, request, repository, user):
        self.manual.check_enabled()
        access, owner, name = await self.manual.resolver.authorize(user, request)
        linked = f"{owner}/{name}"
        if repository.casefold() != linked.casefold():
            raise HTTPException(409, "The linked repository changed. Refresh the task evidence.")
        project = PRRepository._project_scope([request.project_id], access["organization_id"])
        prs = await col("pull_requests").find({
            **project, "repo_id": {"$regex": "^" + re.escape(linked) + "$", "$options": "i", "$not": {"$type": "array"}},
            "pr_number": {"$eq": request.pr_number, "$not": {"$type": "array"}},
        }, {"head_sha": 1}).limit(2).to_list(2)
        if len(prs) != 1 or prs[0].get("head_sha") != request.expected_head_sha:
            raise HTTPException(409, "The synchronized PR head changed or is ambiguous. Refresh the task evidence.")
        identities = await self.repository.collection.find({
            "schema_version": JOB_VERSION, "scope.owner_id": access["owner_id"],
            "scope.organization_id": access["organization_id"], "scope.project_id": request.project_id,
            "scope.repository": linked, "scope.pr_number": request.pr_number, "scope.head_sha": request.expected_head_sha,
        }, {"_id": 1}).limit(2).to_list(2)
        if len(identities) > 1:
            raise HTTPException(409, "Multiple base revisions match this head. Open the intended analysis by ID.")
        if not identities:
            return None
        # Reuse the private job read, including current permissions and immutable report validation.
        row = await self.get(identities[0]["_id"], user)
        return row.get("report")

    async def _heartbeat(self, lease):
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            if not await self.repository.renew(lease):
                raise LeaseLost("Heartbeat lost ownership")

    async def execute(self, key):
        self.manual.check_enabled()
        async with self._slot:
            lease = await self.repository.claim(key, self.worker_id)
            if lease is None:
                return
            work = beat = None
            try:
                async with asyncio.timeout(EXECUTION_SECONDS):
                    header = await self.repository.header(key)
                    _, request = await self.authorize_header(header, {"employee_id": lease.scope.owner_id})
                    graph = DurablePRGraph(self.manual, self.repository, lease).compiled
                    work = asyncio.create_task(graph.ainvoke({"actor_id": lease.scope.owner_id, "request": request},
                                                            config={"recursion_limit": 10}))
                    beat = asyncio.create_task(self._heartbeat(lease))
                    done, _ = await asyncio.wait((work, beat), return_when=asyncio.FIRST_COMPLETED)
                    if work in done:
                        await work
                    else:
                        await beat
            except LeaseLost:
                pass
            except RetryableInference as error:
                await self._fail(lease, "TRANSIENT_MODEL", error.code, retry=True)
            except HTTPException as error:
                retry = error.status_code >= 500
                await self._fail(lease, "TRANSIENT_SOURCE" if retry else "AUTHORIZATION_OR_SCOPE",
                                 "SOURCE_UNAVAILABLE" if retry else "AUTHORIZATION_OR_SCOPE_REVOKED", retry=retry)
            except (TimeoutError, httpx.HTTPError):
                await self._fail(lease, "TRANSIENT_INFRASTRUCTURE", "EXECUTION_UNAVAILABLE", retry=True)
            except InvalidWorkflowRecord:
                await self._fail(lease, "INTEGRITY", "INVALID_STORED_WORKFLOW")
            except PyMongoError:
                # A write acknowledgement may have been lost. Never overwrite an uncertain result;
                # the next owner reconciles the atomically stored document after lease expiry.
                pass
            except Exception:
                await self._fail(lease, "INTERNAL", "WORKFLOW_INTERNAL_FAILURE")
            finally:
                for task in (work, beat):
                    if task is not None:
                        task.cancel()
                await asyncio.gather(*(task for task in (work, beat) if task is not None), return_exceptions=True)

    async def _fail(self, lease, category, code, retry=False):
        try:
            await self.repository.fail(lease, category, code, retry=retry)
        except (LeaseLost, PyMongoError):
            pass

    async def run_ready(self, limit=20):
        """Explicit restart/recovery pump; callers await it. Never registered at application startup."""
        self.manual.check_enabled()
        await self.repository.ensure_indexes()
        for key in await self.repository.ready_ids(limit):
            await self.execute(key)
