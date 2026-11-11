"""
Webhook Event Repository.
"""

from typing import Optional, List, Dict, Any
from core.database import db
from datetime import datetime, timedelta
from uuid import uuid4
from pymongo import ReturnDocument


class WebhookEventRepository:
    """Repository for webhook event operations."""
    
    def __init__(self):
        self.collection = db["webhook_events"]
    
    async def insert(self, event: Dict[str, Any]) -> str:
        """Insert a new webhook event."""
        await self.collection.insert_one(event)
        return event["id"]
    
    async def find_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Find webhook event by ID."""
        return await self.collection.find_one({"id": event_id})
    
    async def update(self, filter_dict: Dict[str, Any], update_dict: Dict[str, Any]) -> bool:
        """Update webhook event."""
        result = await self.collection.update_one(
            filter_dict,
            {"$set": update_dict}
        )
        return result.modified_count > 0
    
    async def find_by_status(
        self, status: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Find webhook events by status."""
        cursor = self.collection.find({"status": status}).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def find_by_repository(
        self, repository: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Find webhook events by repository."""
        cursor = self.collection.find({"repository": repository}).sort("created_at", -1).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def ensure_indexes(self):
        await self.collection.create_index("delivery_key", unique=True, sparse=True)
        await self.collection.create_index([("status", 1), ("next_attempt_at", 1)])
        await self.collection.create_index([("status", 1), ("lease_expires_at", 1)])

    @staticmethod
    def _recoverable(now: datetime, lease_seconds: int, max_retries: int = 3) -> dict:
        return {"$and": [
            {"$or": [{"retry_count": {"$lt": max_retries}}, {"retry_count": {"$exists": False}}]},
            {"$or": [
                {"status": "pending"},
                {"status": "failed", "$or": [{"next_attempt_at": {"$lte": now}}, {"next_attempt_at": {"$exists": False}}]},
                {"status": "processing", "lease_expires_at": {"$lte": now}},
                # Old records predate leases; reclaim only after the lease window.
                {"status": "processing", "lease_expires_at": {"$exists": False}, "$or": [
                    {"processing_started_at": {"$lte": (now - timedelta(seconds=lease_seconds)).isoformat()}},
                    {"processing_started_at": None},
                ]},
            ]},
        ]}

    async def get_recoverable_events(self, now: datetime, lease_seconds: int, limit: int) -> list:
        # A worker that died on its last attempt must not stay 'processing' forever.
        await self.collection.update_many({"status": "processing", "retry_count": {"$gte": 3},
                                          "lease_expires_at": {"$lte": now}},
                                         {"$set": {"status": "failed", "error": "Lease expired; retry limit reached"}})
        return await self.collection.find(self._recoverable(now, lease_seconds)).sort("created_at", 1).limit(limit).to_list(limit)

    async def claim(self, event_id: str, now: datetime, lease_seconds: int) -> Optional[dict]:
        """Atomic ownership prevents duplicate execution by competing workers."""
        return await self.collection.find_one_and_update(
            {"id": event_id, **self._recoverable(now, lease_seconds)},
            {"$set": {"status": "processing", "processing_started_at": now.isoformat(),
                      "lease_id": uuid4().hex, "lease_expires_at": now + timedelta(seconds=lease_seconds),
                      "error": None}, "$inc": {"retry_count": 1}},
            return_document=ReturnDocument.AFTER,
        )

    async def renew(self, event_id: str, lease_id: str, now: datetime, lease_seconds: int) -> bool:
        result = await self.collection.update_one(
            {"id": event_id, "status": "processing", "lease_id": lease_id, "lease_expires_at": {"$gt": now}},
            {"$set": {"lease_expires_at": now + timedelta(seconds=lease_seconds)}})
        return result.matched_count == 1
    
    async def mark_completed(
        self,
        event_id: str,
        completed_at: str,
        triggers_executed: List[str],
        risks_detected: List[str],
        notifications_sent: List[str],
        recommendations_created: List[str],
        *, lease_id: str,
    ) -> bool:
        """Mark event as completed with results."""
        return await self.update(
            {"id": event_id, "status": "processing", "lease_id": lease_id},
            {
                "status": "completed",
                "processing_completed_at": completed_at,
                "triggers_executed": triggers_executed,
                "risks_detected": risks_detected,
                "notifications_sent": notifications_sent,
                "recommendations_created": recommendations_created
            }
        )
    
    async def mark_failed(self, event_id: str, error: str, *, lease_id: str, next_attempt_at: datetime) -> bool:
        """Mark event as failed."""
        return await self.update(
            {"id": event_id, "status": "processing", "lease_id": lease_id},
            {
                "status": "failed",
                "error": error,
                "next_attempt_at": next_attempt_at,
            }
        )
    
    async def get_pending_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get pending events for processing."""
        cursor = self.collection.find(
            {"status": "pending"}
        ).sort("created_at", 1).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def get_failed_events_for_retry(
        self, max_retries: int = 3, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get failed events that can be retried."""
        cursor = self.collection.find(
            {
                "status": "failed",
                "retry_count": {"$lt": max_retries}
            }
        ).sort("created_at", 1).limit(limit)
        return await cursor.to_list(length=limit)
