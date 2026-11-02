"""
QA Engineer role-specific dashboard endpoints.
Shows: Test health, bug reports, regression risks, release readiness.
"""

from fastapi import APIRouter, Depends
from typing import Optional
from core.dependencies import require_roles
from core.database import col
from repositories.task_repository import TaskRepository
from domain.services.qa_service import QAService


async def _qa_snapshot(user: dict | None = None, project_id: str | None = None):
    task_repo = TaskRepository()
    if user is None:
        project_ids = None
    else:
        service = QAService()
        if project_id:
            await service.accessible_project(user, project_id)
            project_ids = [project_id]
        else:
            projects = await service.list_projects(user)
            project_ids = [project["id"] for project in projects]
    query = {"type": {"$regex": "^bug$", "$options": "i"}}
    run_query = {}
    case_query = {}
    if project_ids is not None:
        query["project_id"] = {"$in": project_ids}
        run_query["project_id"] = {"$in": project_ids}
        case_query["project_id"] = {"$in": project_ids}
    bugs = await task_repo.find_all(query)
    test_runs = await col("test_runs").find(run_query, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    test_cases = await col("qa_test_cases").find(
        {**case_query, "is_archived": False}, {"_id": 0, "id": 1}
    ).limit(5000).to_list(5000)
    if user is not None and project_ids:
        qa_defects = await col("qa_defects").find(
            {"project_id": {"$in": project_ids}}, {"_id": 0}
        ).limit(5000).to_list(5000)
        bugs.extend(qa_defects)
    total_tests = sum(int(run.get("tests_run", 0) or 0) for run in test_runs)
    passed_tests = sum(int(run.get("tests_passed", 0) or 0) for run in test_runs)
    failed_tests = sum(int(run.get("tests_failed", 0) or 0) for run in test_runs)
    open_bugs = [
        bug for bug in bugs
        if str(bug.get("status", "")).lower() not in {"done", "completed", "closed", "resolved"}
    ]
    critical_bugs = [
        bug for bug in open_bugs
        if str(bug.get("priority", bug.get("severity", ""))).lower() == "critical"
    ]
    regression_risk = None
    if total_tests or open_bugs:
        failure_rate = failed_tests / total_tests if total_tests else 0
        regression_risk = "HIGH" if critical_bugs or failure_rate >= 0.1 else "MEDIUM" if open_bugs else "LOW"
    return {
        "bugs": bugs,
        "test_runs": test_runs,
        "total_test_cases": len(test_cases),
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": failed_tests,
        "open_bugs": open_bugs,
        "critical_bugs": critical_bugs,
        "regression_risk": regression_risk,
    }


def _test_suite_view(run: dict) -> dict:
    """Normalize CI ingestion fields for the QA dashboard table."""
    tests_run = int(run.get("tests_run", 0) or 0)
    tests_passed = int(run.get("tests_passed", 0) or 0)
    tests_failed = int(run.get("tests_failed", 0) or 0)
    tests_skipped = int(run.get("tests_skipped", 0) or 0)
    return {
        "name": run.get("test_suite") or run.get("name") or "Unnamed suite",
        "status": run.get("status", "pending"),
        "total": tests_run,
        "passed": tests_passed,
        "failed": tests_failed,
        "skipped": tests_skipped,
        "duration": run.get("duration_seconds"),
        "pass_rate": round(tests_passed / tests_run * 100, 2) if tests_run else 0,
        "repository": run.get("repository"),
        "branch": run.get("branch"),
        "commit_sha": run.get("commit_sha"),
        "project_id": run.get("project_id"),
    }


router = APIRouter()


@router.get("/dashboard")
async def qa_dashboard(
    project_id: Optional[str] = None,
    user: dict = Depends(require_roles("QA")),
):
    """
    QA dashboard - Quality and testing overview.
    
    Returns:
        - Test execution status
        - Bug reports
        - Regression risk
        - Release readiness
    """
    snapshot = await _qa_snapshot(user, project_id)
    return {
        "role": "QA",
        "name": user["name"],
        "summary": {
            "total_test_cases": snapshot["total_test_cases"],
            "passed_tests": snapshot["passed_tests"],
            "failed_tests": snapshot["failed_tests"],
            "open_bugs": len(snapshot["open_bugs"]),
            "critical_bugs": len(snapshot["critical_bugs"]),
            "regression_risk": snapshot["regression_risk"],
        },
        "insufficient_data": not snapshot["test_runs"] and not snapshot["bugs"],
    }


@router.get("/test-health")
async def test_health(
    project_id: Optional[str] = None,
    user: dict = Depends(require_roles("QA")),
):
    """Get test execution health metrics."""
    snapshot = await _qa_snapshot(user, project_id)
    suites = [_test_suite_view(run) for run in snapshot["test_runs"]]
    no_test_failures = sum(
        1 for suite in suites
        if suite["status"] == "failed" and suite["total"] == 0
    )
    return {
        "test_suites": suites,
        "overall_pass_rate": (
            round(snapshot["passed_tests"] / snapshot["total_tests"] * 100, 2)
            if snapshot["total_tests"] else None
        ),
        "no_test_failures": no_test_failures,
        "has_blocking_failures": any(suite["status"] == "failed" for suite in suites),
        "insufficient_data": not snapshot["test_runs"],
    }


@router.get("/bugs")
async def bug_reports(
    project_id: Optional[str] = None,
    user: dict = Depends(require_roles("QA")),
):
    """Get all bug reports."""
    snapshot = await _qa_snapshot(user, project_id)
    return {
        "bugs": snapshot["bugs"],
        "total": len(snapshot["bugs"]),
        "open": len(snapshot["open_bugs"]),
        "critical": len(snapshot["critical_bugs"]),
        "insufficient_data": not snapshot["bugs"],
    }
