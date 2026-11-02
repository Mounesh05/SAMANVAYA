"""Domain models for project-scoped QA management."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


TestPriority = Literal["low", "medium", "high", "critical"]
TestType = Literal["functional", "negative", "regression", "integration", "smoke", "other"]
ExecutionStatus = Literal["PASSED", "FAILED", "BLOCKED"]
StepStatus = Literal["PASSED", "FAILED", "BLOCKED"]
DefectStatus = Literal[
    "OPEN",
    "ASSIGNED",
    "IN_PROGRESS",
    "FIXED",
    "READY_FOR_RETEST",
    "CLOSED",
    "REOPENED",
]


class TestSuiteCreate(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    story_id: str | None = Field(default=None, max_length=100)


class TestSuiteUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    story_id: str | None = Field(default=None, max_length=100)
    status: Literal["active", "archived"] | None = None


class TestStep(BaseModel):
    step_number: int = Field(..., ge=1)
    instruction: str = Field(..., min_length=1, max_length=2000)
    expected_result: str = Field(..., min_length=1, max_length=2000)


class TestCaseCreate(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=100)
    suite_id: str | None = Field(default=None, max_length=100)
    story_id: str | None = Field(default=None, max_length=100)
    task_id: str | None = Field(default=None, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    objective: str = Field(default="", max_length=2000)
    preconditions: str = Field(default="", max_length=4000)
    steps: list[TestStep] = Field(..., min_length=1, max_length=50)
    expected_result: str = Field(..., min_length=1, max_length=4000)
    priority: TestPriority = "medium"
    test_type: TestType = "functional"

    @model_validator(mode="after")
    def validate_step_order(self):
        numbers = [step.step_number for step in self.steps]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("Test steps must be ordered consecutively starting at 1")
        return self


class TestCaseUpdate(BaseModel):
    suite_id: str | None = Field(default=None, max_length=100)
    story_id: str | None = Field(default=None, max_length=100)
    task_id: str | None = Field(default=None, max_length=100)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    objective: str | None = Field(default=None, max_length=2000)
    preconditions: str | None = Field(default=None, max_length=4000)
    steps: list[TestStep] | None = Field(default=None, min_length=1, max_length=50)
    expected_result: str | None = Field(default=None, min_length=1, max_length=4000)
    priority: TestPriority | None = None
    test_type: TestType | None = None
    is_archived: bool | None = None

    @model_validator(mode="after")
    def validate_step_order(self):
        if self.steps is not None:
            numbers = [step.step_number for step in self.steps]
            if numbers != list(range(1, len(numbers) + 1)):
                raise ValueError("Test steps must be ordered consecutively starting at 1")
        return self


class ExecutionStepResult(BaseModel):
    step_number: int = Field(..., ge=1)
    actual_result: str = Field(..., max_length=4000)
    status: StepStatus
    comments: str = Field(default="", max_length=2000)


class TestExecutionCreate(BaseModel):
    test_case_id: str = Field(..., min_length=1, max_length=100)
    defect_id: str | None = Field(default=None, max_length=100)
    status: ExecutionStatus
    actual_result: str = Field(..., min_length=1, max_length=8000)
    notes: str = Field(default="", max_length=8000)
    step_results: list[ExecutionStepResult] = Field(default_factory=list, max_length=50)
    evidence: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def validate_evidence_references(self):
        if any(not item.strip() or len(item) > 2000 for item in self.evidence):
            raise ValueError("Evidence references must be non-empty and at most 2000 characters")
        failed = any(step.status == "FAILED" for step in self.step_results)
        blocked = any(step.status == "BLOCKED" for step in self.step_results)
        if failed and self.status != "FAILED":
            raise ValueError("A failed step requires a FAILED execution")
        if blocked and not failed and self.status == "PASSED":
            raise ValueError("A blocked step cannot have a PASSED execution")
        return self


class DefectCreate(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=100)
    test_case_id: str | None = Field(default=None, max_length=100)
    execution_id: str | None = Field(default=None, max_length=100)
    story_id: str | None = Field(default=None, max_length=100)
    task_id: str | None = Field(default=None, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=8000)
    steps_to_reproduce: str = Field(default="", max_length=8000)
    expected_result: str = Field(default="", max_length=4000)
    actual_result: str = Field(default="", max_length=4000)
    severity: TestPriority = "medium"
    priority: TestPriority = "medium"


class DefectUpdate(BaseModel):
    status: DefectStatus | None = None
    assignee_id: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=8000)
    steps_to_reproduce: str | None = Field(default=None, max_length=8000)
    expected_result: str | None = Field(default=None, max_length=4000)
    actual_result: str | None = Field(default=None, max_length=4000)
