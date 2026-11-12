"""Frozen local evidence observations; neither collection nor shape grants authority."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from domain.models.performance_scoring import (
    CoverageSummary, DimensionId, EvidenceKind, FrozenContract, NonEmpty, Number, Digest, SubjectRole,
)

Count = Annotated[int, Field(strict=True, ge=0, le=1_000_000_000)]
Revision = Annotated[str, Field(strict=True, pattern=r"^[a-fA-F0-9]{7,64}$")]
State = Literal["VERIFIED_SNAPSHOT", "UNVERIFIED", "REJECTED", "DISPUTED", "STALE"]
Origin = Literal["tasks", "stories", "pull_requests", "test_runs", "qa_defects", "code_quality_runs",
                 "algorithm_benchmark_runs", "commits", "code_reviews", "incidents"]


def utc_time(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Evidence timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def canonical_digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode("utf-8")).hexdigest()


class EvidenceWindow(FrozenContract):
    period_start: datetime
    period_end: datetime

    @field_validator("period_start", "period_end", mode="before")
    @classmethod
    def no_epoch_coercion(cls, value):
        if not isinstance(value, (str, datetime)):
            raise ValueError("An explicit timezone-aware datetime is required")
        return value

    @field_validator("period_start", "period_end")
    @classmethod
    def normalize_time(cls, value):
        return utc_time(value)

    @model_validator(mode="after")
    def valid_window(self):
        if self.period_start >= self.period_end:
            raise ValueError("Evidence period must be nonempty [start, end)")
        return self


class EvidencePreviewRequest(EvidenceWindow):
    employee_id: NonEmpty
    project_id: NonEmpty


class EvidenceScope(EvidenceWindow):
    organization_id: NonEmpty
    employee_id: NonEmpty
    project_id: NonEmpty
    repository: NonEmpty | None = None
    role_at_period: SubjectRole | None = None
    repository_mapping_status: Literal["AVAILABLE", "MISSING", "AMBIGUOUS", "UNAVAILABLE"] = "AVAILABLE"


class EvidenceFacts(FrozenContract):
    """Allowlisted observations only. No prose, source code, credentials or point totals."""
    status: Literal["todo", "in_progress", "review", "done", "completed", "closed", "resolved", "blocked",
                    "open", "merged", "passed", "failed", "error", "cancelled", "skipped", "unknown",
                    "assigned", "fixed", "ready_for_retest", "reopened"] = "unknown"
    head_sha: Revision | None = None
    baseline_sha: Revision | None = None
    tests_run: Count | None = None
    tests_passed: Count | None = None
    tests_failed: Count | None = None
    tests_skipped: Count | None = None
    workload_key: Digest | None = None
    environment_key: Digest | None = None
    correctness_status: Literal["MISSING", "FAILED", "REQUIRES_REVIEW"] = "MISSING"
    suppressed: Annotated[bool, Field(strict=True)] | None = None

    @model_validator(mode="after")
    def consistent_test_observations(self):
        counts = (self.tests_run, self.tests_passed, self.tests_failed, self.tests_skipped)
        if any(value is not None for value in counts):
            if any(value is None for value in counts) or sum(counts[1:]) != counts[0]:
                raise ValueError("Test counts must be complete and sum to tests_run")
            if self.status == "passed" and self.tests_failed:
                raise ValueError("A passed run cannot contain failed tests")
        return self


class EvidenceAttribution(FrozenContract):
    basis: Literal["DIRECT_EMPLOYEE_ID", "EXACT_GITHUB_MAPPING", "PR_REVISION_LINK", "UNKNOWN"]
    shared: Annotated[bool, Field(strict=True)] | None = None
    share: Annotated[Number, Field(ge=0, le=1)] | None = None
    # Shares are not inferred from authorship, project membership or trigger identity.


class EvidenceRecord(FrozenContract):
    source_id: Digest
    content_digest: Digest
    origin: Origin
    scope_basis: Literal["DIRECT_ORG", "AUTHORIZED_PARENT_PROJECT"] = "DIRECT_ORG"
    kind: EvidenceKind
    source_revision: NonEmpty | None
    occurred_at: datetime | None
    parent_source_id: Digest | None = None
    state: State
    attribution: EvidenceAttribution
    facts: EvidenceFacts
    limitations: tuple[NonEmpty, ...] = ()

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurrence(cls, value):
        return utc_time(value) if value is not None else None


class ConnectorObservation(FrozenContract):
    origin: Origin
    availability: Literal["AVAILABLE", "PARTIAL", "UNAVAILABLE", "NOT_CONFIGURED"]
    fetched_count: Count = 0
    limitations: tuple[NonEmpty, ...] = ()


class DimensionEvidence(FrozenContract):
    dimension_id: DimensionId
    state: Literal["NOT_ASSESSED"] = "NOT_ASSESSED"
    score: None = None
    verified_source_refs: tuple[Digest, ...] = ()
    opportunity: Literal["UNKNOWN"] = "UNKNOWN"
    limitations: tuple[NonEmpty, ...] = ("CALIBRATION_REQUIRED", "OPPORTUNITY_CONTEXT_UNKNOWN")


class EvidenceSnapshot(FrozenContract):
    schema_version: Literal["performance-evidence-v1"] = "performance-evidence-v1"
    method: Literal["performance-evidence-v1"] = "performance-evidence-v1"
    scope: EvidenceScope
    captured_at: datetime
    records: tuple[EvidenceRecord, ...]
    connectors: tuple[ConnectorObservation, ...] = ()
    dimensions: tuple[DimensionEvidence, ...]
    coverage: CoverageSummary = Field(default_factory=CoverageSummary)
    status: Literal["INSUFFICIENT_EVIDENCE", "POLICY_PENDING", "UNDER_REVIEW"]
    engineering_score: None = None
    human_score: None = None
    combined_score: None = None
    is_finalizable: Literal[False] = False
    limitations: tuple[NonEmpty, ...] = (
        "SNAPSHOT_FACTS_ARE_NOT_PERFORMANCE_MEASUREMENTS", "CALIBRATION_REQUIRED",
        "HISTORICAL_ROLE_AND_OPPORTUNITY_UNKNOWN", "LOCAL_CAPTURE_NOT_LIVE_EXTERNAL_VERIFICATION",
    )

    @field_validator("captured_at")
    @classmethod
    def normalize_capture(cls, value):
        return utc_time(value)

    @field_validator("records")
    @classmethod
    def ordered_records(cls, value):
        keys = [(r.source_id, r.content_digest) for r in value]
        if len(keys) != len(set(keys)):
            raise ValueError("Snapshot records must be deduplicated")
        return tuple(sorted(value, key=lambda r: (r.source_id, r.content_digest)))

    @field_validator("dimensions", "connectors")
    @classmethod
    def ordered_sections(cls, value):
        keys = [item.dimension_id if isinstance(item, DimensionEvidence) else item.origin for item in value]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate manifest sections are not permitted")
        return tuple(sorted(value, key=lambda item: item.dimension_id if isinstance(item, DimensionEvidence) else item.origin))

    @model_validator(mode="after")
    def consistent_snapshot(self):
        if {d.dimension_id for d in self.dimensions} != set(DimensionId):
            raise ValueError("Every catalog dimension must retain an explicit assessment state")
        verified_ids = {r.source_id for r in self.records if r.state == "VERIFIED_SNAPSHOT"}
        if any(set(d.verified_source_refs) - verified_ids for d in self.dimensions):
            raise ValueError("Coverage references must point to verified in-snapshot observations")
        for record in self.records:
            if record.content_digest != canonical_digest(record.model_dump(mode="json", exclude={"content_digest"})):
                raise ValueError("Evidence content digest is inconsistent")
            if record.state == "VERIFIED_SNAPSHOT" and (
                record.occurred_at is None or not self.scope.period_start <= record.occurred_at < self.scope.period_end
                or record.occurred_at > self.captured_at or record.source_revision is None
                or record.attribution.basis == "UNKNOWN" or record.attribution.shared is not False
            ):
                raise ValueError("Verified snapshot facts require valid period, revision and attribution")
        expected = ("UNDER_REVIEW" if any(r.state == "DISPUTED" for r in self.records) else
                    "POLICY_PENDING" if verified_ids else "INSUFFICIENT_EVIDENCE")
        if self.status != expected:
            raise ValueError("Snapshot status must match the evidence state")
        if self.coverage != CoverageSummary():
            raise ValueError("Uncalibrated evidence cannot establish weighted or human coverage")
        return self


class EvidencePreview(FrozenContract):
    snapshot: EvidenceSnapshot
    digest: Digest

    @model_validator(mode="after")
    def matching_digest(self):
        if self.digest != canonical_digest(self.snapshot.model_dump(mode="json")):
            raise ValueError("Preview digest does not match its snapshot")
        return self


class EvidenceChange(FrozenContract):
    source_id: Digest
    change: Literal["ADDED", "MISSING", "CHANGED", "UNCHANGED"]
    previous_digests: tuple[Digest, ...]
    current_digests: tuple[Digest, ...]
