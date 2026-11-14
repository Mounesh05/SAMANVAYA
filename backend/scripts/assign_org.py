"""
One-off fix: give employees without an organisation the install's organisation.

Organisation-scoped features (performance, HR assessments, reports, project
organisation checks) need `users.org_id`, but installs built through the app
before this fix never set it, so the Performance area refused everyone.

Run from the backend folder:

    python -m scripts.assign_org                    # review only (dry run)
    python -m scripts.assign_org --apply            # apply after confirming
    python -m scripts.assign_org --apply --org ORG7 # another organisation ID

It only fills in a missing org_id (never changes an existing one), prints the
list first, and writes one audit entry per employee.
"""

import asyncio
import re
import sys
from datetime import datetime, timezone
from typing import List


async def plan(db) -> List[dict]:
    """Employees with no organisation."""
    return await db["users"].find(
        {"$or": [{"org_id": {"$exists": False}}, {"org_id": None}, {"org_id": ""}]},
        {"_id": 0, "employee_id": 1, "name": 1, "role": 1},
    ).to_list(length=None)


async def apply(db, people: List[dict], org_id: str) -> int:
    ids = [p["employee_id"] for p in people]
    result = await db["users"].update_many(
        {"employee_id": {"$in": ids}, "$or": [{"org_id": {"$exists": False}}, {"org_id": None}, {"org_id": ""}]},
        {"$set": {"org_id": org_id}},
    )
    now = datetime.now(timezone.utc)
    if ids:
        await db["audit_logs"].insert_many([{
            "action": "USER_UPDATED", "actor_id": "scripts.assign_org", "actor_name": "Organisation fix",
            "resource_type": "employee", "resource_id": employee_id,
            "details": {"field": "org_id", "old": None, "new": org_id},
            "ip_address": None, "user_agent": None, "success": True, "error_message": None,
            "timestamp": now.isoformat(), "date": now.strftime("%Y-%m-%d"),
        } for employee_id in ids])
    return result.modified_count


def parse(argv, default_org):
    org = default_org
    if "--org" in argv:
        org = argv[argv.index("--org") + 1]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,50}", org):
        raise SystemExit("Organisation IDs use letters, digits, '-' and '_' only")
    return "--apply" in argv, org


async def main(argv) -> int:
    from motor.motor_asyncio import AsyncIOMotorClient

    from core.config import settings

    do_apply, org_id = parse(argv, settings.DEFAULT_ORG_ID)
    client = AsyncIOMotorClient(settings.MONGO_URI)
    try:
        db = client[settings.DB_NAME]
        people = await plan(db)
        print(f"Database: {settings.DB_NAME}\n{len(people)} employees have no organisation (would become {org_id}):")
        for p in people:
            print(f"  {p['employee_id']:<14} {p.get('role', ''):<10} {p.get('name', '')}")
        if not do_apply or not people:
            print("\nDry run only. Re-run with --apply to make these changes." if people else "\nNothing to do.")
            return 0
        if input("\nApply? (y/n): ").strip().lower() != "y":
            print("Cancelled. Nothing was changed.")
            return 1
        print(f"Updated {await apply(db, people, org_id)} employees.")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
