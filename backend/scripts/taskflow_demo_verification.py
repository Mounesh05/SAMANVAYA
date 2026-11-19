"""Verify the synthetic TaskFlow setup through real auth and ASGI read APIs.

No application lifespan, live inference, GitHub mutations or business writes.
Tokens are issued by the existing password-authentication service and revoked
through the normal logout API. Results never contain credentials or JWTs.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from core.database import close_db, get_db
from domain.services.auth_service import AuthService
from scripts.setup_taskflow_demo import LOCAL, ORG, TEAM, require_safe_environment


async def main():
    require_safe_environment("samanvaya_test", True)
    accounts = json.loads((LOCAL / "accounts.json").read_text())["accounts"]
    state = json.loads((LOCAL / "state.json").read_text())
    project_id, sprint_id = state["project_id"], state["sprint_id"]
    from main import app

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("main").setLevel(logging.WARNING)
    results = []

    def record(label, passed, **extra):
        results.append({"check": label, "passed": bool(passed), **extra})

    db = get_db()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost", timeout=30) as client:
        for account in accounts:
            identifier, role = account["employee_id"], account["role"]
            result = await AuthService().authenticate_user(account["username"], account["organisation_password"], account["employee_password"])
            record(f"{identifier}: credential authentication", result is not None)
            if not result:
                continue
            token = result.token

            async def check(label, path, expected=200, method="GET", **kwargs):
                response = await client.request(method, "/api" + path, headers={"Authorization": "Bearer " + token}, **kwargs)
                record(f"{identifier}: {label}", response.status_code == expected, status=response.status_code, expected=expected)
                return response

            has_project = identifier not in ("DEMO_HR", "DEMO_ADMIN")
            await check("current profile", "/auth/me")
            dashboard = await check("own role dashboard", f"/role/{role.lower()}/dashboard")
            record(f"{identifier}: dashboard excludes credential fields", not any(
                key in dashboard.text for key in ('"organisation_password"', '"employee_password"', '"password_hash"')))
            await check("other role denied", "/role/" + ("hr" if role != "HR" else "ceo") + "/dashboard", 403)
            projects = await check("project list", "/projects/")
            record(f"{identifier}: expected project visibility", (project_id in {p["id"] for p in projects.json()}) == has_project)
            await check("foreign organization denied", "/projects/", 403, params={"org_id": "UNRELATED-VERIFICATION-ORG"})
            for label, path in [
                ("project detail", f"/projects/{project_id}"),
                ("project members", f"/projects/{project_id}/members"),
                ("project sprints", f"/sprints/project/{project_id}"),
                ("project tasks", f"/tasks/project/{project_id}"),
                ("sprint stories", f"/stories/sprint/{sprint_id}"),
                ("repository configuration", f"/github/projects/{project_id}/config"),
                ("code configuration", f"/code-quality/projects/{project_id}/config"),
                ("QA evidence", "/qa/test-runs"),
            ]:
                kwargs = {"params": {"project_id": project_id}} if label == "QA evidence" else {}
                await check(label, path, 200 if has_project else 403, **kwargs)
            await check("team read", f"/teams/{TEAM}")
            if role in ("DEVELOPER", "QA", "DEVOPS", "HR", "LEAD", "CEO") and not account["username"] == "demo_admin":
                await check("project creation denied", "/projects/", 403, method="POST",
                    json={"name": "Must not be created", "org_id": ORG, "team_id": TEAM})
            if role in ("DEVELOPER", "QA", "DEVOPS", "PM", "LEAD") and identifier != "DEMO_ADMIN":
                await check("team creation denied", "/teams/", 403, method="POST",
                    json={"team_id": "MUST-NOT-EXIST", "name": "Must not be created"})
            incident_access = role != "HR" and has_project
            await check("incident visibility", "/incidents/", 200 if incident_access else 403, params={"project_id": project_id})
            permissions = set(result.user.permissions)
            await check("pipeline visibility", "/role/devops/pipelines", 200 if "VIEW_PIPELINES" in permissions else 403)
            if role == "HR":
                await check("HR employee view", "/role/hr/employees")
                await check("engineering analysis denied", "/code-quality/analyze", 403, method="POST",
                    json={"repository_id": "Mounesh05/taskflow-samanvaya-lab", "use_ai": False})
            await check("logout", "/auth/logout", method="POST")
            await check("revoked token denied", "/auth/me", 401)
        counts = {name: await db[name].count_documents({}) for name in ("users", "teams", "projects", "sprints", "stories", "tasks")}
        record("exact synthetic business counts", counts == {"users": 9, "teams": 1, "projects": 1, "sprints": 1, "stories": 7, "tasks": 7})
        record("no false completed tasks", await db.tasks.count_documents({"status": {"$ne": "todo"}}) == 0)
        record("CEO and HR have no team", await db.users.count_documents({"role": {"$in": ["CEO", "HR"]}, "team_id": {"$ne": None}}) == 0)
        record("all accounts have exact approved tenant", await db.users.count_documents({"org_id": {"$ne": ORG}}) == 0)
        record("no failed negative-check records", await db.projects.count_documents({"name": "Must not be created"}) == 0
               and await db.teams.count_documents({"team_id": "MUST-NOT-EXIST"}) == 0)
        bad = await AuthService().authenticate_user("mounesh", "Incorrect-Org-Password1!", "Incorrect-Employee-Password2!")
        record("wrong credentials rejected", bad is None)
        summary = {"checks": results, "passed": sum(r["passed"] for r in results), "failed": sum(not r["passed"] for r in results), "counts": counts}
        (LOCAL / "verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in summary.items() if k != "checks"}))
        for failure in results:
            if not failure["passed"]:
                print(json.dumps(failure))
    await close_db()
    if summary["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
