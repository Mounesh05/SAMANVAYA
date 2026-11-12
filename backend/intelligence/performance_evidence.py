"""Deterministic evidence normalization, never a volume-to-performance calculator."""

import re
from collections import defaultdict
from datetime import datetime
from itertools import islice
from types import MappingProxyType

from pydantic import ValidationError

from domain.models.performance_evidence import (
    ConnectorObservation, DimensionEvidence, EvidenceAttribution, EvidenceChange, EvidenceFacts,
    EvidenceRecord, EvidenceScope, EvidenceSnapshot, utc_time, canonical_digest as digest,
)
from intelligence.performance_registry import DIMENSIONS

# No approved calibration was supplied. Source/request/LLM flags cannot register rules.
MEASUREMENT_RULES = MappingProxyType({})
_ORIGINS = {"tasks": "task", "stories": "story", "pull_requests": "pr", "test_runs": "test_run",
            "qa_defects": "defect", "code_quality_runs": "analysis", "algorithm_benchmark_runs": "benchmark",
            "commits": "commit", "code_reviews": "review", "incidents": "incident"}


def source_identity(scope: EvidenceScope, kind: str, external_id, repository=None) -> str:
    return digest([scope.organization_id, scope.project_id, repository, kind, str(external_id)])


def parse_time(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise ValueError("Missing explicit timestamp")
    return utc_time(value)


def _sealed(record, **changes):
    value = EvidenceRecord.model_validate({**record.model_dump(), **changes})
    checksum = digest(value.model_dump(mode="json", exclude={"content_digest"}))
    return EvidenceRecord.model_validate({**value.model_dump(), "content_digest": checksum})


def _normalize(scope, row, captured_at):
    reasons, state = [], "VERIFIED_SNAPSHOT"

    def flag(reason, severity="UNVERIFIED"):
        nonlocal state
        reasons.append(reason)
        priority = {"VERIFIED_SNAPSHOT": 0, "UNVERIFIED": 1, "STALE": 2, "DISPUTED": 3, "REJECTED": 4}
        if priority[severity] > priority[state]:
            state = severity

    origin = row.get("origin")
    if origin not in _ORIGINS:
        raise ValueError("Unknown evidence adapter")
    kind = _ORIGINS[origin]
    if row.get("kind") != kind:
        flag("SOURCE_KIND_MISMATCH", "REJECTED")
    external_id = row.get("external_id")
    if type(external_id) not in (str, int) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", str(external_id)):
        external_id = "missing"
        flag("MISSING_OR_INVALID_SOURCE_ID", "REJECTED")
    repository = row.get("repository")
    github_kind = kind in {"pr", "commit", "review", "test_run", "analysis", "benchmark"}
    if (row.get("organization_id") != scope.organization_id or row.get("project_id") != scope.project_id
            or (github_kind and (not scope.repository or repository != scope.repository))):
        flag("SOURCE_SCOPE_MISMATCH", "REJECTED")
    occurred = None
    try:
        occurred = parse_time(row.get("occurred_at"))
        if not scope.period_start <= occurred < scope.period_end or occurred > captured_at:
            flag("SOURCE_OUTSIDE_PERIOD", "REJECTED")
    except (ValueError, TypeError, OverflowError):
        flag("MISSING_OR_INVALID_OCCURRENCE", "REJECTED")
    revision = row.get("source_revision")
    if isinstance(revision, str) and re.fullmatch(r"[a-fA-F0-9]{7,64}", revision):
        revision = revision.lower()
    else:
        try:
            revision = parse_time(revision).isoformat()
        except (ValueError, TypeError, OverflowError):
            revision = None
            flag("SOURCE_REVISION_UNKNOWN")
    basis = row.get("attribution_basis")
    if basis not in {"DIRECT_EMPLOYEE_ID", "EXACT_GITHUB_MAPPING", "PR_REVISION_LINK"}:
        basis = "UNKNOWN"
        flag("ATTRIBUTION_BASIS_UNKNOWN")
    if row.get("actor_id") is None:
        flag("IDENTITY_MAPPING_MISSING")
    elif row.get("actor_id") != scope.employee_id:
        flag("SUBJECT_ATTRIBUTION_MISMATCH", "REJECTED")
    shared = row.get("shared")
    if type(shared) is not bool:
        shared = None
    if shared is not False:
        flag("SHARED_CONTRIBUTION_UNRESOLVED")
    attribution = EvidenceAttribution(basis=basis, shared=shared)
    raw_facts = row.get("facts") if isinstance(row.get("facts"), dict) else {}
    try:
        facts = EvidenceFacts.model_validate({key: value for key, value in raw_facts.items()
                                             if key in EvidenceFacts.model_fields})
    except ValidationError:
        facts = EvidenceFacts()
        flag("INVALID_SOURCE_FACTS", "REJECTED")
    if kind == "pr" and facts.status != "merged":
        flag("UNMERGED_WORK_IS_CONTEXT_ONLY")
    if revision is not None and facts.head_sha is not None and revision != facts.head_sha.lower():
        flag("DECLARED_REVISION_AND_FACT_HEAD_DISAGREE", "STALE")
    if kind in {"task", "story", "defect"} and facts.status not in {"done", "completed", "resolved", "closed"}:
        flag("DEFECT_RESOLUTION_REQUIRES_RETEST" if kind == "defect" and facts.status in {"fixed", "ready_for_retest"}
             else "IN_PROGRESS_WORK_IS_CONTEXT_ONLY")
    if kind == "test_run" and (facts.tests_run is None or facts.tests_run == facts.tests_skipped
                                or facts.status in {"error", "cancelled", "skipped", "unknown"}):
        flag("TEST_EXECUTION_INCOMPLETE")
    if kind == "analysis":
        flag("FINDING_BASELINE_OWNERSHIP_AND_EXEMPTIONS_REQUIRE_REVIEW")
    if kind == "benchmark":
        flag("CONTRACT_CORRECTNESS_WORKLOAD_AND_ENVIRONMENT_REQUIRE_REVIEW")
    if row.get("current_head_sha") is not None and revision != row["current_head_sha"]:
        flag("SOURCE_HEAD_CHANGED", "STALE")
    if row.get("deleted") is True:
        flag("SOURCE_DELETED", "REJECTED")
    if row.get("disputed") is True:
        flag("SOURCE_DISPUTED", "DISPUTED")
    parent = row.get("parent_source_id")
    if not isinstance(parent, str) or not re.fullmatch(r"[0-9a-f]{64}", parent):
        parent = None
    identity = digest([row.get("organization_id"), row.get("project_id"),
                       repository if github_kind else None, kind, str(external_id)])
    record = EvidenceRecord(source_id=identity,
        content_digest="0" * 64, origin=origin, kind=kind, source_revision=revision, occurred_at=occurred,
        scope_basis=row.get("scope_basis", "DIRECT_ORG"),
        parent_source_id=parent, state=state, attribution=attribution, facts=facts,
        limitations=tuple(sorted(set(reasons))))
    return _sealed(record)


def build_evidence_snapshot(scope, candidates, *, captured_at, connectors=()):
    scope = EvidenceScope.model_validate(scope)
    captured_at = parse_time(captured_at)
    rows = list(islice(candidates, 2001))
    if len(rows) > 2000:
        raise ValueError("Evidence preview exceeds its bounded input size")
    grouped = defaultdict(dict)
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("An evidence adapter returned an invalid record")
        record = _normalize(scope, row, captured_at)
        grouped[record.source_id][record.content_digest] = record
    records = []
    for group in grouped.values():
        for record in group.values():
            if len(group) > 1:
                record = _sealed(record, state="REJECTED" if record.state == "REJECTED" else "DISPUTED",
                    limitations=tuple(sorted(set((*record.limitations, "CONFLICTING_SOURCE_OBSERVATIONS")))))
            records.append(record)
    records.sort(key=lambda r: (r.source_id, r.content_digest))
    dimensions = tuple(DimensionEvidence(dimension_id=key,
        verified_source_refs=tuple(sorted({r.source_id for r in records
            if r.state == "VERIFIED_SNAPSHOT" and r.kind in definition.evidence_kinds})))
        for key, definition in DIMENSIONS.items())
    status = ("UNDER_REVIEW" if any(r.state == "DISPUTED" for r in records) else
              "POLICY_PENDING" if any(r.state == "VERIFIED_SNAPSHOT" for r in records) else "INSUFFICIENT_EVIDENCE")
    return EvidenceSnapshot(scope=scope, captured_at=captured_at, records=tuple(records),
        connectors=tuple(sorted((ConnectorObservation.model_validate(c) for c in connectors), key=lambda c: c.origin)),
        dimensions=dimensions, status=status)


def evidence_digest(snapshot) -> str:
    value = EvidenceSnapshot.model_validate(snapshot)
    return digest(value.model_dump(mode="json"))


def verify_evidence_snapshot(payload, expected_digest):
    snapshot = EvidenceSnapshot.model_validate(payload)
    if evidence_digest(snapshot) != expected_digest:
        raise ValueError("Evidence snapshot digest does not match the recorded reference")
    for record in snapshot.records:
        if _sealed(record).content_digest != record.content_digest:
            raise ValueError("An evidence record digest is inconsistent")
    return snapshot


def compare_evidence_snapshots(previous, current) -> tuple[EvidenceChange, ...]:
    before = EvidenceSnapshot.model_validate(previous)
    after = EvidenceSnapshot.model_validate(current)
    if before.scope != after.scope:
        raise ValueError("Only the same subject, organization, project and period can be compared")
    old, new = defaultdict(set), defaultdict(set)
    for record in before.records:
        old[record.source_id].add(record.content_digest)
    for record in after.records:
        new[record.source_id].add(record.content_digest)
    return tuple(EvidenceChange(source_id=key, change="ADDED" if key not in old else "MISSING" if key not in new
        else "UNCHANGED" if old[key] == new[key] else "CHANGED", previous_digests=tuple(sorted(old[key])),
        current_digests=tuple(sorted(new[key]))) for key in sorted(old.keys() | new.keys()))
