"""Predicate-level validation. Neither model prose nor source counts award points."""

import json
from types import MappingProxyType

from domain.models.performance_claims import ClaimProposal, ClaimValidation, ProposalPayload, ValidatedClaimFact
from intelligence.performance_evidence import verify_evidence_snapshot
from intelligence.performance_registry import DIMENSIONS

CLAIM_KINDS = MappingProxyType({
    "recorded_status": frozenset({"pr", "task", "story", "defect", "ci", "test_run"}),
    "recorded_test_outcome": frozenset({"ci", "test_run"}),
    "possible_regression_fixed": frozenset({"defect", "test_run", "pr"}),
    "possible_benchmark_improvement": frozenset({"benchmark"}),
    "possible_architecture_tradeoff": frozenset({"pr", "design_record", "analysis"}),
    "possible_mentoring_contribution": frozenset({"review", "human_observation", "design_record"}),
    "possible_substantive_review": frozenset({"review", "pr"}),
})


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON fields are not allowed")
        value[key] = item
    return value


def parse_proposals(response):
    if not isinstance(response, str) or len(response.encode("utf-8")) > 64000:
        raise ValueError("Model output exceeds the supported JSON budget")
    def invalid_constant(value):
        raise ValueError("Nonfinite JSON numbers are not permitted")
    return ProposalPayload.model_validate(json.loads(response, object_pairs_hook=_unique_object, parse_constant=invalid_constant))


def validate_claim(claim, snapshot, expected_digest):
    claim = ClaimProposal.model_validate(claim)
    snapshot = verify_evidence_snapshot(snapshot, expected_digest)
    records = {(r.source_id, r.content_digest): r for r in snapshot.records}
    referenced = [records.get((c.source_id, c.content_digest)) for c in claim.citations]
    def result(status, reason, fact=None):
        return ClaimValidation(claim_id=claim.claim_id, status=status, reasons=(reason,), fact=fact)
    if any(r is None for r in referenced):
        return result("REJECTED", "CITATION_NOT_IN_EXACT_SNAPSHOT")
    allowed = set(DIMENSIONS[claim.dimension_id].evidence_kinds) & CLAIM_KINDS[claim.claim_type]
    if any(r.kind not in allowed for r in referenced):
        return result("REJECTED", "SOURCE_KIND_OR_DIMENSION_DOES_NOT_SUPPORT_PREDICATE")
    if any(r.state in {"REJECTED", "STALE", "DISPUTED"} for r in referenced):
        return result("REJECTED", "SOURCE_INVALID_STALE_OR_DISPUTED")
    if claim.claim_type == "recorded_status":
        if any(r.facts.status != claim.expected_status for r in referenced):
            return result("REJECTED", "STATUS_PREDICATE_CONTRADICTED")
    elif claim.claim_type == "recorded_test_outcome":
        for r in referenced:
            f = r.facts
            if any(v is None for v in (f.tests_run, f.tests_passed, f.tests_failed, f.tests_skipped)):
                return result("NEEDS_REVIEW", "TEST_EXECUTION_NOT_ESTABLISHED")
            if (f.status == "failed" and not f.tests_failed) or (f.status == "skipped" and f.tests_run != f.tests_skipped):
                return result("NEEDS_REVIEW", "RUN_STATUS_AND_TEST_COUNTS_DO_NOT_ESTABLISH_A_SUCCESSFUL_EXECUTION")
            outcome = "NO_EXECUTED_TESTS" if f.tests_run == f.tests_skipped else "FAILED" if f.tests_failed else "PASSED"
            if ((f.tests_passed, f.tests_failed, f.tests_skipped) != (claim.tests_passed, claim.tests_failed, claim.tests_skipped)
                    or outcome != claim.test_outcome or f.status not in {"passed", "failed", "skipped"}):
                return result("REJECTED", "TEST_OUTCOME_PREDICATE_CONTRADICTED")
    else:
        return result("NEEDS_REVIEW", "SPECIALIZED_VALIDATOR_OR_QUALIFIED_INDEPENDENT_REVIEW_REQUIRED")
    if any(r.state != "VERIFIED_SNAPSHOT" for r in referenced):
        return result("NEEDS_REVIEW", "SOURCE_ATTRIBUTION_OR_VERIFICATION_INCOMPLETE")
    fact = ValidatedClaimFact(predicate=claim.claim_type, recorded_status=claim.expected_status,
        test_outcome=claim.test_outcome, tests_passed=claim.tests_passed, tests_failed=claim.tests_failed,
        tests_skipped=claim.tests_skipped, citations=claim.citations, snapshot_digest=expected_digest)
    return result("VALIDATED", "ONLY_TYPED_RECORDED_PREDICATE_VALIDATED_NOT_MODEL_INTERPRETATION", fact)


def prompt_contract():
    return {"schema": ProposalPayload.model_json_schema(),
        "dimensions": {key.value: {"source_kinds": [k.value for k in value.evidence_kinds]}
                       for key, value in DIMENSIONS.items()},
        "claim_source_kinds": {key: sorted(value) for key, value in CLAIM_KINDS.items()}}
