"""Explicit contract authority and provisional implementation comparisons."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from benchmark_worker.contracts import validate_function_payload, _resources
from domain.schemas.algorithm_benchmark import FunctionCandidate
from domain.schemas.decision_policy import DecisionPolicy
from domain.schemas.requirement_discovery import RequirementContext


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FunctionReference(StrictModel):
    run_id: str = Field(min_length=1, max_length=100)
    function_id: str = Field(min_length=1, max_length=100)


class ContractRequirement(StrictModel):
    id: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)
    source_reference: str = Field(min_length=1, max_length=500)
    dataset_ids: list[str] = Field(min_length=1, max_length=32)


class AutomaticFunctionScope(StrictModel):
    repository: str = Field(min_length=3, max_length=200)
    path: str = Field(min_length=1, max_length=500)
    qualified_name: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def safe_scope(self):
        from intelligence.algorithms.discovery.service import safe_relative_path
        if self.repository.count("/") != 1 or not safe_relative_path(self.path):
            raise ValueError("Automatic scope requires an exact repository and safe relative source path")
        return self


class ContractProposal(StrictModel):
    project_id: str = Field(min_length=1, max_length=200)
    contract: dict
    datasets: list[dict] = Field(min_length=1, max_length=32)
    required_dataset_ids: list[str] = Field(min_length=1, max_length=32)
    requirements: list[ContractRequirement] = Field(min_length=1, max_length=32)
    scope_description: str = Field(min_length=1, max_length=2000)
    validator_requirement: Literal["expected_output", "numerical_tolerance", "property_oracle", "stability_oracle"] = "expected_output"
    function_bindings: list[FunctionReference] = Field(default_factory=list, max_length=64)
    automatic_scope: AutomaticFunctionScope | None = None

    @model_validator(mode="after")
    def validate_scope(self):
        validate_function_payload({"contract": self.contract, "datasets": self.datasets})
        ids = set(self.required_dataset_ids)
        if len(ids) != len(self.required_dataset_ids) or any(not key.strip() or len(key) > 128 for key in ids):
            raise ValueError("Required check IDs must be nonblank and unique")
        if len({r.id for r in self.requirements}) != len(self.requirements):
            raise ValueError("Requirement IDs must be unique")
        if any(not set(r.dataset_ids) <= ids for r in self.requirements):
            raise ValueError("Requirements must reference required checks")
        if set().union(*(set(r.dataset_ids) for r in self.requirements)) != ids:
            raise ValueError("Every required check needs a requirement source")
        return self


class ContractApproval(StrictModel):
    expected_fingerprint: str = Field(min_length=1, max_length=200)
    source_reference: str = Field(min_length=1, max_length=500)
    rationale: str = Field(min_length=1, max_length=2000)
    scope_reviewed: bool = Field(strict=True)

    @model_validator(mode="after")
    def explicit_review(self):
        if self.scope_reviewed is not True:
            raise ValueError("Scope review must be explicitly acknowledged")
        return self


class CompatibilityCandidate(FunctionCandidate):
    language: Literal["python", "javascript", "typescript"]
    function_reference: FunctionReference | None = None


class BehavioralComparisonRequest(StrictModel):
    project_id: str = Field(min_length=1, max_length=200)
    previous: CompatibilityCandidate
    current: CompatibilityCandidate
    contract_ids: list[str] = Field(default_factory=list, max_length=4)
    dataset_ids: list[str] | None = Field(default=None, max_length=32)
    resources: dict = Field(default_factory=dict)
    repetitions: int = Field(default=3, ge=1, le=10, strict=True)
    decision_policy: DecisionPolicy | None = None
    requirement_context: RequirementContext | None = None

    @model_validator(mode="after")
    def bounded(self):
        _resources(self.resources)
        if self.previous.name == self.current.name:
            raise ValueError("Previous and current candidate names must differ")
        for ids in (self.contract_ids, self.dataset_ids or []):
            if len(set(ids)) != len(ids) or any(not isinstance(v, str) or not v.strip() or len(v) > 200 for v in ids):
                raise ValueError("Reference IDs must be nonblank and unique")
        for candidate in (self.previous, self.current):
            if candidate.language == "python":
                import keyword
                if not candidate.entrypoint.isidentifier() or keyword.iskeyword(candidate.entrypoint):
                    raise ValueError("Python entrypoint must be a non-keyword identifier")
        return self
