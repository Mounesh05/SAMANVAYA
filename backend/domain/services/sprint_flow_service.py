"""
Sprint flow service: loads sprint data and feeds intelligence/metrics/flow.py.

Also owns the two moments that make scope and velocity measurable:
    start_sprint      planning -> active; snapshots the committed scope
                      (items and points) and the start time
    complete_sprint   active -> completed; stores the points completed
                      (velocity) and the completion percentage
    record_scope_change  logs an item moving into or out of a sprint, with
                      its points and time (collection "sprint_scope_changes")

Work items of a sprint are its stories plus tasks without a story, the same
rule SprintService.calculate_sprint_health uses. Unestimated items count as 1.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.database import col
from intelligence.metrics.flow import DONE, flow_for_items, item_points, sprint_flow_report
from repositories.sprint_repository import SprintRepository
from repositories.story_repository import StoryRepository
from repositories.task_repository import TaskRepository

SCOPE_CHANGES = "sprint_scope_changes"
TRANSITIONS = "transitions"
HISTORY_SPRINTS = 3   # recent completed sprints whose finished items feed the forecast


class SprintTransitionError(ValueError):
    """A sprint cannot move to the requested state."""


class SprintFlowService:
    def __init__(self) -> None:
        self.sprint_repo = SprintRepository()
        self.story_repo = StoryRepository()
        self.task_repo = TaskRepository()

    # ── loading ───────────────────────────────────────────────────
    async def work_items(self, sprint_id: str) -> List[Dict[str, Any]]:
        stories = await self.story_repo.find_by_sprint(sprint_id)
        tasks = await self.task_repo.find_by_sprint(sprint_id)
        return [*stories, *[t for t in tasks if not t.get("story_id")]]

    async def transitions(self, item_ids: List[str]) -> List[Dict[str, Any]]:
        if not item_ids:
            return []
        return await col(TRANSITIONS).find({"item_id": {"$in": item_ids}}, {"_id": 0}).to_list(length=None)

    async def scope_changes(self, sprint_id: str) -> List[Dict[str, Any]]:
        return await col(SCOPE_CHANGES).find({"sprint_id": sprint_id}, {"_id": 0}).to_list(length=None)

    async def completed_sprints(self, project_id: str) -> List[Dict[str, Any]]:
        sprints = await self.sprint_repo.find_by_project(project_id)
        return [s for s in sprints if s.get("status") == "completed"]

    async def flow_report(self, sprint_id: str, now: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
        sprint = await self.sprint_repo.find_by_id(sprint_id)
        if not sprint:
            return None
        items = await self.work_items(sprint_id)
        completed = sorted(await self.completed_sprints(sprint.get("project_id", "")),
                           key=lambda s: str(s.get("end_date") or ""))
        history_items = list(items)
        for past in completed[-HISTORY_SPRINTS:]:
            if past.get("id") != sprint_id:
                history_items += await self.work_items(past["id"])
        history_transitions = await self.transitions([str(i.get("id")) for i in history_items])
        history_flows = flow_for_items(history_items, history_transitions, now)
        ids = {str(i.get("id")) for i in items}
        return sprint_flow_report(
            sprint=sprint,
            items=items,
            transitions=[t for t in history_transitions if str(t.get("item_id")) in ids],
            changes=await self.scope_changes(sprint_id),
            completed_sprints=[s for s in completed if s.get("id") != sprint_id],
            history_flows=history_flows,
            now=now,
        )

    # ── state changes ─────────────────────────────────────────────
    async def start_sprint(self, sprint_id: str) -> Dict[str, Any]:
        sprint = await self.sprint_repo.find_by_id(sprint_id)
        if not sprint:
            raise LookupError("Sprint not found")
        if sprint.get("status") != "planning":
            raise SprintTransitionError(f"Only a planning sprint can be started (status: {sprint.get('status')})")
        project_id = sprint.get("project_id")
        for other in await self.sprint_repo.find_by_project(project_id):
            if other.get("id") != sprint_id and other.get("status") == "active":
                raise SprintTransitionError(f"Sprint {other.get('id')} is already active in this project")
        items = await self.work_items(sprint_id)
        snapshot = {
            "status": "active",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "committed_points": sum(item_points(i) for i in items),
            "committed_item_ids": [str(i.get("id")) for i in items],
        }
        await self.sprint_repo.update({"id": sprint_id}, snapshot)
        return {**sprint, **snapshot}

    async def complete_sprint(self, sprint_id: str) -> Dict[str, Any]:
        sprint = await self.sprint_repo.find_by_id(sprint_id)
        if not sprint:
            raise LookupError("Sprint not found")
        if sprint.get("status") != "active":
            raise SprintTransitionError(f"Only an active sprint can be completed (status: {sprint.get('status')})")
        items = await self.work_items(sprint_id)
        total = sum(item_points(i) for i in items)
        done = sum(item_points(i) for i in items if i.get("status") == DONE)
        result = {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "completed_points": done,
            "velocity": int(round(done)),
            "completion_pct": round(100 * done / total, 2) if total else 0.0,
        }
        await self.sprint_repo.update({"id": sprint_id}, result)
        return {**sprint, **result}

    async def record_scope_change(self, item: Dict[str, Any], item_type: str,
                                  old_sprint_id: Optional[str], new_sprint_id: Optional[str],
                                  changed_by: Optional[str] = None) -> None:
        """Log an item leaving one sprint and/or joining another (no-op if unchanged)."""
        if old_sprint_id == new_sprint_id:
            return
        now = datetime.now(timezone.utc).isoformat()
        base = {"item_id": str(item.get("id")), "item_type": item_type, "points": item_points(item),
                "changed_by": changed_by, "at": now}
        records = []
        if old_sprint_id:
            records.append({**base, "sprint_id": old_sprint_id, "action": "removed"})
        if new_sprint_id:
            records.append({**base, "sprint_id": new_sprint_id, "action": "added"})
        if records:
            await col(SCOPE_CHANGES).insert_many(records)
