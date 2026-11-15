"""
Background check of linked repositories for new or changed pull requests.

GitHub can only push webhooks to a public address. An install on localhost
(or behind a firewall) never receives them, so pull requests would only
arrive when someone clicks "Sync PR". This poller closes that gap: every
GITHUB_POLL_INTERVAL_SECONDS it lists the most recently updated pull requests
of each repository linked to a project (github_project_configs) and syncs
the ones whose GitHub `updated_at` changed since the last successful sync.

- Unchanged pull requests are skipped, so analysis (and the AI review) does
  not re-run for nothing.
- A pull request is marked as seen only after its sync succeeds, so a failed
  sync is retried on the next round.
- Syncing is idempotent (PR revisions and task auto-progress), so a second
  API instance doing the same work is harmless.
- It does nothing without a GitHub token or with an interval of 0.
"""

import asyncio
import logging
from typing import Optional

from core.config import settings
from core.database import col

logger = logging.getLogger(__name__)

POLLER_ACTOR = "github-poller"
PRS_PER_REPOSITORY = 20


class GitHubPRPoller:
    def __init__(self, interval_seconds: Optional[int] = None, sync_service=None):
        self.interval_seconds = settings.GITHUB_POLL_INTERVAL_SECONDS if interval_seconds is None else interval_seconds
        self._sync_service = sync_service
        self._task: Optional[asyncio.Task] = None

    @property
    def enabled(self) -> bool:
        return bool(settings.GITHUB_TOKEN) and self.interval_seconds > 0

    def _service(self):
        if self._sync_service is None:
            from domain.services.github_sync_service import GitHubSyncService
            self._sync_service = GitHubSyncService()
        return self._sync_service

    async def poll_once(self) -> dict:
        """One round over every linked repository. Returns counts for logging and tests."""
        summary = {"repositories": 0, "checked": 0, "synced": 0, "failed": 0}
        configs = await col("github_project_configs").find({}, {"_id": 0}).to_list(None)
        service = self._service()
        for config in configs:
            owner, repo, project_id = config.get("repository_owner"), config.get("repository_name"), config.get("project_id")
            if not (owner and repo and project_id):
                continue
            summary["repositories"] += 1
            try:
                pull_requests = await service.api_service.list_pull_requests(
                    owner, repo, state="all", per_page=PRS_PER_REPOSITORY)
            except Exception:
                logger.warning("PR poll: could not list pull requests of %s/%s", owner, repo, exc_info=True)
                summary["failed"] += 1
                continue
            for pr in pull_requests or []:
                summary["checked"] += 1
                key = f"{project_id}:{owner}/{repo}#{pr.get('number')}"
                seen = await col("github_pr_poll_state").find_one({"_id": key})
                if seen and seen.get("updated_at") == pr.get("updated_at"):
                    continue
                try:
                    await service.sync_pull_request(owner, repo, pr["number"], project_id, triggered_by=POLLER_ACTOR)
                except Exception:
                    logger.warning("PR poll: sync of %s failed; will retry next round", key, exc_info=True)
                    summary["failed"] += 1
                    continue
                await col("github_pr_poll_state").update_one(
                    {"_id": key}, {"$set": {"updated_at": pr.get("updated_at")}}, upsert=True)
                summary["synced"] += 1
        return summary

    async def _loop(self):
        while True:
            try:
                summary = await self.poll_once()
                if summary["synced"] or summary["failed"]:
                    logger.info("PR poll: %s", summary)
            except Exception:
                logger.exception("PR poll round failed; will retry")
            await asyncio.sleep(self.interval_seconds)

    async def start(self):
        if not self.enabled:
            logger.info("PR poll is off (no GitHub token or interval 0)")
            return
        logger.info("PR poll every %ss for linked repositories", self.interval_seconds)
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None


pr_poller = GitHubPRPoller()
