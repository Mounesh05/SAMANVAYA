"""Bounded API requests for legacy sorting and generic function benchmarks."""

import keyword
from typing import Literal

from benchmark_worker.contracts import is_generic, validate_function_payload
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from intelligence.algorithms.runner import DockerBenchmarkRunner
from domain.schemas.decision_policy import DecisionPolicy
from domain.schemas.requirement_discovery import RequirementContext


class FunctionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=200_000)
    entrypoint: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z_$][A-Za-z0-9_$]*$")

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value):
        value = value.strip()
        if not value or "\x00" in value:
            raise ValueError("Candidate name must be nonblank and contain no NUL bytes")
        value.encode("utf-8")
        return value

    @field_validator("source")
    @classmethod
    def bounded_source(cls, value):
        if not value.strip() or len(value.encode("utf-8")) > 200_000:
            raise ValueError("Source must contain 1..200000 UTF-8 bytes")
        return value


# Existing callers can continue importing the sorting-era name.
SortCandidate = FunctionCandidate


class BenchmarkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=200)
    language: Literal["python", "javascript", "typescript"]
    candidates: list[FunctionCandidate] = Field(min_length=1, max_length=5)
    contract: dict | None = Field(default=None, strict=True)
    datasets: list[dict] = Field(default_factory=list, strict=True)
    resources: dict = Field(default_factory=dict, strict=True)
    decision_policy: DecisionPolicy | None = None
    requirement_context: RequirementContext | None = None
    sizes: list[int] = Field(default_factory=lambda: [100, 1000], min_length=1, max_length=16)
    distributions: list[Literal["random", "sorted", "reversed", "duplicates"]] = Field(
        default_factory=lambda: ["random", "sorted", "reversed", "duplicates"], min_length=1, max_length=4
    )
    repetitions: int = Field(default=5, ge=1, le=10, strict=True)
    seed: int = Field(default=42, ge=0, le=0xFFFFFFFF, strict=True)
    objective: Literal["time", "memory"] = "time"
    memory_limit_bytes: int | None = Field(default=None, gt=0, le=536_870_912, strict=True)

    @field_validator("project_id")
    @classmethod
    def nonblank_project(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("A project ID is required")
        return value

    @field_validator("sizes", mode="before")
    @classmethod
    def integer_sizes(cls, value):
        if not isinstance(value, list) or any(type(n) is not int for n in value):
            raise ValueError("Sizes must be integers, not booleans or strings")
        return value

    @model_validator(mode="after")
    def compatible_contract(self):
        payload = self.model_dump()
        validate_function_payload(payload)
        if not is_generic(payload) and len(self.candidates) < 2:
            raise ValueError("Legacy sorting requires 2..5 candidates")
        DockerBenchmarkRunner._validate(payload)
        if self.language == "python":
            for candidate in self.candidates:
                if not candidate.entrypoint.isidentifier() or keyword.iskeyword(candidate.entrypoint):
                    raise ValueError("Python entrypoint must be a valid non-keyword identifier")
        elif self.objective == "memory" or self.memory_limit_bytes is not None:
            raise ValueError("Node heap delta cannot support a peak-memory objective or limit")
        return self


class StructureRequest(BaseModel):
    """Inspect source without executing function bodies or requiring test datasets."""

    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=1, max_length=200)
    language: Literal["python", "javascript", "typescript"]
    candidates: list[FunctionCandidate] = Field(min_length=1, max_length=5)
    resources: dict = Field(default_factory=dict, strict=True)

    @model_validator(mode="after")
    def bounded(self):
        DockerBenchmarkRunner._validate({**self.model_dump(), "sizes": [0],
                                        "distributions": ["random"], "repetitions": 1, "seed": 42})
        return self


class BenchmarkFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["accepted", "rejected"]
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Explain the decision")
        return value
