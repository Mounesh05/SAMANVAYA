"""
Developer Data Aggregator
Collects all data for a specific developer in a given period.
Pure data collection - no analysis, just aggregation.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from integrations.github.client import GitHubClient
from repositories.pr_repository import PRRepository
from repositories.task_repository import TaskRepository
from repositories.sprint_repository import SprintRepository


class DeveloperDataAggregator:
    """
    Aggregates all developer activity data from multiple sources.
    
    This is PURE DATA COLLECTION - no scoring, no analysis.
    Just collect everything the AI needs to evaluate.
    """
    
    def __init__(self, github_token: Optional[str] = None):
        self.github_client = GitHubClient(token=github_token)
        self.pr_repo = PRRepository()
        self.task_repo = TaskRepository()
        self.sprint_repo = SprintRepository()
    
    async def aggregate_developer_data(
        self,
        developer_id: str,
        developer_email: str,
        project_id: str,
        period_start: datetime,
        period_end: datetime,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Collect ALL data for a developer in the given period.
        
        Returns comprehensive evidence package with:
        - GitHub commits (with diffs)
        - Pull requests (with conversations)
        - CI/CD logs
        - Tasks and stories
        - Bugs introduced/fixed
        - Sprint contributions
        
        Args:
            developer_id: User ID
            developer_email: GitHub email for commit matching
            project_id: Project ID
            period_start: Start of evaluation period
            period_end: End of evaluation period
            repo_owner: GitHub repo owner (optional)
            repo_name: GitHub repo name (optional)
        
        Returns:
            Complete evidence package (dict)
        """
        
        evidence = {
            "developer_id": developer_id,
            "developer_email": developer_email,
            "project_id": project_id,
            "period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat(),
            },
            "data_collected_at": datetime.now(timezone.utc).isoformat(),
            
            # Will be populated
            "commits": [],
            "pull_requests": [],
            "ci_cd_logs": [],
            "tasks": [],
            "bugs": [],
            "code_reviews": [],
            "sprint_contributions": [],
            
            # Summary stats
            "summary": {
                "total_commits": 0,
                "total_prs": 0,
                "total_tasks": 0,
                "total_reviews_given": 0,
                "lines_added": 0,
                "lines_deleted": 0,
            }
        }
        
        # Collect from each source
        if repo_owner and repo_name:
            # GitHub data
            commits_data = await self._collect_github_commits(
                repo_owner, repo_name, developer_email, period_start, period_end
            )
            evidence["commits"] = commits_data["commits"]
            evidence["summary"]["total_commits"] = len(commits_data["commits"])
            evidence["summary"]["lines_added"] = commits_data["total_lines_added"]
            evidence["summary"]["lines_deleted"] = commits_data["total_lines_deleted"]
            
            # Pull requests
            prs_data = await self._collect_pull_requests(
                repo_owner, repo_name, developer_email, period_start, period_end
            )
            evidence["pull_requests"] = prs_data["prs"]
            evidence["summary"]["total_prs"] = len(prs_data["prs"])
            
            # Code reviews given
            reviews_data = await self._collect_code_reviews(
                repo_owner, repo_name, developer_email, period_start, period_end
            )
            evidence["code_reviews"] = reviews_data["reviews"]
            evidence["summary"]["total_reviews_given"] = len(reviews_data["reviews"])
        
        # Project management data
        tasks_data = await self._collect_tasks(
            developer_id, project_id, period_start, period_end
        )
        evidence["tasks"] = tasks_data["tasks"]
        evidence["summary"]["total_tasks"] = len(tasks_data["tasks"])
        
        # Bug data
        bugs_data = await self._collect_bugs(
            developer_id, project_id, period_start, period_end
        )
        evidence["bugs"] = bugs_data
        
        # Sprint contributions
        sprint_data = await self._collect_sprint_contributions(
            developer_id, project_id, period_start, period_end
        )
        evidence["sprint_contributions"] = sprint_data
        
        return evidence
    
    async def _collect_github_commits(
        self,
        owner: str,
        repo: str,
        author_email: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Collect commits with full diffs for AI to read.
        
        Returns commits with:
        - Commit message
        - Full diff (actual code changes)
        - Files changed
        - Stats (additions, deletions)
        """
        try:
            # Get commits by author in date range
            commits = await self.github_client.get_commits(
                owner, repo,
                author=author_email,
                since=start_date.isoformat(),
                until=end_date.isoformat()
            )
            
            commits_data = []
            total_lines_added = 0
            total_lines_deleted = 0
            
            for commit in commits[:50]:  # Limit to recent 50 commits
                sha = commit["sha"]
                
                # Get full commit details with diff
                commit_detail = await self.github_client.get_commit(owner, repo, sha)
                
                # Extract diff
                files_changed = []
                for file in commit_detail.get("files", []):
                    files_changed.append({
                        "filename": file["filename"],
                        "status": file["status"],
                        "additions": file["additions"],
                        "deletions": file["deletions"],
                        "patch": file.get("patch", ""),  # The actual diff!
                    })
                    total_lines_added += file["additions"]
                    total_lines_deleted += file["deletions"]
                
                commits_data.append({
                    "sha": sha,
                    "message": commit["commit"]["message"],
                    "author": commit["commit"]["author"]["name"],
                    "date": commit["commit"]["author"]["date"],
                    "files_changed": files_changed,
                    "stats": commit_detail["stats"],
                })
            
            return {
                "commits": commits_data,
                "total_lines_added": total_lines_added,
                "total_lines_deleted": total_lines_deleted
            }
            
        except Exception as e:
            print(f"Error collecting commits: {e}")
            return {"commits": [], "total_lines_added": 0, "total_lines_deleted": 0}
    
    async def _collect_pull_requests(
        self,
        owner: str,
        repo: str,
        author_email: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Collect PRs with full conversations for AI to read.
        
        Returns PRs with:
        - PR description
        - All comments and review conversations
        - Review decisions
        - Files changed
        """
        try:
            # Get PRs from database (already synced)
            repo_id = f"{owner}/{repo}"
            prs = await self.pr_repo.find_by_date_range(
                repo_id, start_date, end_date
            )
            
            prs_data = []
            for pr in prs:
                # Get PR comments and reviews from GitHub
                pr_number = pr.get("pr_number")
                
                try:
                    # Get review comments
                    comments = await self.github_client.get_pr_comments(
                        owner, repo, pr_number
                    )
                    
                    # Get reviews
                    reviews = await self.github_client.get_pr_reviews(
                        owner, repo, pr_number
                    )
                    
                    prs_data.append({
                        "number": pr_number,
                        "title": pr.get("title"),
                        "description": pr.get("description", ""),
                        "state": pr.get("state"),
                        "created_at": pr.get("created_at"),
                        "merged_at": pr.get("merged_at"),
                        "comments": comments,
                        "reviews": reviews,
                        "files_changed": pr.get("files_changed_count", 0),
                        "lines_added": pr.get("lines_added", 0),
                        "lines_deleted": pr.get("lines_deleted", 0),
                    })
                except Exception:
                    # If can't fetch details, use basic info
                    prs_data.append({
                        "number": pr_number,
                        "title": pr.get("title"),
                        "description": pr.get("description", ""),
                        "state": pr.get("state"),
                        "files_changed": pr.get("files_changed_count", 0),
                    })
            
            return {"prs": prs_data}
            
        except Exception as e:
            print(f"Error collecting PRs: {e}")
            return {"prs": []}
    
    async def _collect_code_reviews(
        self,
        owner: str,
        repo: str,
        reviewer_email: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Collect code reviews given by the developer.
        
        Returns reviews with:
        - PR reviewed
        - Review comments
        - Approval/changes requested
        """
        try:
            # This would need custom GitHub API call to filter by reviewer
            # For now, return empty - can be enhanced later
            reviews = []
            
            return {"reviews": reviews}
            
        except Exception as e:
            print(f"Error collecting reviews: {e}")
            return {"reviews": []}
    
    async def _collect_tasks(
        self,
        developer_id: str,
        project_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Collect tasks completed by developer.
        
        Returns tasks with:
        - Task description
        - Story points
        - Completion status
        - Time taken
        """
        try:
            tasks = await self.task_repo.find_by_assignee_and_date(
                developer_id, start_date, end_date
            )
            
            tasks_data = []
            for task in tasks:
                tasks_data.append({
                    "id": task.get("id"),
                    "title": task.get("title"),
                    "description": task.get("description", ""),
                    "status": task.get("status"),
                    "story_points": task.get("story_points", 0),
                    "priority": task.get("priority", "medium"),
                    "created_at": task.get("created_at"),
                    "completed_at": task.get("completed_at"),
                    "time_spent_hours": task.get("time_spent_hours", 0),
                })
            
            return {"tasks": tasks_data}
            
        except Exception as e:
            print(f"Error collecting tasks: {e}")
            return {"tasks": []}
    
    async def _collect_bugs(
        self,
        developer_id: str,
        project_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Collect bugs introduced and fixed by developer.
        
        Returns:
        - Bugs introduced (found to be caused by this developer)
        - Bugs fixed (resolved by this developer)
        """
        try:
            # This would need bug tracking integration
            # For now, return structure - can be enhanced later
            bugs_introduced = []
            bugs_fixed = []
            
            return {
                "bugs_introduced": bugs_introduced,
                "bugs_fixed": bugs_fixed,
                "bugs_introduced_count": len(bugs_introduced),
                "bugs_fixed_count": len(bugs_fixed),
            }
            
        except Exception as e:
            print(f"Error collecting bugs: {e}")
            return {
                "bugs_introduced": [],
                "bugs_fixed": [],
                "bugs_introduced_count": 0,
                "bugs_fixed_count": 0,
            }
    
    async def _collect_sprint_contributions(
        self,
        developer_id: str,
        project_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Collect sprint-level contributions.
        
        Returns:
        - Sprints participated in
        - Story points completed
        - Tasks completed
        """
        try:
            sprints = await self.sprint_repo.find_by_date_range(
                project_id, start_date, end_date
            )
            
            sprint_data = []
            for sprint in sprints:
                # Get developer's tasks in this sprint
                sprint_tasks = await self.task_repo.find_by_sprint_and_assignee(
                    sprint.get("id"), developer_id
                )
                
                completed_tasks = [t for t in sprint_tasks if t.get("status") == "completed"]
                total_points = sum(t.get("story_points", 0) for t in completed_tasks)
                
                sprint_data.append({
                    "sprint_id": sprint.get("id"),
                    "sprint_name": sprint.get("name"),
                    "tasks_assigned": len(sprint_tasks),
                    "tasks_completed": len(completed_tasks),
                    "story_points_completed": total_points,
                })
            
            return {
                "sprints": sprint_data,
                "total_sprints": len(sprint_data),
            }
            
        except Exception as e:
            print(f"Error collecting sprint contributions: {e}")
            return {"sprints": [], "total_sprints": 0}
    
    def _format_for_ai(self, evidence: Dict[str, Any]) -> str:
        """
        Format evidence package as readable text for AI.
        
        This converts the structured data into a text format
        that AI can easily read and understand.
        """
        output = []
        
        output.append("=" * 60)
        output.append(f"DEVELOPER PERFORMANCE DATA")
        output.append("=" * 60)
        output.append(f"Developer ID: {evidence['developer_id']}")
        output.append(f"Period: {evidence['period']['start']} to {evidence['period']['end']}")
        output.append("")
        
        # Summary
        output.append("SUMMARY:")
        summary = evidence['summary']
        output.append(f"  • Commits: {summary['total_commits']}")
        output.append(f"  • Pull Requests: {summary['total_prs']}")
        output.append(f"  • Tasks: {summary['total_tasks']}")
        output.append(f"  • Code Reviews: {summary['total_reviews_given']}")
        output.append(f"  • Lines Added: {summary['lines_added']}")
        output.append(f"  • Lines Deleted: {summary['lines_deleted']}")
        output.append("")
        
        # Commits with diffs
        output.append("=" * 60)
        output.append("COMMITS & CODE CHANGES:")
        output.append("=" * 60)
        for commit in evidence['commits'][:10]:  # First 10
            output.append(f"\nCommit: {commit['sha'][:8]}")
            output.append(f"Date: {commit['date']}")
            output.append(f"Message: {commit['message']}")
            output.append(f"Files changed: {len(commit['files_changed'])}")
            for file in commit['files_changed'][:3]:  # First 3 files
                output.append(f"\n  File: {file['filename']}")
                output.append(f"  +{file['additions']} -{file['deletions']}")
                if file['patch']:
                    output.append(f"  Diff:\n{file['patch'][:500]}")  # First 500 chars
        
        # Pull Requests
        output.append("\n" + "=" * 60)
        output.append("PULL REQUESTS:")
        output.append("=" * 60)
        for pr in evidence['pull_requests'][:5]:  # First 5
            output.append(f"\nPR #{pr['number']}: {pr['title']}")
            output.append(f"Description: {pr['description'][:200]}")
            output.append(f"State: {pr['state']}")
            output.append(f"Files: {pr['files_changed']}")
        
        # Tasks
        output.append("\n" + "=" * 60)
        output.append("TASKS COMPLETED:")
        output.append("=" * 60)
        for task in evidence['tasks'][:10]:
            output.append(f"\nTask: {task['title']}")
            output.append(f"Status: {task['status']}")
            output.append(f"Story Points: {task['story_points']}")
            output.append(f"Description: {task['description'][:100]}")
        
        return "\n".join(output)
