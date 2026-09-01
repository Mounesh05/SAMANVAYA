"""
Entity Relationship Repository.

Manages the evidence graph - all relationships between entities.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from core.database import db
from domain.models.entity_relationship import EntityType, RelationshipType


class EntityRelationshipRepository:
    """Repository for entity relationship operations."""
    
    def __init__(self):
        self.collection = db["entity_relationships"]
        # Create indexes for fast graph traversal
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create indexes for graph queries."""
        import asyncio
        # These will be created when first accessed
        self._indexes_to_create = [
            ("source_type", "source_id"),
            ("target_type", "target_id"),
            ("relationship_type",),
            ("source_id",),
            ("target_id",),
        ]
    
    async def create_indexes(self):
        """Actually create the indexes (call this on startup)."""
        for index_fields in self._indexes_to_create:
            await self.collection.create_index([(f, 1) for f in index_fields])
    
    async def insert(self, relationship: Dict[str, Any]) -> str:
        """Insert a new relationship."""
        result = await self.collection.insert_one(relationship)
        return relationship["id"]
    
    async def find_by_id(self, relationship_id: str) -> Optional[Dict[str, Any]]:
        """Find relationship by ID."""
        return await self.collection.find_one({"id": relationship_id})
    
    async def find_outbound(
        self,
        source_type: EntityType,
        source_id: str,
        relationship_type: Optional[RelationshipType] = None,
        target_type: Optional[EntityType] = None
    ) -> List[Dict[str, Any]]:
        """
        Find all relationships FROM an entity.
        
        Example: Find all PRs that implement a Task
        find_outbound(source_type=TASK, source_id="TASK-123", relationship_type=IMPLEMENTS)
        """
        query = {
            "source_type": source_type.value,
            "source_id": source_id
        }
        
        if relationship_type:
            query["relationship_type"] = relationship_type.value
        
        if target_type:
            query["target_type"] = target_type.value
        
        cursor = self.collection.find(query)
        return await cursor.to_list(length=1000)
    
    async def find_inbound(
        self,
        target_type: EntityType,
        target_id: str,
        relationship_type: Optional[RelationshipType] = None,
        source_type: Optional[EntityType] = None
    ) -> List[Dict[str, Any]]:
        """
        Find all relationships TO an entity.
        
        Example: Find all tasks that a PR implements
        find_inbound(target_type=TASK, target_id="TASK-123", relationship_type=IMPLEMENTS)
        """
        query = {
            "target_type": target_type.value,
            "target_id": target_id
        }
        
        if relationship_type:
            query["relationship_type"] = relationship_type.value
        
        if source_type:
            query["source_type"] = source_type.value
        
        cursor = self.collection.find(query)
        return await cursor.to_list(length=1000)
    
    async def find_bidirectional(
        self,
        entity_type: EntityType,
        entity_id: str,
        relationship_type: Optional[RelationshipType] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Find all relationships connected to an entity (both directions).
        
        Returns:
            {
                "outbound": [...],  # Relationships FROM this entity
                "inbound": [...]     # Relationships TO this entity
            }
        """
        outbound = await self.find_outbound(entity_type, entity_id, relationship_type)
        inbound = await self.find_inbound(entity_type, entity_id, relationship_type)
        
        return {
            "outbound": outbound,
            "inbound": inbound
        }
    
    async def exists(
        self,
        source_type: EntityType,
        source_id: str,
        target_type: EntityType,
        target_id: str,
        relationship_type: RelationshipType
    ) -> bool:
        """Check if a specific relationship already exists."""
        count = await self.collection.count_documents({
            "source_type": source_type.value,
            "source_id": source_id,
            "target_type": target_type.value,
            "target_id": target_id,
            "relationship_type": relationship_type.value
        })
        return count > 0
    
    async def delete(self, relationship_id: str) -> bool:
        """Delete a relationship."""
        result = await self.collection.delete_one({"id": relationship_id})
        return result.deleted_count > 0
    
    async def delete_all_for_entity(
        self,
        entity_type: EntityType,
        entity_id: str
    ) -> int:
        """Delete all relationships connected to an entity (cleanup)."""
        result = await self.collection.delete_many({
            "$or": [
                {"source_type": entity_type.value, "source_id": entity_id},
                {"target_type": entity_type.value, "target_id": entity_id}
            ]
        })
        return result.deleted_count
    
    async def find_path(
        self,
        start_type: EntityType,
        start_id: str,
        end_type: EntityType,
        end_id: str,
        max_depth: int = 5
    ) -> List[List[Dict[str, Any]]]:
        """
        Find paths between two entities in the graph.
        
        Uses BFS to find shortest paths.
        
        Returns:
            List of paths (each path is a list of relationships)
        """
        # This is a complex graph traversal - implement later if needed
        # For now, return empty list
        # TODO: Implement BFS/DFS path finding
        return []
    
    async def get_blast_radius(
        self,
        entity_type: EntityType,
        entity_id: str,
        max_hops: int = 2,
        relationship_types: Optional[List[RelationshipType]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all entities within N hops of a given entity.
        
        This is used for impact analysis.
        
        Returns:
            List of related entities with their distances
        """
        visited = set()
        queue = [(entity_type, entity_id, 0)]  # (type, id, distance)
        result = []
        
        while queue:
            current_type, current_id, distance = queue.pop(0)
            
            if distance > max_hops:
                continue
            
            key = f"{current_type.value}:{current_id}"
            if key in visited:
                continue
            
            visited.add(key)
            
            if distance > 0:  # Don't include the starting entity
                result.append({
                    "entity_type": current_type.value,
                    "entity_id": current_id,
                    "distance": distance
                })
            
            # Find all outbound relationships
            outbound = await self.find_outbound(current_type, current_id)
            
            for rel in outbound:
                if relationship_types and rel["relationship_type"] not in [rt.value for rt in relationship_types]:
                    continue
                
                target_type = EntityType(rel["target_type"])
                target_id = rel["target_id"]
                queue.append((target_type, target_id, distance + 1))
        
        return result
    
    async def get_entity_metrics(
        self,
        entity_type: EntityType,
        entity_id: str
    ) -> Dict[str, int]:
        """
        Get metrics for an entity (how connected it is).
        
        Returns:
            {
                "inbound_count": 5,
                "outbound_count": 10,
                "total_connections": 15
            }
        """
        inbound_count = await self.collection.count_documents({
            "target_type": entity_type.value,
            "target_id": entity_id
        })
        
        outbound_count = await self.collection.count_documents({
            "source_type": entity_type.value,
            "source_id": entity_id
        })
        
        return {
            "inbound_count": inbound_count,
            "outbound_count": outbound_count,
            "total_connections": inbound_count + outbound_count
        }
    
    async def update_metadata(
        self,
        relationship_id: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """Update relationship metadata."""
        result = await self.collection.update_one(
            {"id": relationship_id},
            {"$set": {"metadata": metadata}}
        )
        return result.modified_count > 0
    
    async def mark_verified(
        self,
        relationship_id: str,
        verified_by: str
    ) -> bool:
        """Mark a relationship as manually verified."""
        result = await self.collection.update_one(
            {"id": relationship_id},
            {"$set": {
                "verified": True,
                "verified_by": verified_by,
                "verified_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        return result.modified_count > 0

