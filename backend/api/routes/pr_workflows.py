"""Authorized, manual-only v1 surface over the existing durable workflow."""

from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pymongo.errors import PyMongoError

from core.dependencies import get_current_user
from domain.models.pr_multi_agent import ManualPRRequest
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


@router.get("/jobs/{job_id}/report", response_model=DurablePRReport)
async def advisory_report(job_id: JobID, request: Request, user: dict = Depends(get_current_user)):
    async with available_storage():
        row = await runtime(request).service.get(job_id, user)
        if "report" not in row:
            raise HTTPException(409, "The advisory report is not available yet")
        return parse(DurablePRReport, row["report"])
