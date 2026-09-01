"""
Webhook Event Repository.
"""

from typing import Optional, List, Dict, Any
from core.database import db


class WebhookEventRepository:
    """Repository for webhook event operations."""
    
    def __init__(self):
        self.collection = db["webhook_events"]
    
    async def insert(self, event: Dict[str, Any]) -> str:
        """Insert a new webhook event."""
        result = await self.collection.insert_one(event)
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
    
    async def mark_processing(self, event_id: str, started_at: str) -> bool:
        """Mark event as processing."""
        return await self.update(
            {"id": event_id},
            {"status": "processing", "processing_started_at": started_at}
        )
    
    async def mark_completed(
        self,
        event_id: str,
        completed_at: str,
        triggers_executed: List[str],
        risks_detected: List[str],
        notifications_sent: List[str],
        recommendations_created: List[str]
    ) -> bool:
        """Mark event as completed with results."""
        return await self.update(
            {"id": event_id},
            {
                "status": "completed",
                "processing_completed_at": completed_at,
                "triggers_executed": triggers_executed,
                "risks_detected": risks_detected,
                "notifications_sent": notifications_sent,
                "recommendations_created": recommendations_created
            }
        )
    
    async def mark_failed(self, event_id: str, error: str) -> bool:
        """Mark event as failed."""
        event = await self.find_by_id(event_id)
        retry_count = event.get("retry_count", 0) + 1 if event else 1
        
        return await self.update(
            {"id": event_id},
            {
                "status": "failed",
                "error": error,
                "retry_count": retry_count
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
