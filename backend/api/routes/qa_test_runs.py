"""CI test-result ingestion for the QA dashboard."""

import hashlib
import hmac
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from core.config import settings
from core.database import col
from core.dependencies import get_current_user

router = APIRouter(tags=["QA Test Results"])


class TestRunSubmission(BaseModel):
    project_id: str = Field(..., min_length=1)
    repository: str = Field(..., min_length=1)
    branch: str = Field(..., min_length=1)
    commit_sha: str = Field(..., min_length=7, max_length=64)
    test_suite: str = Field(..., min_length=1)
    tests_run: int = Field(..., ge=0)
    tests_passed: int = Field(..., ge=0)
    tests_failed: int = Field(..., ge=0)
    tests_skipped: int = Field(default=0, ge=0)
    duration_seconds: float | None = Field(default=None, ge=0)
    status: str = Field(..., pattern="^(passed|failed|error|cancelled)$")
    created_at: datetime | None = None
    
    # GitHub Actions metadata
    source: str = Field(default="github_actions")
    pr_number: int | None = Field(default=None, ge=1)
    workflow_run_id: str | None = Field(default=None, max_length=100)
    workflow_name: str | None = Field(default=None, max_length=200)
    run_attempt: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_counts(self):
        if self.tests_passed + self.tests_failed > self.tests_run:
            raise ValueError("tests_passed + tests_failed cannot exceed tests_run")
        return self


def _record_id(submission: TestRunSubmission) -> str:
    """Generate idempotency key including workflow run details."""
    if submission.workflow_run_id and submission.run_attempt:
        # Use workflow run ID + attempt for GitHub Actions runs
        key = "|".join([
            submission.repository,
            submission.workflow_run_id,
            str(submission.run_attempt),
            submission.test_suite
        ])
    else:
        # Fallback to commit-based key for other sources
        key = "|".join([
            submission.repository,
            submission.commit_sha,
            submission.test_suite
        ])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _verify_ci_token(token: str | None) -> None:
    configured = settings.QA_TEST_RESULTS_TOKEN
    if not configured:
        raise HTTPException(
            status_code=503,
            detail="QA test-result ingestion is not configured",
        )
    if not token or not hmac.compare_digest(token, configured):
        raise HTTPException(status_code=401, detail="Invalid test-result token")


@router.post("/test-runs", status_code=201)
async def submit_test_run(
    submission: TestRunSubmission,
    x_test_results_token: str | None = Header(None, alias="X-Test-Results-Token"),
):
    """Store one CI test result. Safe to retry for the same commit and suite."""
    _verify_ci_token(x_test_results_token)
    
    # Only repositories with CI enabled for this project may report results.
    # (Bug sweep: results for a project with no CI configuration used to be
    # accepted from any repository.)
    ci_configs = await col("qa_ci_configs").find({"project_id": submission.project_id}).to_list(length=None)
    allowed_repos = set(config.get("repository") for config in ci_configs if config.get("repository"))
    if not allowed_repos:
        raise HTTPException(
            status_code=403,
            detail="CI is not enabled for this project, so it cannot receive test results",
        )
    if submission.repository not in allowed_repos:
        raise HTTPException(
            status_code=403,
            detail=f"Repository {submission.repository} is not authorized for this project"
        )

    now = datetime.now(timezone.utc)
    document = submission.model_dump(mode="json")
    document["id"] = _record_id(submission)
    document["created_at"] = (
        submission.created_at.isoformat() if submission.created_at else now.isoformat()
    )
    document["received_at"] = now.isoformat()

    await col("test_runs").replace_one(
        {"id": document["id"]},
        document,
        upsert=True,
    )
    return {
        "id": document["id"],
        "status": "accepted",
        "message": "Test result stored",
    }


@router.get("/test-runs")
async def list_test_runs(
    project_id: str = Query(..., min_length=1),
    source: str | None = Query(None, max_length=50),
    branch: str | None = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    """CI test results for one project, newest first (QA dashboard).

    Bug sweep: the QA dashboard called this route but it did not exist, so the
    test-run list always failed. Access follows the QA project rules (the
    caller must be able to open the project's QA data).
    """
    from domain.services.qa_service import QAService

    await QAService().accessible_project(user, project_id)
    query: dict = {"project_id": project_id}
    if source:
        query["source"] = source
    if branch:
        query["branch"] = branch
    runs = await (
        col("test_runs").find(query, {"_id": 0}).sort("received_at", -1).limit(limit).to_list(length=limit)
    )
    return {"project_id": project_id, "runs": runs, "count": len(runs)}
