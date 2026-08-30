"""
Generic async MongoDB repository.
All entity-specific repos extend this.
Pagination built in — no endpoint should return unbounded results.
"""

from motor.motor_asyncio import AsyncIOMotorCollection
from typing import Any, Optional


class BaseRepository:
    """Base repository with common MongoDB operations."""

    def __init__(self, collection: AsyncIOMotorCollection):
        self.col = collection

    async def find_one(self, query: dict) -> Optional[dict]:
        """Find a single document by query."""
        return await self.col.find_one(query, {"_id": 0})

    async def find_many(
        self,
        query: dict,
        limit: int = 50,
        skip: int = 0,
        sort_field: Optional[str] = None,
        sort_dir: int = -1,
    ) -> dict:
        """
        Find multiple documents with pagination.
        Always paginated to prevent unbounded results.
        
        Returns:
            dict with keys: data, total, limit, skip
        """
        total = await self.col.count_documents(query)
        cursor = self.col.find(query, {"_id": 0}).skip(skip).limit(limit)
        
        if sort_field:
            cursor = cursor.sort(sort_field, sort_dir)
        
        data = [doc async for doc in cursor]
        
        return {"data": data, "total": total, "limit": limit, "skip": skip}

    async def find_all(self, query: dict) -> list:
        """
        Unbounded fetch — only use for small controlled datasets.
        Prefer find_many() with pagination for user-facing endpoints.
        """
        return [doc async for doc in self.col.find(query, {"_id": 0})]

    async def insert(self, doc: dict) -> bool:
        """Insert a single document."""
        result = await self.col.insert_one(doc)
        return result.acknowledged

    async def update(self, query: dict, update: dict) -> bool:
        """Update a single document matching query."""
        result = await self.col.update_one(query, {"$set": update})
        return result.matched_count > 0

    async def upsert(self, query: dict, doc: dict) -> bool:
        """Update or insert a document."""
        result = await self.col.update_one(query, {"$set": doc}, upsert=True)
        return result.acknowledged

    async def delete(self, query: dict) -> bool:
        """Delete a single document matching query."""
        result = await self.col.delete_one(query)
        return result.deleted_count > 0

    async def count(self, query: dict) -> int:
        """Count documents matching query."""
        return await self.col.count_documents(query)

    async def exists(self, query: dict) -> bool:
        """Check if any document matches query."""
        return await self.count(query) > 0
