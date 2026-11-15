"""Proposed calibration context cannot establish representative or approved work."""

from typing import Annotated, Literal
from pydantic import Field, model_validator
from domain.models.performance_claims import Text
from domain.models.performance_scoring import Digest, FrozenContract, NonEmpty, SubjectRole


class CalibrationSample(FrozenContract):
    run_id: NonEmpty
    source_ids: Annotated[tuple[Digest, ...], Field(min_length=1, max_length=16)]
    purpose: Literal["representative_work", "gaming_sensitivity", "coverage_gap", "role_boundary", "low_activity_high_value"]
    rationale: Text

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("Repeated sources cannot establish representative coverage")
        return self


class CalibrationPacketRequest(FrozenContract):
    project_id: NonEmpty
    subject_role: SubjectRole
    rationale: Text
    proposed_rules: Text
    samples: Annotated[tuple[CalibrationSample, ...], Field(min_length=1, max_length=16)]

    @model_validator(mode="after")
    def unique(self):
        if len({s.run_id for s in self.samples}) != len(self.samples):
            raise ValueError("Repeated snapshots are not independent calibration cases")
        return self
