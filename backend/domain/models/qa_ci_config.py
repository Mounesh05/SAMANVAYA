"""
QA CI test-automation provisioning request (CR-002).

api/routes/qa_ci_provisioning.py imported this model, but the file was missing,
so the router could never load and the QA dashboard's Enable CI calls had no
endpoint behind them.
"""

from pydantic import BaseModel, Field, field_validator

# GitHub "owner/name"; each part is letters, digits, '.', '_' or '-'.
REPOSITORY_PATTERN = r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$"
BRANCH_PATTERN = r"^[A-Za-z0-9._/-]{1,200}$"


class CIProvisionRequest(BaseModel):
    repository: str = Field(..., pattern=REPOSITORY_PATTERN, description="GitHub repository as owner/name")
    branch: str = Field(default="main", pattern=BRANCH_PATTERN)

    @field_validator("branch")
    @classmethod
    def _safe_branch(cls, value: str) -> str:
        # A conservative git branch name: no leading '-', no '..'.
        if value.startswith("-") or ".." in value:
            raise ValueError("Branch name is not a valid git branch")
        return value
