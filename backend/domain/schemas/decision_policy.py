"""Explicit acceptance policy, independent of functional contracts and sandbox limits."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, model_validator

PEAK_TRACKED = "memray_peak_tracked_allocations_bytes"


class PolicyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class TimingPolicy(PolicyModel):
    version: Literal["1"] = "1"
    minimum_samples: int = Field(default=3, ge=2, le=10, strict=True)
    practical_difference_ratio: float = Field(default=0.05, ge=0, le=1, strict=True)
    maximum_variability_ratio: float = Field(default=0.20, ge=0, le=10, strict=True)


class Constraint(PolicyModel):
    id: str = Field(min_length=1, max_length=128)
    type: Literal["EXPECTED_OUTPUT", "MAX_LATENCY", "MAX_MEMORY", "DATASET_COVERAGE"]
    classification: Literal["MANDATORY", "PREFERENTIAL"] = "MANDATORY"
    dataset_ids: list[str] = Field(default_factory=list, max_length=64)
    required_dataset_ids: list[str] = Field(default_factory=list, max_length=64)
    threshold: StrictInt | StrictFloat | None = Field(default=None, ge=0, le=2**63 - 1)
    unit: Literal["seconds", "bytes"] | None = None
    metric: Literal["elapsed_invocation_seconds", "memray_peak_tracked_allocations_bytes", "rss_peak_bytes"] | None = None
    evaluation_policy: Literal["MAX_OBSERVED_INVOCATION", "OBSERVED_PEAK", "ALL_EXPECTED", "ALL_REQUIRED"]
    source_reference: str = Field(min_length=1, max_length=500)
    applicability: Literal["APPLIES", "NOT_APPLICABLE", "UNRESOLVED"] = "APPLIES"
    # A project-authorized submitter may record an unresolved relationship, never
    # claim an approved override or silently remove the original upper bound.
    unresolved_override_of: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def supported_shape(self):
        for ids in (self.dataset_ids, self.required_dataset_ids):
            if len(set(ids)) != len(ids) or any(not i.strip() or len(i) > 128 for i in ids):
                raise ValueError("Dataset IDs must be nonblank, unique, and at most 128 characters")
        resource = self.type in ("MAX_LATENCY", "MAX_MEMORY")
        if resource != (self.threshold is not None):
            raise ValueError("Only resource constraints require thresholds")
        if self.type == "MAX_LATENCY":
            if (self.unit, self.metric, self.evaluation_policy) != (
                    "seconds", "elapsed_invocation_seconds", "MAX_OBSERVED_INVOCATION"):
                raise ValueError("Latency requires seconds and MAX_OBSERVED_INVOCATION")
        elif self.type == "MAX_MEMORY":
            if (self.unit != "bytes" or self.metric not in (PEAK_TRACKED, "rss_peak_bytes")
                    or self.evaluation_policy != "OBSERVED_PEAK" or type(self.threshold) is not int):
                raise ValueError("Memory requires integer bytes and an explicitly named peak metric")
        elif self.unit is not None or self.metric is not None:
            raise ValueError("Non-resource constraints cannot declare a measurement metric")
        if self.type == "EXPECTED_OUTPUT" and self.evaluation_policy != "ALL_EXPECTED":
            raise ValueError("Correctness requires ALL_EXPECTED")
        if self.type == "DATASET_COVERAGE":
            if not self.required_dataset_ids or self.dataset_ids or self.evaluation_policy != "ALL_REQUIRED":
                raise ValueError("Coverage requires a required dataset set and ALL_REQUIRED")
        elif self.required_dataset_ids:
            raise ValueError("Only coverage constraints declare a required dataset set")
        return self


class UnknownRequirement(PolicyModel):
    id: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=1000)


class DecisionPolicy(PolicyModel):
    id: str = Field(min_length=1, max_length=128)
    version: Literal["1"]
    objective: Literal["MINIMIZE_TIME", "MINIMIZE_MEMORY", "TRADEOFF_ONLY"] | None = None
    memory_metric: Literal["memray_peak_tracked_allocations_bytes"] | None = None
    required_dataset_ids: list[str] = Field(default_factory=list, max_length=64)
    constraints: list[Constraint] = Field(default_factory=list, max_length=64)
    unknown_requirements: list[UnknownRequirement] = Field(default_factory=list, max_length=32)
    timing: TimingPolicy = Field(default_factory=TimingPolicy)

    @model_validator(mode="after")
    def consistent(self):
        ids = [c.id for c in self.constraints]
        if len(ids) != len(set(ids)) or any(i.startswith("__") for i in ids):
            raise ValueError("Constraint IDs must be unique and cannot start with __")
        if (len(self.required_dataset_ids) != len(set(self.required_dataset_ids))
                or any(not i.strip() or len(i) > 128 for i in self.required_dataset_ids)):
            raise ValueError("Required dataset IDs must be unique nonblank IDs")
        for c in self.constraints:
            if c.unresolved_override_of is not None and (
                    c.unresolved_override_of not in ids or c.unresolved_override_of == c.id):
                raise ValueError("Unresolved override must reference a different constraint in this policy")
        if self.objective == "MINIMIZE_MEMORY" and self.memory_metric != PEAK_TRACKED:
            raise ValueError("Memory optimization requires the approved tracked allocation peak metric")
        return self


class ReevaluationRequest(PolicyModel):
    decision_policy: DecisionPolicy
