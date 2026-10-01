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

    @model_validator(mode="after")
    def validate_counts(self):
        if self.tests_passed + self.tests_failed > self.tests_run:
            raise ValueError("tests_passed + tests_failed cannot exceed tests_run")
        return self


def _record_id(submission: TestRunSubmission) -> str:
    key = "|".join(
        [submission.repository, submission.commit_sha, submission.test_suite]
    )
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
