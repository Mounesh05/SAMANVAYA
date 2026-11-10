"""
Deployment service: turns GitHub webhook events into deployment records for
the DORA metrics ("deployments" collection).

Sources
    deployment / deployment_status   GitHub Deployments API (environments)
    workflow_run                     a GitHub Actions workflow named in the
                                     project's GitHub config (deploy_workflow);
                                     completed runs on the default branch

Only deployments to a production environment (github_project_configs
.production_environments, default production / prod / live) count as
production; others are stored with production=False.

When a production deployment succeeds, it is compared with the previous
successful production deployment of the same project and environment
(GitHub compare API, one call):
    ahead / diverged  the new commits are stored (sha + committer date) for
                      change lead time
    behind            the deployed commit is OLDER: a rollback; the previous
                      deployment is marked as the one rolled back
    identical         a redeploy; no new commits
The first deployment of a project has no predecessor: only its head commit
is stored (its lead time covers that commit only).

Hotfixes: a ref starting with hotfix/ (or "hotfix" in the description).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.database import col
from intelligence.metrics.pull_requests import parse_time
from repositories.incident_repository import DeploymentRepository

logger = logging.getLogger(__name__)

DEFAULT_PRODUCTION = ("production", "prod", "live")
_STATE = {
    "success": "success",
    "failure": "failure",
    "error": "error",
    "pending": "in_progress",
    "queued": "in_progress",
    "in_progress": "in_progress",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _commit_time(commit: Dict[str, Any]) -> Optional[str]:
    """Committer date: when the change entered the repository's history."""
    info = commit.get("commit") or {}
    return (info.get("committer") or {}).get("date") or (info.get("author") or {}).get("date")


class DeploymentService:
    def __init__(self, github_client: Any = None, repository: Optional[DeploymentRepository] = None,
                 configs: Any = None) -> None:
        self._github = github_client
        self.deployments = repository or DeploymentRepository()
        self._configs = configs

    @property
    def github(self) -> Any:
        if self._github is None:
            from integrations.github.client import GitHubClient
            self._github = GitHubClient()
        return self._github

    async def _config(self, project_id: Optional[str]) -> Dict[str, Any]:
        if not project_id:
            return {}
        configs = self._configs if self._configs is not None else col("github_project_configs")
        return await configs.find_one({"project_id": project_id}, {"_id": 0}) or {}

    @staticmethod
    def _is_production(environment: Optional[str], config: Dict[str, Any]) -> bool:
        names = config.get("production_environments") or DEFAULT_PRODUCTION
        return str(environment or "").lower() in {n.lower() for n in names}

    # ── GitHub Deployments API ────────────────────────────────────
    async def _upsert_from_payload(self, event: Any, deployment: Dict[str, Any]) -> Dict[str, Any]:
        config = await self._config(event.project_id)
        ref = str(deployment.get("ref") or "")
        description = str(deployment.get("description") or "")
        doc_id = f"GH-{event.repository}-{deployment.get('id')}"
        fields = {
            "id": doc_id,
            "project_id": event.project_id,
            "repository": event.repository,
            "source": "github_deployment",
            "github_deployment_id": deployment.get("id"),
            "environment": deployment.get("environment"),
            "production": self._is_production(deployment.get("environment"), config),
            "sha": deployment.get("sha"),
            "ref": ref,
            "created_at": deployment.get("created_at") or _now(),
            "deployed_by": (deployment.get("creator") or {}).get("login"),
            "is_hotfix": ref.lower().startswith("hotfix/") or "hotfix" in description.lower(),
        }
        existing = await self.deployments.find_by_id(doc_id)
        if existing is not None:
            # a later event may carry less detail: never erase what is already known
            fields = {k: v for k, v in fields.items() if v is not None or k not in existing}
        if existing is None:
            fields["status"] = "in_progress"
        await self.deployments.upsert({"id": doc_id}, fields)
        return {**(existing or {}), **fields}

    async def record_deployment(self, event: Any) -> Optional[Dict[str, Any]]:
        deployment = event.payload.get("deployment") or {}
        if not event.project_id or not deployment.get("id"):
            return None
        return await self._upsert_from_payload(event, deployment)

    async def record_deployment_status(self, event: Any) -> Optional[Dict[str, Any]]:
        deployment = event.payload.get("deployment") or {}
        status = event.payload.get("deployment_status") or {}
        state = _STATE.get(str(status.get("state", "")).lower())
        if not event.project_id or not deployment.get("id") or state is None:
            return None  # unknown project, or "inactive" (superseded): nothing to record
        doc = await self._upsert_from_payload(event, deployment)
        if state == "in_progress" and doc.get("status") in ("success", "failure", "error"):
            return doc  # webhooks can arrive out of order: never reopen a finished deployment
        update: Dict[str, Any] = {"status": state}
        if state in ("success", "failure", "error"):
            update["finished_at"] = status.get("updated_at") or status.get("created_at") or _now()
        await self.deployments.update({"id": doc["id"]}, update)
        doc.update(update)
        if state == "success" and doc.get("production"):
            doc.update(await self._finalize(doc))
        return doc

    # ── GitHub Actions deploy workflow ────────────────────────────
    async def record_workflow_run(self, event: Any) -> Optional[Dict[str, Any]]:
        run = event.payload.get("workflow_run") or {}
        if not event.project_id or event.event_action not in ("completed", None) or run.get("status") != "completed":
            return None
        config = await self._config(event.project_id)
        workflow = config.get("deploy_workflow")
        if not workflow or run.get("name") != workflow:
            return None
        default_branch = config.get("default_branch")
        if default_branch and run.get("head_branch") != default_branch:
            return None
        conclusion = str(run.get("conclusion") or "")
        status = "success" if conclusion == "success" else "failure" if conclusion in ("failure", "timed_out") else None
        if status is None:
            return None  # cancelled / skipped: not a deployment attempt
        doc = {
            "id": f"WF-{event.repository}-{run.get('id')}",
            "project_id": event.project_id,
            "repository": event.repository,
            "source": "workflow_run",
            "environment": "production",
            "production": True,
            "sha": run.get("head_sha"),
            "ref": run.get("head_branch"),
            "created_at": run.get("run_started_at") or run.get("created_at") or _now(),
            "finished_at": run.get("updated_at") or _now(),
            "status": status,
            "deployed_by": (run.get("actor") or {}).get("login"),
            "is_hotfix": str(run.get("head_branch") or "").lower().startswith("hotfix/"),
        }
        await self.deployments.upsert({"id": doc["id"]}, doc)
        if status == "success":
            doc.update(await self._finalize(doc))
        return doc

    # ── commits, rollbacks ────────────────────────────────────────
    async def _previous_success(self, doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        finished = parse_time(doc.get("finished_at"))
        candidates = [
            d for d in await self.deployments.find_by_project(doc["project_id"])
            if d.get("id") != doc["id"] and d.get("status") == "success" and d.get("production")
            and d.get("environment") == doc.get("environment") and parse_time(d.get("finished_at"))
            and (finished is None or parse_time(d.get("finished_at")) <= finished)
        ]
        return max(candidates, key=lambda d: parse_time(d["finished_at"])) if candidates else None

    async def _finalize(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Commits in this deployment and rollback detection (stored on the record)."""
        owner, _, repo = str(doc.get("repository", "")).partition("/")
        previous = await self._previous_success(doc)
        result: Dict[str, Any] = {"commits": [], "is_rollback": False, "previous_deployment_id": None}
        try:
            if previous is None:
                commit = await self.github.get_commit(owner, repo, doc["sha"])
                result["commits"] = [{"sha": doc["sha"], "committed_at": _commit_time(commit)}]
            else:
                result["previous_deployment_id"] = previous["id"]
                if previous.get("sha") != doc.get("sha"):
                    comparison = await self.github.compare_commits(owner, repo, previous["sha"], doc["sha"])
                    if comparison.get("status") == "behind":
                        result["is_rollback"] = True
                        result["rolled_back_deployment_id"] = previous["id"]
                    else:
                        result["commits"] = [
                            {"sha": c.get("sha"), "committed_at": _commit_time(c)}
                            for c in comparison.get("commits", []) if c.get("sha")
                        ]
        except Exception as exc:  # GitHub unavailable: keep the deployment, note why commits are missing
            logger.warning(f"Could not load commits for deployment {doc.get('id')}: {exc}")
            result["commits_error"] = str(exc)[:200]
        await self.deployments.update({"id": doc["id"]}, result)
        return result
