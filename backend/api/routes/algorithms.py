"""Project-authorized, evidence-first function inspection and comparisons."""

import asyncio

from core.permissions import Permission, get_user_permissions
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
from domain.schemas.behavioral_compatibility import ContractProposal, ContractApproval, BehavioralComparisonRequest
from domain.services.function_contract_service import FunctionContractService
from domain.services.behavioral_compatibility_service import BehavioralCompatibilityService
from intelligence.algorithms.compatibility import provisional_relationships
from core.database import col
from domain.services.requirement_discovery_service import RequirementDiscoveryService
from domain.schemas.requirement_discovery import RequirementDiscoveryRequest, RequirementSourceProposal, RequirementReview

router = APIRouter()
requirement_service = RequirementDiscoveryService()
service = AlgorithmBenchmarkService(requirements=requirement_service)
contract_service = FunctionContractService()


def normalized_role(user):
    role = user.get("role", user.get("organizational_role", ""))
    return role.upper() if isinstance(role, str) else ""


async def engineering_user(user: dict = Depends(get_current_user)):
    if Permission.USE_ENGINEERING_INTELLIGENCE not in get_user_permissions(
            normalized_role(user), user.get("is_admin", False), user.get("designation")):
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
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
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


@router.post("/contracts", status_code=201)
async def propose_contract(body: ContractProposal, user: dict = Depends(engineering_user)):
    await project_access(user, body.project_id)
    try:
        return await contract_service.propose(body.model_dump(), user)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/contracts/{contract_id}")
async def read_contract(contract_id: str, user: dict = Depends(get_current_user)):
    document = await contract_service.get(contract_id)
    if not document:
        raise HTTPException(status_code=404, detail="Functional contract not found")
    await project_access(user, document["project_id"])
    return document


@router.post("/contracts/{contract_id}/approve")
async def approve_contract(contract_id: str, body: ContractApproval, user: dict = Depends(engineering_user)):
    document = await read_contract(contract_id, user)
    try:
        return await contract_service.approve(document, body.model_dump(), user)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.post("/compatibility/runs", status_code=202)
async def start_compatibility(body: BehavioralComparisonRequest, background_tasks: BackgroundTasks,
                              user: dict = Depends(engineering_user)):
    await project_access(user, body.project_id)
    try:
        # Missing/proposed/conflicting contracts can be reported without executing
        # code, even when benchmarking is disabled.
        resolution = await contract_service.resolve(body.project_id, body.contract_ids)
        if resolution["status"] == "APPROVED" and resolution.get("validator_available") and not settings.ALGORITHM_BENCHMARK_ENABLED:
            raise HTTPException(status_code=503, detail="Isolated workers must be enabled for approved-contract validation")
        result = await BehavioralCompatibilityService(service, contract_service).create(body.model_dump(), user)
    except BenchmarkBusy as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if result["status"] == "pending":
        background_tasks.add_task(service.execute, result["run_id"])
    return result


@router.get("/compatibility/relationships")
async def candidate_relationships(project_id: str, previous_run_id: str, current_run_id: str,
                                   user: dict = Depends(get_current_user)):
    await project_access(user, project_id)
    snapshots = []
    for run_id in (previous_run_id, current_run_id):
        run = await col("code_quality_runs").find_one({"run_id": run_id, "repository_id": project_id}, {"_id": 0})
        if run is None:
            raise HTTPException(status_code=404, detail="Project discovery snapshot not found")
        snapshots.append(run.get("function_discovery", {}))
    approved = await contract_service.collection.find({"project_id": project_id, "status": "APPROVED"}, {"_id": 0}).limit(100).to_list(100)
    return {"relationships": provisional_relationships(*snapshots, previous_run_id, current_run_id, approved),
            "status": "PROVISIONAL", "execution_performed": False}


@router.get("/compatibility/functions/{function_id}/history")
async def function_compatibility_history(function_id: str, project_id: str,
                                         user: dict = Depends(get_current_user)):
    await project_access(user, project_id)
    query = {"project_id": project_id, "kind": "behavioral_compatibility", "$or": [
        {"request.compatibility_context.previous.function_reference.function_id": function_id},
        {"request.compatibility_context.current.function_reference.function_id": function_id},
    ]}
    docs = await service.collection.find(query, {"_id": 0, "run_id": 1, "status": 1, "behavioral_compatibility": 1}).sort("created_at", -1).limit(10).to_list(10)
    return {"history": docs, "historical_only": True}


@router.get("/projects/{project_id}/contracts")
async def list_contracts(project_id: str, user: dict = Depends(get_current_user)):
    await project_access(user, project_id)
    return {"contracts": await contract_service.collection.find({"project_id": project_id}, {"_id": 0}).limit(100).to_list(100)}


@router.post("/requirements/discover")
async def discover_requirements(body: RequirementDiscoveryRequest, user: dict = Depends(engineering_user)):
    await project_access(user, body.project_id)
    try:
        return await requirement_service.discover(body.project_id, body.context.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/requirements/sources", status_code=201)
async def propose_requirement_source(body: RequirementSourceProposal, user: dict = Depends(engineering_user)):
    await project_access(user, body.project_id)
    try:
        return await requirement_service.propose(body.model_dump(), user)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/projects/{project_id}/requirement-sources")
async def list_requirement_sources(project_id: str, user: dict = Depends(engineering_user)):
    await project_access(user, project_id)
    return {"sources": await requirement_service.collection("algorithm_requirement_sources").find({"project_id": project_id}, {"_id": 0}).limit(32).to_list(32)}


@router.post("/requirements/sources/{source_id}/approve")
async def approve_requirement_source(source_id: str, body: RequirementReview, user: dict = Depends(engineering_user)):
    document = await requirement_service.get(source_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Requirement source not found")
    await project_access(user, document["project_id"])
    try:
        return await requirement_service.approve(document, body.model_dump(), user)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/pr-intelligence")
async def pr_intelligence_history(project_id: str | None = None, pr_id: str | None = None,
                                  user: dict = Depends(engineering_user)):
    if pr_id:
        pr = await col("pull_requests").find_one({"id": pr_id})
        if not pr:
            raise HTTPException(status_code=404, detail="PR not found")
        project_id = pr["project_id"]
    if project_id:
        await project_access(user, project_id)
        projects = [project_id]
    else:
        projects = []
        available = await col("projects").find({"org_id": user.get("org_id")}, {"id": 1}).limit(100).to_list(100)
        for project in available:
            try:
                await project_access(user, project["id"])
                projects.append(project["id"])
            except HTTPException as error:
                if error.status_code != 403:
                    raise
    from domain.services.pr_algorithm_intelligence_service import expire_pr_jobs, recommendation_status
    # Reads also expire interrupted local continuations, without replaying code.
    await expire_pr_jobs(col("code_quality_runs"), col("pull_requests"), project_ids=projects)
    query = {"kind": "pr_algorithm_intelligence", "project_id": {"$in": projects}}
    if pr_id:
        query["pr_id"] = pr_id
    rows = await col("code_quality_runs").find(query, {"_id": 0, "function_discovery": 0, "files": 0}).sort("created_at", -1).limit(30).to_list(30)
    # Only the latest revision is actionable. Earlier records remain historical.
    for row in rows:
        pr = await col("pull_requests").find_one({"id": row["pr_id"], "project_id": row["project_id"]})
        row["historical_only"] = row["status"] == "superseded" or not pr or pr.get("status") != "open" or pr.get("head_sha") != row["head_sha"] or pr.get("algorithm_intelligence_run_id") != row["run_id"]
        for function in row.get("functions", []):
            if not function.get("benchmark_run_id"):
                continue
            benchmark = await col("algorithm_benchmark_runs").find_one({"run_id": function["benchmark_run_id"], "project_id": row["project_id"]},
                {"behavioral_compatibility.status": 1, "decision.task_suitability": 1, "decision.unknown_requirements": 1, "decision.revision_id": 1})
            if benchmark and (benchmark.get("decision") or {}).get("revision_id"):
                function["finding_status"] = recommendation_status(benchmark)
                function["current_decision_reference"] = function["benchmark_run_id"] + "/" + benchmark["decision"]["revision_id"]
    return {"analyses": rows}
