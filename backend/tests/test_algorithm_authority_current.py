"""The reviewed-contract guard on benchmark execution (8b56018), for PR automation runs."""
from types import SimpleNamespace

import pytest

from domain.services.algorithm_benchmark_service import AlgorithmBenchmarkService
from intelligence.algorithms.decision import fingerprint

SNAPSHOT = {"contract": {"kind": "sort"}, "datasets": [{"id": "D1", "input": [3, 1]}], "required_dataset_ids": ["D1"]}


def _service(snapshot, status="APPROVED"):
    async def resolve(project_id, ids):
        return {"status": status, "validator_available": True, "fingerprint": "payload-fp", "snapshot": snapshot}
    return SimpleNamespace(requirements=SimpleNamespace(contracts=SimpleNamespace(resolve=resolve)))


def _document(applied):
    return {"project_id": "P1", "request": {"contract": SNAPSHOT["contract"], "datasets": SNAPSHOT["datasets"],
                                            "requirement_context": {"contract_ids": ["FC-1"]}},
            "pr_automation": {"contract_id": "FC-1", "contract_fingerprint": fingerprint({**applied, "contract_id": "FC-1"})}}


@pytest.mark.anyio
async def test_pr_automation_benchmark_with_the_applied_contract_is_authorised():
    assert await AlgorithmBenchmarkService.authority_current(_service(SNAPSHOT), _document(SNAPSHOT))


@pytest.mark.anyio
@pytest.mark.parametrize("current,status", [
    ({**SNAPSHOT, "required_dataset_ids": []}, "APPROVED"),  # the reviewed contract changed
    (SNAPSHOT, "PROPOSED"),                                     # approval withdrawn
])
async def test_pr_automation_benchmark_is_refused_after_the_contract_changes(current, status):
    assert not await AlgorithmBenchmarkService.authority_current(_service(current, status), _document(SNAPSHOT))
