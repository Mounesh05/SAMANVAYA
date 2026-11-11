"""Bounded source references and explicit requirements; approval is server owned."""

from typing import Literal
import json

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from domain.schemas.decision_policy import Constraint


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RequirementScope(StrictModel):
    repository: str | None = Field(default=None, min_length=1, max_length=200)
    contract_id: str | None = Field(default=None, min_length=1, max_length=100)
    function_id: str | None = Field(default=None, min_length=1, max_length=100)
    source_revision: str | None = Field(default=None, min_length=1, max_length=200)
    dataset_ids: list[str] = Field(default_factory=list, max_length=32)


class RequirementDeclaration(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    type: Literal["MAX_LATENCY", "MAX_MEMORY", "INPUT_SCHEMA", "OUTPUT_BEHAVIOR", "WORKLOAD"]
    key: str = Field(min_length=1, max_length=100)
    value: JsonValue
    unit: Literal["seconds", "bytes"] | None = None
    metric: Literal["elapsed_invocation_seconds", "memray_peak_tracked_allocations_bytes", "rss_peak_bytes"] | None = None
    scope: RequirementScope = Field(default_factory=RequirementScope)
    description: str = Field(min_length=1, max_length=1000)
    override_of: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def supported(self):
        if self.type in {"MAX_LATENCY", "MAX_MEMORY"}:
            Constraint(id=self.id, type=self.type, threshold=self.value, unit=self.unit, metric=self.metric,
                       evaluation_policy="MAX_OBSERVED_INVOCATION" if self.type == "MAX_LATENCY" else "OBSERVED_PEAK",
                       source_reference="proposal")
        elif self.unit is not None or self.metric is not None:
            raise ValueError("Only performance requirements declare units and measurement metrics")
        if self.type == "WORKLOAD":
            ids = self.value.get("required_dataset_ids") if isinstance(self.value, dict) else None
            if (not isinstance(ids, list) or not 1 <= len(ids) <= 32 or set(self.value) != {"required_dataset_ids"}
                    or any(not isinstance(i, str) or not i.strip() or len(i) > 128 for i in ids) or len(set(ids)) != len(ids)):
                raise ValueError("Workload constraints require explicit required_dataset_ids; production frequencies are not inferred")
        if len(set(self.scope.dataset_ids)) != len(self.scope.dataset_ids) or any(not x.strip() or len(x) > 128 for x in self.scope.dataset_ids):
            raise ValueError("Dataset scope requires unique, nonblank IDs")
        return self


class RequirementSourceProposal(StrictModel):
    project_id: str = Field(min_length=1, max_length=200)
    source_kind: Literal["project_configuration", "repository_configuration"] = "project_configuration"
    source_reference: str = Field(min_length=1, max_length=500)
    source_revision: str = Field(min_length=1, max_length=200)
    requirements: list[RequirementDeclaration] = Field(min_length=1, max_length=32)
    supersedes: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_ids(self):
        if len(json.dumps(self.model_dump()).encode()) > 64000:
            raise ValueError("A requirement source revision must fit within 64000 bytes")
        if len({r.id for r in self.requirements}) != len(self.requirements):
            raise ValueError("Requirement IDs must be unique within a source revision")
        if self.source_kind == "repository_configuration" and any(not r.scope.repository for r in self.requirements):
            raise ValueError("Repository configuration requires an exact repository scope")
        return self


class RequirementReview(StrictModel):
    expected_fingerprint: str = Field(min_length=1, max_length=200)
    source_reference: str = Field(min_length=1, max_length=500)
    rationale: str = Field(min_length=1, max_length=2000)
    scope_reviewed: bool = Field(strict=True)

    @model_validator(mode="after")
    def reviewed(self):
        if self.scope_reviewed is not True:
            raise ValueError("Explicit scope review is required")
        return self


class RequirementContext(StrictModel):
    repository: str | None = Field(default=None, min_length=1, max_length=200)
    source_revision: str | None = Field(default=None, min_length=1, max_length=200)
    contract_ids: list[str] = Field(default_factory=list, max_length=4)
    function_ids: list[str] = Field(default_factory=list, max_length=8)
    discovery_run_ids: list[str] = Field(default_factory=list, max_length=4)
    task_ids: list[str] = Field(default_factory=list, max_length=8)
    story_ids: list[str] = Field(default_factory=list, max_length=8)
    pr_ids: list[str] = Field(default_factory=list, max_length=4)
    benchmark_run_ids: list[str] = Field(default_factory=list, max_length=4)


class RequirementDiscoveryRequest(StrictModel):
    project_id: str = Field(min_length=1, max_length=200)
    context: RequirementContext = Field(default_factory=RequirementContext)
