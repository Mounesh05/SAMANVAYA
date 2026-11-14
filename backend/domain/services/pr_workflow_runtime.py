"""One lifecycle-owned sequential poller; MongoDB leases fence competing processes."""

import asyncio
import logging

from fastapi import HTTPException

from core.config import settings
from domain.services.pr_workflow_durable import DurablePRWorkflowService
from domain.services.pr_multi_agent_service import ManualPRWorkflowService

logger = logging.getLogger(__name__)


def require_manual_workflow():
    ManualPRWorkflowService.check_enabled()
    if not settings.PR_MULTI_AGENT_MANUAL_ENABLED:
        raise HTTPException(404, "Manual PR analysis is disabled")


class PRWorkflowRuntime:
    poll_seconds = 2

    def __init__(self, service_factory=DurablePRWorkflowService):
        self._factory = service_factory
        self._service = None
        self._task = None
        self._wake = asyncio.Event()
        self._intake = asyncio.Lock()
        self._lifecycle = asyncio.Lock()

    @property
    def service(self):
        if self._service is None:
            self._service = self._factory()
        return self._service

    @property
    def running(self):
        return self._task is not None and not self._task.done()

    async def start(self):
        async with self._lifecycle:
            try:
                require_manual_workflow()
            except HTTPException:
                return
            if not self.running:
                self._task = asyncio.create_task(self._loop(), name="manual-pr-workflow")

    async def stop(self):
        async with self._lifecycle:
            if self._task is not None:
                self._task.cancel()
                await asyncio.gather(self._task, return_exceptions=True)
                self._task = None

    async def submit(self, request, user):
        require_manual_workflow()
        if not self.running:
            raise HTTPException(503, "Manual PR analysis worker is unavailable")
        # Do not create a background task per request or accumulate evidence-collection waiters.
        if self._intake.locked():
            raise HTTPException(429, "Another manual request is being prepared. Retry shortly.")
        async with self._intake:
            result = await self.service.start(request, user)
        self._wake.set()
        return result

    async def _loop(self):
        while True:
            try:
                require_manual_workflow()
            except HTTPException:
                return
            self._wake.clear()
            try:
                await self.service.run_ready(limit=1)
            except Exception as error:
                logger.warning("Manual PR workflow poll failed (%s); retrying", type(error).__name__)
            try:
                await asyncio.wait_for(self._wake.wait(), self.poll_seconds)
            except TimeoutError:
                pass
