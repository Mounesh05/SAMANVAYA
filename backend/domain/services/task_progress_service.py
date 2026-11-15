"""
Task progress from pull requests.

A pull request that names a task ID (TSK-XXXXXXXX) in its title, branch name
or description moves that task along the normal task workflow:

    pull request open (not draft)          -> review
    draft, or latest decisive review asked
    for changes                            -> in_progress
    merged                                 -> done
    closed without merging                 -> in_progress

Safety rules:
- Only tasks in the same project as the repository are moved.
- Only tasks assigned to the pull request's author (matched through the
  employee's GitHub username) are moved.
- Every step goes through WorkflowService.transition_task, so the workflow
  rules apply and each step is recorded in the task's history as made by
  GitHub. Steps are never skipped (todo -> in_progress -> review -> done).
- Blocked tasks are left alone (someone flagged them on purpose), and a done
  task is never reopened automatically.
- Applying the same pull request state twice changes nothing.
"""

import logging
import re
from collections import deque
from typing import Any, Optional

from domain.models.workflow import TASK_WORKFLOW
from domain.services.workflow_service import WorkflowService
from repositories.task_repository import TaskRepository
from repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

TASK_ID_PATTERN = re.compile(r"\bTSK-[0-9A-F]{8}\b", re.IGNORECASE)
GITHUB_ACTOR_ID = "github"
DECISIVE_REVIEWS = {"APPROVED", "CHANGES_REQUESTED"}


def task_ids_in(pr: dict) -> list[str]:
    """Task IDs named in the pull request title, branch name or description, in order."""
    text = " ".join([
        pr.get("title") or "",
        (pr.get("head") or {}).get("ref") or "",
        pr.get("body") or "",
    ])
    seen: dict[str, None] = {}
    for match in TASK_ID_PATTERN.findall(text):
        seen.setdefault(match.upper(), None)
    return list(seen)


def target_status(pr: dict, reviews: Optional[list] = None) -> Optional[str]:
    """The task status this pull request state stands for."""
    if pr.get("merged") or pr.get("merged_at"):
        return "done"
    if pr.get("state") == "closed":
        return "in_progress"
    if pr.get("draft"):
        return "in_progress"
    decisive = [r for r in (reviews or []) if str(r.get("state", "")).upper() in DECISIVE_REVIEWS]
    decisive.sort(key=lambda r: r.get("submitted_at") or "")
    if decisive and str(decisive[-1].get("state")).upper() == "CHANGES_REQUESTED":
        return "in_progress"
    return "review"


def workflow_path(current: str, target: str) -> Optional[list[str]]:
    """Shortest list of steps from current to target along the task workflow,
    never passing through 'blocked'. [] when already there, None if unreachable."""
    if current == target:
        return []
    queue = deque([(current, [])])
    visited = {current}
    while queue:
        status, path = queue.popleft()
        for nxt in TASK_WORKFLOW.get(status, []):
            if nxt in visited or nxt == "blocked":
                continue
            if nxt == target:
                return path + [nxt]
            visited.add(nxt)
            queue.append((nxt, path + [nxt]))
    return None


class TaskProgressService:
    """Moves tasks named in a pull request to match the pull request's state."""

    def __init__(self):
        self.task_repo = TaskRepository()
        self.user_repo = UserRepository()
        self.workflow = WorkflowService()

    async def _author_employee_id(self, login: str) -> Optional[str]:
        if not login:
            return None
        user = await self.user_repo.find_one({
            "github_username": {"$regex": f"^{re.escape(login)}$", "$options": "i"},
            "is_active": {"$ne": False},
        })
        return user.get("employee_id") if user else None

    async def apply(self, project_id: Optional[str], pr: dict, reviews: Optional[list] = None) -> list[dict[str, Any]]:
        """Move the tasks this pull request names. Returns one entry per task:
        {task_id, from, to, steps} when moved, or {task_id, skipped} with the reason."""
        task_ids = task_ids_in(pr)
        if not task_ids or not project_id:
            return []
        target = target_status(pr, reviews)
        number = pr.get("number")
        login = (pr.get("user") or {}).get("login", "")
        author_id = await self._author_employee_id(login)

        results = []
        for task_id in task_ids:
            task = await self.task_repo.find_one({"id": task_id})
            if not task:
                results.append({"task_id": task_id, "skipped": "No task with this ID"})
                continue
            if task.get("project_id") != project_id:
                results.append({"task_id": task_id, "skipped": "Task belongs to another project"})
                continue
            if not author_id or task.get("assignee_id") != author_id:
                results.append({"task_id": task_id, "skipped": f"Pull request author {login or 'unknown'} is not the task's assignee"})
                continue
            current = task.get("status") or "todo"
            if current == "blocked":
                results.append({"task_id": task_id, "skipped": "Task is blocked; move it manually"})
                continue
            if current == "done" and target != "done":
                results.append({"task_id": task_id, "skipped": "Task is done; reopen it manually"})
                continue
            steps = workflow_path(current, target)
            if not steps:
                results.append({"task_id": task_id, "from": current, "to": current, "steps": []})
                continue
            moved_to = current
            try:
                for step in steps:
                    await self.workflow.transition_task(
                        task_id,
                        step,
                        user_id=GITHUB_ACTOR_ID,
                        user_name=f"GitHub (PR #{number})",
                        reason=f"Pull request #{number} is {self._describe(pr, target)}",
                    )
                    moved_to = step
            except ValueError as error:
                # Someone moved the task meanwhile; keep what was applied.
                logger.info("Task %s auto-progress stopped at %s: %s", task_id, moved_to, error)
            results.append({"task_id": task_id, "from": current, "to": moved_to,
                            "steps": steps[: steps.index(moved_to) + 1] if moved_to in steps else []})
        return results

    @staticmethod
    def _describe(pr: dict, target: str) -> str:
        if target == "done":
            return "merged"
        if pr.get("state") == "closed":
            return "closed without merging"
        if pr.get("draft"):
            return "a draft"
        return "waiting for review" if target == "review" else "back with changes requested"


async def apply_task_progress(project_id: Optional[str], pr: dict, reviews: Optional[list] = None) -> list[dict]:
    """Best-effort wrapper: task progress never makes a pull request sync fail."""
    try:
        return await TaskProgressService().apply(project_id, pr, reviews)
    except Exception:  # pragma: no cover - logged, never raised to the caller
        logger.exception("Task auto-progress failed for PR #%s", pr.get("number"))
        return []
