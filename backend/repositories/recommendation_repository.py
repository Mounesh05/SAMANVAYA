"""
Recommendation Repository.
"""

from typing import Optional, List, Dict, Any
from core.database import db


class RecommendationRepository:
    """Repository for recommendation operations."""
    
    def __init__(self):
        self.collection = db["recommendations"]
    
    async def insert(self, recommendation: Dict[str, Any]) -> str:
        """Insert a new recommendation."""
        result = await self.collection.insert_one(recommendation)
        return recommendation["id"]
    
    async def find_by_id(self, recommendation_id: str) -> Optional[Dict[str, Any]]:
        """Find recommendation by ID."""
        return await self.collection.find_one({"id": recommendation_id})
    
    async def find_by_entity(
        self,
        entity_type: str,
        entity_id: str,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Find recommendations for an entity."""
        query = {
            "entity_type": entity_type,
            "entity_id": entity_id
        }
        
        if status:
            query["status"] = status
        
        cursor = self.collection.find(query).sort("priority", -1).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def find_by_user(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Find recommendations for a user."""
        query = {"target_user_id": user_id}
        
        if status:
            query["status"] = status
        
        cursor = self.collection.find(query).sort("priority", -1).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def find_by_role(
        self,
        role: str,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Find recommendations for a role."""
        query = {"target_roles": role}
        
        if project_id:
            query["project_id"] = project_id
        
        if status:
            query["status"] = status
        
        cursor = self.collection.find(query).sort("priority", -1).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def update_status(
        self,
        recommendation_id: str,
        status: str,
        updated_by: str,
        notes: Optional[str] = None
    ) -> bool:
        """Update recommendation status."""
        from datetime import datetime, timezone
        
        update_data = {
            "status": status,
            "status_updated_at": datetime.now(timezone.utc).isoformat(),
            "status_updated_by": updated_by
        }
        
        if notes:
            update_data["implementation_notes"] = notes
        
        result = await self.collection.update_one(
            {"id": recommendation_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    async def link_to_pr(
        self,
        recommendation_id: str,
        pr_id: str
    ) -> bool:
        """Link recommendation to implementing PR."""
        result = await self.collection.update_one(
            {"id": recommendation_id},
            {"$set": {"related_pr_id": pr_id}}
        )
        return result.modified_count > 0
    
    async def mark_obsolete(
        self,
        entity_type: str,
        entity_id: str
    ) -> int:
        """Mark all pending recommendations for an entity as obsolete."""
        from datetime import datetime, timezone
        
        result = await self.collection.update_many(
            {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "status": "pending"
            },
            {"$set": {
                "status": "obsolete",
                "status_updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        return result.modified_count
    
    async def get_pending_count(self, user_id: Optional[str] = None) -> int:
        """Get count of pending recommendations."""
        query = {"status": "pending"}
        
        if user_id:
            query["target_user_id"] = user_id
        
        return await self.collection.count_documents(query)
