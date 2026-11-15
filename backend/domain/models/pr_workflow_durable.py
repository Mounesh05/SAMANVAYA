"""Versioned persistence payloads; no new public API contracts."""

from typing import Annotated, Literal

from pydantic import Field

from domain.models.pr_multi_agent import (
    Contract, PRAnalysisContent, AgentOutcome, Digest, Specialist, Text,
)


class WorkflowCheckpoint(Contract):
    schema_version: Literal["pr-workflow-checkpoint-v1"] = "pr-workflow-checkpoint-v1"
    sequence: Annotated[int, Field(ge=0, le=6)] = 0
    snapshot_id: Digest
    outcomes: dict[Specialist, AgentOutcome] = Field(default_factory=dict)


class WorkflowStepResult(Contract):
    schema_version: Literal["pr-workflow-step-v1"] = "pr-workflow-step-v1"
    sequence: Annotated[int, Field(ge=1, le=6)]
    generation: Annotated[int, Field(ge=1)]
    attempt: Annotated[int, Field(ge=1, le=3)]
    snapshot_id: Digest
    outcome: AgentOutcome
    content_sha256: Digest
    advances_checkpoint: bool


class DurablePRReport(PRAnalysisContent):
    schema_version: Literal["pr-multi-agent-report-v2"] = "pr-multi-agent-report-v2"
    workflow_type: Literal["pr_multi_agent_v1"] = "pr_multi_agent_v1"
    durable: Literal[True] = True
    job_id: Digest
    generation: Annotated[int, Field(ge=1)]
    published_at: Text
