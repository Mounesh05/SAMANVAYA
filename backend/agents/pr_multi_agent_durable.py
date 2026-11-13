"""Persist/replay the existing sequential graph's boundaries, without changing legacy dispatch."""

from datetime import datetime, timezone

from agents.pr_multi_agent import PRMultiAgentGraph
from domain.models.pr_multi_agent import PRSnapshot
from domain.models.pr_workflow_durable import WorkflowCheckpoint, DurablePRReport
from repositories.pr_workflow_repository import parse, MAX_ATTEMPTS


class RetryableInference(RuntimeError):
    def __init__(self, code):
        self.code = code


class DurablePRGraph(PRMultiAgentGraph):
    def __init__(self, manual, repository, lease):
        self.repository, self.lease = repository, lease
        super().__init__(manual)

    async def resolve(self, state):
        row = await self.repository.read_owned(self.lease)
        snapshot = parse(PRSnapshot, row["snapshot"])
        checkpoint = parse(WorkflowCheckpoint, row["checkpoint"])
        return {"snapshot": snapshot, "outcomes": dict(checkpoint.outcomes), "trace": ("resolve_evidence",)}

    async def specialist(self, state, specialist, source_kind, runner):
        await self.service.authorize_snapshot(state)
        row = await self.repository.read_owned(self.lease)
        if specialist in state["outcomes"]:
            return {"trace": (*state["trace"], specialist)}
        result = await super().specialist(state, specialist, source_kind, runner)
        outcome = result["outcomes"][specialist]
        retry = outcome.error_code in {"MODEL_TIMEOUT", "MODEL_UNAVAILABLE"} and row["attempts"] < MAX_ATTEMPTS
        # A response cannot commit under a lost/expired generation, even if cancellation was delayed.
        await self.service.authorize_snapshot(state)
        await self.repository.append_step(self.lease, outcome, advances=not retry)
        if retry:
            raise RetryableInference(outcome.error_code)
        return result

    async def finalize(self, state):
        result = await super().finalize(state)
        data = result["report"].model_dump(mode="json")
        data.update(schema_version="pr-multi-agent-report-v2", durable=True, job_id=self.lease.job_id,
                    generation=self.lease.generation, published_at=datetime.now(timezone.utc).isoformat())
        data["limitations"] = [item for item in data["limitations"] if item != "TASK2_INTERNAL_EPHEMERAL_EXECUTION_NO_DURABILITY"]
        report = parse(DurablePRReport, data)
        await self.service.authorize_snapshot(state)
        await self.repository.publish(self.lease, report)
        return result
