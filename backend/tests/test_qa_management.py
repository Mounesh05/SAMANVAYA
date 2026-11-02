"""Isolated QA lifecycle, project-scope, and defect workflow tests."""

from copy import deepcopy

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from domain.models.qa import (
    DefectCreate,
    DefectUpdate,
    ExecutionStepResult,
    TestCaseCreate as QACaseCreate,
    TestCaseUpdate as QACaseUpdate,
    TestExecutionCreate as QAExecutionCreate,
    TestStep as QATestStep,
    TestSuiteCreate as QASuiteCreate,
)
from domain.services.auth_service import AuthService
from domain.services.qa_service import QAService
from repositories.qa_repository import QARepository


class Cursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, field, direction):
        self.documents.sort(key=lambda item: item.get(field, ""), reverse=direction < 0)
        return self

    def skip(self, count):
        self.documents = self.documents[count:]
        return self

    def limit(self, count):
        self.documents = self.documents[:count]
        return self

    async def to_list(self, length=None):
        return deepcopy(self.documents[:length] if length is not None else self.documents)


class Collection:
    def __init__(self, documents=None):
        self.documents = deepcopy(documents or [])

    @staticmethod
    def _matches(document, query):
        for key, expected in query.items():
            actual = document.get(key)
            if isinstance(expected, dict):
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
            elif actual != expected:
                return False
        return True

    async def find_one(self, query, *_args):
        return deepcopy(next((item for item in self.documents if self._matches(item, query)), None))

    def find(self, query, *_args):
        return Cursor([deepcopy(item) for item in self.documents if self._matches(item, query)])

    async def insert_one(self, document):
        self.documents.append(deepcopy(document))

    async def update_one(self, query, update):
        for item in self.documents:
            if self._matches(item, query):
                item.update(deepcopy(update["$set"]))
                return type("UpdateResult", (), {"matched_count": 1})()
        return type("UpdateResult", (), {"matched_count": 0})()

    async def count_documents(self, query):
        return sum(self._matches(item, query) for item in self.documents)


class Repository:
    def __init__(self):
        self.projects = Collection([
            {"id": "PRJ-1", "org_id": "ORG001", "team_id": "TEAM-1", "name": "CampusConnect"},
            {"id": "PRJ-2", "org_id": "ORG002", "team_id": "TEAM-2", "name": "Other"},
        ])
        self.stories = Collection([
            {"id": "STY-1", "project_id": "PRJ-1", "title": "CC-01 | Event API"},
            {"id": "STY-2", "project_id": "PRJ-2", "title": "Other story"},
        ])
        self.tasks = Collection([
            {"id": "TSK-1", "project_id": "PRJ-1", "story_id": "STY-1"},
            {"id": "TSK-2", "project_id": "PRJ-2", "story_id": "STY-2"},
        ])
        self.users = Collection([
            {"employee_id": "DEMO-DEV", "role": "DEVELOPER", "team_id": "TEAM-1", "is_active": True},
            {"employee_id": "DEMO-OTHER", "role": "DEVELOPER", "team_id": "TEAM-2", "org_id": "ORG002", "is_active": True},
            {"employee_id": "DEMO-INACTIVE", "role": "DEVELOPER", "team_id": "TEAM-1", "is_active": False},
        ])
        self.suites = Collection()
        self.cases = Collection()
        self.executions = Collection()
        self.defects = Collection()

    async def find_one(self, collection, query):
        return await collection.find_one(query)

    async def list_documents(self, collection, query, *, skip=0, limit=100, sort_field="created_at"):
        cursor = collection.find(query).sort(sort_field, -1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_documents(self, collection, query):
        return await collection.count_documents(query)

    async def insert(self, collection, document):
        await collection.insert_one(document)
        return deepcopy(document)

    async def update(self, collection, query, updates):
        result = await collection.update_one(query, {"$set": updates})
        return result.matched_count > 0


QA = {"employee_id": "DEMO-QA", "name": "QA User", "role": "QA", "team_id": "TEAM-1", "org_id": "ORG001"}
DEVELOPER = {"employee_id": "DEMO-DEV", "name": "Dev User", "role": "DEVELOPER", "team_id": "TEAM-1", "org_id": "ORG001"}


def test_authentication_claims_preserve_organization_scope():
    claims = AuthService._token_payload({
        "employee_id": "QA-ORG-2",
        "role": "QA",
        "org_id": "ORG002",
    })
    assert claims["org_id"] == "ORG002"


@pytest.mark.asyncio
async def test_mongo_insert_response_does_not_expose_driver_object_id():
    class MongoCollection:
        async def insert_one(self, document):
            document["_id"] = object()

    document = {"id": "QAS-1", "name": "Regression"}
    inserted = await QARepository.insert(None, MongoCollection(), document)

    assert inserted == document
    assert "_id" not in inserted


def new_case_data(**overrides):
    values = {
        "project_id": "PRJ-1",
        "story_id": "STY-1",
        "task_id": "TSK-1",
        "title": "Create event with valid fields",
        "description": "Check event creation.",
        "objective": "Verify valid event payload.",
        "preconditions": "API is available.",
        "steps": [
            QATestStep(step_number=1, instruction="Submit a valid event", expected_result="Event is created"),
            QATestStep(step_number=2, instruction="Fetch the event", expected_result="Event is returned"),
        ],
        "expected_result": "The event is persisted and returned.",
        "priority": "high",
        "test_type": "functional",
    }
    values.update(overrides)
    return QACaseCreate(**values)


def execution(case_id, status, *, defect_id=None, step_status="PASSED"):
    return QAExecutionCreate(
        test_case_id=case_id,
        defect_id=defect_id,
        status=status,
        actual_result=f"Observed {status.lower()} outcome.",
        step_results=[
            ExecutionStepResult(step_number=1, actual_result="Observed step one.", status=step_status),
            ExecutionStepResult(step_number=2, actual_result="Observed step two.", status="PASSED"),
        ],
    )


@pytest.mark.asyncio
async def test_suite_and_case_crud_archive_and_clone_preserve_links():
    repo = Repository()
    service = QAService(repo)
    suite = await service.create_suite(
        QA, QASuiteCreate(project_id="PRJ-1", name="Event API Regression", story_id="STY-1")
    )
    case = await service.create_case(QA, new_case_data(suite_id=suite["id"], story_id=None))
    assert case["story_id"] == "STY-1"
    assert case["author_id"] == "DEMO-QA"

    clone = await service.clone_case(QA, case["id"])
    assert clone["id"] != case["id"]
    assert clone["title"].endswith("(copy)")

    updated = await service.update_case(QA, case["id"], QACaseUpdate(priority="critical"))
    assert updated["priority"] == "critical"
    archived = await service.update_case(QA, case["id"], QACaseUpdate(is_archived=True))
    assert archived["is_archived"] is True
    with pytest.raises(HTTPException) as error:
        await service.update_case(QA, case["id"], QACaseUpdate(title="Not allowed"))
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_suite_case_and_story_links_are_project_scoped():
    repo = Repository()
    service = QAService(repo)
    with pytest.raises(HTTPException) as error:
        await service.create_suite(
            QA, QASuiteCreate(project_id="PRJ-1", name="Invalid", story_id="STY-2")
        )
    assert error.value.status_code == 400
    with pytest.raises(HTTPException) as error:
        await service.create_case(QA, new_case_data(task_id="TSK-2"))
    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_project_and_organization_access_are_enforced():
    service = QAService(Repository())
    with pytest.raises(HTTPException) as error:
        await service.list_cases(
            {**QA, "team_id": "TEAM-2", "org_id": "ORG002"}, "PRJ-1"
        )
    assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        await service.list_cases(QA, "PRJ-2")
    assert error.value.status_code == 403
    with pytest.raises(HTTPException) as error:
        await service.create_case(DEVELOPER, new_case_data())
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_manual_executions_are_append_only_and_archived_case_history_remains():
    repo = Repository()
    service = QAService(repo)
    case = await service.create_case(QA, new_case_data())
    first = await service.create_execution(QA, execution(case["id"], "FAILED", step_status="FAILED"))
    second = await service.create_execution(QA, execution(case["id"], "PASSED"))
    assert first["id"] != second["id"]
    history = await service.list_executions(QA, case["id"])
    assert {item["status"] for item in history} == {"FAILED", "PASSED"}

    await service.update_case(QA, case["id"], QACaseUpdate(is_archived=True))
    dashboard = await service.dashboard(QA, "PRJ-1")
    assert dashboard["total_test_cases"] == 0
    assert dashboard["total_executions"] == 2
    assert len(repo.executions.documents) == 2


@pytest.mark.asyncio
async def test_execution_actor_comes_from_authenticated_identity_not_request_fields():
    service = QAService(Repository())
    case = await service.create_case(QA, new_case_data())
    body = execution(case["id"], "PASSED").model_dump()
    body["executed_by"] = "DEMO-DEV"

    saved = await service.create_execution(QA, QAExecutionCreate(**body))

    assert saved["executed_by"] == "DEMO-QA"


def test_execution_requires_step_results_and_consistent_status():
    with pytest.raises(ValidationError):
        QAExecutionCreate(
            test_case_id="QAT-1",
            status="PASSED",
            actual_result="The request succeeded.",
            step_results=[
                ExecutionStepResult(step_number=1, actual_result="Failed.", status="FAILED")
            ],
        )


@pytest.mark.asyncio
async def test_defect_assignment_fix_retest_and_closure_keep_execution_history():
    repo = Repository()
    service = QAService(repo)
    case = await service.create_case(QA, new_case_data())
    failed = await service.create_execution(
        QA, execution(case["id"], "FAILED", step_status="FAILED")
    )
    defect = await service.create_defect(
        QA,
        DefectCreate(
            project_id="PRJ-1",
            test_case_id=case["id"],
            execution_id=failed["id"],
            title="Event creation validation failed",
            description="The invalid payload was accepted.",
            severity="high",
        ),
    )
    assert defect["reporter_id"] == "DEMO-QA"
    assert defect["actual_result"] == failed["actual_result"]

    defect = await service.update_defect(
        QA, defect["id"], DefectUpdate(assignee_id="DEMO-DEV")
    )
    assert defect["status"] == "ASSIGNED"
    defect = await service.update_defect(
        DEVELOPER, defect["id"], DefectUpdate(status="IN_PROGRESS")
    )
    defect = await service.update_defect(
        DEVELOPER, defect["id"], DefectUpdate(status="FIXED")
    )
    defect = await service.update_defect(
        DEVELOPER, defect["id"], DefectUpdate(status="READY_FOR_RETEST")
    )
    with pytest.raises(HTTPException) as error:
        await service.update_defect(DEVELOPER, defect["id"], DefectUpdate(status="CLOSED"))
    assert error.value.status_code == 400
    passed_retest = await service.create_execution(
        QA, execution(case["id"], "PASSED", defect_id=defect["id"])
    )
    assert passed_retest["defect_id"] == defect["id"]
    closed = await service.update_defect(
        QA, defect["id"], DefectUpdate(status="CLOSED")
    )
    assert closed["status"] == "CLOSED"
    assert len(repo.executions.documents) == 2
    assert len(closed["history"]) == 6


@pytest.mark.asyncio
async def test_failed_retest_reopens_defect_and_cross_project_assignee_is_rejected():
    repo = Repository()
    service = QAService(repo)
    case = await service.create_case(QA, new_case_data())
    failed = await service.create_execution(
        QA, execution(case["id"], "FAILED", step_status="FAILED")
    )
    defect = await service.create_defect(
        QA,
        DefectCreate(
            project_id="PRJ-1",
            test_case_id=case["id"],
            execution_id=failed["id"],
            title="Regression failure",
            description="The case failed.",
        ),
    )
    with pytest.raises(HTTPException) as error:
        await service.update_defect(QA, defect["id"], DefectUpdate(assignee_id="DEMO-OTHER"))
    assert error.value.status_code == 400

    defect = await service.update_defect(QA, defect["id"], DefectUpdate(assignee_id="DEMO-DEV"))
    defect = await service.update_defect(DEVELOPER, defect["id"], DefectUpdate(status="IN_PROGRESS"))
    defect = await service.update_defect(DEVELOPER, defect["id"], DefectUpdate(status="FIXED"))
    defect = await service.update_defect(QA, defect["id"], DefectUpdate(status="READY_FOR_RETEST"))
    retried = await service.create_execution(
        QA, execution(case["id"], "FAILED", defect_id=defect["id"], step_status="FAILED")
    )
    assert retried["id"] != failed["id"]
    updated = await service.get_defect(QA, defect["id"])
    assert updated["status"] == "REOPENED"


@pytest.mark.asyncio
async def test_execution_dashboard_counts_completed_and_blocked_without_fabrication():
    repo = Repository()
    service = QAService(repo)
    case = await service.create_case(QA, new_case_data())
    empty = await service.dashboard(QA, "PRJ-1")
    assert empty["pass_rate"] is None
    assert empty["not_executed"] == 1

    await service.create_execution(QA, execution(case["id"], "PASSED"))
    await service.create_execution(QA, execution(case["id"], "BLOCKED", step_status="BLOCKED"))
    result = await service.dashboard(QA, "PRJ-1")
    assert result["passed"] == 1
    assert result["blocked"] == 1
    assert result["pass_rate"] == 100
    assert result["pass_rate_excludes_blocked"] is True
