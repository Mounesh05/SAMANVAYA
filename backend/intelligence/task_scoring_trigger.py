"""
Task Scoring Trigger.
Automatically updates the employee's performance score upon task completion.

Workflow:
1. When a task status transitions to completed / done / closed.
2. Identifies the assignee employee ID and project/company context.
3. Automatically triggers multi-agent re-evaluation across all specialist dimensions
   (including the Meeting Agent which evaluates task delivery, completion rate, and velocity).
4. Persists the updated Agent Score (out of 80 marks), preserved Superior Score (out of 20 marks),
   and updated Final Score (out of 100 marks) directly into MongoDB.
"""

import asyncio
import calendar
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from core.database import col

logger = logging.getLogger("samanvaya.task_trigger")

COMPLETION_STATUSES = {"done", "completed", "closed", "resolved"}


def is_completion_status(status: Optional[str]) -> bool:
    """Check if status represents a completed task."""
    if not status:
        return False
    return str(status).strip().lower() in COMPLETION_STATUSES


async def execute_employee_score_update(
    employee_id: str,
    company_id: str = "ORG-001",
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
    period_label: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Directly recalculates and updates the multi-agent score for an employee.
    """
    from agents.supervisor import evaluate_employee

    now = datetime.now(timezone.utc)
    start_date = period_start or now.strftime("%Y-%m-01")
    _, last_day = calendar.monthrange(now.year, now.month)
    end_date = period_end or f"{now.year:04d}-{now.month:02d}-{last_day:02d}"
    p_label = period_label or now.strftime("%Y-%m")

    logger.info(
        "[TASK-TRIGGER] Re-evaluating score for employee %s on task completion (period: %s)",
        employee_id, p_label
    )

    try:
        result = await evaluate_employee(
            employee_id=employee_id,
            start_date=start_date,
            end_date=end_date,
            company_id=company_id,
            evaluator_id="system-task-completion-trigger",
            period_label=p_label,
            skip_llm=True,  # Fast deterministic multi-agent update
        )
        logger.info(
            "[TASK-TRIGGER] Completed score update for %s: Overall=%s, AgentScore=%s/80, FinalScore=%s/100",
            employee_id,
            result.get("overall_score"),
            result.get("agent_score_marks"),
            result.get("final_score"),
        )
        return result
    except Exception as exc:
        logger.error("[TASK-TRIGGER] Error updating score for employee %s: %s", employee_id, exc)
        return None


async def on_task_completed(
    task_id: str,
    assignee_id: Optional[str] = None,
    company_id: Optional[str] = None,
    run_in_background: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Hook called when a task is completed.
    Stamps completion time and initiates employee score recalculation.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Fetch task document to determine assignee and timestamps
    task_doc = await col("tasks").find_one({"$or": [{"id": task_id}, {"_id": task_id}]})
    if not task_doc:
        logger.warning("[TASK-TRIGGER] Task %s not found in database", task_id)
        return None

    # 2. Stamp completed_at if missing
    if not task_doc.get("completed_at"):
        await col("tasks").update_one(
            {"$or": [{"id": task_id}, {"_id": task_id}]},
            {"$set": {"completed_at": now_iso}}
        )

    # 3. Resolve assignee employee ID
    target_employee_id = (
        assignee_id
        or task_doc.get("assignee_id")
        or task_doc.get("assignee")
    )

    if not target_employee_id:
        logger.info("[TASK-TRIGGER] Task %s has no assignee; skipping score recalculation", task_id)
        return None

_background_tasks = set()


def _track_bg_task(coro) -> asyncio.Task:
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def wait_for_pending_triggers():
    """Wait for all running background score recalculations to finish (useful in tests and shutdown)."""
    if _background_tasks:
        await asyncio.gather(*list(_background_tasks), return_exceptions=True)


async def on_task_completed(
    task_id: str,
    assignee_id: Optional[str] = None,
    company_id: Optional[str] = None,
    run_in_background: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Hook called when a task is completed.
    Stamps completion time and initiates employee score recalculation.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Fetch task document to determine assignee and timestamps
    task_doc = await col("tasks").find_one({"$or": [{"id": task_id}, {"_id": task_id}]})
    if not task_doc:
        logger.warning("[TASK-TRIGGER] Task %s not found in database", task_id)
        return None

    # 2. Stamp completed_at if missing
    if not task_doc.get("completed_at"):
        await col("tasks").update_one(
            {"$or": [{"id": task_id}, {"_id": task_id}]},
            {"$set": {"completed_at": now_iso}}
        )

    # 3. Resolve assignee employee ID
    target_employee_id = (
        assignee_id
        or task_doc.get("assignee_id")
        or task_doc.get("assignee")
    )

    if not target_employee_id:
        logger.info("[TASK-TRIGGER] Task %s has no assignee; skipping score recalculation", task_id)
        return None

    target_company = company_id or task_doc.get("company_id") or "ORG-001"

    if run_in_background:
        _track_bg_task(
            execute_employee_score_update(
                employee_id=target_employee_id,
                company_id=target_company,
            )
        )
        return {
            "status": "score_update_queued",
            "task_id": task_id,
            "employee_id": target_employee_id,
        }
    else:
        return await execute_employee_score_update(
            employee_id=target_employee_id,
            company_id=target_company,
        )
