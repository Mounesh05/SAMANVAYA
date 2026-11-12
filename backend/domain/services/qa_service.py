"""Project-scoped QA workflows and authorization."""

from datetime import datetime, timezone
import re
import uuid

from fastapi import HTTPException

from core.config import settings
from core.permissions import Permission, get_user_permissions
from domain.models.qa import (
    DefectCreate,
    DefectUpdate,
    TestCaseCreate,
    TestCaseUpdate,
    TestExecutionCreate,
    TestSuiteCreate,
    TestSuiteUpdate,
)
from repositories.qa_repository import QARepository


MANAGEMENT_ROLES = {"QA", "PM", "LEAD", "CEO"}
READ_ROLES = {"QA", "DEVELOPER", "DEVOPS", "LEAD", "PM", "CEO"}
TERMINAL_DEFECT_STATES = {"CLOSED"}


def _role(user):
    return str(user.get("role", user.get("organizational_role", ""))).upper()


def _permissions(user):
    return get_user_permissions(_role(user), user.get("is_admin", False), user.get("designation"))


def _identity(user):
    return user.get("employee_id") or user.get("id") or user.get("sub") or ""


def _now():
    return datetime.now(timezone.utc).isoformat()


class QAService:
    def __init__(self, repository=None):
        self.repo = repository or QARepository()

    @staticmethod
    def _org_id(user):
        return (
            user.get("org_id")
            or user.get("organization_id")
            or user.get("organisation_id")
            or settings.DEFAULT_ORG_ID
        )

    async def accessible_project(self, user, project_id):
        role = _role(user)
        if role not in READ_ROLES:
            raise HTTPException(status_code=403, detail="QA project access is not available for this role")

        project = await self.repo.find_one(self.repo.projects, {"id": project_id})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        user_org = self._org_id(user)
        project_org = project.get("org_id") or project.get("organization_id")
        if user_org and project_org and user_org != project_org:
            raise HTTPException(status_code=403, detail="Project belongs to another organization")

        if role == "CEO":
            return project

        assigned_projects = set(user.get("project_ids") or [])
        if project_id in assigned_projects:
            return project

        user_team = user.get("team_id")
        project_team = project.get("team_id")
        if user_team and project_team and user_team == project_team:
            return project

        # CR-004: Leads use the same project scope as the rest of the app (team
        # and assigned projects, checked above). PM keeps organisation-wide QA
        # access until CR-005.
        if role == "PM" and user_org and project_org == user_org:
            return project

        raise HTTPException(status_code=403, detail="You don't have access to this project")

    async def list_projects(self, user):
        role = _role(user)
        if role not in READ_ROLES:
            raise HTTPException(status_code=403, detail="QA project access is not available for this role")
        cursor = self.repo.projects.find({}, {"_id": 0}).sort("name", 1)
        projects = await cursor.to_list(length=1000)
        allowed = []
        for project in projects:
            try:
                await self.accessible_project(user, project.get("id", ""))
                allowed.append(project)
            except HTTPException as error:
                if error.status_code != 403:
                    raise
        return allowed

    async def _require(self, user, permission):
        if permission not in _permissions(user):
            raise HTTPException(status_code=403, detail="Insufficient permissions for this QA operation")

    async def _linked_document(self, collection, record_id, project_id, label):
        if not record_id:
            return None
        document = await self.repo.find_one(collection, {"id": record_id})
        if not document:
            raise HTTPException(status_code=404, detail=f"{label} not found")
        if document.get("project_id") != project_id:
            raise HTTPException(status_code=400, detail=f"{label} must belong to the same project")
        return document

    async def _validate_case_links(self, project_id, suite_id, story_id, task_id):
        suite = await self._linked_document(self.repo.suites, suite_id, project_id, "Test suite")
        if suite and suite.get("status") != "active":
            raise HTTPException(status_code=400, detail="Archived test suites cannot accept test cases")
        if suite and suite.get("story_id"):
            if story_id and suite["story_id"] != story_id:
                raise HTTPException(status_code=400, detail="Story does not match the test suite")
            story_id = story_id or suite["story_id"]
        story = await self._linked_document(self.repo.stories, story_id, project_id, "Story")
        task = await self._linked_document(self.repo.tasks, task_id, project_id, "Task")
        if task and story_id and task.get("story_id") != story_id:
            raise HTTPException(status_code=400, detail="Task must belong to the selected story")
        return story_id

    async def list_suites(self, user, project_id):
        await self.accessible_project(user, project_id)
        return await self.repo.list_documents(
            self.repo.suites, {"project_id": project_id}, limit=500
        )

    async def create_suite(self, user, data: TestSuiteCreate):
        await self._require(user, Permission.MANAGE_TEST_CASES)
        await self.accessible_project(user, data.project_id)
        await self._linked_document(self.repo.stories, data.story_id, data.project_id, "Story")
        timestamp = _now()
        document = {
            **data.model_dump(),
            "id": f"QAS-{uuid.uuid4().hex[:8].upper()}",
            "status": "active",
            "created_by": _identity(user),
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        return await self.repo.insert(self.repo.suites, document)

    async def update_suite(self, user, suite_id, updates: TestSuiteUpdate):
        await self._require(user, Permission.MANAGE_TEST_CASES)
        suite = await self.repo.find_one(self.repo.suites, {"id": suite_id})
        if not suite:
            raise HTTPException(status_code=404, detail="Test suite not found")
        await self.accessible_project(user, suite["project_id"])
        fields = updates.model_dump(exclude_unset=True)
        if "story_id" in fields:
            await self._linked_document(
                self.repo.stories, fields["story_id"], suite["project_id"], "Story"
            )
        if fields:
            fields["updated_at"] = _now()
            await self.repo.update(
                self.repo.suites, {"id": suite_id, "project_id": suite["project_id"]}, fields
            )
            suite.update(fields)
        return suite

    async def list_cases(self, user, project_id, *, suite_id=None, story_id=None, search=None,
                         priority=None, include_archived=False, skip=0, limit=100):
        await self.accessible_project(user, project_id)
        query = {"project_id": project_id}
        if not include_archived:
            query["is_archived"] = False
        if suite_id:
            query["suite_id"] = suite_id
        if story_id:
            query["story_id"] = story_id
        if priority:
            query["priority"] = priority
        if search:
            query["title"] = {"$regex": re.escape(search), "$options": "i"}
        return await self.repo.list_documents(
            self.repo.cases, query, skip=skip, limit=limit
        )

    async def create_case(self, user, data: TestCaseCreate):
        await self._require(user, Permission.MANAGE_TEST_CASES)
        await self.accessible_project(user, data.project_id)
        story_id = await self._validate_case_links(
            data.project_id, data.suite_id, data.story_id, data.task_id
        )
        timestamp = _now()
        document = {
            **data.model_dump(mode="json"),
            "story_id": story_id,
            "id": f"QAT-{uuid.uuid4().hex[:8].upper()}",
            "author_id": _identity(user),
            "is_archived": False,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        return await self.repo.insert(self.repo.cases, document)

    async def get_case(self, user, case_id):
        case = await self.repo.find_one(self.repo.cases, {"id": case_id})
        if not case:
            raise HTTPException(status_code=404, detail="Test case not found")
        await self.accessible_project(user, case["project_id"])
        return case

    async def update_case(self, user, case_id, updates: TestCaseUpdate):
        await self._require(user, Permission.MANAGE_TEST_CASES)
        case = await self.get_case(user, case_id)
        if case.get("is_archived"):
            raise HTTPException(status_code=409, detail="Archived test cases cannot be edited")
        fields = updates.model_dump(exclude_unset=True, mode="json")
        effective_story_id = await self._validate_case_links(
            case["project_id"],
            fields.get("suite_id", case.get("suite_id")),
            fields.get("story_id", case.get("story_id")),
            fields.get("task_id", case.get("task_id")),
        )
        if effective_story_id != case.get("story_id"):
            fields["story_id"] = effective_story_id
        if fields:
            fields["updated_at"] = _now()
            await self.repo.update(
                self.repo.cases, {"id": case_id, "project_id": case["project_id"]}, fields
            )
            case.update(fields)
        return case

    async def clone_case(self, user, case_id):
        await self._require(user, Permission.MANAGE_TEST_CASES)
        original = await self.get_case(user, case_id)
        if original.get("is_archived"):
            raise HTTPException(status_code=409, detail="Archived test cases cannot be cloned")
        timestamp = _now()
        clone = {
            key: value
            for key, value in original.items()
            if key not in {"id", "created_at", "updated_at"}
        }
        clone.update(
            id=f"QAT-{uuid.uuid4().hex[:8].upper()}",
            title=f"{original['title']} (copy)",
            author_id=_identity(user),
            created_at=timestamp,
            updated_at=timestamp,
        )
        return await self.repo.insert(self.repo.cases, clone)

    async def create_execution(self, user, data: TestExecutionCreate):
        await self._require(user, Permission.MANAGE_TEST_CASES)
        case = await self.get_case(user, data.test_case_id)
        if case.get("is_archived"):
            raise HTTPException(status_code=409, detail="Archived test cases cannot be executed")
        required_steps = list(range(1, len(case.get("steps", [])) + 1))
        submitted_steps = [step.step_number for step in data.step_results]
        if submitted_steps != required_steps:
            raise HTTPException(
                status_code=400,
                detail="Record one result for every test step in its original order",
            )

        defect = None
        if data.defect_id:
            defect = await self._linked_document(
                self.repo.defects, data.defect_id, case["project_id"], "Defect"
            )
            if defect.get("test_case_id") != case["id"]:
                raise HTTPException(status_code=400, detail="Defect must reference this test case")
            if defect.get("status") != "READY_FOR_RETEST":
                raise HTTPException(status_code=409, detail="Defect is not ready for retest")

        timestamp = _now()
        document = {
            **data.model_dump(mode="json"),
            "id": f"QAX-{uuid.uuid4().hex[:8].upper()}",
            "project_id": case["project_id"],
            "executed_by": _identity(user),
            "executed_at": timestamp,
            "created_at": timestamp,
        }
        await self.repo.insert(self.repo.executions, document)
        if defect and data.status == "FAILED":
            await self.repo.update(
                self.repo.defects,
                {"id": defect["id"], "project_id": case["project_id"]},
                {
                    "status": "REOPENED",
                    "last_execution_id": document["id"],
                    "updated_at": timestamp,
                },
            )
        return document

    async def list_executions(self, user, case_id, *, skip=0, limit=100):
        case = await self.get_case(user, case_id)
        return await self.repo.list_documents(
            self.repo.executions,
            {"project_id": case["project_id"], "test_case_id": case_id},
            skip=skip,
            limit=limit,
            sort_field="executed_at",
        )

    async def _validate_assignee(self, user, project, assignee_id):
        if not assignee_id:
            return
        employee = await self.repo.find_one(
            self.repo.users, {"employee_id": assignee_id, "is_active": {"$ne": False}}
        )
        if not employee:
            raise HTTPException(status_code=404, detail="Active assignee not found")
        if str(employee.get("role", "")).upper() not in {"DEVELOPER", "DEVOPS"}:
            raise HTTPException(status_code=400, detail="Defects can only be assigned to developers or DevOps")
        project_org = project.get("org_id") or project.get("organization_id")
        employee_org = (
            employee.get("org_id")
            or employee.get("organization_id")
            or employee.get("organisation_id")
        )
        if project_org and employee_org and project_org != employee_org:
            raise HTTPException(status_code=400, detail="Assignee belongs to another organization")
        employee_team = employee.get("team_id")
        project_team = project.get("team_id")
        employee_projects = employee.get("project_ids") or []
        if not (employee_team == project_team or project["id"] in employee_projects):
            raise HTTPException(status_code=400, detail="Assignee is not a member of this project")

    async def _validate_defect_links(self, project_id, test_case_id, execution_id, story_id, task_id):
        case = await self._linked_document(
            self.repo.cases, test_case_id, project_id, "Test case"
        )
        execution = await self._linked_document(
            self.repo.executions, execution_id, project_id, "Execution"
        )
        story = await self._linked_document(self.repo.stories, story_id, project_id, "Story")
        task = await self._linked_document(self.repo.tasks, task_id, project_id, "Task")
        if execution and execution.get("status") != "FAILED":
            raise HTTPException(status_code=400, detail="Defects can only link to failed executions")
        if execution and case and execution.get("test_case_id") != case.get("id"):
            raise HTTPException(status_code=400, detail="Execution does not belong to the test case")
        if execution and not case:
            case = await self._linked_document(
                self.repo.cases, execution["test_case_id"], project_id, "Test case"
            )
        if case and story_id and case.get("story_id") != story_id:
            raise HTTPException(status_code=400, detail="Story does not match the test case")
        if task and story_id and task.get("story_id") != story_id:
            raise HTTPException(status_code=400, detail="Task does not belong to the selected story")
        if case:
            story_id = story_id or case.get("story_id")
            task_id = task_id or case.get("task_id")
        return case, execution, story_id, task_id

    async def list_defects(self, user, project_id=None, *, status=None, skip=0, limit=100):
        await self._require(user, Permission.VIEW_DEFECTS)
        if project_id:
            project = await self.accessible_project(user, project_id)
            project_ids = [project_id]
        else:
            projects = await self.list_projects(user)
            project_ids = [project["id"] for project in projects]
        query = {"project_id": {"$in": project_ids}}
        if status:
            query["status"] = status
        if _role(user) in {"DEVELOPER", "DEVOPS"}:
            # Defects assigned to them, plus the ones they reported (CR-001/CR-003).
            query["$or"] = [{"assignee_id": _identity(user)}, {"reporter_id": _identity(user)}]
        return await self.repo.list_documents(
            self.repo.defects, query, skip=skip, limit=limit
        )

    async def create_defect(self, user, data: DefectCreate):
        # Anyone holding CREATE_BUG (QA, Developer, Lead) can report a defect;
        # QA still owns assignment, verification and closure via update_defect.
        if Permission.CREATE_BUG not in _permissions(user):
            raise HTTPException(status_code=403, detail="Insufficient permissions to report a defect")
        project = await self.accessible_project(user, data.project_id)
        case, execution, story_id, task_id = await self._validate_defect_links(
            data.project_id,
            data.test_case_id,
            data.execution_id,
            data.story_id,
            data.task_id,
        )
        if execution:
            if not data.actual_result:
                data = data.model_copy(update={"actual_result": execution["actual_result"]})
            if not data.expected_result and case:
                data = data.model_copy(update={"expected_result": case["expected_result"]})
        timestamp = _now()
        document = {
            **data.model_dump(exclude={"project_id"}),
            "id": f"QAB-{uuid.uuid4().hex[:8].upper()}",
            "project_id": data.project_id,
            "story_id": story_id,
            "task_id": task_id,
            "status": "OPEN",
            "reporter_id": _identity(user),
            "reporter_name": user.get("name", _identity(user)),
            "assignee_id": None,
            "history": [{"status": "OPEN", "actor_id": _identity(user), "at": timestamp}],
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        return await self.repo.insert(self.repo.defects, document)

    async def get_defect(self, user, defect_id):
        await self._require(user, Permission.VIEW_DEFECTS)
        defect = await self.repo.find_one(self.repo.defects, {"id": defect_id})
        if not defect:
            raise HTTPException(status_code=404, detail="Defect not found")
        await self.accessible_project(user, defect["project_id"])
        identity = _identity(user)
        if _role(user) in {"DEVELOPER", "DEVOPS"} and identity not in {defect.get("assignee_id"), defect.get("reporter_id")}:
            raise HTTPException(status_code=403, detail="You can only view defects assigned to you or reported by you")
        return defect

    async def update_defect(self, user, defect_id, updates: DefectUpdate):
        defect = await self.get_defect(user, defect_id)
        role = _role(user)
        fields = updates.model_dump(exclude_unset=True)
        if not fields:
            return defect
        project = await self.accessible_project(user, defect["project_id"])
        timestamp = _now()
        new_status = fields.pop("status", None)
        new_assignee = fields.pop("assignee_id", None) if "assignee_id" in fields else None
        changes = dict(fields)
        history = list(defect.get("history") or [])

        if "assignee_id" in updates.model_fields_set:
            if role not in MANAGEMENT_ROLES:
                raise HTTPException(status_code=403, detail="Only QA, PM, or Lead can assign defects")
            await self._validate_assignee(user, project, new_assignee)
            changes["assignee_id"] = new_assignee
            if new_assignee and defect["status"] == "OPEN":
                new_status = "ASSIGNED"

        if changes and role not in MANAGEMENT_ROLES:
            raise HTTPException(status_code=403, detail="Only QA, PM, or Lead can edit defect details")
        if new_status:
            current = defect["status"]
            if current in TERMINAL_DEFECT_STATES:
                raise HTTPException(status_code=409, detail="Closed defects cannot be changed")
            if role in {"DEVELOPER", "DEVOPS"}:
                if defect.get("assignee_id") != _identity(user):
                    raise HTTPException(status_code=403, detail="You can only update assigned defects")
                allowed = {
                    "ASSIGNED": {"IN_PROGRESS"},
                    "IN_PROGRESS": {"FIXED"},
                    "FIXED": {"READY_FOR_RETEST"},
                    "REOPENED": {"IN_PROGRESS"},
                }
                if new_status not in allowed.get(current, set()):
                    raise HTTPException(status_code=400, detail="Invalid developer defect transition")
            elif Permission.VERIFY_DEFECTS in _permissions(user):  # QA (CR-002)
                allowed = {
                    "OPEN": {"ASSIGNED"},
                    "ASSIGNED": {"IN_PROGRESS"},
                    "IN_PROGRESS": {"FIXED"},
                    "FIXED": {"READY_FOR_RETEST"},
                    "READY_FOR_RETEST": {"CLOSED", "REOPENED"},
                    "REOPENED": {"ASSIGNED", "IN_PROGRESS"},
                }
                if new_status not in allowed.get(current, set()):
                    raise HTTPException(status_code=400, detail="Invalid QA defect transition")
            elif role not in {"PM", "LEAD", "CEO"}:
                raise HTTPException(status_code=403, detail="Insufficient permissions to change defect status")
            elif role in {"LEAD", "PM"} and current == "READY_FOR_RETEST":
                # CR-004 (Lead) and CR-005 (PM): QA verifies fixes; managers
                # assign and prioritise.
                raise HTTPException(status_code=403, detail="QA verifies and closes defects; Leads and PMs can assign and prioritise them")
            else:
                allowed = {
                    "OPEN": {"ASSIGNED"},
                    "ASSIGNED": {"IN_PROGRESS"},
                    "IN_PROGRESS": {"FIXED"},
                    "FIXED": {"READY_FOR_RETEST"},
                    "READY_FOR_RETEST": {"CLOSED", "REOPENED"},
                    "REOPENED": {"ASSIGNED", "IN_PROGRESS"},
                }
                if new_status not in allowed.get(current, set()):
                    raise HTTPException(status_code=400, detail="Invalid defect transition")

            if new_status == "CLOSED":
                executions = await self.repo.list_documents(
                    self.repo.executions,
                    {
                        "project_id": defect["project_id"],
                        "test_case_id": defect.get("test_case_id"),
                        "defect_id": defect_id,
                    },
                    limit=1,
                    sort_field="executed_at",
                )
                latest = executions[0] if executions else None
                if not latest or latest.get("status") != "PASSED":
                    raise HTTPException(status_code=409, detail="A passing retest is required to close this defect")
                if latest.get("id") == defect.get("execution_id"):
                    raise HTTPException(status_code=409, detail="A new retest is required before closing this defect")

            changes["status"] = new_status
            history.append(
                {"status": new_status, "actor_id": _identity(user), "at": timestamp}
            )

        changes["history"] = history
        changes["updated_at"] = timestamp
        await self.repo.update(
            self.repo.defects,
            {"id": defect_id, "project_id": defect["project_id"]},
            changes,
        )
        defect.update(changes)
        return defect

    async def dashboard(self, user, project_id=None):
        if project_id:
            await self.accessible_project(user, project_id)
            project_ids = [project_id]
        else:
            projects = await self.list_projects(user)
            project_ids = [project["id"] for project in projects]
        scope = {"project_id": {"$in": project_ids}}
        cases = await self.repo.list_documents(
            self.repo.cases,
            {**scope, "is_archived": False},
            limit=5000,
        )
        executions = await self.repo.list_documents(
            self.repo.executions, scope, limit=5000, sort_field="executed_at"
        )
        defects = await self.repo.list_documents(
            self.repo.defects, scope, limit=5000
        )
        counts = {
            status: sum(1 for item in executions if item.get("status") == status)
            for status in ("PASSED", "FAILED", "BLOCKED")
        }
        executed_case_ids = {item["test_case_id"] for item in executions}
        passed_failed = counts["PASSED"] + counts["FAILED"]
        trend = {}
        for execution in executions:
            day = str(execution.get("executed_at", ""))[:10]
            point = trend.setdefault(day, {"passed": 0, "failed": 0, "blocked": 0})
            key = execution.get("status", "").lower()
            if key in point:
                point[key] += 1
        open_defects = [
            item for item in defects if item.get("status") not in TERMINAL_DEFECT_STATES
        ]
        return {
            "project_ids": project_ids,
            "total_test_cases": len(cases),
            "total_executions": len(executions),
            "passed": counts["PASSED"],
            "failed": counts["FAILED"],
            "blocked": counts["BLOCKED"],
            "not_executed": sum(1 for case in cases if case["id"] not in executed_case_ids),
            "pass_rate": round(counts["PASSED"] / passed_failed * 100, 2)
            if passed_failed
            else None,
            "pass_rate_excludes_blocked": True,
            "open_defects": len(open_defects),
            "awaiting_retest": sum(
                1 for item in defects if item.get("status") == "READY_FOR_RETEST"
            ),
            "recent_executions": sorted(
                executions, key=lambda item: item.get("executed_at", ""), reverse=True
            )[:10],
            "execution_trend": [
                {"date": day, **trend[day]} for day in sorted(trend)[-30:]
            ],
        }
