"""Evidence-backed AI developer evaluation API."""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from agents.llm_provider import check_ollama_connection, get_ollama_llm
from core.config import settings
from core.dependencies import get_current_user, require_roles
from domain.models.developer_evaluation import DeveloperEvaluation
from domain.services.github_api_service import GitHubAPIService
from repositories.evaluation_repository import EvaluationRepository

router = APIRouter()
logger = logging.getLogger(__name__)
MODEL_REQUEST_TIMEOUT_SECONDS = 150

AI_DIMENSION_WEIGHTS = {
    "code_quality": 25,
    "delivery": 20,
    "collaboration": 15,
    "reliability": 15,
    "engineering_impact": 10,
    "engineering_judgment": 5,
}


class EvaluationProcessingError(RuntimeError):
    """Base error for an evaluation that must not be persisted as successful."""


class EvidenceUnavailableError(EvaluationProcessingError):
    """Raised when the requested PR evidence is missing or incomplete."""


class ModelResponseValidationError(EvaluationProcessingError):
    """Raised when the model response does not match the supported schema."""


class SimpleEvalRequest(BaseModel):
    """Request for one developer evaluation."""

    employee_id: Optional[str] = None
    github_username: str
    repo_owner: str
    repo_name: str
    pr_number: Optional[int] = Field(default=None, ge=1)
    human_score: Optional[float] = Field(default=None, ge=1, le=10)
    evaluation_focus: str = "code_quality"


class EvaluationResult(BaseModel):
    """API representation of a persisted evaluation."""

    evaluation_id: str
    employee_id: str
    github_username: str
    repo_info: Dict[str, Any]
    repo_owner: str
    repo_name: str
    pr_number: Optional[int]
    head_commit_sha: Optional[str]
    human_score: Optional[float]
    ai_provider: str
    model_name: str
    evaluation_focus: str = "code_quality"
    ai_analysis: Dict[str, Any]
    overall_score: Optional[float]
    recommendations: List[str]
    evidence_references: List[Dict[str, Any]]
    evidence_manifest: Dict[str, Any] = {}
    evidence_coverage: Dict[str, str] = {}
    unsupported_references: List[Dict[str, Any]] = []
    limitations: List[str] = []
    is_preliminary: bool = True
    status: str
    timestamp: str


def _result_from_evaluation(evaluation: DeveloperEvaluation) -> EvaluationResult:
    unsupported = evaluation.unsupported_references
    limitations = list(evaluation.limitations)
    if not evaluation.evidence_manifest:
        manifest_files = {
            item.get("file")
            for item in evaluation.repo_info.get("changed_files", [])
            if item.get("file")
        }
        unsupported = [
            reference for reference in evaluation.evidence_references
            if reference.get("file") not in manifest_files
        ]
        if unsupported:
            limitations.append(
                "Historical evaluation contains evidence references that do not resolve to the recorded PR files."
            )
        limitations.append(
            "Historical evaluation predates evidence-manifest validation and is preliminary."
        )
    return EvaluationResult(
        evaluation_id=evaluation.evaluation_id,
        employee_id=evaluation.employee_id,
        github_username=evaluation.github_username,
        repo_info=evaluation.repo_info,
        repo_owner=evaluation.repo_owner,
        repo_name=evaluation.repo_name,
        pr_number=evaluation.pr_number,
        head_commit_sha=evaluation.head_commit_sha,
        human_score=evaluation.human_score,
        ai_provider=evaluation.ai_provider,
        model_name=evaluation.model_name,
        evaluation_focus=evaluation.evaluation_focus,
        ai_analysis={
            "evidence_score": evaluation.overall_score,
            "dimensions": evaluation.dimensions,
            "analysis": evaluation.analysis,
            "strengths": evaluation.strengths,
            "weaknesses": evaluation.weaknesses,
            "confidence": evaluation.repo_info.get("confidence"),
            "evidence_coverage": evaluation.evidence_coverage,
        },
        overall_score=evaluation.overall_score,
        recommendations=evaluation.recommendations,
        evidence_references=evaluation.evidence_references,
        evidence_manifest=evaluation.evidence_manifest,
        evidence_coverage=evaluation.evidence_coverage,
        unsupported_references=unsupported,
        limitations=limitations,
        is_preliminary=evaluation.is_preliminary,
        status=evaluation.status,
        timestamp=evaluation.created_at.isoformat(),
    )


def _calculate_ai_evidence_score(dimensions: Dict[str, Any]) -> float:
    """Aggregate the existing weighted 0-10 dimensions into a 0-10 score."""
    weighted_points = sum(
        float(dimensions[name]["score"]) * weight
        for name, weight in AI_DIMENSION_WEIGHTS.items()
    )
    return round(weighted_points / 90, 2)


def _require_evidence(evidence: Dict[str, Any]) -> None:
    pr = evidence.get("pr")
    if not isinstance(pr, dict):
        raise EvidenceUnavailableError("Pull request metadata was not retrieved")
    if not evidence.get("files"):
        raise EvidenceUnavailableError("Pull request changed files were not retrieved")
    if not evidence.get("commits"):
        raise EvidenceUnavailableError("Pull request commits were not retrieved")
    if not pr.get("head", {}).get("sha"):
        raise EvidenceUnavailableError("Pull request head commit SHA is missing")


def _build_evidence_references(evidence: Dict[str, Any]) -> List[Dict[str, Any]]:
    references = []
    for changed_file in evidence["files"]:
        references.append({
            "file": changed_file.get("filename"),
            "status": changed_file.get("status"),
            "additions": changed_file.get("additions", 0),
            "deletions": changed_file.get("deletions", 0),
        })
    return references


def _build_evidence_manifest(
    owner: str,
    repo: str,
    pr_number: int,
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    """Create the allow-list used to validate every AI evidence citation."""
    files = []
    for changed_file in evidence["files"]:
        files.append({
            "file": changed_file.get("filename"),
            "patch": changed_file.get("patch"),
            "status": changed_file.get("status"),
        })
    check_runs = evidence.get("check_runs", {})
    if isinstance(check_runs, dict):
        check_runs = check_runs.get("check_runs", [])
    return {
        "repository": f"{owner}/{repo}",
        "pull_request": pr_number,
        "head_commit_sha": evidence["pr"]["head"]["sha"],
        "files": files,
        "commits": [
            {
                "sha": commit.get("sha"),
                "message": commit.get("commit", {}).get("message"),
            }
            for commit in evidence.get("commits", [])
        ],
        "check_runs": [
            {
                "id": check.get("id"),
                "name": check.get("name"),
                "status": check.get("status"),
                "conclusion": check.get("conclusion"),
            }
            for check in check_runs
        ],
        "reviews": [
            {"id": review.get("id"), "state": review.get("state")}
            for review in evidence.get("reviews", [])
        ],
        "comments": [
            {"id": comment.get("id")}
            for comment in evidence.get("comments", [])
        ],
        "source": "GitHub REST API via Samanvaya",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }


def _compact_evidence_for_prompt(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Keep attributable PR evidence without duplicating GitHub resource graphs."""
    pr = evidence["pr"]
    check_runs = evidence.get("check_runs", [])
    if isinstance(check_runs, dict):
        check_runs = check_runs.get("check_runs", [])
    return {
        "pr": {
            "number": pr.get("number"),
            "title": pr.get("title"),
            "body": pr.get("body"),
            "state": pr.get("state"),
            "user": {"login": pr.get("user", {}).get("login")},
            "head": {
                "ref": pr.get("head", {}).get("ref"),
                "sha": pr.get("head", {}).get("sha"),
            },
            "base": {
                "ref": pr.get("base", {}).get("ref"),
                "sha": pr.get("base", {}).get("sha"),
            },
        },
        "files": [
            {
                "filename": item.get("filename"),
                "status": item.get("status"),
                "additions": item.get("additions", 0),
                "deletions": item.get("deletions", 0),
                "patch": item.get("patch"),
            }
            for item in evidence.get("files", [])
        ],
        "commits": [
            {
                "sha": commit.get("sha"),
                "message": commit.get("commit", {}).get("message"),
            }
            for commit in evidence.get("commits", [])
        ],
        "check_runs": [
            {
                "name": check.get("name"),
                "status": check.get("status"),
                "conclusion": check.get("conclusion"),
            }
            for check in check_runs
        ],
        "reviews": [
            {
                "id": review.get("id"),
                "user": {"login": review.get("user", {}).get("login")},
                "state": review.get("state"),
                "body": review.get("body"),
            }
            for review in evidence.get("reviews", [])
        ],
        "comments": [
            {
                "id": comment.get("id"),
                "user": {"login": comment.get("user", {}).get("login")},
                "body": comment.get("body"),
                "path": comment.get("path"),
                "line": comment.get("line"),
            }
            for comment in evidence.get("comments", [])
        ],
    }


def _diff_lines(patch: Optional[str]) -> set[int]:
    """Return added-line numbers represented by a unified diff patch."""
    lines = set()
    if not patch:
        return lines
    current = None
    for line in patch.splitlines():
        if line.startswith("@@"):
            try:
                current = int(line.split("+", 1)[1].split(",", 1)[0].split()[0])
            except (IndexError, ValueError):
                current = None
        elif current is not None and not line.startswith("-"):
            if line.startswith("+") or line.startswith(" "):
                lines.add(current)
            current += 1
    return lines


def _validate_evidence_references(
    references: List[Dict[str, Any]],
    manifest: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Return unsupported citations; callers must reject, never discard them."""
    files = {item["file"]: item for item in manifest.get("files", [])}
    commits = {item.get("sha") for item in manifest.get("commits", [])}
    checks = {item.get("name") for item in manifest.get("check_runs", [])}
    reviews = {item.get("id") for item in manifest.get("reviews", [])}
    comments = {item.get("id") for item in manifest.get("comments", [])}
    invalid = []
    for reference in references:
        reason = None
        file_name = reference.get("file")
        if file_name and file_name not in files:
            reason = f"Unknown file: {file_name}"
        elif reference.get("commit_sha") and reference["commit_sha"] not in commits:
            reason = f"Unknown commit: {reference['commit_sha']}"
        elif reference.get("check_name") and reference["check_name"] not in checks:
            reason = f"Unknown check: {reference['check_name']}"
        elif reference.get("review_id") and reference["review_id"] not in reviews:
            reason = f"Unknown review: {reference['review_id']}"
        elif reference.get("comment_id") and reference["comment_id"] not in comments:
            reason = f"Unknown comment: {reference['comment_id']}"
        elif "line" in reference:
            if not file_name or file_name not in files:
                reason = "Line reference requires a known file"
            elif not isinstance(reference["line"], int):
                reason = "Line reference must be an integer"
            elif reference["line"] not in _diff_lines(files[file_name].get("patch")):
                reason = f"Line {reference['line']} is not present in the retrieved diff"
        if reason:
            invalid.append({"reference": reference, "reason": reason})
    return invalid


def _assess_dimension_coverage(
    dimensions: Dict[str, Any],
    evidence: Dict[str, Any],
    focus: str,
) -> Dict[str, str]:
    """Constrain assessment labels using available evidence, not assumptions."""
    coverage = {}
    for name in AI_DIMENSION_WEIGHTS:
        declared = dimensions[name].get("assessment", "assessed")
        coverage[name] = declared
    if not evidence.get("reviews") and not evidence.get("comments"):
        coverage["collaboration"] = "insufficient_evidence"
    if focus == "code_quality":
        coverage["engineering_impact"] = "insufficient_evidence"
        coverage["engineering_judgment"] = "insufficient_evidence"
    return coverage


def _calculate_focus_score(
    dimensions: Dict[str, Any],
    coverage: Dict[str, str],
) -> Optional[float]:
    """Normalize only assessable dimensions using the existing weights."""
    included = [
        name for name, weight in AI_DIMENSION_WEIGHTS.items()
        if coverage.get(name) in {"assessed", "partially_assessable"}
        and isinstance(dimensions.get(name), dict)
        and isinstance(dimensions[name].get("score"), (int, float))
    ]
    if not included:
        return None
    total_weight = sum(AI_DIMENSION_WEIGHTS[name] for name in included)
    return round(
        sum(float(dimensions[name]["score"]) * AI_DIMENSION_WEIGHTS[name] for name in included)
        / total_weight,
        2,
    )


async def _run_ai_evaluation(
    github_username: str,
    repo_info: Dict[str, Any],
    evidence: Dict[str, Any],
    focus: str,
    evidence_manifest: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the configured model against the complete, attributable PR evidence."""
    _require_evidence(evidence)
    if not check_ollama_connection():
        raise EvaluationProcessingError("Ollama is not available")

    prompt = f"""
Evaluate GitHub user '{github_username}' for the repository contribution below.
Use only the supplied pull request evidence. Do not invent files, tests, reviews,
security properties, or outcomes. This is a preliminary PR evaluation focused on
{focus}, not an overall performance assessment.

Repository metadata:
{json.dumps(repo_info, default=str, indent=2)}

Pull request evidence, including metadata, code patches, commits, CI checks,
reviews, and comments:
{json.dumps(_compact_evidence_for_prompt(evidence), default=str, indent=2)}

Evidence manifest (the only allowed citation source):
{json.dumps(evidence_manifest or _build_evidence_manifest(
    repo_info.get("owner", "unknown"),
    repo_info.get("name", "unknown"),
    evidence["pr"].get("number", 0),
    evidence,
), default=str, indent=2)}

Assess code correctness, readability, maintainability, API design, validation,
error handling, security, automated tests, edge cases, and architecture
consistency only where the evidence supports it.

Scoring contract:
- Every score must be a JSON number from 0 to 10 inclusive.
- Never return percentages or a 0-100 score. Do not divide, multiply, or
  otherwise normalize scores.
- Include only the supported dimensions listed below.
- For insufficient_evidence or not_assessed dimensions, do not invent a score;
  omit the score field. Those dimensions must not contribute to the overall score.
- Every assessed or partially_assessable dimension must include a numeric score.

Return JSON only with this exact shape:
{{
  "dimensions": {{
    "code_quality": {{"score": 0, "assessment": "assessed|partially_assessable|insufficient_evidence|not_assessed", "reasoning": "Evidence-backed reasoning"}},
    "delivery": {{"score": 0, "assessment": "assessed|partially_assessable|insufficient_evidence|not_assessed", "reasoning": "Evidence-backed reasoning"}},
    "collaboration": {{"score": 0, "assessment": "assessed|partially_assessable|insufficient_evidence|not_assessed", "reasoning": "Evidence-backed reasoning"}},
    "reliability": {{"score": 0, "assessment": "assessed|partially_assessable|insufficient_evidence|not_assessed", "reasoning": "Evidence-backed reasoning"}},
    "engineering_impact": {{"score": 0, "assessment": "assessed|partially_assessable|insufficient_evidence|not_assessed", "reasoning": "Evidence-backed reasoning"}},
    "engineering_judgment": {{"score": 0, "assessment": "assessed|partially_assessable|insufficient_evidence|not_assessed", "reasoning": "Evidence-backed reasoning"}}
  }},
  "analysis": "Evidence-backed overall assessment",
  "strengths": ["Evidence-backed strength"],
  "weaknesses": ["Evidence-backed weakness"],
  "recommendations": ["Evidence-backed recommendation"],
  "evidence": [
    {{"file": "path/to/file", "reason": "What the evidence shows", "recommendation": "Optional improvement"}}
  ],
  "confidence": 0.0
}}
"""
    try:
        llm = get_ollama_llm(temperature=0.3)
        response = await asyncio.wait_for(
            asyncio.to_thread(llm.invoke, prompt),
            timeout=MODEL_REQUEST_TIMEOUT_SECONDS,
        )
        if not isinstance(response, str):
            raise ModelResponseValidationError("AI response must be a JSON string")
        start_idx = response.find("{")
        end_idx = response.rfind("}") + 1
        if start_idx < 0 or end_idx <= start_idx:
            raise ModelResponseValidationError("AI response did not contain JSON")
        ai_data = json.loads(response[start_idx:end_idx])
    except ModelResponseValidationError:
        raise
    except asyncio.TimeoutError as exc:
        logger.error(
            "Ollama evaluation timed out after %s seconds",
            MODEL_REQUEST_TIMEOUT_SECONDS,
        )
        raise EvaluationProcessingError("AI evaluation timed out") from exc
    except json.JSONDecodeError as exc:
        raise ModelResponseValidationError("AI response was not valid JSON") from exc
    except Exception as exc:
        logger.error("Ollama evaluation request failed: %s", exc)
        raise EvaluationProcessingError(f"AI evaluation failed: {exc}") from exc

    dimensions = ai_data.get("dimensions")
    if not isinstance(dimensions, dict):
        raise ModelResponseValidationError("AI response did not contain dimensions")
    unsupported_dimensions = set(dimensions) - set(AI_DIMENSION_WEIGHTS)
    if unsupported_dimensions:
        raise ModelResponseValidationError(
            "AI response contains unsupported dimensions: "
            + ", ".join(sorted(unsupported_dimensions))
        )
    for name in AI_DIMENSION_WEIGHTS:
        dimension = dimensions.get(name)
        if not isinstance(dimension, dict):
            raise ModelResponseValidationError(f"AI response missing dimension: {name}")
        assessment = dimension.get("assessment")
        if assessment not in {
            "assessed",
            "partially_assessable",
            "insufficient_evidence",
            "not_assessed",
        }:
            raise ModelResponseValidationError(f"AI assessment invalid for {name}")
        if "score" not in dimension:
            if assessment in {"assessed", "partially_assessable"}:
                raise ModelResponseValidationError(f"AI response missing score for {name}")
        else:
            score = dimension["score"]
            if (
                not isinstance(score, (int, float))
                or isinstance(score, bool)
                or not 0 <= score <= 10
            ):
                raise ModelResponseValidationError(
                    f"AI score for {name} must be a numeric value between 0 and 10"
                )
        if not isinstance(dimension.get("reasoning"), str) or not dimension["reasoning"].strip():
            raise ModelResponseValidationError(f"AI reasoning missing for {name}")

    for field in ("analysis", "strengths", "weaknesses", "recommendations", "evidence"):
        if field not in ai_data:
            raise ModelResponseValidationError(f"AI response missing {field}")
    if not isinstance(ai_data["analysis"], str) or not ai_data["analysis"].strip():
        raise ModelResponseValidationError("AI analysis must be a non-empty string")
    for field in ("strengths", "weaknesses", "recommendations"):
        if not isinstance(ai_data[field], list) or not all(isinstance(item, str) for item in ai_data[field]):
            raise ModelResponseValidationError(f"AI response field {field} must be a list of strings")
    if not isinstance(ai_data["evidence"], list) or not all(isinstance(item, dict) for item in ai_data["evidence"]):
        raise ModelResponseValidationError("AI evidence must be a list of objects")
    try:
        ai_data["confidence"] = max(0.0, min(1.0, float(ai_data.get("confidence", 0.0))))
    except (TypeError, ValueError) as exc:
        raise ModelResponseValidationError("AI confidence must be numeric") from exc
    return ai_data


async def _authorized_evaluation(
    evaluation_id: str,
    user: dict,
) -> DeveloperEvaluation:
    evaluation = await EvaluationRepository().get_by_id(evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    role = user.get("role", user.get("organizational_role", "")).upper()
    if role not in {"CEO", "HR", "LEAD"} and user.get("employee_id") != evaluation.employee_id:
        raise HTTPException(status_code=403, detail="You cannot view this evaluation")
    return evaluation


@router.post("/evaluate", response_model=EvaluationResult)
async def evaluate_developer_ai(
    request: SimpleEvalRequest,
    user: dict = Depends(require_roles("CEO", "HR", "LEAD")),
):
    """Evaluate one attributable PR and persist the completed result."""
    employee_id = request.employee_id or user.get("employee_id")
    if not employee_id:
        raise HTTPException(status_code=400, detail="Employee ID is required")

    evaluation_id = f"EVAL-{uuid.uuid4().hex[:8].upper()}"
    try:
        github_service = GitHubAPIService()
        repo_info = await github_service.get_repository_info(request.repo_owner, request.repo_name)
        if request.pr_number is None:
            raise HTTPException(status_code=400, detail="A pull request number is required")

        evidence = await github_service.fetch_pull_request_evidence(
            request.repo_owner,
            request.repo_name,
            request.pr_number,
        )
        _require_evidence(evidence)
        evidence_manifest = _build_evidence_manifest(
            request.repo_owner,
            request.repo_name,
            request.pr_number,
            evidence,
        )
        pr = evidence["pr"]
        author = pr.get("user", {}).get("login")
        if author != request.github_username:
            raise EvidenceUnavailableError(
                f"Pull request author {author or 'unknown'} does not match {request.github_username}"
            )

        ai_evaluation = await _run_ai_evaluation(
            github_username=request.github_username,
            repo_info=repo_info,
            evidence=evidence,
            focus=request.evaluation_focus,
            evidence_manifest=evidence_manifest,
        )
        unsupported_references = _validate_evidence_references(
            ai_evaluation["evidence"],
            evidence_manifest,
        )
        if unsupported_references:
            raise EvidenceUnavailableError(
                f"AI returned unsupported evidence references: {unsupported_references}"
            )
        evidence_coverage = _assess_dimension_coverage(
            ai_evaluation["dimensions"],
            evidence,
            request.evaluation_focus,
        )
        evidence_score = _calculate_focus_score(
            ai_evaluation["dimensions"],
            evidence_coverage,
        )
        overall_score = evidence_score
        if overall_score is None:
            raise EvidenceUnavailableError(
                "Insufficient evidence prevents a reliable overall score"
            )
        if request.human_score is not None:
            overall_score = evidence_score * 0.9 + request.human_score * 0.1

        evaluation = DeveloperEvaluation(
            evaluation_id=evaluation_id,
            employee_id=employee_id,
            github_username=request.github_username,
            repo_owner=request.repo_owner,
            repo_name=request.repo_name,
            pr_number=request.pr_number,
            head_commit_sha=pr["head"]["sha"],
            evaluation_focus=request.evaluation_focus,
            ai_provider="ollama",
            model_name=settings.OLLAMA_MODEL,
            overall_score=round(overall_score, 2),
            human_score=request.human_score,
            dimensions=ai_evaluation["dimensions"],
            analysis=ai_evaluation["analysis"],
            strengths=ai_evaluation["strengths"],
            weaknesses=ai_evaluation["weaknesses"],
            recommendations=ai_evaluation["recommendations"],
            evidence_references=ai_evaluation["evidence"],
            evidence_manifest=evidence_manifest,
            evidence_coverage=evidence_coverage,
            limitations=[
                "Preliminary pull-request evaluation; not a complete performance assessment.",
            ],
            repo_info={
                "name": repo_info.get("name"),
                "owner": repo_info.get("owner"),
                "language": repo_info.get("language"),
                "description": repo_info.get("description"),
                "pr_title": pr.get("title"),
                "source_branch": pr.get("head", {}).get("ref"),
                "target_branch": pr.get("base", {}).get("ref"),
                "changed_files": _build_evidence_references(evidence),
                "confidence": ai_evaluation["confidence"],
            },
        )
        saved = await EvaluationRepository().create_or_get(evaluation)
        return _result_from_evaluation(saved)
    except HTTPException:
        raise
    except EvidenceUnavailableError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ModelResponseValidationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except EvaluationProcessingError as exc:
        detail = str(exc)
        status = 503 if "Ollama" in detail or "AI evaluation failed" in detail else 500
        raise HTTPException(status_code=status, detail=detail) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {exc}") from exc


@router.get("/latest", response_model=Optional[EvaluationResult])
async def get_latest_evaluation(user: dict = Depends(get_current_user)):
    role = user.get("role", user.get("organizational_role", "")).upper()
    query = {} if role in {"CEO", "HR", "LEAD"} else {"employee_id": user.get("employee_id")}
    evaluation = await EvaluationRepository().latest(query)
    return _result_from_evaluation(evaluation) if evaluation else None


@router.get("/employee/{employee_id}", response_model=List[EvaluationResult])
async def list_employee_evaluations(employee_id: str, user: dict = Depends(get_current_user)):
    role = user.get("role", user.get("organizational_role", "")).upper()
    if role not in {"CEO", "HR", "LEAD"} and user.get("employee_id") != employee_id:
        raise HTTPException(status_code=403, detail="You cannot view these evaluations")
    evaluations = await EvaluationRepository().list({"employee_id": employee_id})
    return [_result_from_evaluation(item) for item in evaluations]


@router.get("/repository/{owner}/{repo}/pr/{pr_number}", response_model=List[EvaluationResult])
async def list_pr_evaluations(
    owner: str,
    repo: str,
    pr_number: int,
    user: dict = Depends(get_current_user),
):
    role = user.get("role", user.get("organizational_role", "")).upper()
    if role not in {"CEO", "HR", "LEAD"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    evaluations = await EvaluationRepository().list({
        "repo_owner": owner,
        "repo_name": repo,
        "pr_number": pr_number,
    })
    return [_result_from_evaluation(item) for item in evaluations]


@router.get("/health")
async def evaluation_health():
    """Check evaluation dependencies without running an evaluation."""
    from integrations.github.client import GitHubClient

    github_status = "not_configured"
    try:
        client = GitHubClient()
        github_status = "configured" if await client.check_token_validity() else "invalid"
    except Exception:
        github_status = "error"

    return {
        "status": "operational",
        "ai_available": check_ollama_connection(),
        "github_available": github_status,
        "evaluation_ready": check_ollama_connection() and github_status in ["configured", "not_configured"],
    }


@router.get("/{evaluation_id}", response_model=EvaluationResult)
async def get_evaluation(evaluation_id: str, user: dict = Depends(get_current_user)):
    evaluation = await _authorized_evaluation(evaluation_id, user)
    return _result_from_evaluation(evaluation)
