"""Single-document Mongo CAS ledger. Server time and fencing guard every worker write."""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from bson import BSON
from pymongo import ReturnDocument, ReadPreference
from pymongo.errors import DuplicateKeyError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from core.database import col
from domain.models.performance_evidence import canonical_digest
from domain.models.pr_multi_agent import PRScope, PRSnapshot
from domain.models.pr_workflow_durable import WorkflowCheckpoint, WorkflowStepResult, DurablePRReport

MAX_ATTEMPTS = 3
LEASE_SECONDS = 90
JOB_VERSION = "pr-workflow-job-v1"
MAX_JOB_BYTES = 2_000_000
HEADER = {"_id": 1, "job_id": 1, "scope": 1, "request": 1, "status": 1, "generation": 1, "attempts": 1}
ACTIVE = ["PENDING", "RUNNING", "RETRY_WAIT"]
STATUSES = {"PENDING", "RUNNING", "RETRY_WAIT", "FAILED", "FINALIZED", "CANCELLED"}


class LeaseLost(RuntimeError):
    """The caller no longer owns this execution; its outputs must be discarded."""


class InvalidWorkflowRecord(ValueError):
    """Stored evidence/checkpoints failed version, scope or integrity validation."""


@dataclass(frozen=True)
class WorkflowLease:
    job_id: str
    worker_id: str
    generation: int
    scope: PRScope


def parse(model, data):
    return model.model_validate_json(json.dumps(data, allow_nan=False))


def snapshot_digest(snapshot):
    return canonical_digest({key: snapshot.model_dump(mode="json")[key]
                             for key in ("scope", "references", "observations", "limitations")})


class PRWorkflowRepository:
    def __init__(self, collection=None, *, clock=None):
        source = collection if collection is not None else col("pr_multi_agent_jobs")
        # Keep acknowledged reports/fencing generations across journal recovery and replica failover.
        # These concerns apply only to this new ledger, never to existing application collections.
        self.collection = source.with_options(write_concern=WriteConcern(w="majority", j=True, wtimeout=5000),
                                              read_concern=ReadConcern("majority"), read_preference=ReadPreference.PRIMARY)
        # Trusted deterministic test seam only. Production leases use MongoDB $$NOW.
        self.clock = clock

    def now(self):
        return self.clock() if self.clock else "$$NOW"

    def later(self, seconds):
        return self.clock() + timedelta(seconds=seconds) if self.clock else {"$add": ["$$NOW", seconds * 1000]}

    async def ensure_indexes(self):
        # _id is the unique, actor/tenant/revision-bound idempotency key.
        await self.collection.create_index([("status", 1), ("next_attempt_at", 1)])
        await self.collection.create_index([("status", 1), ("lease_expires_at", 1)])
        await self.collection.create_index([("scope.owner_id", 1), ("scope.organization_id", 1),
            ("scope.project_id", 1), ("scope.pr_number", 1), ("scope.head_sha", 1)])

    @staticmethod
    def identity(scope):
        return canonical_digest([JOB_VERSION, "pr_multi_agent_v1", scope.model_dump(mode="json")])

    async def create(self, request, snapshot):
        if snapshot_digest(snapshot) != snapshot.snapshot_id:
            raise InvalidWorkflowRecord("Snapshot digest mismatch")
        key = self.identity(snapshot.scope)
        document = {"_id": key, "job_id": key, "schema_version": JOB_VERSION, "workflow_type": "pr_multi_agent_v1",
            "scope": snapshot.scope.model_dump(mode="json"), "request": request.model_dump(mode="json"),
            "snapshot": snapshot.model_dump(mode="json"), "snapshot_id": snapshot.snapshot_id,
            "status": "PENDING", "generation": 0, "attempts": 0, "step_results": [],
            "checkpoint": WorkflowCheckpoint(snapshot_id=snapshot.snapshot_id).model_dump(mode="json"),
            "created_at": datetime.now(timezone.utc).isoformat()}
        if len(BSON.encode(document)) > MAX_JOB_BYTES:
            raise InvalidWorkflowRecord("Workflow document exceeds its bound")
        try:
            await self.collection.insert_one(document)
        except DuplicateKeyError:
            pass
        return key

    async def header(self, key):
        return await self.collection.find_one({"_id": key, "schema_version": JOB_VERSION}, HEADER)

    def recoverable(self):
        return {"schema_version": JOB_VERSION, "attempts": {"$lt": MAX_ATTEMPTS}, "$or": [
            {"status": "PENDING"},
            {"status": "RETRY_WAIT", "$expr": {"$lte": ["$next_attempt_at", self.now()]}},
            {"status": "RUNNING", "$expr": {"$lte": ["$lease_expires_at", self.now()]}},
        ]}

    async def active_counts(self, owner_id, organization_id):
        """AI-02: active jobs per requester, per organisation and in total (quota checks)."""
        active = {"schema_version": JOB_VERSION, "status": {"$in": ACTIVE}}
        return {"actor": await self.collection.count_documents({**active, "scope.owner_id": owner_id}),
                "organization": await self.collection.count_documents({**active, "scope.organization_id": organization_id}),
                "total": await self.collection.count_documents(active)}

    async def cancel(self, key, actor_id):
        """AI-02: stop a queued or running job.

        Raising the generation fences the current worker: its lease guard
        (status RUNNING + same generation) stops matching, so its next
        heartbeat, step commit or publish fails with LeaseLost and nothing it
        produces afterwards is stored.
        """
        row = await self.collection.find_one_and_update(
            {"_id": key, "schema_version": JOB_VERSION, "status": {"$in": ACTIVE}},
            [{"$set": {"status": "CANCELLED", "generation": {"$add": ["$generation", 1]},
                       "cancelled_by": {"$literal": actor_id}, "cancelled_at": self.now(),
                       "last_error": {"category": "CANCELLED", "code": "CANCELLED_BY_REQUESTER"}}}],
            projection=HEADER, return_document=ReturnDocument.AFTER)
        return row is not None

    async def reap_exhausted(self):
        await self.collection.update_many({"schema_version": JOB_VERSION, "status": "RUNNING",
            "attempts": {"$gte": MAX_ATTEMPTS}, "$expr": {"$lte": ["$lease_expires_at", self.now()]}}, [{"$set": {
                "status": "FAILED", "generation": {"$add": ["$generation", 1]},
                "last_error": {"category": "EXHAUSTED", "code": "RETRY_EXHAUSTED"}}}])

    async def ready_ids(self, limit=20):
        if type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("Recovery batches must contain 1..20 jobs")
        await self.reap_exhausted()
        rows = await self.collection.find(self.recoverable(), {"_id": 1}).sort("created_at", 1).limit(limit).to_list(limit)
        return [row["_id"] for row in rows]

    async def claim(self, key, worker_id):
        await self.reap_exhausted()
        header = await self.collection.find_one_and_update({"_id": key, **self.recoverable()}, [{"$set": {
            "status": "RUNNING", "worker_id": {"$literal": worker_id}, "lease_expires_at": self.later(LEASE_SECONDS),
            "generation": {"$add": ["$generation", 1]}, "attempts": {"$add": ["$attempts", 1]},
        }}], projection=HEADER, return_document=ReturnDocument.AFTER)
        if header is None:
            return None
        return WorkflowLease(key, worker_id, header["generation"], parse(PRScope, header["scope"]))

    def guard(self, lease):
        return {"_id": lease.job_id, "schema_version": JOB_VERSION, "status": "RUNNING",
            "worker_id": lease.worker_id, "generation": lease.generation,
            **{"scope." + key: value for key, value in lease.scope.model_dump(mode="json").items()},
            "$expr": {"$gt": ["$lease_expires_at", self.now()]}}

    async def renew(self, lease):
        result = await self.collection.update_one(self.guard(lease), [{"$set": {"lease_expires_at": self.later(LEASE_SECONDS)}}])
        return result.matched_count == 1

    async def read_owned(self, lease):
        row = await self.collection.find_one(self.guard(lease))
        if row is None:
            raise LeaseLost("Workflow lease lost")
        self.validate(row)
        return row

    @staticmethod
    def validate(row):
        try:
            if row["schema_version"] != JOB_VERSION or len(BSON.encode(row)) > MAX_JOB_BYTES:
                raise ValueError("Unsupported job version or size")
            if (row.get("workflow_type") != "pr_multi_agent_v1"
                    or row["status"] not in STATUSES
                    or type(row["attempts"]) is not int or not 0 <= row["attempts"] <= MAX_ATTEMPTS
                    or type(row["generation"]) is not int or row["generation"] < row["attempts"]
                    or row["status"] == "FINALIZED" and "report" not in row):
                raise ValueError("Invalid workflow state")
            snapshot = parse(PRSnapshot, row["snapshot"])
            checkpoint = parse(WorkflowCheckpoint, row["checkpoint"])
            if (snapshot.scope.model_dump(mode="json") != row["scope"] or snapshot_digest(snapshot) != row["snapshot_id"]
                    or snapshot.snapshot_id != row["snapshot_id"] or checkpoint.snapshot_id != row["snapshot_id"]
                    or PRWorkflowRepository.identity(snapshot.scope) != row["_id"] or row["job_id"] != row["_id"]
                    or checkpoint.sequence != len(row["step_results"])):
                raise ValueError("Snapshot or checkpoint identity mismatch")
            outcomes = {}
            for index, raw in enumerate(row["step_results"], 1):
                step = parse(WorkflowStepResult, raw)
                if (step.sequence != index or step.snapshot_id != snapshot.snapshot_id
                        or step.content_sha256 != canonical_digest(step.outcome.model_dump(mode="json"))
                        or step.generation > row["generation"] or step.attempt > row["attempts"]):
                    raise ValueError("Step integrity mismatch")
                if step.advances_checkpoint:
                    if step.outcome.specialist in outcomes:
                        raise ValueError("Completed step must be immutable")
                    outcomes[step.outcome.specialist] = step.outcome
            if outcomes != checkpoint.outcomes:
                raise ValueError("Checkpoint does not match committed steps")
            if "report" in row:
                report = parse(DurablePRReport, row["report"])
                if (row["status"] != "FINALIZED" or report.job_id != row["_id"] or report.snapshot != snapshot
                        or report.scope != snapshot.scope or report.generation != row["generation"]
                        or list(checkpoint.outcomes.values()) != list(report.outcomes)
                        or report.status != row["analysis_status"]
                        or canonical_digest(row["report"]) != row["report_sha256"]):
                    raise ValueError("Final report integrity mismatch")
        except (ValueError, KeyError, TypeError) as error:
            raise InvalidWorkflowRecord("Workflow record failed integrity validation") from error

    async def append_step(self, lease, outcome, *, advances):
        row = await self.read_owned(lease)
        checkpoint = parse(WorkflowCheckpoint, row["checkpoint"])
        if outcome.specialist in checkpoint.outcomes:
            raise InvalidWorkflowRecord("Completed step cannot be overwritten")
        if outcome.specialist == "qa_analysis" and "code_analysis" not in checkpoint.outcomes:
            raise InvalidWorkflowRecord("QA requires a committed Code handoff")
        step = WorkflowStepResult(sequence=checkpoint.sequence + 1, generation=lease.generation, attempt=row["attempts"],
            snapshot_id=row["snapshot_id"], outcome=outcome, content_sha256=canonical_digest(outcome.model_dump(mode="json")),
            advances_checkpoint=advances)
        outcomes = dict(checkpoint.outcomes)
        if advances:
            outcomes[outcome.specialist] = outcome
        next_checkpoint = WorkflowCheckpoint(sequence=step.sequence, snapshot_id=row["snapshot_id"], outcomes=outcomes)
        step_data, next_data = step.model_dump(mode="json"), next_checkpoint.model_dump(mode="json")
        candidate = {**row, "step_results": [*row["step_results"], step_data], "checkpoint": next_data}
        if len(BSON.encode(candidate)) > MAX_JOB_BYTES:
            raise InvalidWorkflowRecord("Workflow document exceeds its bound")
        result = await self.collection.update_one({**self.guard(lease), "checkpoint.sequence": checkpoint.sequence},
            {"$push": {"step_results": step_data}, "$set": {"checkpoint": next_data}})
        if result.matched_count != 1:
            raise LeaseLost("Lease or checkpoint changed before step commit")

    async def fail(self, lease, category, code, *, retry=False):
        # Failure handling must not read sensitive payload after permission revocation.
        row = await self.collection.find_one(self.guard(lease), {"attempts": 1})
        if row is None:
            raise LeaseLost("Lease lost before failure classification")
        retry = retry and row["attempts"] < MAX_ATTEMPTS
        result = await self.collection.update_one(self.guard(lease), [{"$set": {
            "status": "RETRY_WAIT" if retry else "FAILED", "next_attempt_at": self.later(2 ** row["attempts"]),
            "last_error": {"category": category, "code": code},
        }}])
        if result.matched_count != 1:
            raise LeaseLost("Lease lost before failure commit")

    async def publish(self, lease, report):
        row = await self.read_owned(lease)
        if set(row["checkpoint"]["outcomes"]) != {"code_analysis", "qa_analysis"}:
            raise InvalidWorkflowRecord("Cannot publish an incomplete workflow")
        data = report.model_dump(mode="json")
        if (report.job_id != lease.job_id or report.generation != lease.generation or report.scope != lease.scope
                or data["snapshot"] != row["snapshot"]
                or [item.model_dump(mode="json") for item in report.outcomes] != list(row["checkpoint"]["outcomes"].values())):
            raise InvalidWorkflowRecord("Report does not match the committed workflow")
        if len(BSON.encode({**row, "report": data})) > MAX_JOB_BYTES:
            raise InvalidWorkflowRecord("Workflow document exceeds its bound")
        result = await self.collection.update_one({**self.guard(lease), "report": {"$exists": False},
            "checkpoint.sequence": row["checkpoint"]["sequence"]}, {"$set": {
                "status": "FINALIZED", "analysis_status": report.status, "report": data,
                "report_sha256": canonical_digest(data)}})
        if result.matched_count != 1:
            raise LeaseLost("Lease lost or final report already committed")
