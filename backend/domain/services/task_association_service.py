"""
Task & Employee Association Service.
Correlates incoming GitHub webhook activity (commits, branches, PRs, workflow runs)
with specific Samanvaya tasks, employees, and companies with strict tenant isolation.
"""

import re
import logging
from typing import Optional, Dict, Any, List
from core.database import col

logger = logging.getLogger("samanvaya.task_association")

TASK_ID_REGEX = re.compile(r"\b(TSK-[A-Z0-9]+|PRJ-\d+-TSK-\d+|SAM-\d+)\b", re.IGNORECASE)


class TaskAssociationService:
    """Matches GitHub activity to the appropriate Developer, DevOps, or QA task."""

    @staticmethod
    def extract_task_identifiers(*texts: Optional[str]) -> List[str]:
        """Extracts task keys from branch names, PR titles, descriptions, and commit messages."""
        found = set()
        for text in texts:
            if not text:
                continue
            matches = TASK_ID_REGEX.findall(text)
            for m in matches:
                found.add(m.upper())
        return list(found)

    @staticmethod
    async def resolve_company_from_repo(repo_full_name: str) -> Optional[str]:
        """Resolves company_id from repository mapping in organizations or projects."""
        if not repo_full_name:
            return None

        # 1. Search organizations.repositories
        org = await col("organizations").find_one({
            "$or": [
                {"repositories": repo_full_name},
                {"github_repo": repo_full_name},
                {"code": {"$regex": repo_full_name.split("/")[0], "$options": "i"}},
            ]
        })
        if org:
            return org.get("company_id") or org.get("id")

        # 2. Search projects.github_repo
        project = await col("projects").find_one({
            "$or": [
                {"github_repo": repo_full_name},
                {"repo": repo_full_name},
                {"name": {"$regex": repo_full_name.split("/")[-1], "$options": "i"}},
            ]
        })
        if project:
            return project.get("company_id") or project.get("org_id") or "ORG-001"

        return "ORG-001"  # Default fallback

    @staticmethod
    async def resolve_employee_from_github_user(
        github_username: str, company_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Resolves employee record from GitHub login username."""
        if not github_username:
            return None

        query: Dict[str, Any] = {
            "$or": [
                {"github_username": github_username},
                {"github_login": github_username},
                {"email": {"$regex": f"^{github_username}@", "$options": "i"}},
                {"id": {"$regex": github_username, "$options": "i"}},
            ]
        }
        if company_id:
            query["$and"] = [{"$or": [{"company_id": company_id}, {"org_id": company_id}]}]

        user = await col("users").find_one(query)
        return user

    @classmethod
    async def find_matching_task(
        cls,
        company_id: str,
        repo_full_name: str,
        branch_name: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        commit_messages: Optional[List[str]] = None,
        workflow_name: Optional[str] = None,
        role_type: str = "developer",  # developer | devops | qa
        sender_login: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Finds the exact task matching the activity within the tenant boundary.
        Enforces company data isolation.
        """
        texts_to_scan = [branch_name, title, description, workflow_name]
        if commit_messages:
            texts_to_scan.extend(commit_messages)

        task_keys = cls.extract_task_identifiers(*texts_to_scan)

        # 1. Direct match by extracted task ID
        for key in task_keys:
            task = await col("tasks").find_one({
                "$or": [
                    {"id": key},
                    {"id": key.upper()},
                    {"title": {"$regex": key, "$options": "i"}},
                ]
            })
            if task:
                # Validate company isolation
                proj_id = task.get("project_id")
                if proj_id:
                    proj = await col("projects").find_one({"id": proj_id})
                    if proj and proj.get("company_id") and company_id and proj.get("company_id") != company_id:
                        logger.warning("[TASK-ASSOC] Tenant mismatch: Task %s belongs to %s, not %s", key, proj.get("company_id"), company_id)
                        continue
                logger.info("[TASK-ASSOC] Matched task %s by explicit identifier", task.get("id"))
                return task

        # 2. Match by role-type and assignee in active project
        role_filters = {
            "developer": {"type": {"$in": ["feature", "bug", "chore", "task", None]}},
            "devops": {"$or": [
                {"type": "devops"},
                {"title": {"$regex": "deploy|ci|cd|pipeline|k8s|ingress|docker", "$options": "i"}},
            ]},
            "qa": {"$or": [
                {"type": "qa"},
                {"title": {"$regex": "test|qa|regression|automation|suite", "$options": "i"}},
            ]},
        }

        # Resolve employee if sender provided
        employee = await cls.resolve_employee_from_github_user(sender_login, company_id) if sender_login else None
        
        fallback_query: Dict[str, Any] = {
            "status": {"$in": ["todo", "in_progress", "review", "changes_requested"]},
        }
        if employee:
            fallback_query["assignee_id"] = employee.get("employee_id") or employee.get("id")

        if role_type in role_filters:
            fallback_query.update(role_filters[role_type])

        # Find most recently updated active task
        task = await col("tasks").find_one(fallback_query, sort=[("updated_at", -1), ("_id", -1)])
        if task:
            logger.info("[TASK-ASSOC] Matched task %s by %s role context", task.get("id"), role_type)
            return task

        return None

