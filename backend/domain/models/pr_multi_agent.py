"""Internal PR workflow v1 contracts. Observations and model statements have distinct authority."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Text = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=800)]
Label = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=128)]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Revision = Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]
Value = Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)] | Annotated[bool, Field(strict=True)] | Text
Specialist = Literal["code_analysis", "qa_analysis"]
AssertionStatus = Literal["SUPPORTED", "PROPOSED", "UNSUPPORTED", "CONFLICTING"]
ReportStatus = Literal["COLLABORATIVE_ADVISORY", "PARTIAL_COLLABORATIVE_ADVISORY", "PARTIAL_SINGLE_SPECIALIST_ADVISORY",
                       "INSUFFICIENT_EVIDENCE", "FAILED", "STALE_ADVISORY"]
Collaboration = Literal["TWO_SPECIALIST", "SINGLE_SPECIALIST", "NONE"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)


class ManualPRRequest(Contract):
    project_id: Label
    pr_number: Annotated[int, Field(strict=True, ge=1)]
    expected_head_sha: Revision | None = None


class PRScope(Contract):
    owner_id: Label
    organization_id: Label
    project_id: Label
    repository: Annotated[str, StringConstraints(strict=True, min_length=3, max_length=201)]
    pr_number: int
    head_sha: Revision
    base_sha: Revision


class EvidenceReference(Contract):
    evidence_id: Digest
    scope: PRScope
    kind: Literal["STATIC_SOURCE", "CI_SUBMISSION"]
    source_reference: Text
    content_sha256: Digest
    method: Literal["github-blob-and-static-discovery-v1", "scoped-ci-submission-v1"]
    verification_scope: Literal["SOURCE_IDENTITY_AND_BYTES", "LOCAL_RECORDED_SUBMISSION"]


class Observation(Contract):
    observation_id: Digest
    evidence_id: Digest
    subject: Text
    metric: Label
    value: Value
    status: Literal["OBSERVED"] = "OBSERVED"


class PRSnapshot(Contract):
    schema_version: Literal["pr-evidence-v1"] = "pr-evidence-v1"
    snapshot_id: Digest
    scope: PRScope
    references: Annotated[tuple[EvidenceReference, ...], Field(max_length=8)]
    observations: Annotated[tuple[Observation, ...], Field(max_length=64)]
    limitations: Annotated[tuple[Text, ...], Field(max_length=32)] = ()

    @model_validator(mode="after")
    def consistent_scope(self):
        refs = {ref.evidence_id for ref in self.references}
        if len(refs) != len(self.references) or any(ref.scope != self.scope for ref in self.references):
            raise ValueError("Evidence references must be unique and share the pinned scope")
        if any(observation.evidence_id not in refs for observation in self.observations):
            raise ValueError("Observations must reference snapshot evidence")
        if len({item.observation_id for item in self.observations}) != len(self.observations):
            raise ValueError("Observation identities must be unique")
        return self


class ClaimDraft(Contract):
    kind: Literal["OBSERVATION", "INTERPRETATION"]
    statement: Text
    topic: Label
    position: Literal["AFFIRM", "DENY", "NEUTRAL"] = "NEUTRAL"
    evidence_refs: Annotated[tuple[Digest, ...], Field(max_length=8)] = ()
    observation_id: Digest | None = None
    asserted_value: Value | None = None

    @field_validator("evidence_refs", mode="before")
    @classmethod
    def reference_array(cls, value):
        return tuple(value) if isinstance(value, list) else value


class SpecialistReply(Contract):
    schema_version: Literal["pr-specialist-v1"] = "pr-specialist-v1"
    summary: Annotated[str, StringConstraints(strict=True, min_length=1, max_length=2400, strip_whitespace=True)]
    claims: Annotated[tuple[ClaimDraft, ...], Field(min_length=1, max_length=12)]
    limitations: Annotated[tuple[Text, ...], Field(max_length=8)] = ()

    @field_validator("claims", "limitations", mode="before")
    @classmethod
    def arrays(cls, value):
        return tuple(value) if isinstance(value, list) else value


class AgentOutcome(Contract):
    specialist: Specialist
    status: Literal["SUCCEEDED", "FAILED", "TIMED_OUT", "SKIPPED"]
    summary: str | None = None
    claims: tuple[ClaimDraft, ...] = ()
    limitations: tuple[Text, ...] = ()
    error_code: Label | None = None
    consumed_outputs: tuple[Specialist, ...] = ()
    model: Label | None = None
    method: Literal["pr-specialist-v1"] = "pr-specialist-v1"


class SpecialistView(Contract):
    specialist: Specialist
    snapshot_id: Digest
    scope: PRScope
    references: tuple[EvidenceReference, ...]
    observations: tuple[Observation, ...]
    prior_outcomes: tuple[AgentOutcome, ...] = ()
    handoff_authority: Literal["ADVISORY_NOT_INDEPENDENT_EVIDENCE"] = "ADVISORY_NOT_INDEPENDENT_EVIDENCE"


class AssessedClaim(Contract):
    claim_id: Label
    specialist: Specialist
    draft: ClaimDraft
    statement_status: Literal["ADVISORY"] = "ADVISORY"
    assertion_status: AssertionStatus
    supported_conclusion: str | None = None
    reason: Label
    conflicts_with: tuple[Label, ...] = ()


class PRAnalysisContent(Contract):
    scope: PRScope
    snapshot: PRSnapshot
    status: ReportStatus
    collaboration: Collaboration
    eligible_specialists: tuple[Specialist, ...]
    outcomes: tuple[AgentOutcome, ...]
    claims: tuple[AssessedClaim, ...]
    transitions: tuple[str, ...]
    limitations: tuple[Text, ...]
    read_only: Literal[True] = True
    authoritative_score: None = None


class PRAdvisoryReport(PRAnalysisContent):
    schema_version: Literal["pr-multi-agent-report-v1"] = "pr-multi-agent-report-v1"
    workflow_type: Literal["pr_multi_agent_v1"] = "pr_multi_agent_v1"
    durable: Literal[False] = False
