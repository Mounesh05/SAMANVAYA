"""
Per-project PR risk model: train it from the project's GitHub repository and
use it to score PRs.

Training (slow: minutes on large histories) runs as a background task:
    1. read the project's repository from github_project_configs
    2. clone it into a temporary folder (full history: SZZ needs git blame);
       the server's GITHUB_TOKEN is passed in an environment-only git config
       header, never on the command line or in the URL
    3. intelligence/risk_model/predictor.train_from_repository
    4. store the bundle in "risk_models" (one per project, replaced on retrain)
       and its evaluation in "risk_model_history"

Scoring never touches git: it uses the history state saved in the bundle.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

from core.database import col
from intelligence.risk_model.predictor import predict, train_from_repository

logger = logging.getLogger(__name__)

MODELS = "risk_models"
HISTORY = "risk_model_history"
_SAFE_NAME = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")


def _valid_name(name: str) -> bool:
    return bool(name) and set(name) <= _SAFE_NAME and not name.startswith((".", "-"))


def clone_repository(owner: str, name: str, dest: str, token: str = "", timeout: int = 900) -> None:
    if not (_valid_name(owner) and _valid_name(name)):
        raise ValueError("invalid repository owner or name")
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    if token:
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
                    "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}"})
    result = subprocess.run(
        ["git", "clone", "--quiet", "--no-checkout", f"https://github.com/{owner}/{name}.git", dest],
        capture_output=True, text=True, timeout=timeout, env=env,
    )
    if result.returncode != 0:
        raise RuntimeError("git clone failed")   # stderr may echo URLs; not propagated


def _stale(started_at: Optional[str], hours: float = 2.0) -> bool:
    """A run 'training' for longer than this was interrupted (e.g. server restart)."""
    try:
        started = datetime.fromisoformat(started_at)
    except (TypeError, ValueError):
        return True
    return (datetime.now(timezone.utc) - started).total_seconds() > hours * 3600


class RiskModelService:
    def __init__(self, models=None, history=None, configs=None):
        self.models = models if models is not None else col(MODELS)
        self.history = history if history is not None else col(HISTORY)
        self.configs = configs if configs is not None else col("github_project_configs")

    async def get(self, project_id: str) -> Optional[Dict[str, Any]]:
        return await self.models.find_one({"project_id": project_id}, {"_id": 0})

    async def summary(self, project_id: str) -> Optional[Dict[str, Any]]:
        """The stored model without its (large) history state."""
        doc = await self.models.find_one({"project_id": project_id}, {"_id": 0, "bundle.state": 0, "bundle.model": 0})
        return doc

    async def mark_training(self, project_id: str, user_id: Optional[str]) -> bool:
        """False when a training run for this project is already in progress."""
        existing = await self.models.find_one({"project_id": project_id}, {"_id": 0, "status": 1, "started_at": 1})
        if existing and existing.get("status") == "training" and not _stale(existing.get("started_at")):
            return False
        await self.models.update_one(
            {"project_id": project_id},
            {"$set": {"project_id": project_id, "status": "training", "requested_by": user_id,
                      "started_at": datetime.now(timezone.utc).isoformat(), "error": None}},
            upsert=True,
        )
        return True

    async def train(self, project_id: str, token: str = "") -> None:
        config = await self.configs.find_one({"project_id": project_id}, {"_id": 0})
        if not config:
            await self._fail(project_id, "GitHub project configuration not found")
            return
        owner, name = config.get("repository_owner", ""), config.get("repository_name", "")
        branch = config.get("default_branch") or "HEAD"
        tmp = tempfile.mkdtemp(prefix="samanvaya-risk-")
        try:
            dest = os.path.join(tmp, "repo")
            await asyncio.to_thread(clone_repository, owner, name, dest, token)
            ref = f"origin/{branch}" if branch != "HEAD" else "HEAD"
            bundle = await asyncio.to_thread(train_from_repository, dest, ref)
            now = datetime.now(timezone.utc).isoformat()
            await self.models.update_one(
                {"project_id": project_id},
                {"$set": {"status": "ready", "repository": f"{owner}/{name}", "branch": branch,
                          "bundle": bundle, "usable": bundle["usable"], "trained_at": now, "error": None}},
                upsert=True,
            )
            await self.history.insert_one({
                "project_id": project_id, "repository": f"{owner}/{name}", "trained_at": now,
                "head": bundle.get("head"), "usable": bundle["usable"], "szz": bundle.get("szz"),
                "evaluation": bundle.get("evaluation"),
            })
        except Exception as error:  # noqa: BLE001 - stored as a status, logged without secrets
            logger.warning("risk model training failed for %s: %s", project_id, type(error).__name__)
            await self._fail(project_id, f"training failed ({type(error).__name__})")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    async def _fail(self, project_id: str, message: str) -> None:
        await self.models.update_one({"project_id": project_id},
                                     {"$set": {"status": "failed", "error": message}}, upsert=True)

    async def score(self, project_id: Optional[str], files: Iterable[Tuple[str, int, int]], author: str,
                    timestamp: Optional[int] = None, messages: Sequence[str] = ()) -> Optional[Dict[str, Any]]:
        if not project_id:
            return None
        doc = await self.get(project_id)
        # a retrain in progress (or a failed retrain) keeps the previous model
        if not doc or not doc.get("bundle") or not doc.get("usable"):
            return None
        return predict(doc["bundle"], files, author, timestamp, messages)
