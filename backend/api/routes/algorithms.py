"""Project-authorized, evidence-first function inspection and comparisons."""

import asyncio

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from core.authorization import verify_project_access
from core.config import settings
from core.dependencies import get_current_user
from domain.schemas.algorithm_benchmark import BenchmarkFeedback, BenchmarkRequest, StructureRequest
from domain.schemas.decision_policy import ReevaluationRequest
from domain.services.algorithm_benchmark_service import AlgorithmBenchmarkService, BenchmarkBusy
from repositories.project_repository import ProjectRepository
from intelligence.algorithms.runner import BenchmarkFailure, BenchmarkUnavailable
from intelligence.algorithms.structure import analyze_python

router = APIRouter()
service = AlgorithmBenchmarkService()
_ENGINEERING_ROLES = {"DEVELOPER", "LEAD", "PM", "CEO", "QA", "DEVOPS"}


def normalized_role(user):
    role = user.get("role", user.get("organizational_role", ""))
    return role.upper() if isinstance(role, str) else ""


async def engineering_user(user: dict = Depends(get_current_user)):
    role = normalized_role(user)
    if not user.get("is_admin") and role not in _ENGINEERING_ROLES:
        raise HTTPException(status_code=403, detail="Engineering project access is required")
    identity = user.get("employee_id") or user.get("sub")
    if not isinstance(identity, str) or not identity.strip():
        raise HTTPException(status_code=403, detail="An authenticated user identity is required")
    return user


async def project_access(user, project_id):
    # The shared helper bypasses existence for CEO and currently grants PM access
    # across orgs. Keep this new evidence store scoped to an actual project/org.
    project = await ProjectRepository().find_by_id(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    org_id = user.get("org_id")
    if (not isinstance(org_id, str) or not org_id.strip()
            or org_id != project.get("org_id")):
        raise HTTPException(status_code=403, detail="Project belongs to a different organization")
    await verify_project_access({**user, "role": normalized_role(user)}, project_id)


async def authorized_run(run_id, user):
    document = await service.get(run_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Benchmark run not found")
    await project_access(user, document["project_id"])
    return document


@router.get("/availability")
async def availability(user: dict = Depends(get_current_user)):
    if not settings.ALGORITHM_BENCHMARK_ENABLED:
        return {"available": False, "environment": {},
                "error": "Benchmark execution is disabled. Build the worker images and set "
                         "ALGORITHM_BENCHMARK_ENABLED=true on an isolated benchmark backend."}
    return await service.runner.availability()


@router.post("/structure")
async def inspect_structure(body: StructureRequest, user: dict = Depends(engineering_user)):
    await project_access(user, body.project_id)
    if body.language == "python":
        structures = await asyncio.to_thread(
            lambda: {candidate.name: analyze_python(candidate.source, candidate.entrypoint)
                     for candidate in body.candidates}
        )
        return {"structural_analysis": structures, "execution_performed": False, "environment": {}}
    if not settings.ALGORITHM_BENCHMARK_ENABLED:
        raise HTTPException(status_code=503, detail="JS/TS AST inspection requires enabled Docker workers")
    try:
        report = await service.runner.analyze(body.model_dump())
    except BenchmarkUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except BenchmarkFailure as exc:
        raise HTTPException(status_code=502, detail="Structural worker failed; check container setup") from exc
    return {"structural_analysis": {row["candidate"]: row["structure"] for row in report["results"]},
            "execution_performed": False, "environment": report["environment"]}


@router.post("/runs", status_code=202)
async def start_run(body: BenchmarkRequest, background_tasks: BackgroundTasks,
                    user: dict = Depends(engineering_user)):
    await project_access(user, body.project_id)
    if not settings.ALGORITHM_BENCHMARK_ENABLED:
        raise HTTPException(status_code=503, detail="Algorithm benchmarks are disabled by the administrator")
    try:
        result = await service.create(body.model_dump(), user)
    except BenchmarkBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    background_tasks.add_task(service.execute, result["run_id"])
    return result


@router.get("/runs/{run_id}")
async def get_run(run_id: str, user: dict = Depends(get_current_user)):
    return await authorized_run(run_id, user)


@router.get("/projects/{project_id}/history")
async def history(project_id: str, limit: int = Query(default=10, ge=1, le=50),
                  user: dict = Depends(get_current_user)):
    await project_access(user, project_id)
    return {"history": await service.history(project_id, limit)}


@router.get("/runs/{run_id}/compatible-history")
async def compatible_history(run_id: str, limit: int = Query(default=10, ge=1, le=50),
                             user: dict = Depends(get_current_user)):
    document = await authorized_run(run_id, user)
    return {"history": await service.compatible_history(document, limit), "historical_only": True,
            "limitations": ["Declared contract compatibility does not prove semantic equivalence.",
                            "Different workloads or environments cannot establish a fresh speed comparison."]}


@router.post("/runs/{run_id}/feedback")
async def feedback(run_id: str, body: BenchmarkFeedback, user: dict = Depends(engineering_user)):
    document = await authorized_run(run_id, user)
    if document["status"] != "completed" or not (document.get("recommendation") or document.get("decision")):
        raise HTTPException(status_code=409, detail="Feedback requires a completed comparison")
    return await service.feedback(document, body.model_dump(), user)


@router.post("/runs/{run_id}/reevaluate")
async def reevaluate(run_id: str, body: ReevaluationRequest, user: dict = Depends(engineering_user)):
    document = await authorized_run(run_id, user)
    if document["status"] != "completed":
        raise HTTPException(status_code=409, detail="Reevaluation requires a completed run")
    try:
        return await service.reevaluate(run_id, body.decision_policy.model_dump(), user)
    except BenchmarkBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/runs/{run_id}/explanation")
async def explanation(run_id: str, user: dict = Depends(engineering_user)):
    document = await authorized_run(run_id, user)
    if document["status"] != "completed" or not (document.get("recommendation") or document.get("decision")):
        raise HTTPException(status_code=409, detail="Explanations require a completed comparison")
    return await service.explain(document)
