"""Authenticated APIs for test management, manual execution, and defects."""

from fastapi import APIRouter, Depends, HTTPException, Query

from core.dependencies import get_current_user
from domain.models.qa import (
    DefectCreate,
    DefectUpdate,
    TestCaseCreate,
    TestCaseUpdate,
    TestExecutionCreate,
    TestSuiteCreate,
    TestSuiteUpdate,
)
from domain.services.qa_service import QAService

router = APIRouter(tags=["QA Management"])
qa_service = QAService()


@router.get("/projects")
async def list_qa_projects(user: dict = Depends(get_current_user)):
    return await qa_service.list_projects(user)


@router.get("/dashboard")
async def get_qa_dashboard(
    project_id: str | None = None,
    user: dict = Depends(get_current_user),
):
    return await qa_service.dashboard(user, project_id)


@router.get("/suites")
async def list_test_suites(
    project_id: str = Query(..., min_length=1),
    user: dict = Depends(get_current_user),
):
    return await qa_service.list_suites(user, project_id)


@router.post("/suites", status_code=201)
async def create_test_suite(
    data: TestSuiteCreate,
    user: dict = Depends(get_current_user),
):
    return await qa_service.create_suite(user, data)


@router.patch("/suites/{suite_id}")
async def update_test_suite(
    suite_id: str,
    updates: TestSuiteUpdate,
    user: dict = Depends(get_current_user),
):
    return await qa_service.update_suite(user, suite_id, updates)


@router.get("/cases")
async def list_test_cases(
    project_id: str = Query(..., min_length=1),
    suite_id: str | None = None,
    story_id: str | None = None,
    priority: str | None = None,
    search: str | None = Query(default=None, max_length=160),
    include_archived: bool = False,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    return await qa_service.list_cases(
        user,
        project_id,
        suite_id=suite_id,
        story_id=story_id,
        priority=priority,
        search=search,
        include_archived=include_archived,
        skip=skip,
        limit=limit,
    )


@router.post("/cases", status_code=201)
async def create_test_case(
    data: TestCaseCreate,
    user: dict = Depends(get_current_user),
):
    return await qa_service.create_case(user, data)


@router.get("/cases/{case_id}")
async def get_test_case(case_id: str, user: dict = Depends(get_current_user)):
    return await qa_service.get_case(user, case_id)


@router.patch("/cases/{case_id}")
async def update_test_case(
    case_id: str,
    updates: TestCaseUpdate,
    user: dict = Depends(get_current_user),
):
    return await qa_service.update_case(user, case_id, updates)


@router.post("/cases/{case_id}/clone", status_code=201)
async def clone_test_case(case_id: str, user: dict = Depends(get_current_user)):
    return await qa_service.clone_case(user, case_id)


@router.get("/cases/{case_id}/executions")
async def list_case_executions(
    case_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    return await qa_service.list_executions(user, case_id, skip=skip, limit=limit)


@router.post("/cases/{case_id}/executions", status_code=201)
async def execute_test_case(
    case_id: str,
    data: TestExecutionCreate,
    user: dict = Depends(get_current_user),
):
    if data.test_case_id != case_id:
        raise HTTPException(status_code=400, detail="Test case ID does not match the URL")
    return await qa_service.create_execution(user, data)


@router.get("/defects")
async def list_qa_defects(
    project_id: str | None = None,
    status: str | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    user: dict = Depends(get_current_user),
):
    return await qa_service.list_defects(
        user, project_id, status=status, skip=skip, limit=limit
    )


@router.post("/defects", status_code=201)
async def create_qa_defect(
    data: DefectCreate,
    user: dict = Depends(get_current_user),
):
    return await qa_service.create_defect(user, data)


@router.get("/defects/{defect_id}")
async def get_qa_defect(defect_id: str, user: dict = Depends(get_current_user)):
    return await qa_service.get_defect(user, defect_id)


@router.patch("/defects/{defect_id}")
async def update_qa_defect(
    defect_id: str,
    updates: DefectUpdate,
    user: dict = Depends(get_current_user),
):
    return await qa_service.update_defect(user, defect_id, updates)
