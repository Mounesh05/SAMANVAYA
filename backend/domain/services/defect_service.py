"""
Defect Management Service.
Automatically tracks bugs detected by GitHub Actions test failures,
links them to responsible developer tasks, notifies assignees, and clears them on retest.
"""

import uuid
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from core.database import col
from domain.services.notification_service import NotificationService
from domain.services.realtime_service import broadcaster

logger = logging.getLogger("samanvaya.defects")


class DefectService:
    """Manages automated defects created from QA test failures."""

    def __init__(self):
        self.notification_service = NotificationService()

    async def create_or_update_defect(
        self,
        title: str,
        workflow_run_id: str,
        commit_sha: str,
        qa_task_id: str,
        linked_dev_task_id: Optional[str] = None,
        responsible_developer_id: Optional[str] = None,
        failed_tests: Optional[List[Dict[str, Any]]] = None,
        company_id: Optional[str] = "ORG-001",
    ) -> Dict[str, Any]:
        """Creates or updates a defect record from automated test failures."""
        now = datetime.now(timezone.utc).isoformat()
        
        # Check if defect for this workflow run already exists
        existing = await col("defects").find_one({
            "workflow_run_id": str(workflow_run_id),
            "commit_sha": commit_sha,
        })
        
        if existing:
            await col("defects").update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "failed_tests": failed_tests or [],
                    "updated_at": now,
                    "status": "open",
                }}
            )
            return existing

        defect_id = f"DEF-{uuid.uuid4().hex[:8].upper()}"
        doc = {
            "id": defect_id,
            "title": title,
            "workflow_run_id": str(workflow_run_id),
            "commit_sha": commit_sha,
            "qa_task_id": qa_task_id,
            "linked_dev_task_id": linked_dev_task_id,
            "responsible_developer_id": responsible_developer_id,
            "failed_tests": failed_tests or [],
            "severity": "high",
            "status": "open",
            "company_id": company_id,
            "created_at": now,
            "updated_at": now,
        }
        await col("defects").insert_one(doc)
        logger.info("[DEFECT] Created defect %s linked to dev task %s", defect_id, linked_dev_task_id)

        # Notify responsible developer
        if responsible_developer_id:
            await self.notification_service.notify(
                user_id=responsible_developer_id,
                notification_type="qa_defect_opened",
                title=f"QA Test Failure ({defect_id})",
                body=f"Automated test failure on commit {commit_sha[:7]}: {title}. Please review and push a fix.",
                link=f"/defects/{defect_id}",
            )

        # Broadcast real-time event
        await broadcaster.broadcast("defect_created", doc)
        return doc

    async def resolve_defects_for_task(self, dev_task_id: str, qa_task_id: str):
        """Resolves open defects when retests pass."""
        now = datetime.now(timezone.utc).isoformat()
        res = await col("defects").update_many(
            {
                "$or": [{"linked_dev_task_id": dev_task_id}, {"qa_task_id": qa_task_id}],
                "status": "open",
            },
            {"$set": {"status": "resolved", "resolved_at": now}}
        )
        if res.modified_count > 0:
            logger.info("[DEFECT] Automatically resolved %d defect(s) for task %s", res.modified_count, dev_task_id)
            await broadcaster.broadcast("defects_resolved", {
                "dev_task_id": dev_task_id,
                "qa_task_id": qa_task_id,
                "resolved_count": res.modified_count,
            })

