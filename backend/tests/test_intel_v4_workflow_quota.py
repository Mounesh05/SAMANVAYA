"""v4 MA-19: the advisory-job quota holds under simultaneous admissions.

``start`` counted active jobs, then awaited evidence resolution and snapshot
authorization, and only then inserted the job. Six simultaneous starts by one
requester (limit 3) all passed the count and six jobs were queued.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from core.config import settings
from domain.services.pr_workflow_durable import DurablePRWorkflowService
from repositories.pr_workflow_repository import JOB_VERSION, PRWorkflowRepository

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def with_options(monkeypatch):
    from mongomock_motor import AsyncMongoMockCollection

    def shim(collection, **options):  # same test shim as test_pr_workflow_durability
        delegate = AsyncMongoMockCollection.__getattr__(collection, "with_options")(**options)
        return AsyncMongoMockCollection(collection.database, delegate)
    monkeypatch.setattr(AsyncMongoMockCollection, "with_options", shim, raising=False)


class Repository(PRWorkflowRepository):
    """Real ``active_counts``; a minimal job document instead of a full snapshot."""

    async def ensure_indexes(self):
        return None

    async def create(self, request, snapshot):
        await asyncio.sleep(0)
        key = self.identity(snapshot.scope)
        await self.collection.insert_one({"_id": key, "job_id": key, "schema_version": JOB_VERSION, "status": "PENDING",
                                          "scope": snapshot.scope.model_dump(mode="json"), "snapshot_id": "s"})
        return key


def service(db):
    async def resolve(user, request):
        await asyncio.sleep(0.01)  # evidence acquisition (GitHub reads) takes real time
        from domain.models.pr_multi_agent import PRScope
        return SimpleNamespace(scope=PRScope(owner_id="E5", organization_id="ORG-A", project_id="P1", repository="o/r",
                                             pr_number=request.pr_number, head_sha="a" * 40, base_sha="b" * 40))

    async def get_pr(owner, repo, number):
        return {"number": number, "head": {"sha": "a" * 40}, "base": {"sha": "b" * 40, "repo": {"full_name": "o/r"}}}

    resolver = SimpleNamespace(authorize=AsyncMock(return_value=({"owner_id": "E5", "organization_id": "ORG-A"}, "o", "r")),
                               resolve=resolve, api=SimpleNamespace(client=SimpleNamespace(get_pull_request=get_pr)))
    manual = SimpleNamespace(check_enabled=lambda: None, resolver=resolver, authorize_snapshot=AsyncMock())
    instance = DurablePRWorkflowService(manual=manual, repository=Repository(db.pr_multi_agent_jobs))
    instance.get = AsyncMock(side_effect=lambda key, user: {"job_id": key, "status": "PENDING", "snapshot_id": "s"})
    return instance


async def test_simultaneous_starts_cannot_exceed_the_requester_quota(mock_db):
    workflow = service(mock_db)
    results = await asyncio.gather(*(workflow.start({"project_id": "P1", "pr_number": n}, {"employee_id": "E5"})
                                     for n in range(1, 7)), return_exceptions=True)
    rejected = [r for r in results if isinstance(r, HTTPException)]
    assert await mock_db.pr_multi_agent_jobs.count_documents({}) == settings.PR_WORKFLOW_MAX_ACTIVE_PER_ACTOR
    assert len(rejected) == 6 - settings.PR_WORKFLOW_MAX_ACTIVE_PER_ACTOR
    assert {r.status_code for r in rejected} == {429}


async def test_sequential_starts_within_quota_are_admitted(mock_db):
    workflow = service(mock_db)
    for n in range(1, settings.PR_WORKFLOW_MAX_ACTIVE_PER_ACTOR + 1):
        await workflow.start({"project_id": "P1", "pr_number": n}, {"employee_id": "E5"})
    assert await mock_db.pr_multi_agent_jobs.count_documents({}) == settings.PR_WORKFLOW_MAX_ACTIVE_PER_ACTOR
