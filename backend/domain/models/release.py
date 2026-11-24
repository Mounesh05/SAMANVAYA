"""Persistent release candidate request contracts."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Revision = Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
ReleaseId = Annotated[str, Field(pattern=r"^RL-[a-f0-9]{32}$")]
ProviderId = Annotated[int, Field(strict=True, gt=0, lt=2**63)]
Reason = Annotated[str, Field(min_length=1, max_length=1000)]


class ReleaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CandidateRequest(ReleaseRequest):
    baseline_sha: Revision
    target_sha: Revision
    run_id: ProviderId
    artifact_id: ProviderId
    kind: Literal["standard", "hotfix", "rollback"] = "standard"


class BaselineRequest(ReleaseRequest):
    revision: Revision
    reason: Reason


class ReleaseAction(ReleaseRequest):
    action: Literal["submit", "verify_qa", "approve", "hold", "refresh", "supersede"]
    version: int = Field(strict=True, ge=1)
    evidence_digest: Digest | None = None
    reason: Reason
    verified_task_ids: list[Annotated[str, Field(pattern=r"^TSK-[0-9A-F]{8}$")]] = Field(
        default_factory=list, max_length=100
    )
