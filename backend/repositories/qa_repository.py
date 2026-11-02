"""Persistence helpers for the QA management collections."""

from core.database import col


class QARepository:
    COLLECTIONS = ("qa_test_suites", "qa_test_cases", "qa_test_executions", "qa_defects")

    def __init__(self):
        self.projects = col("projects")
        self.stories = col("stories")
        self.tasks = col("tasks")
        self.users = col("users")
        self.suites = col("qa_test_suites")
        self.cases = col("qa_test_cases")
        self.executions = col("qa_test_executions")
        self.defects = col("qa_defects")

    async def ensure_indexes(self):
        await self.suites.create_index([("id", 1)], unique=True)
        await self.suites.create_index([("project_id", 1), ("status", 1)])
        await self.cases.create_index([("id", 1)], unique=True)
        await self.cases.create_index(
            [("project_id", 1), ("is_archived", 1), ("created_at", -1)]
        )
        await self.cases.create_index([("project_id", 1), ("suite_id", 1)])
        await self.cases.create_index([("project_id", 1), ("story_id", 1)])
        await self.executions.create_index([("id", 1)], unique=True)
        await self.executions.create_index(
            [("project_id", 1), ("test_case_id", 1), ("created_at", -1)]
        )
        await self.executions.create_index([("project_id", 1), ("defect_id", 1)])
        await self.defects.create_index([("id", 1)], unique=True)
        await self.defects.create_index(
            [("project_id", 1), ("status", 1), ("created_at", -1)]
        )
        await self.defects.create_index([("project_id", 1), ("assignee_id", 1)])

    async def find_one(self, collection, query):
        return await collection.find_one(query, {"_id": 0})

    async def list_documents(
        self,
        collection,
        query,
        *,
        skip=0,
        limit=100,
        sort_field="created_at",
    ):
        cursor = collection.find(query, {"_id": 0}).sort(sort_field, -1).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_documents(self, collection, query):
        return await collection.count_documents(query)

    async def insert(self, collection, document):
        await collection.insert_one(document.copy())
        return document

    async def update(self, collection, query, updates):
        result = await collection.update_one(query, {"$set": updates})
        return result.matched_count > 0
