"""Server-only pinned evidence for the internal manual PR workflow."""

import asyncio
import base64
import hashlib
import re
from collections import Counter
from datetime import datetime

import httpx
from fastapi import HTTPException

from core.database import col
from core.permissions import Permission
from domain.models.ai_evidence import GitHubFileEvidenceV1
from domain.models.performance_evidence import canonical_digest
from domain.models.pr_multi_agent import EvidenceReference, Observation, PRScope, PRSnapshot
from domain.services.ai_evidence_service import _repository, _file, MAX_SOURCE_BYTES
from domain.services.ai_run_access import invocation_scope, permissions
from domain.services.auth_service import AuthService
from intelligence.algorithms.discovery.service import discover_sources, source_language
from repositories.user_repository import UserRepository

MAX_FILES = 4
MAX_CI_RUNS = 4


def pr_revisions(pr, repository, number):
    """Reject malformed or mismatched provider metadata before using its revisions."""
    if not isinstance(pr, dict):
        raise HTTPException(409, "PR identity or exact revision could not be established")
    head, base = pr.get("head"), pr.get("base")
    if not isinstance(head, dict) or not isinstance(base, dict) or not isinstance(base.get("repo"), dict):
        raise HTTPException(409, "PR identity or exact revision could not be established")
    revisions = (head.get("sha"), base.get("sha"))
    if (type(pr.get("number")) is not int or pr["number"] != number
            or str(base["repo"].get("full_name", "")).casefold() != repository.casefold()
            or any(not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{40}", sha) for sha in revisions)):
        raise HTTPException(409, "PR identity or exact revision could not be established")
    return revisions


class PREvidenceResolver:
    def __init__(self, api):
        self.api = api

    @staticmethod
    async def current_actor(actor):
        identity = actor.get("employee_id") if isinstance(actor, dict) else None
        if not isinstance(identity, str) or not identity:
            raise HTTPException(403, "An authenticated account is required")
        account = await UserRepository().find_by_employee_id(identity)
        if not account or not account.get("is_active", True):
            raise HTTPException(403, "Current account is unavailable")
        user = AuthService._token_payload(account)
        user.update(role=user["organizational_role"], is_admin=user["system_access"] == "ADMIN")
        allowed = permissions(user)
        if user["role"] == "HR" or not {Permission.TRIGGER_AI_EVALUATION, Permission.VIEW_AI_EVALUATION} <= allowed:
            raise HTTPException(403, "Insufficient permissions for manual PR interpretation")
        return user

    async def authorize(self, actor, request):
        user = await self.current_actor(actor)
        scope = await invocation_scope(user, {"project_id": request.project_id})
        owner, repo = await _repository(request.project_id, scope["organization_id"])
        return scope, owner, repo

    async def resolve(self, actor, request):
        async with asyncio.timeout(60):
            access, owner, repo = await self.authorize(actor, request)
            pr = await self.api.client.get_pull_request(owner, repo, request.pr_number)
            repository = owner + "/" + repo
            head, base = pr_revisions(pr, repository, request.pr_number)
            if request.expected_head_sha is not None and request.expected_head_sha != head:
                raise HTTPException(409, "PR identity or exact revision could not be established")
            scope = PRScope(owner_id=access["owner_id"], organization_id=access["organization_id"], project_id=request.project_id,
                            repository=repository, pr_number=request.pr_number, head_sha=head, base_sha=base)
            files = await self.api.client.get_pr_files(owner, repo, request.pr_number)
            if not isinstance(files, list):
                raise HTTPException(409, "Changed-file metadata is unavailable")
            limitations = []
            if pr.get("changed_files") != len(files) or len(files) > MAX_FILES:
                limitations.append("CHANGED_FILE_SCOPE_BOUNDED_OR_INCOMPLETE")
            references, observations = [], []
            for row in files[:MAX_FILES]:
                path = row.get("filename") if isinstance(row, dict) else None
                if not isinstance(path, str) or row.get("status") == "removed" or not source_language(path):
                    limitations.append("UNSUPPORTED_OR_REMOVED_SOURCE")
                    continue
                try:
                    reference = GitHubFileEvidenceV1(kind="github_file", path=path, source_revision=head, content_sha256="0" * 64)
                    initial = await self.api.client.get_file(owner, repo, path, ref=head)
                    if (not isinstance(initial, dict) or type(initial.get("size")) is not int
                            or not 0 <= initial["size"] <= MAX_SOURCE_BYTES or not isinstance(initial.get("content"), str)
                            or len(initial["content"]) > MAX_SOURCE_BYTES * 2):
                        raise ValueError("Bounded source response required")
                    raw = base64.b64decode("".join(initial["content"].split()), validate=True)
                    if len(raw) != initial["size"]:
                        raise ValueError("Source size mismatch")
                    reference = reference.model_copy(update={"content_sha256": hashlib.sha256(raw).hexdigest()})
                    verified = await _file(self.api.client, owner, repo, reference)
                except (HTTPException, ValueError, TypeError, KeyError, AttributeError, httpx.HTTPError):
                    limitations.append("SOURCE_IDENTITY_OR_BYTES_UNAVAILABLE")
                    continue
                evidence = self.reference(scope, "STATIC_SOURCE", f"github://{repository}/{path}@{head}",
                                          verified["content_sha256"])
                references.append(evidence)
                discovery = await discover_sources({path: verified["content"].removeprefix("\ufeff")}, request.project_id, head)
                if discovery.status != "available":
                    limitations.append("STATIC_DISCOVERY_PARTIAL_OR_UNAVAILABLE")
                if discovery.status != "unavailable":
                    metric = "function_count" if discovery.status == "available" else "retained_function_count"
                    observations.append(self.observation(evidence, path, metric, len(discovery.functions)))
                observations.append(self.observation(evidence, path, "source_bytes", len(raw)))
                kinds = Counter(fact.kind for function in discovery.functions for fact in function.evidence)
                for kind, count in sorted(kinds.items())[:6]:
                    observations.append(self.observation(evidence, path, "static_structure_" + kind, count))
                if len(kinds) > 6:
                    limitations.append("STRUCTURAL_OBSERVATIONS_BOUNDED")
                for function in discovery.functions[:4]:
                    if len(function.qualified_name) > 800:
                        limitations.append("FUNCTION_IDENTITIES_BOUNDED")
                        continue
                    observations.append(self.observation(evidence, f"{path}:{function.line}",
                                                         "declared_function", function.qualified_name))
                if len(discovery.functions) > 4:
                    limitations.append("FUNCTION_IDENTITIES_BOUNDED")
            await self.ci_observations(scope, references, observations, limitations)
            latest = await self.api.client.get_pull_request(owner, repo, request.pr_number)
            if pr_revisions(latest, repository, request.pr_number) != (head, base):
                raise HTTPException(409, "PR revision moved during evidence collection")
            unique_limits = tuple(dict.fromkeys(limitations))
            body = {"scope": scope.model_dump(), "references": [ref.model_dump() for ref in references],
                    "observations": [row.model_dump() for row in observations], "limitations": unique_limits}
            return PRSnapshot(snapshot_id=canonical_digest(body), scope=scope, references=tuple(references),
                              observations=tuple(observations), limitations=unique_limits)

    @staticmethod
    def reference(scope, kind, source, digest):
        identity = canonical_digest([scope.model_dump(), kind, source, digest])
        return EvidenceReference(evidence_id=identity, scope=scope, kind=kind, source_reference=source, content_sha256=digest,
            method="github-blob-and-static-discovery-v1" if kind == "STATIC_SOURCE" else "scoped-ci-submission-v1",
            verification_scope="SOURCE_IDENTITY_AND_BYTES" if kind == "STATIC_SOURCE" else "LOCAL_RECORDED_SUBMISSION")

    @staticmethod
    def observation(reference, subject, metric, value):
        return Observation(observation_id=canonical_digest([reference.evidence_id, subject, metric, value]),
                           evidence_id=reference.evidence_id, subject=subject, metric=metric, value=value)

    async def ci_observations(self, scope, references, observations, limitations):
        repository = {"$regex": "^" + re.escape(scope.repository) + "$", "$options": "i"}
        configured = await col("qa_ci_configs").find_one({"project_id": scope.project_id, "repository": repository, "enabled": True})
        if not configured or any(key in configured and configured[key] != scope.organization_id for key in ("org_id", "organization_id")):
            limitations.append("REGISTERED_QA_SOURCE_UNAVAILABLE")
            return
        rows = await col("test_runs").find({"project_id": scope.project_id, "repository": repository,
            "commit_sha": scope.head_sha, "pr_number": scope.pr_number}, {"_id": 0}).sort("received_at", -1).limit(MAX_CI_RUNS + 1).to_list(MAX_CI_RUNS + 1)
        if len(rows) > MAX_CI_RUNS:
            limitations.append("CI_SUBMISSION_SCOPE_BOUNDED")
        for row in rows[:MAX_CI_RUNS]:
            counts = [row.get(key) for key in ("tests_run", "tests_passed", "tests_failed", "tests_skipped")]
            try:
                received = datetime.fromisoformat(row.get("received_at", ""))
                if (received.utcoffset() is None or row.get("source") != "github_actions"
                        or any(key in row and row[key] != scope.organization_id for key in ("org_id", "organization_id"))
                        or not re.fullmatch(r"[a-f0-9]{64}", row.get("id", ""))
                        or not isinstance(row.get("workflow_run_id"), str) or not row["workflow_run_id"]
                        or type(row.get("run_attempt")) is not int or row["run_attempt"] < 1
                        or any(type(value) is not int or not 0 <= value <= 1_000_000_000 for value in counts)
                        or counts[0] == 0 or sum(counts[1:]) != counts[0] or row.get("status") not in {"passed", "failed"}
                        or row["status"] == "passed" and counts[2] != 0):
                    raise ValueError("Incomplete revision-linked submission")
                digest = canonical_digest(row)
            except (ValueError, TypeError):
                limitations.append("INCOMPLETE_CI_SUBMISSION")
                continue
            reference = self.reference(scope, "CI_SUBMISSION", "test_runs/" + row["id"], digest)
            references.append(reference)
            for key, value in zip(("ci_reported_total_tests", "ci_reported_passed_tests", "ci_reported_failed_tests", "ci_reported_skipped_tests"), counts):
                observations.append(self.observation(reference, "test_runs/" + row["id"], key, value))
            limitations.append("CI_COUNTS_ARE_RECORDED_SUBMISSIONS_NOT_INDEPENDENT_EXECUTION_PROOF")
