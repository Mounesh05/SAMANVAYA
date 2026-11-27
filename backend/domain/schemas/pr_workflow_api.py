"""Separate versioned manual API projections; private persistence internals are omitted."""

from typing import Literal

from domain.models.pr_multi_agent import Contract, Digest, Label, Revision, ReportStatus, Specialist, Text

JobState = Literal["PENDING", "RUNNING", "RETRY_WAIT", "FAILED", "FINALIZED", "CANCELLED"]


class WorkflowProject(Contract):
    id: Label
    name: Text


class WorkflowProjects(Contract):
    schema_version: Literal["pr-workflow-projects-v1"] = "pr-workflow-projects-v1"
    projects: tuple[WorkflowProject, ...]
    truncated: bool


class ManualWorkflowAccepted(Contract):
    schema_version: Literal["pr-workflow-accepted-v1"] = "pr-workflow-accepted-v1"
    job_id: Digest
    status: JobState
    snapshot_id: Digest


class SpecialistProgress(Contract):
    specialist: Specialist
    status: Literal["WAITING", "RUNNING", "RETRY_WAIT", "SUCCEEDED", "FAILED", "TIMED_OUT", "SKIPPED"]
    error_code: Label | None = None


class ManualWorkflowStatus(Contract):
    schema_version: Literal["pr-workflow-status-v1"] = "pr-workflow-status-v1"
    job_id: Digest
    project_id: Label
    repository: Text
    pr_number: int
    head_sha: Revision
    base_sha: Revision
    snapshot_id: Digest
    status: JobState
    analysis_status: ReportStatus | None = None
    report_available: bool
    specialists: tuple[SpecialistProgress, ...]
    failure_reason: Label | None = None
    limitations: tuple[Text, ...]


def status_projection(row):
    outcomes = row["checkpoint"]["outcomes"]
    progress = []
    names: tuple[Specialist, ...] = ("code_analysis", "qa_analysis")
    first_missing = next((name for name in names if name not in outcomes), None)
    for name in names:
        saved = outcomes.get(name)
        last = next((step["outcome"] for step in reversed(row["step_results"]) if step["outcome"]["specialist"] == name), None)
        state = saved["status"] if saved else "WAITING"
        if not saved and first_missing == name:
            if row["status"] in {"RUNNING", "RETRY_WAIT"}:
                state = row["status"]
            elif row["status"] == "FAILED":
                state = "FAILED"
            elif row["status"] == "CANCELLED":
                state = "SKIPPED"
        progress.append(SpecialistProgress(specialist=name, status=state, error_code=(saved or last or {}).get("error_code")))
    scope = row["scope"]
    return ManualWorkflowStatus(job_id=row["job_id"], project_id=scope["project_id"], repository=scope["repository"],
        pr_number=scope["pr_number"], head_sha=scope["head_sha"], base_sha=scope["base_sha"], snapshot_id=row["snapshot_id"],
        status=row["status"], analysis_status=row.get("analysis_status"), report_available="report" in row,
        specialists=tuple(progress), failure_reason=(row.get("last_error") or {}).get("code"),
        limitations=tuple(row["snapshot"]["limitations"]))
