"""Explicit local TaskFlow setup, using existing bootstrap and authorized APIs.

Run from backend with --database samanvaya_test --approve-synthetic-data.
Credentials must already exist in the restricted, Git-ignored local directory.
Never run automated MongoDB tests while this demo database is in use.
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import settings
from core.database import close_db, get_db
from core.security import verify_password
from create_first_user import create_first_accounts
from domain.services.auth_service import AuthService
from domain.services.first_accounts import FirstAccount

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "credentials" / "taskflow-demo"
ORG = "TASKFLOW-DEMO"
TEAM = "TASKFLOW-ENGINEERING"


def require_safe_environment(database: str, approved: bool) -> None:
    from urllib.parse import urlsplit

    if not approved or database != "samanvaya_test" or settings.DB_NAME != database:
        raise RuntimeError("Explicit approval and the exact approved database are required")
    if not settings.is_development() or urlsplit(settings.MONGO_URI).hostname not in ("localhost", "127.0.0.1", "::1"):
        raise RuntimeError("Setup is restricted to local development")
    if settings.PR_MULTI_AGENT_INTERNAL_ENABLED or settings.PR_MULTI_AGENT_MANUAL_ENABLED:
        raise RuntimeError("Multi-agent flags must remain disabled")
    if not settings.GITHUB_TOKEN:
        raise RuntimeError("A configured GitHub read token is required")


async def main(database: str, approved: bool) -> None:
    require_safe_environment(database, approved)
    accounts = json.loads((LOCAL / "accounts.json").read_text(encoding="utf-8"))
    if accounts["database"] != database or accounts["org_id"] != ORG:
        raise RuntimeError("Credential manifest scope mismatch")
    accounts = accounts["accounts"]
    by_id = {a["employee_id"]: a for a in accounts}
    db = get_db()
    existing = await db.users.find({}, {"_id": 0}).to_list(1000)
    state_path = LOCAL / "state.json"
    if existing and not state_path.exists():
        raise RuntimeError("Existing accounts without a matching local setup manifest; nothing changed")
    for person in existing:
        expected = by_id.get(person.get("employee_id"))
        if not expected or any(person.get(k) != expected[k] for k in ("name", "email", "role")) or person.get("org_id") != ORG:
            raise RuntimeError("An existing identity conflicts with this synthetic setup")
        if not all(verify_password(expected[k], person.get(k, "")) for k in ("organisation_password", "employee_password")):
            raise RuntimeError("Existing credentials differ; refusing to reset any password")
    if not state_path.exists():
        if any([await db[name].count_documents({}) for name in await db.list_collection_names()]):
            raise RuntimeError("First setup requires an empty approved database")
        state_path.write_text(json.dumps({"database": database, "org_id": ORG}), encoding="utf-8")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("database") != database or state.get("org_id") != ORG:
        raise RuntimeError("Setup state scope mismatch")
    actions = []

    def checkpoint():
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def first(identifier):
        a = by_id[identifier]
        return FirstAccount(a["employee_id"], a["name"], a["email"], a["organisation_password"], a["employee_password"])

    if not existing:
        await create_first_accounts(db, first("DEMO_CEO"), first("DEMO_ADMIN"), org_id=ORG)
        actions.extend([{"record": "DEMO_CEO", "action": "CREATED"}, {"record": "DEMO_ADMIN", "action": "CREATED"}])

    # ASGI requests use the real auth dependencies. No lifespan means this command
    # does not launch pollers, background workers, model inference or GitHub writes.
    import httpx
    from main import app

    logging.getLogger("httpx").setLevel(logging.WARNING)
    tokens = {}

    async def authenticate(identifier):
        a = by_id[identifier]
        result = await AuthService().authenticate_user(identifier, a["organisation_password"], a["employee_password"])
        if not result:
            raise RuntimeError(f"Authentication failed for {identifier}")
        tokens[identifier] = result.token

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost", timeout=60) as client:
        async def call(method, path, actor="DEMO_ADMIN", expected=(200,), **kwargs):
            response = await client.request(method, "/api" + path, headers={"Authorization": "Bearer " + tokens[actor]}, **kwargs)
            if response.status_code not in expected:
                # Do not print response bodies: validation details can contain credentials.
                raise RuntimeError(f"{method} {path} returned {response.status_code}")
            return response.json()

        await authenticate("DEMO_ADMIN")
        for a in accounts:
            identifier = a["employee_id"]
            person = await db.users.find_one({"employee_id": identifier})
            if not person:
                await call("POST", "/employees/", expected=(201,), json={k: a[k] for k in (
                    "employee_id", "name", "email", "role", "dept", "organisation_password", "employee_password")})
                actions.append({"record": identifier, "action": "CREATED"})
            else:
                actions.append({"record": identifier, "action": "REUSED"})
        for identifier in ("DEMO_PM", "DEMO_LEAD", "DEMO_DEVOPS"):
            await authenticate(identifier)
        team = await db.teams.find_one({"team_id": TEAM})
        if team and (team.get("name") != "TaskFlow Engineering" or team.get("team_lead_id") != "DEMO_LEAD"):
            raise RuntimeError("Conflicting team identity")
        if not team:
            await call("POST", "/teams/", expected=(201,), json={"team_id": TEAM, "name": "TaskFlow Engineering",
                "description": "TaskFlow Demo Organization — controlled synthetic integration testing", "team_lead_id": "DEMO_LEAD"})
        for identifier in ("MOUNESH", "MALLIKARJUN", "SHREYAS", "DEMO_DEVOPS"):
            person = await db.users.find_one({"employee_id": identifier})
            if person.get("team_id") not in (None, TEAM):
                raise RuntimeError("Employee already belongs to another team")
            if person.get("team_id") != TEAM:
                await call("POST", f"/teams/{TEAM}/members/{identifier}")

        project = await db.projects.find_one({"name": "TaskFlow", "org_id": ORG})
        if project and (project.get("team_id") != TEAM or project.get("created_by") != "DEMO_PM"):
            raise RuntimeError("Conflicting project identity")
        if not project:
            project = await call("POST", "/projects/", actor="DEMO_PM", expected=(201,), json={"name": "TaskFlow",
                "description": "Synthetic collaborative application: Python, FastAPI, MongoDB, React, TypeScript and GitHub Actions",
                "org_id": ORG, "team_id": TEAM})
        project_id = project["id"]
        state["project_id"] = project_id
        checkpoint()
        for identifier in ("DEMO_LEAD", "MOUNESH", "MALLIKARJUN", "SHREYAS", "DEMO_DEVOPS"):
            await call("POST", f"/projects/{project_id}/members", actor="DEMO_PM", expected=(201,), json={"employee_id": identifier})
        team = await db.teams.find_one({"team_id": TEAM})
        team_projects = list(team.get("project_ids") or [])
        if project_id not in team_projects:
            await call("PUT", f"/teams/{TEAM}", json={"project_ids": team_projects + [project_id]})

        # Only repository metadata GETs occur inside the existing validated linking flow.
        config = {"project_id": project_id, "repository_owner": "Mounesh05", "repository_name": "taskflow-samanvaya-lab",
            "repository_url": "https://github.com/Mounesh05/taskflow-samanvaya-lab", "default_branch": "main", "developer_mappings": []}
        prior = await db.github_project_configs.find_one({"project_id": project_id}, {"_id": 0})
        if prior and prior != config:
            raise RuntimeError("Existing GitHub configuration differs; refusing to overwrite it")
        if not prior:
            await call("PUT", f"/github/projects/{project_id}/config", actor="DEMO_DEVOPS", json=config)
        sprint = await db.sprints.find_one({"name": "TaskFlow Sprint 1", "project_id": project_id})
        if not sprint:
            sprint = await call("POST", "/sprints/", actor="DEMO_PM", expected=(201,), json={"name": "TaskFlow Sprint 1",
                "project_id": project_id, "goal": "Controlled integration verification; no completion claims",
                "start_date": date.today().isoformat(), "end_date": (date.today() + timedelta(days=14)).isoformat()})
        state["sprint_id"] = sprint["id"]
        state["work_items"] = []
        for title, assignee, priority, description in [
            ("Backend API foundation", "MOUNESH", "high", "Implement backend API foundation"),
            ("MongoDB persistence and data validation", "MOUNESH", "high", "Persist and validate application data"),
            ("React task dashboard", "MALLIKARJUN", "high", "Build the frontend task dashboard"),
            ("TypeScript sorting and searching functions", "MALLIKARJUN", "medium", "Implement typed collection operations"),
            ("Backend integration tests", "SHREYAS", "high", "Create and execute repository integration tests"),
            ("GitHub Actions CI configuration", "DEMO_DEVOPS", "high", "DevOps owns this task; Shreyas executes the actual repository work"),
            ("QA verification of task lifecycle", "SHREYAS", "medium", "Verify task lifecycle behavior; no results have been asserted"),
        ]:
            story = await db.stories.find_one({"project_id": project_id, "title": title})
            if not story:
                story = await call("POST", "/stories/", actor="DEMO_PM", expected=(201,), json={"title": title,
                    "description": description, "project_id": project_id, "sprint_id": sprint["id"], "assignee_id": assignee, "priority": priority})
            task = await db.tasks.find_one({"project_id": project_id, "title": title})
            if not task:
                task = await call("POST", "/tasks/", actor="DEMO_PM", expected=(201,), json={"title": title,
                    "project_id": project_id, "story_id": story["id"], "sprint_id": sprint["id"], "assignee_id": assignee, "priority": priority})
            if task["assignee_id"] != assignee or story["assignee_id"] != assignee:
                raise RuntimeError("Existing workload assignment differs")
            state["work_items"].append({"title": title, "story_id": story["id"], "task_id": task["id"], "assignee_id": assignee})
            checkpoint()
        state["last_actions"] = actions
        state["setup_complete"] = True
        checkpoint()
        print(json.dumps({"database": database, "organization_id": ORG, "team_id": TEAM,
            "project_id": project_id, "sprint_id": sprint["id"], "stories": len(state["work_items"]),
            "tasks": len(state["work_items"]), "accounts": len(accounts), "setup_complete": True}))
    await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--approve-synthetic-data", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.database, args.approve_synthetic_data))
