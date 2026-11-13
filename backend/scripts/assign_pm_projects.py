"""
CR-013 rollout helper: give each existing PM the projects they created.

After CR-013 a PM sees only the projects they manage (users.project_ids).
Run this once before PMs use the new version, from the backend folder:

    python -m scripts.assign_pm_projects          # review only (dry run)
    python -m scripts.assign_pm_projects --apply  # apply after confirming

It only adds assignments (never removes any), only for active PMs, only for
projects in the same organisation, and prints the full list first. Every
change is recorded in the audit log. Add anything else on the project's
Members panel.
"""

import asyncio
import sys
from datetime import datetime, timezone
from typing import Dict, List


async def plan(db) -> Dict[str, List[str]]:
    """{pm_employee_id: [project ids to add]} — projects each active PM created."""
    pms = await db["users"].find({"role": "PM", "is_active": {"$ne": False}},
                                 {"_id": 0, "employee_id": 1, "project_ids": 1, "org_id": 1}).to_list(length=None)
    proposal = {}
    for pm in pms:
        query = {"created_by": pm["employee_id"]}
        if pm.get("org_id"):
            query["org_id"] = pm["org_id"]
        created = await db["projects"].find(query, {"_id": 0, "id": 1}).to_list(length=None)
        missing = sorted({p["id"] for p in created} - set(pm.get("project_ids") or []))
        if missing:
            proposal[pm["employee_id"]] = missing
    return proposal


async def apply(db, proposal: Dict[str, List[str]]) -> int:
    """Add the proposed assignments; returns how many were added."""
    added = 0
    for employee_id, project_ids in proposal.items():
        result = await db["users"].update_one({"employee_id": employee_id},
                                              {"$addToSet": {"project_ids": {"$each": project_ids}}})
        if result.modified_count:
            added += len(project_ids)
            await db["audit_logs"].insert_one({
                "action": "USER_UPDATED", "actor_id": "scripts.assign_pm_projects", "actor_name": "CR-013 rollout",
                "resource_type": "employee", "resource_id": employee_id,
                "details": {"field": "project_ids", "added": project_ids, "reason": "PM created these projects"},
                "ip_address": None, "user_agent": None, "success": True, "error_message": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            })
    return added


def describe(proposal: Dict[str, List[str]]) -> str:
    if not proposal:
        return "Nothing to do: every PM already manages the projects they created."
    return "\n".join(f"  {pm}: {', '.join(ids)}" for pm, ids in sorted(proposal.items()))


async def main(argv) -> int:
    from motor.motor_asyncio import AsyncIOMotorClient

    from core.config import settings

    client = AsyncIOMotorClient(settings.MONGO_URI)
    try:
        db = client[settings.DB_NAME]
        proposal = await plan(db)
        print(f"Database: {settings.DB_NAME}\nProposed PM assignments (projects each PM created):")
        print(describe(proposal))
        if "--apply" not in argv or not proposal:
            print("\nDry run only. Re-run with --apply to make these changes.")
            return 0
        if input("\nApply these assignments? (y/n): ").strip().lower() != "y":
            print("Cancelled. Nothing was changed.")
            return 1
        print(f"Added {await apply(db, proposal)} assignments.")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
