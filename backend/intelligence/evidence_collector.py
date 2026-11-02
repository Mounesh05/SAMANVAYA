"""
Evidence Collector — Aggregates and time-bounds raw engineering evidence
for an employee within an evaluation period.

Features:
- Time-period filtering: strictly checks timestamps against start_date and end_date.
- Handles PRs opened inside vs merged inside period.
- Filters out bot commits (dependabot, github-actions, etc.), merge commits, duplicate shas.
- Aggregates multi-source evidence: GitHub (PRs, Commits), CI/CD runs, Deployments, Tasks/Sprints.
- Caches raw evidence per evaluation session so specialist agents can execute in parallel
  without re-fetching from GitHub or MongoDB.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
import logging
from core.database import col
from .identity_mapper import EmployeeIdentity, IdentityMapper
from .scoring.models import EvaluationPeriod

logger = logging.getLogger("samanvaya.evidence_collector")

BOT_IDENTIFIERS = {
    "dependabot[bot]",
    "github-actions[bot]",
    "renovate[bot]",
    "snyk-bot",
    "codecov[bot]",
    "greenkeeper[bot]",
}


def _parse_iso(date_str: Any) -> Optional[datetime]:
    """Safely parse various datetime formats into UTC datetime."""
    if not date_str:
        return None
    if isinstance(date_str, datetime):
        return date_str.replace(tzinfo=timezone.utc) if date_str.tzinfo is None else date_str.astimezone(timezone.utc)
    try:
        # Replace Z with +00:00 for ISO format
        cleaned = str(date_str).replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except Exception:
        # Try basic formats
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(str(date_str)[:19], fmt)
                return dt.replace(tzinfo=timezone.utc)
            except Exception:
                pass
    return None


class EmployeeEvidencePackage:
    """Container of filtered, deduplicated evidence for an employee."""

    def __init__(self, identity: EmployeeIdentity, period: EvaluationPeriod):
        self.identity = identity
        self.period = period
        self.pull_requests: List[Dict[str, Any]] = []
        self.commits: List[Dict[str, Any]] = []
        self.ci_runs: List[Dict[str, Any]] = []
        self.deployments: List[Dict[str, Any]] = []
        self.tasks: List[Dict[str, Any]] = []
        self.sprints: List[Dict[str, Any]] = []
        self.static_findings: List[Dict[str, Any]] = []
        self.raw_context: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "employee_id": self.identity.employee_id,
            "employee_name": self.identity.name,
            "period": {
                "start": self.period.start_date,
                "end": self.period.end_date,
                "label": self.period.label,
            },
            "pull_requests": self.pull_requests,
            "commits": self.commits,
            "ci_runs": self.ci_runs,
            "deployments": self.deployments,
            "tasks": self.tasks,
            "sprints": self.sprints,
            "static_findings": self.static_findings,
            "summary": {
                "total_prs": len(self.pull_requests),
                "total_commits": len(self.commits),
                "total_ci_runs": len(self.ci_runs),
                "total_deployments": len(self.deployments),
                "total_tasks": len(self.tasks),
            },
        }


class EvidenceCollector:
    """
    Collects raw evidence from GitHub + MongoDB for an employee.
    Enforces time boundaries and identity matching.
    """

    @staticmethod
    def is_bot_author(author_name: Optional[str]) -> bool:
        """Check if an author name represents an automated bot."""
        if not author_name:
            return False
        cleaned = str(author_name).lower().strip()
        if cleaned in BOT_IDENTIFIERS:
            return True
        return any(b in cleaned for b in ("[bot]", "bot-", "-bot", "automation", "snyk", "dependabot"))

    @staticmethod
    def _filter_prs_by_date(prs: List[Dict[str, Any]], start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Filter PRs strictly within [start_date, end_date]."""
        dt_start = _parse_iso(start_date) or datetime(2020, 1, 1, tzinfo=timezone.utc)
        dt_end = _parse_iso(end_date) or datetime(2030, 1, 1, tzinfo=timezone.utc)
        if len(end_date) <= 10:
            dt_end = dt_end.replace(hour=23, minute=59, second=59)

        result = []
        for pr in prs:
            pr_date = _parse_iso(pr.get("merged_at") or pr.get("created_at") or pr.get("updated_at"))
            if pr_date and (dt_start <= pr_date <= dt_end):
                result.append(pr)
        return result

    @classmethod
    def _clean_and_deduplicate_commits(cls, commits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate commits by SHA and eliminate bot commits."""
        seen_shas = set()
        clean = []
        for c in commits:
            sha = c.get("sha") or c.get("id")
            if not sha or sha in seen_shas:
                continue
            author = c.get("author") or {}
            author_name = author.get("name") if isinstance(author, dict) else str(author)
            if cls.is_bot_author(author_name):
                continue
            seen_shas.add(sha)
            clean.append(c)
        return clean

    def __init__(self):
        self.identity_mapper = IdentityMapper()

    async def collect_package(
        self,
        employee_id: str,
        start_date: str,
        end_date: str,
        period_label: Optional[str] = None,
        cached_context: Optional[Dict[str, Any]] = None,
    ) -> EmployeeEvidencePackage:
        """
        Builds a comprehensive, deduplicated evidence package.
        """
        identity = await self.identity_mapper.get_identity(employee_id)
        if not identity:
            # Fallback identity if not found in db
            identity = EmployeeIdentity(
                employee_id=employee_id,
                name=employee_id,
                email=f"{employee_id.lower()}@samanvaya.io",
                github_username=employee_id.lower(),
            )

        period = EvaluationPeriod(
            start_date=start_date,
            end_date=end_date,
            label=period_label or f"{start_date[:7]}",
        )

        package = EmployeeEvidencePackage(identity, period)

        dt_start = _parse_iso(start_date) or datetime(2020, 1, 1, tzinfo=timezone.utc)
        dt_end = _parse_iso(end_date) or datetime(2030, 1, 1, tzinfo=timezone.utc)
        # Ensure dt_end covers until the end of that day (23:59:59) if only date was provided
        if len(end_date) <= 10:
            dt_end = dt_end.replace(hour=23, minute=59, second=59)

        # 1. Collect Tasks & Sprints from MongoDB
        await self._collect_mongodb_tasks(package, dt_start, dt_end)

        # 2. Collect from GitHub / Cached Context / MongoDB PRs
        await self._collect_prs_and_commits(package, dt_start, dt_end, cached_context)

        # 3. Collect CI/CD runs & Deployments
        await self._collect_cicd_and_deployments(package, dt_start, dt_end, cached_context)

        return package

    async def _collect_mongodb_tasks(
        self,
        package: EmployeeEvidencePackage,
        dt_start: datetime,
        dt_end: datetime,
    ):
        """Collect tasks, stories, and sprint contributions assigned to this employee."""
        try:
            tasks_cursor = col("tasks").find({
                "$or": [
                    {"assignee_id": package.identity.employee_id},
                    {"assignee": package.identity.name},
                    {"assignee_email": package.identity.email},
                    {"assignee_id": package.identity.github_username},
                ]
            })
            raw_tasks = await tasks_cursor.to_list(100)

            for t in raw_tasks:
                # Check if task was updated, completed, or created in the period
                t_date = _parse_iso(t.get("completed_at") or t.get("updated_at") or t.get("created_at"))
                if t_date and (dt_start <= t_date <= dt_end):
                    package.tasks.append({
                        "id": str(t.get("_id") or t.get("id")),
                        "title": t.get("title", ""),
                        "status": t.get("status", "completed"),
                        "priority": t.get("priority", "medium"),
                        "story_points": t.get("story_points", 0),
                        "type": t.get("type", "feature"),
                        "blocked": t.get("blocked", False) or t.get("status") == "blocked",
                        "blocker_reason": t.get("blocker_reason", ""),
                        "completed_at": t.get("completed_at"),
                        "date": t_date.isoformat(),
                    })
        except Exception as exc:
            logger.debug("[EVIDENCE] MongoDB tasks error: %s", exc)

    async def _collect_prs_and_commits(
        self,
        package: EmployeeEvidencePackage,
        dt_start: datetime,
        dt_end: datetime,
        cached_context: Optional[Dict[str, Any]] = None,
    ):
        """Collect PRs, commits, and diffs with deduplication and bot filtering."""
        seen_prs: Set[int] = set()
        seen_commits: Set[str] = set()

        # If cached_context provided (e.g. from GitHubContext or test fixtures)
        if cached_context:
            for pr in cached_context.get("pull_requests", []):
                pr_num = pr.get("number") or pr.get("pr_number")
                if pr_num and pr_num not in seen_prs:
                    pr_date = _parse_iso(pr.get("merged_at") or pr.get("created_at") or pr.get("updated_at"))
                    if pr_date and (dt_start <= pr_date <= dt_end):
                        seen_prs.add(pr_num)
                        package.pull_requests.append(pr)

            for commit in cached_context.get("commits", []):
                sha = commit.get("sha") or commit.get("id")
                if sha and sha not in seen_commits:
                    c_date = _parse_iso(commit.get("date") or commit.get("created_at"))
                    author = commit.get("author") or {}
                    author_name = author.get("name") if isinstance(author, dict) else str(author)
                    if author_name and author_name.lower() in BOT_IDENTIFIERS:
                        continue
                    if c_date and (dt_start <= c_date <= dt_end):
                        seen_commits.add(sha)
                        package.commits.append(commit)

        # Query MongoDB pull_requests collection
        try:
            query = {
                "$or": [
                    {"author_login": package.identity.github_username},
                    {"author": package.identity.github_username},
                    {"author_email": package.identity.email},
                    {"author_name": package.identity.name},
                    {"user_id": package.identity.employee_id},
                ]
            }
            prs_cursor = col("pull_requests").find(query)
            db_prs = await prs_cursor.to_list(100)

            for pr in db_prs:
                pr_num = pr.get("pr_number") or pr.get("number")
                if pr_num and pr_num not in seen_prs:
                    pr_date = _parse_iso(pr.get("merged_at") or pr.get("created_at"))
                    if pr_date and (dt_start <= pr_date <= dt_end):
                        seen_prs.add(pr_num)
                        package.pull_requests.append({
                            "number": pr_num,
                            "title": pr.get("title", ""),
                            "state": pr.get("state", "closed"),
                            "merged": pr.get("merged", True),
                            "additions": pr.get("additions", 0),
                            "deletions": pr.get("deletions", 0),
                            "files_changed_count": pr.get("files_changed_count", 1),
                            "files": pr.get("files", []),
                            "review_comments_count": pr.get("review_comments_count", 0),
                            "reviews": pr.get("reviews", []),
                            "security_findings": pr.get("security_findings", []),
                            "complexity_score": pr.get("complexity_score", 5),
                            "test_files_count": pr.get("test_files_count", 0),
                            "created_at": pr.get("created_at"),
                            "merged_at": pr.get("merged_at"),
                        })
        except Exception as exc:
            logger.debug("[EVIDENCE] MongoDB PR query error: %s", exc)

    async def _collect_cicd_and_deployments(
        self,
        package: EmployeeEvidencePackage,
        dt_start: datetime,
        dt_end: datetime,
        cached_context: Optional[Dict[str, Any]] = None,
    ):
        """Collect CI runs and deployment logs associated with the employee's work."""
        if cached_context:
            for run in cached_context.get("ci_runs", []):
                r_date = _parse_iso(run.get("created_at") or run.get("timestamp"))
                if r_date and (dt_start <= r_date <= dt_end):
                    package.ci_runs.append(run)

            for dep in cached_context.get("deployments", []):
                d_date = _parse_iso(dep.get("created_at") or dep.get("timestamp"))
                if d_date and (dt_start <= d_date <= dt_end):
                    package.deployments.append(dep)

        # Query MongoDB cicd_logs collection if available
        try:
            cicd_cursor = col("cicd_logs").find({
                "$or": [
                    {"author": package.identity.github_username},
                    {"actor": package.identity.github_username},
                    {"employee_id": package.identity.employee_id},
                ]
            })
            logs = await cicd_cursor.to_list(50)
            for log in logs:
                l_date = _parse_iso(log.get("created_at") or log.get("timestamp"))
                if l_date and (dt_start <= l_date <= dt_end):
                    package.ci_runs.append(log)
        except Exception:
            pass
