"""
Webhook Event Processor â€” Real-time event processing pipeline.

This is the CORE of Phase 1.1: transforms webhook events into intelligence-driven actions.

Pipeline:
  1. Receive webhook event â†’ Create WebhookEvent record
  2. Parse event â†’ Extract entities (PR, commit, review)
  3. Trigger intelligence analysis â†’ Risk detection
  4. Generate recommendations â†’ Role-aware AI
  5. Send notifications â†’ Event-driven coordination
  6. Update traceability graph â†’ Link entities

This addresses Critical Gaps #1, #4, #5, #6 from the vision analysis.
"""

import uuid
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from domain.models.webhook_event import WebhookEvent
from repositories.webhook_event_repository import WebhookEventRepository
from repositories.pr_repository import PRRepository
from repositories.project_repository import ProjectRepository
from repositories.user_repository import UserRepository
from domain.services.github_service import GitHubService
from domain.services.enhanced_notification_service import EnhancedNotificationService as NotificationService
from domain.services.traceability_service import TraceabilityService
from domain.services.recommendation_engine import RecommendationEngine
from intelligence.risk_engine import RiskEngine
import logging

logger = logging.getLogger(__name__)


class WebhookEventProcessor:
    """
    Real-time webhook event processor.
    
    Orchestrates the complete pipeline from webhook receipt to notifications.
    """
    
    def __init__(self):
        self.event_repo = WebhookEventRepository()
        self.pr_repo = PRRepository()
        self.project_repo = ProjectRepository()
        self.user_repo = UserRepository()
        self.github_service = GitHubService()
        self.notification_service = NotificationService()
        self.risk_engine = RiskEngine()
        self.traceability_service = TraceabilityService()
        self.recommendation_engine = RecommendationEngine()
    
    async def _get_project_team_lead(self, project_id: str) -> Optional[str]:
        """
        Look up the team lead for a project.
        
        Chain: Project -> team_id -> Team -> team_lead_id
        Returns: employee_id of the team lead, or None
        """
        try:
            project = await self.project_repo.find_by_id(project_id)
            if not project:
                return None
            
            team_id = project.get("team_id")
            if not team_id:
                return None
            
            from core.database import col
            team = await col("teams").find_one({"id": team_id})
            if not team:
                return None
            
            return team.get("team_lead_id")
        except Exception as e:
            logger.warning(f"Error looking up team lead for project {project_id}: {e}")
            return None
    
    async def _get_project_devops_members(self, project_id: str) -> List[str]:
        """
        Look up DevOps team members for a project.
        
        Returns: list of employee_ids with DEVOPS role on the project's team
        """
        try:
            project = await self.project_repo.find_by_id(project_id)
            if not project:
                return []
            
            team_id = project.get("team_id")
            if not team_id:
                return []
            
            members = await self.user_repo.find_by_team(team_id)
            return [m["employee_id"] for m in members if m.get("role", "").upper() == "DEVOPS"]
        except Exception as e:
            logger.warning(f"Error looking up DevOps members for project {project_id}: {e}")
            return []
    
    async def process_github_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        signature: str
    ) -> Dict[str, Any]:
        """
        Main entry point for GitHub webhook processing.
        
        Args:
            event_type: GitHub event type (X-GitHub-Event header)
            payload: Parsed JSON payload
            signature: Webhook signature (already verified)
        
        Returns:
            Processing result with event ID and status
        """
        # Create webhook event record
        event_id = f"WH-{uuid.uuid4().hex[:8].upper()}"
        event_action = payload.get("action", "")
        
        # Extract repository info
        repo_data = payload.get("repository", {})
        repository = repo_data.get("full_name", "unknown/unknown")
        
        # Try to match to a Samanvaya project
        project_id = await self._match_repository_to_project(repository)
        
        webhook_event = WebhookEvent(
            id=event_id,
            event_type=event_type,
            event_action=event_action,
            source="github",
            repository=repository,
            project_id=project_id,
            payload=payload,
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        # Save event to database
        await self.event_repo.insert(webhook_event.dict())
        
        logger.info(f"Webhook event {event_id} created: {event_type}.{event_action} from {repository}")
        
        # Process asynchronously (don't block webhook response)
        asyncio.create_task(self._process_event_async(event_id))
        
        return {
            "event_id": event_id,
            "status": "accepted",
            "message": "Event queued for processing"
        }
    
    async def _process_event_async(self, event_id: str) -> None:
        """
        Process webhook event asynchronously.
        
        This is where the real work happens:
        - Risk analysis
        - AI recommendations
        - Notifications
        - Traceability updates
        """
        try:
            # Mark as processing
            now = datetime.now(timezone.utc).isoformat()
            await self.event_repo.mark_processing(event_id, now)
            
            # Load event
            event_data = await self.event_repo.find_by_id(event_id)
            if not event_data:
                logger.error(f"Event {event_id} not found")
                return
            
            event = WebhookEvent(**event_data)
            
            # Route to appropriate handler
            handler = self._get_event_handler(event.event_type)
            if not handler:
                logger.warning(f"No handler for event type: {event.event_type}")
                await self.event_repo.mark_completed(
                    event_id, datetime.now(timezone.utc).isoformat(),
                    triggers_executed=[],
                    risks_detected=[],
                    notifications_sent=[],
                    recommendations_created=[]
                )
                return
            
            # Process event
            result = await handler(event)
            
            # Mark as completed
            await self.event_repo.mark_completed(
                event_id,
                datetime.now(timezone.utc).isoformat(),
                triggers_executed=result.get("triggers_executed", []),
                risks_detected=result.get("risks_detected", []),
                notifications_sent=result.get("notifications_sent", []),
                recommendations_created=result.get("recommendations_created", [])
            )
            
            logger.info(f"Event {event_id} processed successfully")
            
        except Exception as e:
            logger.error(f"Error processing event {event_id}: {str(e)}", exc_info=True)
            await self.event_repo.mark_failed(event_id, str(e))
    
    def _get_event_handler(self, event_type: str):
        """Get handler function for event type."""
        handlers = {
            "pull_request": self._handle_pull_request_event,
            "push": self._handle_push_event,
            "pull_request_review": self._handle_review_event,
            "pull_request_review_comment": self._handle_review_comment_event,
            "issues": self._handle_issues_event,
            "issue_comment": self._handle_issue_comment_event,
            "deployment": self._handle_deployment_event,
            "deployment_status": self._handle_deployment_status_event,
            "workflow_run": self._handle_workflow_run_event,
            "check_run": self._handle_check_run_event,
        }
        return handlers.get(event_type)
    
    async def _handle_pull_request_event(
        self, event: WebhookEvent
    ) -> Dict[str, Any]:
        """
        Handle pull_request events - the most important for intelligence pipeline.
        
        Actions:
        - opened: Sync PR, run risk analysis, trigger AI review, notify team lead
        - synchronize: Update PR, re-analyze, check for new risks
        - closed/merged: Update status, calculate delivery metrics
        - reopened: Re-analyze with fresh context
        """
        payload = event.payload
        action = event.event_action
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})
        
        pr_number = pr.get("number")
        repo_full_name = repo.get("full_name", "")
        owner, repo_name = repo_full_name.split("/") if "/" in repo_full_name else ("", "")
        
        triggers_executed = []
        risks_detected = []
        notifications_sent = []
        recommendations_created = []
        
        # Critical actions that require full intelligence pipeline
        should_analyze = action in ("opened", "synchronize", "reopened")
        
        if should_analyze and event.project_id:
            # Step 1: Sync PR data from GitHub
            logger.info(f"Syncing PR #{pr_number} from {repo_full_name}")
            
            sync_result = await self.github_service.sync_pull_request(
                owner=owner,
                repo=repo_name,
                pr_number=pr_number,
                project_id=event.project_id,
                use_ai=True,
                use_deep_analysis=(action == "opened"),  # Deep analysis on first open
                triggered_by=f"webhook-{action}"
            )
            
            triggers_executed.append("pr_sync")
            triggers_executed.append("risk_analysis")
            
            if sync_result.get("ai_analysis"):
                triggers_executed.append("ai_review")
            
            # Step 2: Extract risk information
            pr_data = sync_result["pr"]
            risk_analysis = sync_result["risk_analysis"]
            ai_analysis = sync_result.get("ai_analysis", {})
            
            risk_level = risk_analysis.get("risk_level", "unknown")
            risk_score = risk_analysis.get("risk_score", 0)
            
            # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # NEW: Phase 1.2 - Build Evidence Graph
            # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            
            # Link PR to Tasks/Stories mentioned in description
            pr_description = pr.get("body", "")
            pr_title = pr.get("title", "")
            
            task_links = await self.traceability_service.link_pr_to_tasks(
                pr_id=pr_data["id"],
                pr_description=pr_description,
                pr_title=pr_title,
                project_id=event.project_id
            )
            
            if task_links:
                triggers_executed.append("task_linking")
                logger.info(f"Linked PR {pr_data['id']} to {len(task_links)} tasks/stories")
            
            # Link PR to modified files
            file_stats = sync_result.get("file_stats", {})
            changed_files = file_stats.get("changed_files", [])
            
            if changed_files:
                file_links = await self.traceability_service.link_pr_to_files(
                    pr_id=pr_data["id"],
                    changed_files=changed_files,
                    repository=repo_full_name
                )
                triggers_executed.append("file_linking")
                logger.info(f"Linked PR {pr_data['id']} to {len(file_links)} files")
            
            # Calculate blast radius
            if action == "opened":
                blast_radius = await self.traceability_service.calculate_blast_radius(
                    pr_id=pr_data["id"],
                    max_hops=2
                )
                triggers_executed.append("blast_radius_analysis")
                
                # If blast radius is large, increase risk
                if blast_radius.total_affected_entities > 10:
                    logger.warning(
                        f"PR {pr_data['id']} has large blast radius: "
                        f"{blast_radius.total_affected_entities} entities affected"
                    )
            
            # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            
            # Step 3: Determine if risks warrant notification
            if risk_level in ("high", "critical") or risk_score >= 70:
                risks_detected.append(f"PR-{pr_data['id']}-risk")
                
                # Step 4: Generate role-aware recommendations (Phase 1.3)
                try:
                    rec_ids = await self.recommendation_engine.generate_pr_recommendations(
                        pr_id=pr_data["id"],
                        pr_data=pr_data,
                        risk_analysis=risk_analysis,
                        ai_analysis=ai_analysis,
                        code_quality_report=sync_result.get("code_quality_report"),
                        project_id=event.project_id
                    )
                    recommendations_created.extend(rec_ids)
                    triggers_executed.append("recommendation_generation")
                    logger.info(f"Generated {len(rec_ids)} recommendations for PR {pr_data['id']}")
                except Exception as e:
                    logger.error(f"Error generating recommendations: {str(e)}")
                
                # Step 5: Send notifications to relevant roles
                notifications = await self._notify_pr_risks(
                    pr_data=pr_data,
                    risk_level=risk_level,
                    risk_score=risk_score,
                    action=action,
                    ai_analysis=ai_analysis,
                    project_id=event.project_id
                )
                notifications_sent.extend(notifications)
            
            elif action == "opened":
                # Even low-risk PRs notify the lead on open
                notifications = await self._notify_pr_opened(
                    pr_data=pr_data,
                    risk_level=risk_level,
                    project_id=event.project_id
                )
                notifications_sent.extend(notifications)
        
        elif action == "closed":
            # Handle PR closed/merged
            merged = pr.get("merged", False)
            
            if merged:
                triggers_executed.append("pr_merged")
                # TODO: Trigger delivery metrics calculation
                # TODO: Update sprint progress
                # TODO: Link to tasks (Phase 1.2)
            else:
                triggers_executed.append("pr_closed")
        
        return {
            "triggers_executed": triggers_executed,
            "risks_detected": risks_detected,
            "notifications_sent": notifications_sent,
            "recommendations_created": recommendations_created
        }
    
    async def _handle_push_event(self, event: WebhookEvent) -> Dict[str, Any]:
        """
        Handle push events.
        
        Actions:
        - Track commit activity
        - Detect hotspot files (frequently changed files)
        - Monitor for direct pushes to main (potential risk)
        """
        payload = event.payload
        ref = payload.get("ref", "")
        commits = payload.get("commits", [])
        pusher = payload.get("pusher", {}).get("name", "unknown")
        
        triggers_executed = ["commit_tracking"]
        risks_detected = []
        notifications_sent = []
        
        # Check if push to main/master without PR (risk signal)
        branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref
        
        if branch in ("main", "master") and event.project_id:
            # Direct push to main - potential risk
            risks_detected.append(f"direct-push-main-{uuid.uuid4().hex[:8]}")
            
            # Look up actual team lead
            team_lead_id = await self._get_project_team_lead(event.project_id)
            
            if team_lead_id:
                notification_id = await self.notification_service.notify(
                    user_id=team_lead_id,
                    notification_type="direct_push_main",
                    title=f"Direct push to {branch}",
                    body=f"{pusher} pushed {len(commits)} commit(s) directly to {branch} branch",
                    link=f"/activity/{event.repository}"
                )
                notifications_sent.append(notification_id["id"])
        
        return {
            "triggers_executed": triggers_executed,
            "risks_detected": risks_detected,
            "notifications_sent": notifications_sent,
            "recommendations_created": []
        }
    
    async def _handle_review_event(self, event: WebhookEvent) -> Dict[str, Any]:
        """
        Handle pull_request_review events.
        
        Actions:
        - Track review status
        - Notify PR author
        - Update PR status based on approvals
        """
        payload = event.payload
        review = payload.get("review", {})
        pr = payload.get("pull_request", {})
        
        reviewer = review.get("user", {}).get("login", "")
        pr_author = pr.get("user", {}).get("login", "")
        pr_number = pr.get("number")
        review_state = review.get("state", "")
        
        notifications_sent = []
        
        # Notify PR author
        if pr_author and pr_author != reviewer:
            state_labels = {
                "approved": "✅ approved",
                "changes_requested": "📄 requested changes on",
                "commented": "💬 commented on",
            }
            label = state_labels.get(review_state, review_state)
            
            notification = await self.notification_service.notify(
                user_id=pr_author,
                notification_type="pr_review_received",
                title=f"PR #{pr_number} reviewed",
                body=f"{reviewer} {label} your PR",
                link=f"/pr/{pr_number}"
            )
            notifications_sent.append(notification["id"])
        
        return {
            "triggers_executed": ["review_tracking"],
            "risks_detected": [],
            "notifications_sent": notifications_sent,
            "recommendations_created": []
        }
    
    async def _handle_review_comment_event(self, event: WebhookEvent) -> Dict[str, Any]:
        """Handle pull_request_review_comment events."""
        # Similar to review but for inline comments
        return {
            "triggers_executed": ["comment_tracking"],
            "risks_detected": [],
            "notifications_sent": [],
            "recommendations_created": []
        }
    
    async def _handle_issues_event(self, event: WebhookEvent) -> Dict[str, Any]:
        """Handle issues events (bug reports)."""
        payload = event.payload
        action = event.event_action
        issue = payload.get("issue", {})
        
        # Track bug creation/updates
        # TODO: Phase 2.1 - Link bugs to PRs/code changes
        
        return {
            "triggers_executed": ["issue_tracking"],
            "risks_detected": [],
            "notifications_sent": [],
            "recommendations_created": []
        }
    
    async def _handle_issue_comment_event(self, event: WebhookEvent) -> Dict[str, Any]:
        """Handle issue_comment events."""
        return {
            "triggers_executed": ["comment_tracking"],
            "risks_detected": [],
            "notifications_sent": [],
            "recommendations_created": []
        }
    
    async def _handle_deployment_event(self, event: WebhookEvent) -> Dict[str, Any]:
        """
        Handle deployment events.
        
        Critical for operational risk tracking.
        """
        payload = event.payload
        deployment = payload.get("deployment", {})
        
        # Track deployment attempts
        # TODO: Phase 2.1 - Link deployments to PRs
        # TODO: Phase 2.3 - Integrate with CI/CD platforms
        
        return {
            "triggers_executed": ["deployment_tracking"],
            "risks_detected": [],
            "notifications_sent": [],
            "recommendations_created": []
        }
    
    async def _handle_deployment_status_event(self, event: WebhookEvent) -> Dict[str, Any]:
        """
        Handle deployment_status events.
        
        Track success/failure of deployments.
        """
        payload = event.payload
        deployment_status = payload.get("deployment_status", {})
        state = deployment_status.get("state", "")
        
        risks_detected = []
        notifications_sent = []
        
        if state == "failure" and event.project_id:
            # Deployment failed - critical risk
            risks_detected.append(f"deployment-failure-{uuid.uuid4().hex[:8]}")
            
            # Look up actual DevOps members
            devops_members = await self._get_project_devops_members(event.project_id)
            
            for member_id in devops_members:
                notification = await self.notification_service.notify(
                    user_id=member_id,
                    notification_type="deployment_failed",
                    title="Deployment Failed",
                    body=f"Deployment failed for {event.repository}",
                    link=f"/deployments/{event.repository}"
                )
                notifications_sent.append(notification["id"])
        
        return {
            "triggers_executed": ["deployment_status_tracking"],
            "risks_detected": risks_detected,
            "notifications_sent": notifications_sent,
            "recommendations_created": []
        }
    
    async def _handle_workflow_run_event(self, event: WebhookEvent) -> Dict[str, Any]:
        """
        Handle workflow_run events (GitHub Actions).
        
        Critical for CI/CD intelligence.
        """
        payload = event.payload
        workflow_run = payload.get("workflow_run", {})
        conclusion = workflow_run.get("conclusion", "")
        
        risks_detected = []
        
        if conclusion == "failure":
            risks_detected.append(f"ci-failure-{uuid.uuid4().hex[:8]}")
        
        return {
            "triggers_executed": ["ci_tracking"],
            "risks_detected": risks_detected,
            "notifications_sent": [],
            "recommendations_created": []
        }
    
    async def _handle_check_run_event(self, event: WebhookEvent) -> Dict[str, Any]:
        """
        Handle check_run events (CI checks).
        """
        payload = event.payload
        check_run = payload.get("check_run", {})
        conclusion = check_run.get("conclusion", "")
        
        risks_detected = []
        
        if conclusion in ("failure", "cancelled", "timed_out"):
            risks_detected.append(f"check-failure-{uuid.uuid4().hex[:8]}")
        
        return {
            "triggers_executed": ["check_tracking"],
            "risks_detected": risks_detected,
            "notifications_sent": [],
            "recommendations_created": []
        }
    
    # Helper methods
    
    async def _match_repository_to_project(
        self, repository: str
    ) -> Optional[str]:
        """
        Match GitHub repository to Samanvaya project.
        
        TODO: Implement proper project-repository mapping in database.
        For now, we'll search for projects with matching repo URL.
        """
        try:
            # Look for project with matching code_repo_url
            projects = await self.project_repo.find_all({})
            
            for project in projects:
                repo_url = project.get("code_repo_url", "")
                if repository in repo_url or repo_url.endswith(repository):
                    return project["id"]
            
            # No match found
            return None
            
        except Exception as e:
            logger.warning(f"Error matching repository to project: {str(e)}")
            return None
    
    async def _notify_pr_risks(
        self,
        pr_data: Dict[str, Any],
        risk_level: str,
        risk_score: int,
        action: str,
        ai_analysis: Dict[str, Any],
        project_id: str
    ) -> List[str]:
        """
        Send notifications for high-risk PRs.
        
        Returns:
            List of notification IDs
        """
        notification_ids = []
        
        # Look up actual team lead for project
        team_lead_id = await self._get_project_team_lead(project_id)
        
        critical_issues = ai_analysis.get("critical_issues", [])
        risk_factors = ai_analysis.get("risk_factors", [])
        
        emoji = "🔴" if risk_level == "critical" else "🟡"
        
        body_parts = [
            f"Risk Score: {risk_score}/100",
        ]
        
        if critical_issues:
            body_parts.append(f"Critical Issues: {len(critical_issues)}")
        
        if risk_factors:
            body_parts.append(f"Risk Factors: {', '.join(risk_factors[:2])}")
        
        # Notify team lead
        if team_lead_id:
            notification = await self.notification_service.notify(
                user_id=team_lead_id,
                notification_type="pr_high_risk",
                title=f"{emoji} High Risk PR #{pr_data.get('number')}",
                body=" | ".join(body_parts),
                link=f"/pr/{pr_data['id']}"
            )
            notification_ids.append(notification["id"])
        
        # Also notify PR author with recommendations
        pr_author = pr_data.get("author")
        if pr_author:
            recommendations = ai_analysis.get("recommendations", [])
            rec_text = recommendations[0] if recommendations else "Review recommended"
            
            notification = await self.notification_service.notify(
                user_id=pr_author,
                notification_type="pr_risk_feedback",
                title=f"âš ï¸ Risk detected in your PR",
                body=f"Recommendation: {rec_text}",
                link=f"/pr/{pr_data['id']}"
            )
            notification_ids.append(notification["id"])
        
        return notification_ids
    
    async def _notify_pr_opened(
        self,
        pr_data: Dict[str, Any],
        risk_level: str,
        project_id: str
    ) -> List[str]:
        """
        Send notifications for newly opened PRs (even low risk).
        """
        notification_ids = []
        
        # Look up actual team lead
        team_lead_id = await self._get_project_team_lead(project_id)
        
        risk_emoji = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🟠",
            "critical": "🔴"
        }
        
        if team_lead_id:
            notification = await self.notification_service.notify(
                user_id=team_lead_id,
                notification_type="pr_opened",
                title=f"New PR #{pr_data.get('number')} opened",
                body=f"{risk_emoji.get(risk_level, '⚪')} Risk: {risk_level} | {pr_data.get('title', 'Untitled')}",
                link=f"/pr/{pr_data['id']}"
            )
            notification_ids.append(notification["id"])
        
        return notification_ids


