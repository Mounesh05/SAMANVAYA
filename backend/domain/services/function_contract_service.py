"""Immutable functional contracts with independent, project-authorized approval."""

import copy
import uuid
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from core.database import col
from domain.schemas.behavioral_compatibility import ContractProposal
from intelligence.algorithms.decision import fingerprint

CONTENT_FIELDS = ("project_id", "contract", "datasets", "required_dataset_ids", "requirements", "scope_description", "function_bindings", "validator_requirement")


def contract_content(document):
    return {key: copy.deepcopy(document[key]) for key in (*CONTENT_FIELDS, "automatic_scope") if key in document}


def actor(user):
    return user.get("employee_id") or user.get("sub")


class FunctionContractService:
    def __init__(self, collection=None, runs=None):
        self._collection, self._runs = collection, runs

    @property
    def collection(self):
        return self._collection if self._collection is not None else col("algorithm_function_contracts")

    @property
    def runs(self):
        return self._runs if self._runs is not None else col("code_quality_runs")

    async def get(self, contract_id):
        return await self.collection.find_one({"contract_id": contract_id}, {"_id": 0})

    async def propose(self, body, user):
        if not actor(user) or not user.get("org_id"):
            raise ValueError("An authenticated project identity is required")
        content = ContractProposal.model_validate(body).model_dump()
        if content.get("automatic_scope") is None:
            content.pop("automatic_scope", None)
        content["contract"].setdefault("comparison", {"mode": "exact", "version": "1"})
        for binding in content["function_bindings"]:
            run = await self.runs.find_one({"run_id": binding["run_id"], "repository_id": content["project_id"]})
            if not run or not any(f["function_id"] == binding["function_id"] for f in run.get("function_discovery", {}).get("functions", [])):
                raise ValueError("Function binding is not available in this project's discovery evidence")
        await self.collection.create_index([("project_id", 1), ("contract.name", 1), ("contract.version", 1)], unique=True)
        document = {**content, "contract_id": "FCT-" + uuid.uuid4().hex[:16].upper(),
                    "status": "PROPOSED", "payload_fingerprint": fingerprint(content),
                    "proposed_by": actor(user), "organization_id": user.get("org_id"),
                    "created_at": datetime.now(timezone.utc).isoformat(), "approval": None}
        try:
            await self.collection.insert_one(copy.deepcopy(document))
        except DuplicateKeyError as error:
            raise ValueError("Contract name/version already exists in this project; propose a new version") from error
        return document

    async def approve(self, document, approval, user):
        role = str(user.get("role", user.get("organizational_role", ""))).upper()
        if role not in {"LEAD", "PM", "CEO"}:  # CR-008: no admin bypass
            raise PermissionError("Contract approval requires an authorized project lead, PM or CEO")
        if not actor(user) or actor(user) == document["proposed_by"]:
            raise PermissionError("An independent reviewer must approve the proposed contract")
        if not user.get("org_id") or user["org_id"] != document["organization_id"]:
            raise PermissionError("Contract approval must remain in its organization")
        content = contract_content(document)
        if document["status"] != "PROPOSED" or fingerprint(content) != approval["expected_fingerprint"] or document["payload_fingerprint"] != approval["expected_fingerprint"]:
            raise ValueError("Contract is already approved or the reviewed content fingerprint changed")
        if content["contract"]["correctness"] != "expected":
            raise ValueError("Approved compatibility contracts require explicit expected-output validation")
        if not set(content["required_dataset_ids"]) <= {d["id"] for d in content["datasets"]}:
            raise ValueError("Approval requires every required check to have an explicit valid dataset")
        review = {**approval, "approved_by": actor(user), "organization_id": user.get("org_id"),
                  "approved_at": datetime.now(timezone.utc).isoformat(),
                  "authority_basis": "Independent authorized project review of explicit contract and finite validation scope"}
        outcome = await self.collection.update_one(
            {"contract_id": document["contract_id"], "status": "PROPOSED", "payload_fingerprint": approval["expected_fingerprint"]},
            {"$set": {"status": "APPROVED", "approval": review}},
        )
        if outcome.matched_count != 1:
            raise ValueError("Concurrent approval changed this proposal")
        return await self.get(document["contract_id"])

    async def resolve(self, project_id, contract_ids):
        refs = ["algorithm_function_contracts/" + cid for cid in contract_ids]
        resolution = {"status": "MISSING", "contract_ids": contract_ids, "evidence_refs": refs,
                      "fingerprint": None, "snapshot": None, "approval": None, "validator_available": False}
        if not contract_ids:
            return resolution
        records = [await self.collection.find_one({"contract_id": cid, "project_id": project_id}, {"_id": 0}) for cid in contract_ids]
        present = [doc for doc in records if doc]
        if not present:
            return resolution
        project = await self.collection.database["projects"].find_one({"id": project_id}, {"org_id": 1})
        if project and any(doc.get("organization_id") != project.get("org_id") for doc in present):
            resolution["status"] = "CONFLICTING"
            return resolution
        fingerprints = {fingerprint(contract_content(doc)) for doc in present}
        if len(present) != len(records) or len(fingerprints) != 1 or any(doc["payload_fingerprint"] not in fingerprints for doc in present):
            resolution["status"] = "CONFLICTING"
            return resolution
        document = present[0]
        approved = all(doc.get("status") == "APPROVED" and (doc.get("approval") or {}).get("scope_reviewed") is True
                       and doc["approval"].get("expected_fingerprint") == doc["payload_fingerprint"] for doc in present)
        resolution.update(status="APPROVED" if approved else "PROPOSED", fingerprint=document["payload_fingerprint"],
                          snapshot=contract_content(document), approval=document.get("approval"),
                          validator_available=document["validator_requirement"] == "expected_output")
        return resolution
