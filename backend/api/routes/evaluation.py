"""Evidence-backed AI developer evaluation API."""

import asyncio
import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from agents.llm_provider import check_ollama_connection, get_ollama_llm
from core.config import settings
from core.dependencies import get_current_user, require_roles
from core.authorization import has_global_access, team_member_ids, verify_can_view_person_evaluations
from domain.models.developer_evaluation import DeveloperEvaluation
from domain.services.github_api_service import GitHubAPIService
from repositories.evaluation_repository import EvaluationRepository

router = APIRouter()
logger = logging.getLogger(__name__)
MODEL_REQUEST_TIMEOUT_SECONDS = 150
MAX_EVIDENCE_MANIFEST_BYTES = 24_000
MAX_MODEL_PROMPT_BYTES = 32_000

AI_DIMENSION_WEIGHTS = {
    "code_quality": 25,
    "delivery": 20,
    "collaboration": 15,
    "reliability": 15,
    "engineering_impact": 10,
    "engineering_judgment": 5,
}
CONFIGURED_TOTAL_WEIGHT = 100
_REFERENCE_ANCHORS = (
    "file",
    "commit_sha",
    "check_name",
    "review_id",
    "comment_id",
    "impact_metric",
)
_GENERIC_RECOMMENDATION_RE = re.compile(
    r"\b(?:switch|migrate|rewrite|replace)\b.{0,50}\b(?:framework|language|stack)\b"
    r"|\b(?:use|adopt)\s+(?:a\s+)?more modern framework\b"
    r"|\bimprove (?:the )?(?:code )?quality\b"
    r"|\b(?:implement|add|improve|enhance)\s+(?:general\s+)?(?:security measures|access controls|security)\b"
    r"|\badd more tests\b"
    r"|\bimprove documentation\b"
    r"|\boptimize performance\b"
    r"|\benhance security\b",
    re.IGNORECASE,
)
_DEADLINE_CLAIM_RE = re.compile(
    r"\b(?:on[- ]time|ahead of schedule|met (?:the )?deadline|"
    r"before (?:the )?deadline|timely delivery|deadline was met)\b",
    re.IGNORECASE,
)
_PRODUCTION_RELIABILITY_CLAIM_RE = re.compile(
    r"\b(?:production reliability|production[- ]ready|ready for production|"
    r"reliable in production|stable in production)\b",
    re.IGNORECASE,
)
_SECURITY_CLAIM_RE = re.compile(
    r"\b(?:vulnerabilit(?:y|ies)|vulnerable|insecure|security (?:risk|flaw|issue|control|measure)|"
    r"access control(?:s)? (?:is|are) (?:missing|absent)|data integrity (?:risk|concern))\b",
    re.IGNORECASE,
)
_PERFORMANCE_CLAIM_RE = re.compile(
    r"\b(?:performance (?:issue|problem|bottleneck|regression|concern)|"
    r"latency (?:issue|regression|problem)|memory leak|slow(?:er)? response)\b",
    re.IGNORECASE,
)
_RECOMMENDATION_ACTIONS = {
    "add", "assert", "avoid", "check", "cover", "document", "ensure",
    "handle", "implement", "move", "normalize", "preserve", "refactor",
    "reject", "remove", "replace", "return", "split", "validate", "use",
}
_RECOMMENDATION_STOP_WORDS = {
    "a", "an", "and", "for", "from", "in", "into", "it", "more", "of",
    "on", "or", "the", "this", "to", "with", "code", "issue", "better",
    "improve", "recommendation", "evidence", "reason", "dimension", "score",
    "supports", "supported", "retrieved", "available", "changed", "assessed",
    "assessment", "records", "recorded",
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
    
    model_config = {"protected_namespaces": ()}

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
    evidence_coverage_reasons: Dict[str, str] = {}
    score_dimensions: List[str] = []
    score_weights: Dict[str, float] = {}
    score_coverage: Dict[str, Any] = {}
    unsupported_references: List[Dict[str, Any]] = []
    limitations: List[str] = []
    is_preliminary: bool = True
    duplicate: bool = False
    status: str
    timestamp: str


def _result_from_evaluation(
    evaluation: DeveloperEvaluation,
    duplicate: bool = False,
) -> EvaluationResult:
    unsupported = evaluation.unsupported_references
    limitations = list(evaluation.limitations)
    is_preliminary = evaluation.is_preliminary and evaluation.status != "completed"
    scope_limitation = (
        f"{'Preliminary ' if is_preliminary else ''}"
        f"PR-scoped evaluation of the available evidence for PR #{evaluation.pr_number}; "
        "not a complete assessment of the developer's engineering performance."
    )
    legacy_scope_limitation = (
        "Preliminary pull-request evaluation; not a complete performance assessment."
    )
    limitations = [
        scope_limitation if item == legacy_scope_limitation else item
        for item in limitations
    ]
    if not is_preliminary:
        limitations = [
            item for item in limitations
            if "preliminary" not in item.casefold()
        ]
    if not any("PR-scoped evaluation of the available evidence" in item for item in limitations):
        limitations.insert(0, scope_limitation)

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
            "Historical evaluation predates evidence-manifest validation."
            if not is_preliminary
            else "Historical evaluation predates evidence-manifest validation and is preliminary."
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
            "evidence_coverage_reasons": evaluation.evidence_coverage_reasons,
            "score_dimensions": evaluation.score_dimensions,
            "score_weights": evaluation.score_weights,
        },
        overall_score=evaluation.overall_score,
        recommendations=evaluation.recommendations,
        evidence_references=evaluation.evidence_references,
        evidence_manifest=evaluation.evidence_manifest,
        evidence_coverage=evaluation.evidence_coverage,
        evidence_coverage_reasons=evaluation.evidence_coverage_reasons,
        score_dimensions=evaluation.score_dimensions,
        score_weights=evaluation.score_weights,
        score_coverage=evaluation.score_coverage or _score_coverage_metadata(
            evaluation.dimensions,
            evaluation.evidence_coverage,
            evaluation.evidence_coverage_reasons,
            evaluation.human_score,
        ),
        unsupported_references=unsupported,
        limitations=limitations,
        is_preliminary=is_preliminary,
        duplicate=duplicate,
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
            {
                "id": review.get("id"),
                "state": review.get("state"),
                "body": review.get("body"),
            }
            for review in evidence.get("reviews", [])
        ],
        "comments": [
            {
                "id": comment.get("id"),
                "body": comment.get("body"),
                "path": comment.get("path"),
                "line": comment.get("line"),
            }
            for comment in evidence.get("comments", [])
        ],
        "impact_metrics": [
            {
                "metric": item.get("metric"),
                "baseline": item.get("baseline"),
                "observed": item.get("observed"),
                "unit": item.get("unit"),
                "source": item.get("source"),
            }
            for item in evidence.get("impact_metrics", [])
            if isinstance(item, dict)
        ],
        "deadline_evidence": evidence.get("deadline_evidence", []),
        "commitment_evidence": evidence.get("commitment_evidence", []),
        "production_observations": evidence.get("production_observations", []),
        "security_evidence": evidence.get("security_evidence", []),
        "performance_observations": evidence.get("performance_observations", []),
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
        "impact_metrics": [
            {
                "metric": item.get("metric"),
                "baseline": item.get("baseline"),
                "observed": item.get("observed"),
                "unit": item.get("unit"),
                "source": item.get("source"),
            }
            for item in evidence.get("impact_metrics", [])
            if isinstance(item, dict)
        ],
        "deadline_evidence": evidence.get("deadline_evidence", []),
        "commitment_evidence": evidence.get("commitment_evidence", []),
        "production_observations": evidence.get("production_observations", []),
        "security_evidence": evidence.get("security_evidence", []),
        "performance_observations": evidence.get("performance_observations", []),
    }


def _compact_repository_info(repo_info: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only repository attributes useful to evaluation, without nested API objects."""
    owner = repo_info.get("owner")
    if isinstance(owner, dict):
        owner = owner.get("login")
    return {
        key: repo_info[key]
        for key in ("name", "full_name", "description", "language", "default_branch")
        if repo_info.get(key) is not None
    } | ({"owner": owner} if isinstance(owner, str) else {})


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
            if line.startswith("+"):
                lines.add(current)
            current += 1
    return lines


def _validate_evidence_references(
    references: List[Dict[str, Any]],
    manifest: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Return unsupported citations; callers must reject, never discard them."""
    files = {
        item.get("file"): item
        for item in manifest.get("files", [])
        if isinstance(item, dict) and item.get("file")
    }
    commits = {item.get("sha") for item in manifest.get("commits", [])}
    checks = {item.get("name") for item in manifest.get("check_runs", [])}
    reviews = {item.get("id") for item in manifest.get("reviews", [])}
    comments = {item.get("id") for item in manifest.get("comments", [])}
    impact_metrics = {
        item.get("metric")
        for item in manifest.get("impact_metrics", [])
        if isinstance(item, dict) and item.get("metric")
    }
    invalid = []
    for reference in references:
        reason = None
        if not isinstance(reference, dict):
            invalid.append({"reference": reference, "reason": "Evidence reference must be an object"})
            continue
        anchors = [key for key in _REFERENCE_ANCHORS if reference.get(key) is not None]
        if len(anchors) != 1:
            reason = "Evidence reference must identify exactly one manifest source"
        file_name = reference.get("file")
        if not reason:
            if file_name and file_name not in files:
                reason = f"Unknown file: {file_name}"
            elif (
                file_name
                and _diff_lines(files[file_name].get("patch"))
                and "line" not in reference
                and "excerpt" not in reference
            ):
                reason = "File references must identify an added line or exact excerpt when diff lines are available"
            elif reference.get("commit_sha") and reference["commit_sha"] not in commits:
                reason = f"Unknown commit: {reference['commit_sha']}"
            elif reference.get("check_name") and reference["check_name"] not in checks:
                reason = f"Unknown check: {reference['check_name']}"
            elif reference.get("review_id") and reference["review_id"] not in reviews:
                reason = f"Unknown review: {reference['review_id']}"
            elif reference.get("comment_id") and reference["comment_id"] not in comments:
                reason = f"Unknown comment: {reference['comment_id']}"
            elif reference.get("impact_metric") and reference["impact_metric"] not in impact_metrics:
                reason = f"Unknown impact metric: {reference['impact_metric']}"
            elif "line" in reference:
                if not file_name or file_name not in files:
                    reason = "Line reference requires a known file"
                elif not isinstance(reference["line"], int) or isinstance(reference["line"], bool):
                    reason = "Line reference must be an integer"
                elif reference["line"] not in _diff_lines(files[file_name].get("patch")):
                    reason = f"Line {reference['line']} is not present as an added line in the retrieved diff"
        if not reason and "excerpt" in reference:
            patch_lines = [
                line[1:].strip()
                for line in (files.get(file_name, {}).get("patch") or "").splitlines()
                if line.startswith("+") and not line.startswith("+++")
            ]
            excerpt = reference["excerpt"]
            if not isinstance(excerpt, str) or not excerpt.strip():
                reason = "Evidence excerpt must be a non-empty string"
            elif not file_name or not any(excerpt.strip() in line for line in patch_lines):
                reason = "Evidence excerpt does not match a retrieved added line"
        if not reason and (
            not isinstance(reference.get("reason"), str)
            or not reference["reason"].strip()
        ):
            reason = "Evidence reference must explain its relevance"
        if reason:
            invalid.append({"reference": reference, "reason": reason})
    return invalid


def _response_text_values(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for nested in value.values():
            yield from _response_text_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _response_text_values(nested)


def _is_negated_claim(text: str, position: int) -> bool:
    prefix = text[max(0, position - 60):position]
    return bool(re.search(
        r"\b(?:not|no|cannot|can't|does not|doesn't|without|unable to)\b"
        r"(?:\W+\w+){0,5}\W*$",
        prefix,
        re.IGNORECASE,
    ))


def _validate_evidence_bound_claims(
    response: Dict[str, Any],
    manifest: Dict[str, Any],
) -> None:
    schedule_evidence = manifest.get("deadline_evidence") or manifest.get("commitment_evidence")
    production_evidence = manifest.get("production_observations")
    security_evidence = manifest.get("security_evidence")
    performance_evidence = (
        manifest.get("performance_observations")
        or manifest.get("impact_metrics")
    )
    for text in _response_text_values(response):
        if not schedule_evidence:
            for match in _DEADLINE_CLAIM_RE.finditer(text):
                if not _is_negated_claim(text, match.start()):
                    raise ModelResponseValidationError(
                        "AI response makes a deadline claim without deadline or commitment evidence"
                    )
        if not production_evidence:
            for match in _PRODUCTION_RELIABILITY_CLAIM_RE.finditer(text):
                if not _is_negated_claim(text, match.start()):
                    raise ModelResponseValidationError(
                        "AI response infers production reliability without production outcome evidence"
                    )
        if not security_evidence:
            for match in _SECURITY_CLAIM_RE.finditer(text):
                if not _is_negated_claim(text, match.start()):
                    raise ModelResponseValidationError(
                        "AI response makes a security claim without security evidence"
                    )
        if not performance_evidence:
            for match in _PERFORMANCE_CLAIM_RE.finditer(text):
                if not _is_negated_claim(text, match.start()):
                    raise ModelResponseValidationError(
                        "AI response makes a performance claim without measured evidence"
                    )


def _citation_source_text(
    reference: Dict[str, Any],
    manifest: Dict[str, Any],
) -> str:
    if reference.get("file"):
        item = next(
            (
                item for item in manifest.get("files", [])
                if item.get("file") == reference["file"]
            ),
            {},
        )
        return f"{reference['file']} {item.get('patch') or ''}"
    if reference.get("commit_sha"):
        item = next(
            (
                item for item in manifest.get("commits", [])
                if item.get("sha") == reference["commit_sha"]
            ),
            {},
        )
        return f"{item.get('message') or ''}"
    if reference.get("check_name"):
        item = next(
            (
                item for item in manifest.get("check_runs", [])
                if item.get("name") == reference["check_name"]
            ),
            {},
        )
        return f"{item.get('name') or ''} {item.get('conclusion') or ''}"
    if reference.get("review_id"):
        item = next(
            (
                item for item in manifest.get("reviews", [])
                if item.get("id") == reference["review_id"]
            ),
            {},
        )
        return f"{item.get('state') or ''} {item.get('body') or ''}"
    if reference.get("comment_id"):
        item = next(
            (
                item for item in manifest.get("comments", [])
                if item.get("id") == reference["comment_id"]
            ),
            {},
        )
        return f"{item.get('path') or ''} {item.get('body') or ''}"
    if reference.get("impact_metric"):
        item = next(
            (
                item for item in manifest.get("impact_metrics", [])
                if item.get("metric") == reference["impact_metric"]
            ),
            {},
        )
        return " ".join(
            str(item.get(key, ""))
            for key in ("metric", "baseline", "observed", "unit", "source")
        )
    return ""


def _validate_dimension_reasoning_sources(
    dimensions: Dict[str, Any],
    manifest: Dict[str, Any],
) -> None:
    for name, dimension in dimensions.items():
        reasoning_terms = set(
            re.findall(r"[a-z0-9]+", dimension["reasoning"].casefold())
        ) - _RECOMMENDATION_STOP_WORDS - _RECOMMENDATION_ACTIONS
        cited_terms = set()
        for reference in dimension["evidence"]:
            cited_terms.update(
                re.findall(
                    r"[a-z0-9]+",
                    _citation_source_text(reference, manifest).casefold(),
                )
            )
        if not reasoning_terms & cited_terms:
            raise ModelResponseValidationError(
                f"AI reasoning for {name} is not connected to its cited evidence"
            )


def _validate_recommendations(
    recommendations: List[str],
    references: List[Dict[str, Any]],
    manifest: Dict[str, Any],
) -> None:
    for recommendation in recommendations:
        if not recommendation.strip():
            raise ModelResponseValidationError("AI recommendations must not be empty")
        if _GENERIC_RECOMMENDATION_RE.search(recommendation):
            raise ModelResponseValidationError(
                f"AI recommendation is generic or unjustified: {recommendation}"
            )
        recommendation_terms = set(re.findall(r"[a-z0-9]+", recommendation.casefold()))
        specific_terms = recommendation_terms - _RECOMMENDATION_STOP_WORDS - _RECOMMENDATION_ACTIONS
        if not recommendation_terms & _RECOMMENDATION_ACTIONS or len(specific_terms) < 2:
            raise ModelResponseValidationError(
                f"AI recommendation is not sufficiently specific and actionable: {recommendation}"
            )
        linked_references = [
            reference for reference in references
            if isinstance(reference.get("recommendation"), str)
            and reference["recommendation"].strip().casefold()
            == recommendation.strip().casefold()
        ]
        if not linked_references:
            raise ModelResponseValidationError(
                f"AI recommendation has no matching evidence citation: {recommendation}"
            )
        for reference in linked_references:
            evidence_text = _citation_source_text(reference, manifest).casefold()
            evidence_terms = set(re.findall(r"[a-z0-9]+", evidence_text))
            if recommendation_terms & evidence_terms:
                break
        else:
            raise ModelResponseValidationError(
                f"AI recommendation is unrelated to the cited PR evidence: {recommendation}"
            )


def _is_test_file(path: str) -> bool:
    lowered = path.lower().replace("\\", "/")
    filename = lowered.rsplit("/", 1)[-1]
    return (
        "/tests/" in f"/{lowered}"
        or filename.startswith("test_")
        or ".test." in filename
        or ".spec." in filename
    )


def _determine_dimension_eligibility(
    evidence: Dict[str, Any],
    focus: str,
) -> tuple[Dict[str, str], Dict[str, str]]:
    """Derive score eligibility from retrieved evidence before model inference."""
    files = [
        item for item in evidence.get("files", [])
        if isinstance(item, dict) and isinstance(item.get("filename"), str)
    ]
    patched_files = [
        item for item in files
        if isinstance(item.get("patch"), str) and item["patch"].strip()
    ]
    implementation_patches = [
        item for item in patched_files if not _is_test_file(item["filename"])
    ]
    test_patches = [
        item for item in patched_files if _is_test_file(item["filename"])
    ]
    commits = evidence.get("commits", [])
    check_runs = evidence.get("check_runs", [])
    if isinstance(check_runs, dict):
        check_runs = check_runs.get("check_runs", [])
    reviews = evidence.get("reviews", [])
    comments = evidence.get("comments", [])
    impact_metrics = evidence.get("impact_metrics", [])
    has_measured_impact = any(
        isinstance(item, dict)
        and item.get("metric")
        and item.get("baseline") is not None
        and item.get("observed") is not None
        for item in impact_metrics
    )

    assessments: Dict[str, tuple[str, str]] = {}
    if implementation_patches:
        primary = "assessed" if focus == "code_quality" else "partially_assessable"
        assessments["code_quality"] = (
            primary,
            "Retrieved implementation diffs are available for code review."
            if primary == "assessed"
            else "Implementation diffs are available, but code quality is not the selected focus.",
        )
    else:
        assessments["code_quality"] = (
            "insufficient_evidence",
            "No implementation patch was retrieved for this pull request.",
        )

    if commits:
        assessments["delivery"] = (
            "partially_assessable",
            "Commit evidence confirms submitted work; it does not establish completion beyond this pull request.",
        )
    else:
        assessments["delivery"] = (
            "insufficient_evidence",
            "No pull request commits were retrieved.",
        )

    if reviews or comments:
        assessments["collaboration"] = (
            "partially_assessable",
            "Retrieved reviews or comments provide limited collaboration evidence.",
        )
    else:
        assessments["collaboration"] = (
            "insufficient_evidence",
            "No pull request reviews or comments were retrieved.",
        )

    if test_patches or check_runs:
        details = []
        if test_patches:
            details.append(f"{len(test_patches)} changed test file(s)")
        if check_runs:
            details.append(f"{len(check_runs)} CI check run(s)")
        assessments["reliability"] = (
            "partially_assessable",
            f"{' and '.join(details)} provide limited test/CI evidence; successful CI does not establish production reliability.",
        )
    else:
        assessments["reliability"] = (
            "insufficient_evidence",
            "No changed tests or CI check runs were retrieved; production reliability cannot be inferred.",
        )

    if has_measured_impact:
        assessments["engineering_impact"] = (
            "partially_assessable",
            "Retrieved baseline and observed impact measurements permit a limited impact assessment.",
        )
    else:
        assessments["engineering_impact"] = (
            "insufficient_evidence",
            "No measured post-change outcome or impact metrics were retrieved; one pull request alone does not establish long-term impact.",
        )

    if implementation_patches and test_patches:
        assessments["engineering_judgment"] = (
            "partially_assessable",
            "Paired implementation and test diffs permit limited assessment of observable technical decisions, not broader trade-offs.",
        )
    else:
        assessments["engineering_judgment"] = (
            "insufficient_evidence",
            "The retrieved pull request lacks both implementation and test diffs needed to assess technical decisions.",
        )

    coverage = {name: assessments[name][0] for name in AI_DIMENSION_WEIGHTS}
    reasons = {name: assessments[name][1] for name in AI_DIMENSION_WEIGHTS}
    return coverage, reasons


def _included_score_dimensions(
    dimensions: Dict[str, Any],
    coverage: Dict[str, str],
) -> List[str]:
    included = [
        name for name in AI_DIMENSION_WEIGHTS
        if coverage.get(name) in {"assessed", "partially_assessable"}
        and isinstance(dimensions.get(name), dict)
        and isinstance(dimensions[name].get("score"), (int, float))
        and not isinstance(dimensions[name].get("score"), bool)
        and 0 <= dimensions[name]["score"] <= 10
    ]
    return included


def _calculate_focus_score(
    dimensions: Dict[str, Any],
    coverage: Dict[str, str],
) -> Optional[float]:
    """Aggregate eligible scores using the existing normalized weight framework."""
    included = _included_score_dimensions(dimensions, coverage)
    if not included:
        return None
    total_weight = sum(AI_DIMENSION_WEIGHTS[name] for name in included)
    return round(
        sum(float(dimensions[name]["score"]) * AI_DIMENSION_WEIGHTS[name] for name in included)
        / total_weight,
        2,
    )


def _normalized_score_weights(
    dimensions: Dict[str, Any],
    coverage: Dict[str, str],
) -> Dict[str, float]:
    included = _included_score_dimensions(dimensions, coverage)
    total_weight = sum(AI_DIMENSION_WEIGHTS[name] for name in included)
    if not total_weight:
        return {}
    return {
        name: round(AI_DIMENSION_WEIGHTS[name] / total_weight, 6)
        for name in included
    }


def _score_coverage_metadata(
    dimensions: Dict[str, Any],
    coverage: Dict[str, str],
    coverage_reasons: Dict[str, str],
    human_score: Optional[float] = None,
) -> Dict[str, Any]:
    """Describe configured weight coverage and normalized scoring for API consumers."""
    included = _included_score_dimensions(dimensions, coverage)
    excluded = [
        {
            "dimension": name,
            "configured_weight": AI_DIMENSION_WEIGHTS[name],
            "assessment": coverage.get(name, "not_assessed"),
            "reason": coverage_reasons.get(
                name,
                "No validated score was recorded for this dimension.",
            ),
        }
        for name in AI_DIMENSION_WEIGHTS
        if name not in included
    ]
    assessed_weight = sum(AI_DIMENSION_WEIGHTS[name] for name in included)
    weighted_points = sum(
        float(dimensions[name]["score"]) * AI_DIMENSION_WEIGHTS[name]
        for name in included
    )
    formula = None
    dimension_score = None
    overall_score = None
    if assessed_weight:
        terms = " + ".join(
            f"({dimensions[name]['score']} × {AI_DIMENSION_WEIGHTS[name]})"
            for name in included
        )
        dimension_score = round(weighted_points / assessed_weight, 2)
        formula = f"({terms}) / {assessed_weight}"
        overall_score = dimension_score
        if human_score is not None:
            formula = f"round({formula}, 2) × 0.9 + ({human_score} × 0.1)"
            overall_score = round(dimension_score * 0.9 + human_score * 0.1, 2)
        formula = f"{formula} = {overall_score:.2f}"
    return {
        "configured_total_weight": CONFIGURED_TOTAL_WEIGHT,
        "defined_dimension_weight": sum(AI_DIMENSION_WEIGHTS.values()),
        "unallocated_weight": CONFIGURED_TOTAL_WEIGHT - sum(AI_DIMENSION_WEIGHTS.values()),
        "assessed_weight": assessed_weight,
        "coverage_percentage": round(
            assessed_weight / CONFIGURED_TOTAL_WEIGHT * 100,
            2,
        ),
        "included_dimensions": included,
        "configured_weights": {
            name: AI_DIMENSION_WEIGHTS[name]
            for name in included
        },
        "excluded_dimensions": excluded,
        "normalized_weights": {
            name: round(AI_DIMENSION_WEIGHTS[name] / assessed_weight, 6)
            for name in included
        } if assessed_weight else {},
        "normalized_dimension_score": dimension_score,
        "overall_score": overall_score,
        "calculation": formula,
    }


async def _run_ai_evaluation(
    github_username: str,
    repo_info: Dict[str, Any],
    evidence: Dict[str, Any],
    focus: str,
    evidence_manifest: Optional[Dict[str, Any]] = None,
    evidence_coverage: Optional[Dict[str, str]] = None,
    evidence_coverage_reasons: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Run the model only for dimensions already eligible from retrieved evidence."""
    _require_evidence(evidence)
    if evidence_coverage is None or evidence_coverage_reasons is None:
        calculated_coverage, calculated_reasons = _determine_dimension_eligibility(
            evidence,
            focus,
        )
        evidence_coverage = evidence_coverage or calculated_coverage
        evidence_coverage_reasons = evidence_coverage_reasons or calculated_reasons
    expected_dimensions = set(AI_DIMENSION_WEIGHTS)
    if set(evidence_coverage) != expected_dimensions:
        raise ValueError("Evidence coverage must include every supported evaluation dimension")
    if set(evidence_coverage_reasons) != expected_dimensions:
        raise ValueError("Evidence coverage reasons must include every supported evaluation dimension")
    assessable_dimensions = [
        name for name in AI_DIMENSION_WEIGHTS
        if evidence_coverage[name] in {"assessed", "partially_assessable"}
    ]
    excluded_dimensions = [
        {
            "dimension": name,
            "assessment": evidence_coverage[name],
            "reason": evidence_coverage_reasons[name],
        }
        for name in AI_DIMENSION_WEIGHTS
        if name not in assessable_dimensions
    ]
    assessable_dimension_context = [
        {
            "dimension": name,
            "assessment": evidence_coverage[name],
        }
        for name in assessable_dimensions
    ]
    if not assessable_dimensions:
        raise EvidenceUnavailableError(
            "No evaluation dimensions have sufficient evidence for scoring"
        )
    if not check_ollama_connection():
        raise EvaluationProcessingError("Ollama is not available")

    compact_evidence = _compact_evidence_for_prompt(evidence)
    manifest = evidence_manifest or _build_evidence_manifest(
        repo_info.get("owner", "unknown"),
        repo_info.get("name", "unknown"),
        evidence["pr"].get("number", 0),
        evidence,
    )
    manifest_json = json.dumps(manifest, default=str, indent=2)
    if len(manifest_json.encode("utf-8")) > MAX_EVIDENCE_MANIFEST_BYTES:
        raise EvidenceUnavailableError("Pull request evidence manifest exceeds the supported size")

    prompt = f"""
Evaluate GitHub user '{github_username}' for the repository contribution below.
Use only the supplied pull request evidence. Do not invent files, tests, reviews,
security properties, or outcomes. This is a PR-scoped evaluation focused on
{focus}, not an overall performance assessment.

Repository metadata:
{json.dumps(_compact_repository_info(repo_info), default=str, indent=2)}

Pull request evidence, including metadata, code patches, commits, CI checks,
reviews, and comments:
{json.dumps(compact_evidence, default=str, indent=2)}

Evidence manifest (the only allowed citation source):
{manifest_json}

Assess code correctness, readability, maintainability, API design, validation,
error handling, security, automated tests, edge cases, and architecture
consistency only where the evidence supports it.

Scoring contract:
- Score only these backend-approved dimensions:
{json.dumps(assessable_dimension_context, indent=2)}
- Do not return any dimension listed as insufficient evidence or not assessed.
- Please do not invent a score for excluded dimensions.
- Do not decide or change evidence eligibility; the backend has already determined it.
- Every score must be a JSON number from 0 to 10 inclusive.
- Never return percentages or a 0-100 score. Do not divide, multiply, or
  otherwise normalize scores.
- Every scored dimension must cite one or more exact sources from the evidence
  manifest using its "evidence" array. Prefer changed file + added line + a
  short exact excerpt; otherwise cite a retrieved commit, check, review,
  comment, or impact metric. Each citation needs a reason.
- Do not claim delivery was on time, ahead of schedule, or met a deadline unless
  deadline or commitment evidence is explicitly present in the manifest.
- A successful CI check proves only that check passed. It does not establish production reliability,
  production readiness, or deployed behavior.
- Do not make security, performance, or architecture claims without an exact
  supporting citation. If evidence is insufficient, state that as a limitation.
- Do not score collaboration without retrieved reviews/comments. Do not score
  engineering impact without measured outcome evidence.
- These dimensions are excluded and must not appear in the response:
{json.dumps(excluded_dimensions, indent=2)}

Recommendation contract:
- Every recommendation must identify a concrete issue visible in a cited PR
  source, name affected code or behavior, and give a technically actionable
  change.
- Do not recommend framework/language/stack changes without evidence of a
  specific incompatibility that requires it.
- Do not give generic advice such as "add more tests", "improve security", or
  "optimize performance" without a specific observed issue.
- Each recommendation needs one matching evidence citation whose
  "recommendation" field repeats the recommendation text exactly.

Return JSON only with this exact shape:
{{
  "dimensions": {{
{json.dumps({name: {
    "score": 0,
    "reasoning": "Evidence-backed reasoning, with no unsupported claims",
    "evidence": [{
        "file": "path/to/changed-file",
        "line": 1,
        "excerpt": "Exact added line excerpt",
        "reason": "How this line supports the score"
    }]
} for name in assessable_dimensions}, indent=4)}
  }},
  "analysis": "Evidence-backed overall assessment",
  "strengths": ["Evidence-backed strength"],
  "weaknesses": ["Evidence-backed weakness"],
  "recommendations": ["Specific action grounded in a cited issue"],
  "evidence": [
    {{"file": "path/to/changed-file", "line": 1, "excerpt": "Exact added line excerpt", "reason": "What the evidence shows", "recommendation": "Exact recommendation text"}}
  ],
  "confidence": 0.0
}}
"""
    if len(prompt.encode("utf-8")) > MAX_MODEL_PROMPT_BYTES:
        raise EvidenceUnavailableError("Evaluation prompt exceeds the supported size")
    prompt_size = len(prompt.encode("utf-8"))
    request_started = time.monotonic()
    logger.info(
        "Starting Ollama evaluation inference model=%s prompt_bytes=%d",
        settings.OLLAMA_MODEL,
        prompt_size,
    )
    try:
        llm = get_ollama_llm(temperature=0.3)
        response = await asyncio.wait_for(
            asyncio.to_thread(llm.invoke, prompt),
            timeout=MODEL_REQUEST_TIMEOUT_SECONDS,
        )
        logger.info(
            "Completed Ollama evaluation inference model=%s duration_seconds=%.2f",
            settings.OLLAMA_MODEL,
            time.monotonic() - request_started,
        )
        if not isinstance(response, str):
            raise ModelResponseValidationError("AI response must be a JSON string")
        try:
            ai_data = json.loads(response.strip())
        except json.JSONDecodeError:
            start_idx = response.find("{")
            end_idx = response.rfind("}") + 1
            if start_idx < 0 or end_idx <= start_idx:
                raise ModelResponseValidationError("AI response did not contain JSON")
            ai_data = json.loads(response[start_idx:end_idx])
    except ModelResponseValidationError:
        raise
    except asyncio.TimeoutError as exc:
        logger.error(
            "Ollama evaluation timed out model=%s duration_seconds=%.2f",
            settings.OLLAMA_MODEL,
            time.monotonic() - request_started,
        )
        raise EvaluationProcessingError("AI evaluation timed out") from exc
    except json.JSONDecodeError as exc:
        raise ModelResponseValidationError("AI response was not valid JSON") from exc
    except Exception as exc:
        logger.error(
            "Ollama evaluation request failed model=%s duration_seconds=%.2f error_type=%s",
            settings.OLLAMA_MODEL,
            time.monotonic() - request_started,
            type(exc).__name__,
        )
        raise EvaluationProcessingError(f"AI evaluation failed: {exc}") from exc

    if not isinstance(ai_data, dict):
        raise ModelResponseValidationError("AI response must be a JSON object")
    dimensions = ai_data.get("dimensions")
    if not isinstance(dimensions, dict):
        raise ModelResponseValidationError("AI response did not contain dimensions")
    unsupported_dimensions = set(dimensions) - set(AI_DIMENSION_WEIGHTS)
    if unsupported_dimensions:
        raise ModelResponseValidationError(
            "AI response contains unsupported dimensions: "
            + ", ".join(sorted(unsupported_dimensions))
        )
    ineligible_dimensions = set(dimensions) - set(assessable_dimensions)
    if ineligible_dimensions:
        raise ModelResponseValidationError(
            "AI response contains unsupported dimensions without sufficient evidence: "
            + ", ".join(sorted(ineligible_dimensions))
        )
    missing_dimensions = set(assessable_dimensions) - set(dimensions)
    if missing_dimensions:
        raise ModelResponseValidationError(
            "AI response missing assessed dimensions: "
            + ", ".join(sorted(missing_dimensions))
        )
    for name in assessable_dimensions:
        dimension = dimensions[name]
        if not isinstance(dimension, dict):
            raise ModelResponseValidationError(f"AI response missing dimension: {name}")
        if "score" not in dimension:
            raise ModelResponseValidationError(f"AI response missing score for {name}")
        if set(dimension) != {"score", "reasoning", "evidence"}:
            raise ModelResponseValidationError(
                f"AI response schema invalid for {name}; expected score, reasoning, and evidence"
            )
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
        if (
            not isinstance(dimension.get("evidence"), list)
            or not dimension["evidence"]
            or not all(isinstance(item, dict) for item in dimension["evidence"])
        ):
            raise ModelResponseValidationError(
                f"AI score for {name} must cite at least one evidence source"
            )
        if any(
            not isinstance(item.get("reason"), str) or not item["reason"].strip()
            for item in dimension["evidence"]
        ):
            raise ModelResponseValidationError(
                f"AI evidence for {name} must explain how each citation supports the score"
            )

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
    all_references = list(ai_data["evidence"])
    for dimension in dimensions.values():
        if isinstance(dimension, dict) and isinstance(dimension.get("evidence"), list):
            all_references.extend(dimension["evidence"])
    unsupported_references = _validate_evidence_references(all_references, manifest)
    if unsupported_references:
        raise ModelResponseValidationError(
            f"AI response contains evidence references not present in the manifest: {unsupported_references}"
        )
    _validate_evidence_bound_claims(ai_data, manifest)
    _validate_dimension_reasoning_sources(dimensions, manifest)
    _validate_recommendations(ai_data["recommendations"], ai_data["evidence"], manifest)
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
    # CR-004: own, the CEO, or a Lead for their team members.
    await verify_can_view_person_evaluations(user, evaluation.employee_id)
    return evaluation


@router.post("/evaluate", response_model=EvaluationResult)
async def evaluate_developer_ai(
    request: SimpleEvalRequest,
    user: dict = Depends(require_roles("CEO", "LEAD")),
):
    """Evaluate one attributable PR and persist the completed result."""
    employee_id = request.employee_id or user.get("employee_id")
    if not employee_id:
        raise HTTPException(status_code=400, detail="Employee ID is required")
    # CR-004: Leads evaluate only their team members; the CEO anyone.
    await verify_can_view_person_evaluations(user, employee_id)

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

        evidence_coverage, evidence_coverage_reasons = _determine_dimension_eligibility(
            evidence,
            request.evaluation_focus,
        )
        ai_evaluation = await _run_ai_evaluation(
            github_username=request.github_username,
            repo_info=repo_info,
            evidence=evidence,
            focus=request.evaluation_focus,
            evidence_manifest=evidence_manifest,
            evidence_coverage=evidence_coverage,
            evidence_coverage_reasons=evidence_coverage_reasons,
        )
        unsupported_references = _validate_evidence_references(
            ai_evaluation["evidence"],
            evidence_manifest,
        )
        if unsupported_references:
            raise EvidenceUnavailableError(
                f"AI returned unsupported evidence references: {unsupported_references}"
            )
        dimensions = {}
        for name in AI_DIMENSION_WEIGHTS:
            if evidence_coverage[name] in {"assessed", "partially_assessable"}:
                dimensions[name] = {
                    **ai_evaluation["dimensions"][name],
                    "assessment": evidence_coverage[name],
                }
            else:
                dimensions[name] = {
                    "assessment": evidence_coverage[name],
                    "reasoning": evidence_coverage_reasons[name],
                }
        evidence_score = _calculate_focus_score(
            dimensions,
            evidence_coverage,
        )
        overall_score = evidence_score
        if request.human_score is not None:
            if evidence_score is not None:
                overall_score = evidence_score * 0.9 + request.human_score * 0.1
        score_weights = _normalized_score_weights(dimensions, evidence_coverage)
        score_coverage = _score_coverage_metadata(
            dimensions,
            evidence_coverage,
            evidence_coverage_reasons,
            request.human_score,
        )
        is_preliminary = False
        limitations = [
            f"PR-scoped evaluation of the available evidence for PR #{request.pr_number}; "
            "not a complete assessment of the developer's engineering performance.",
            *[
                f"{name.replace('_', ' ').title()} was not scored: {evidence_coverage_reasons[name]}"
                for name in AI_DIMENSION_WEIGHTS
                if evidence_coverage[name] in {"insufficient_evidence", "not_assessed"}
            ],
        ]
        if overall_score is None:
            limitations.append(
                "Overall score unavailable because no dimensions had sufficient evidence for scoring."
            )

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
            overall_score=round(overall_score, 2) if overall_score is not None else None,
            human_score=request.human_score,
            dimensions=dimensions,
            analysis=ai_evaluation["analysis"],
            strengths=ai_evaluation["strengths"],
            weaknesses=ai_evaluation["weaknesses"],
            recommendations=ai_evaluation["recommendations"],
            evidence_references=ai_evaluation["evidence"],
            evidence_manifest=evidence_manifest,
            evidence_coverage=evidence_coverage,
            evidence_coverage_reasons=evidence_coverage_reasons,
            score_dimensions=list(score_weights),
            score_weights=score_weights,
            score_coverage=score_coverage,
            schema_validated=True,
            evidence_validated=True,
            is_preliminary=is_preliminary,
            limitations=limitations,
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
        return _result_from_evaluation(
            saved,
            duplicate=saved.evaluation_id != evaluation_id,
        )
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
    # CR-004: the CEO sees the latest in the organisation; a Lead the latest
    # in their team; everyone else their own.
    if has_global_access(user):
        query = {}
    elif role == "LEAD":
        query = {"employee_id": {"$in": sorted(await team_member_ids(user))}}
    else:
        query = {"employee_id": user.get("employee_id")}
    evaluation = await EvaluationRepository().latest(query)
    return _result_from_evaluation(evaluation) if evaluation else None


@router.get("/employee/{employee_id}", response_model=List[EvaluationResult])
async def list_employee_evaluations(employee_id: str, user: dict = Depends(get_current_user)):
    await verify_can_view_person_evaluations(user, employee_id)
    evaluations = await EvaluationRepository().list({"employee_id": employee_id})
    return [_result_from_evaluation(item) for item in evaluations]


async def _verify_repository_in_scope(user: dict, owner: str, repo: str) -> None:
    from core.authorization import get_accessible_project_ids
    from core.database import col
    project_ids = await get_accessible_project_ids(user)
    link = await col("github_project_configs").find_one({
        "project_id": {"$in": project_ids},
        "repository_owner": {"$regex": f"^{re.escape(owner)}$", "$options": "i"},
        "repository_name": {"$regex": f"^{re.escape(repo)}$", "$options": "i"},
    }, {"_id": 0, "project_id": 1})
    if not link:
        raise HTTPException(status_code=403, detail="This repository is not linked to one of your projects")


@router.get("/repository/{owner}/{repo}/pr/{pr_number}", response_model=List[EvaluationResult])
async def list_pr_evaluations(
    owner: str,
    repo: str,
    pr_number: int,
    user: dict = Depends(get_current_user),
):
    role = user.get("role", user.get("organizational_role", "")).upper()
    if role not in {"CEO", "LEAD"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if not has_global_access(user):
        # CR-004: a Lead only for repositories linked to their projects.
        await _verify_repository_in_scope(user, owner, repo)
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
