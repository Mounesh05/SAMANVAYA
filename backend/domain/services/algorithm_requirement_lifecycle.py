"""Immutable requirement review actions with independent authorization."""
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from core.permissions import Permission, get_user_permissions
from domain.services.function_contract_service import actor, contract_content
from intelligence.algorithms.decision import fingerprint
from intelligence.algorithms.requirements import source_content


class ReviewAction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    action: Literal["reject", "request_changes", "revoke"]
    expected_fingerprint: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=2000)


async def transition(collection, document, action, user, is_contract):
    action = ReviewAction.model_validate(action)
    if (Permission.APPROVE_ENGINEERING_CONTRACTS not in get_user_permissions(
            str(user.get("role", user.get("organizational_role", ""))).upper(), False, user.get("designation"))
            or not actor(user) or actor(user) == document.get("proposed_by")
            or not user.get("org_id") or user["org_id"] != document.get("organization_id")):
        raise PermissionError("Independent authorized review in the same organization is required")
    old = "APPROVED" if action.action == "revoke" else "PROPOSED"
    new = {"reject": "REJECTED", "request_changes": "CHANGES_REQUESTED", "revoke": "REVOKED"}[action.action]
    content = contract_content(document) if is_contract else source_content(document)
    if document.get("status") != old or fingerprint(content) != action.expected_fingerprint or document.get("payload_fingerprint") != action.expected_fingerprint:
        raise ValueError("Reviewed revision changed or no longer permits this action")
    key = "contract_id" if is_contract else "source_id"
    identity = {key: document[key], "project_id": document["project_id"], "organization_id": user["org_id"],
                "status": old, "payload_fingerprint": action.expected_fingerprint}
    audit = {"action": action.action, "previous_status": old, "status": new,
             "reviewed_by": actor(user), "organization_id": user["org_id"], "fingerprint": action.expected_fingerprint,
             "rationale": action.rationale, "reviewed_at": datetime.now(timezone.utc).isoformat()}
    result = await collection.update_one(identity, {"$set": {"status": new, "review_action": audit}})
    if result.matched_count != 1:
        raise ValueError("Concurrent review changed this revision")
    return await collection.find_one({key: document[key], "project_id": document["project_id"]}, {"_id": 0})
