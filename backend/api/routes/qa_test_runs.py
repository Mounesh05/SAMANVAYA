"""CI test-result ingestion for the QA dashboard."""

import hashlib
import hmac
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, model_validator

from core.config import settings
from core.database import col

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
    
    # Validate repository is allowed for this project (check any branch config)
    ci_configs = await col("qa_ci_configs").find({"project_id": submission.project_id}).to_list(length=None)
    if ci_configs:
        # Get unique repositories from all branch configs
        allowed_repos = set(config.get("repository") for config in ci_configs if config.get("repository"))
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
