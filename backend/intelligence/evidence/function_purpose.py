"""Traceable static function evidence, deliberately separate from correctness."""

from typing import Literal

from pydantic import BaseModel, Field

METHOD = "function-purpose-v1"
Status = Literal["OBSERVED", "INFERRED", "VERIFIED_BY_CONTRACT", "UNKNOWN", "AMBIGUOUS"]


class PurposeEvidence(BaseModel):
    id: str
    kind: str
    status: Literal["OBSERVED"] = "OBSERVED"
    path: str
    line: int
    end_line: int
    source_revision: str | None = None
    source_hash: str
    method: str = METHOD
    subject: str = ""
    related: str = ""
    binding: str = ""
    arguments: list[str] = Field(default_factory=list)
    detail: str = ""


class PurposeConclusion(BaseModel):
    kind: str
    status: Literal["OBSERVED", "INFERRED"]
    evidence_refs: list[str] = Field(default_factory=list)
    supported_conclusion: str
    missing_information: list[str] = Field(default_factory=list)
    method: str = METHOD
    source_revision: str | None = None


class DiscoveredFunction(BaseModel):
    function_id: str
    repository_id: str
    path: str
    name: str
    qualified_name: str
    language: str
    line: int
    end_line: int
    column: int = 0
    source_revision: str | None = None
    source_hash: str
    method: str = METHOD
    is_async: bool = False
    parameters: list[dict] = Field(default_factory=list)
    return_annotation: str | None = None
    calls: list[dict] = Field(default_factory=list)
    callers: list[dict] = Field(default_factory=list)
    returns: list[dict] = Field(default_factory=list)
    structure: dict = Field(default_factory=dict)
    evidence: list[PurposeEvidence] = Field(default_factory=list)
    detected_patterns: list[PurposeConclusion] = Field(default_factory=list)
    task_hypotheses: list[PurposeConclusion] = Field(default_factory=list)
    task_status: Literal["INFERRED", "UNKNOWN", "AMBIGUOUS"] = "UNKNOWN"
    possible_task: str | None = None
    # No current repository contract source establishes function semantics.
    # Test assertions and annotations are context, never verified contracts.
    verified_contract: None = None
    requirement_evidence_refs: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)


class FunctionDiscovery(BaseModel):
    method: str = METHOD
    status: Literal["available", "partial", "unavailable", "not_analyzed"] = "not_analyzed"
    source_revision: str | None = None
    functions: list[DiscoveredFunction] = Field(default_factory=list)
    requirement_sources: list[dict] = Field(default_factory=list)
    diagnostics: list[dict] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=lambda: [
        "Syntax and lexical bindings only; dynamic dispatch, rebinding and aliases can change runtime behavior.",
        "Patterns and task hypotheses do not establish correctness, equivalence, optimality or functional requirements.",
        "Test assertions are observed expectations; tests are not executed and their authority is not inferred.",
        "Only available source within the documented analysis bounds is inspected; absent context stays unknown.",
        "Source hashes identify parsed bytes. Local or supplied revision labels are not independently checked against Git; GitHub snapshots are fetched at their head SHA.",
        "No candidate execution, automatic benchmarking, RAG or model availability is required.",
    ])
