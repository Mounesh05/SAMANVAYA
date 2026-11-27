import pytest
from domain.services.algorithm_requirement_lifecycle import transition
from domain.services.function_contract_service import FunctionContractService
from test_behavioral_compatibility import AUTHOR, REVIEWER, proposal, approved

pytestmark = pytest.mark.anyio


async def test_revoke_preserves_approval_but_removes_authority(mock_db):
    contracts = FunctionContractService(mock_db.algorithm_function_contracts, mock_db.code_quality_runs)
    doc = await approved(contracts, proposal())
    action = {"action": "revoke", "expected_fingerprint": doc["payload_fingerprint"], "rationale": "Scope outdated"}
    changed = await transition(contracts.collection, doc, action, REVIEWER, True)
    assert changed["status"] == "REVOKED"
    assert changed["approval"] == doc["approval"]
    assert (await contracts.resolve("P1", [doc["contract_id"]]))["status"] != "APPROVED"


async def test_review_independence_and_stale_fingerprint(mock_db):
    contracts = FunctionContractService(mock_db.algorithm_function_contracts, mock_db.code_quality_runs)
    doc = await contracts.propose(proposal(), AUTHOR)
    action = {"action": "reject", "expected_fingerprint": doc["payload_fingerprint"], "rationale": "Incorrect scope"}
    with pytest.raises(PermissionError):
        await transition(contracts.collection, doc, action, AUTHOR, True)
    with pytest.raises(ValueError):
        await transition(contracts.collection, doc, {**action, "expected_fingerprint": "stale"}, REVIEWER, True)
    rejected = await transition(contracts.collection, doc, action, REVIEWER, True)
    assert rejected["status"] == "REJECTED"
    assert rejected["approval"] is None
