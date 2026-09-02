"""
Performance Repository
Database operations for developer performance data.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from core.database import db


class PerformanceRepository:
    """Repository for developer performance evaluations."""
    
    def __init__(self):
        self.collection = db["developer_performances"]
    
    async def create(self, performance_data: Dict[str, Any]) -> str:
        """Create new performance record."""
        result = await self.collection.insert_one(performance_data)
        return str(result.inserted_id)
    
    async def get_by_id(self, performance_id: str) -> Optional[Dict[str, Any]]:
        """Get performance by ID."""
        from bson import ObjectId
        return await self.collection.find_one({"_id": ObjectId(performance_id)})
    
    async def update(self, performance_id: str, data: Dict[str, Any]) -> bool:
        """Update performance record."""
        from bson import ObjectId
        data["updated_at"] = datetime.now(timezone.utc)
        result = await self.collection.update_one(
            {"_id": ObjectId(performance_id)},
            {"$set": data}
        )
        return result.modified_count > 0
    
    async def get_by_developer_and_period(
        self,
        developer_id: str,
        period_label: str
    ) -> Optional[Dict[str, Any]]:
        """Get performance for specific developer and period."""
        return await self.collection.find_one({
            "developer_id": developer_id,
            "period_label": period_label
        })
    
    async def get_latest_by_developer(
        self,
        developer_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get latest performance for a developer."""
        cursor = self.collection.find(
            {"developer_id": developer_id}
        ).sort("period_start", -1).limit(1)
        
        results = await cursor.to_list(length=1)
        return results[0] if results else None
    
    async def get_by_developer(
        self,
        developer_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get performance history for a developer."""
        cursor = self.collection.find(
            {"developer_id": developer_id}
        ).sort("period_start", -1).limit(limit)
        
        return await cursor.to_list(length=limit)
    
    async def get_previous_performance(
        self,
        developer_id: str,
        before_date: datetime
    ) -> Optional[Dict[str, Any]]:
        """Get performance before a specific date."""
        cursor = self.collection.find({
            "developer_id": developer_id,
            "period_start": {"$lt": before_date}
        }).sort("period_start", -1).limit(1)
        
        results = await cursor.to_list(length=1)
        return results[0] if results else None
    
    async def get_by_project_and_period(
        self,
        project_id: str,
        period_label: str
    ) -> List[Dict[str, Any]]:
        """Get all performances for a project in a specific period."""
        cursor = self.collection.find({
            "project_id": project_id,
            "period_label": period_label
        })
        
        return await cursor.to_list(length=None)

    async def ensure_indexes(self):
        """Create indexes for common query patterns."""
        await self.collection.create_index([("developer_id", 1), ("period_start", -1)])
        await self.collection.create_index([("developer_id", 1), ("period_label", 1)], unique=True, sparse=True)
