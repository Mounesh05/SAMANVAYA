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
        self.ci_configs = col("qa_ci_configs")
        self.test_runs = col("test_runs")

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
        await self.ci_configs.create_index([("project_id", 1), ("branch", 1)], unique=True)
        await self.ci_configs.create_index([("repository", 1)])
        await self.test_runs.create_index([("id", 1)], unique=True)
        await self.test_runs.create_index([("project_id", 1), ("created_at", -1)])
        await self.test_runs.create_index([("repository", 1), ("branch", 1)])

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

    # CI Configuration methods
    async def save_ci_config(self, config: dict):
        """Save or update CI configuration for a project and branch."""
        await self.ci_configs.replace_one(
            {"project_id": config["project_id"], "branch": config["branch"]},
            config,
            upsert=True
        )
        return config

    async def get_ci_config(self, project_id: str, branch: str | None = None):
        """Get CI configuration for a project and optionally a specific branch."""
        query = {"project_id": project_id}
        if branch:
            query["branch"] = branch
        return await self.find_one(self.ci_configs, query)

    async def get_all_ci_configs(self, project_id: str):
        """Get all CI configurations for a project (all branches)."""
        cursor = self.ci_configs.find({"project_id": project_id}, {"_id": 0})
        return await cursor.to_list(length=None)

    async def delete_ci_config(self, project_id: str, branch: str):
        """Delete CI configuration for a specific branch."""
        result = await self.ci_configs.delete_one(
            {"project_id": project_id, "branch": branch}
        )
        return result.deleted_count > 0

    async def get_allowed_repositories(self, project_id: str):
        """Get list of allowed repositories for a project (from any branch config)."""
        configs = await self.get_all_ci_configs(project_id)
        repositories = set()
        for config in configs:
            if config.get("repository"):
                repositories.add(config["repository"])
        return list(repositories)

    async def add_allowed_repository(self, project_id: str, repository: str):
        """Add a repository to the allowed list (deprecated - use per-branch configs)."""
        # For backward compatibility, add to the first config or create a default one
        config = await self.get_ci_config(project_id)
        if config:
            await self.ci_configs.update_one(
                {"project_id": project_id, "branch": config["branch"]},
                {"$set": {"repository": repository}}
            )
        else:
            await self.save_ci_config({
                "project_id": project_id,
                "branch": "main",
                "repository": repository,
                "enabled": False
            })
