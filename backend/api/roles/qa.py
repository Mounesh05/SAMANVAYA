"""
QA Engineer role-specific dashboard endpoints.
Shows: Test health, bug reports, regression risks, release readiness.
"""

from fastapi import APIRouter, Depends
from core.dependencies import require_roles
from core.database import col
from repositories.task_repository import TaskRepository


async def _qa_snapshot():
    task_repo = TaskRepository()
    bugs = await task_repo.find_all({"type": {"$regex": "^bug$", "$options": "i"}})
    test_runs = await col("test_runs").find({}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
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
async def qa_dashboard(user: dict = Depends(require_roles("QA"))):
    """
    QA dashboard - Quality and testing overview.
    
    Returns:
        - Test execution status
        - Bug reports
        - Regression risk
        - Release readiness
    """
    snapshot = await _qa_snapshot()
    return {
        "role": "QA",
        "name": user["name"],
        "summary": {
            "total_test_cases": snapshot["total_tests"],
            "passed_tests": snapshot["passed_tests"],
            "failed_tests": snapshot["failed_tests"],
            "open_bugs": len(snapshot["open_bugs"]),
            "critical_bugs": len(snapshot["critical_bugs"]),
            "regression_risk": snapshot["regression_risk"],
        },
        "insufficient_data": not snapshot["test_runs"] and not snapshot["bugs"],
    }


@router.get("/test-health")
async def test_health(user: dict = Depends(require_roles("QA"))):
    """Get test execution health metrics."""
    snapshot = await _qa_snapshot()
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
async def bug_reports(user: dict = Depends(require_roles("QA"))):
    """Get all bug reports."""
    snapshot = await _qa_snapshot()
    return {
        "bugs": snapshot["bugs"],
        "total": len(snapshot["bugs"]),
        "open": len(snapshot["open_bugs"]),
        "critical": len(snapshot["critical_bugs"]),
        "insufficient_data": not snapshot["bugs"],
    }
