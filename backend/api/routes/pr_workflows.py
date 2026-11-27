"""Authorized, manual-only v1 surface over the existing durable workflow."""

from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response
from pymongo.errors import PyMongoError

from core.dependencies import get_current_user
from domain.models.pr_multi_agent import Label, ManualPRRequest, Revision
from domain.models.pr_workflow_durable import DurablePRReport
from domain.schemas.pr_workflow_api import (
    ManualWorkflowAccepted, ManualWorkflowStatus, WorkflowProjects, WorkflowProject, status_projection,
)
from domain.services.ai_run_access import accessible_projects
from domain.services.pr_multi_agent_evidence import PREvidenceResolver
from domain.services.pr_workflow_runtime import require_manual_workflow
from repositories.pr_workflow_repository import InvalidWorkflowRecord, parse

router = APIRouter(tags=["Manual PR advisory analysis"], dependencies=[Depends(require_manual_workflow)])
JobID = Annotated[str, Path(pattern=r"^[a-f0-9]{64}$")]


def runtime(request):
    instance = getattr(request.app.state, "pr_workflow_runtime", None)
    if instance is None:
        raise HTTPException(503, "Manual PR analysis worker is unavailable")
    return instance


@asynccontextmanager
async def available_storage():
    try:
        yield
    except (PyMongoError, TimeoutError, httpx.HTTPError, InvalidWorkflowRecord):
        raise HTTPException(503, "Manual PR analysis is temporarily unavailable") from None


@router.post("/pr-analysis", status_code=202, response_model=ManualWorkflowAccepted)
async def start_analysis(body: ManualPRRequest, request: Request, user: dict = Depends(get_current_user)):
    async with available_storage():
        return await runtime(request).submit(body, user)


@router.get("/pr-analysis/report", response_model=DurablePRReport | None)
async def lookup_report(request: Request, response: Response, project_id: Label, head_sha: Revision,
                        repository: Annotated[str, Query(min_length=3, max_length=201)],
                        pr_number: Annotated[int, Query(ge=1, le=2**31 - 1)],
                        user: dict = Depends(get_current_user)):
    """Read the caller's published advisory for a synchronized PR head."""
    response.headers["Cache-Control"] = "no-store"
    pinned = ManualPRRequest(project_id=project_id, pr_number=pr_number, expected_head_sha=head_sha)
    async with available_storage():
        report = await runtime(request).service.lookup_report(pinned, repository, user)
        return parse(DurablePRReport, report) if report is not None else None


@router.get("/projects", response_model=WorkflowProjects)
async def project_choices(user: dict = Depends(get_current_user)):
    async with available_storage():
        principal = await PREvidenceResolver.current_actor(user)
        rows = sorted(await accessible_projects(principal), key=lambda row: row["id"])
        return WorkflowProjects(projects=tuple(WorkflowProject(id=row["id"], name=str(row.get("name") or row["id"])[:200])
                                              for row in rows[:100]), truncated=len(rows) > 100)


@router.get("/jobs/{job_id}", response_model=ManualWorkflowStatus)
async def job_status(job_id: JobID, request: Request, user: dict = Depends(get_current_user)):
    async with available_storage():
        return status_projection(await runtime(request).service.get(job_id, user))


@router.post("/jobs/{job_id}/cancel", response_model=ManualWorkflowStatus)
async def cancel_job(job_id: JobID, request: Request, user: dict = Depends(get_current_user)):
    """AI-02: cancel your own queued or running advisory analysis."""
    async with available_storage():
        return status_projection(await runtime(request).service.cancel(job_id, user))


@router.get("/jobs/{job_id}/report", response_model=DurablePRReport)
async def advisory_report(job_id: JobID, request: Request, user: dict = Depends(get_current_user)):
    async with available_storage():
        row = await runtime(request).service.get(job_id, user)
        if "report" not in row:
            raise HTTPException(409, "The advisory report is not available yet")
        return parse(DurablePRReport, row["report"])
