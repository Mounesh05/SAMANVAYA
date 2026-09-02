"""
Webhook Service — processes incoming GitHub webhook events.
Auto-syncs PRs, logs commits, and triggers AI code review.
"""

import hmac
import hashlib
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from core.config import settings
from domain.services.notification_service import NotificationService
from repositories.activity_repository import ActivityRepository
from repositories.pr_repository import PRRepository

logger = logging.getLogger(__name__)


class WebhookService:
    """Processes GitHub webhook payloads."""
    
    def __init__(self):
        self.notification_service = NotificationService()
        self.activity_repo = ActivityRepository()
        self.pr_repo = PRRepository()
    
    @staticmethod
    def verify_signature(payload_body: bytes, signature: str) -> bool:
        """
        Verify GitHub webhook signature using HMAC-SHA256.
        
        Args:
            payload_body: Raw request body bytes
            signature: X-Hub-Signature-256 header value
        
        Returns:
            True if signature is valid
        """
        secret = settings.GITHUB_WEBHOOK_SECRET
        if not secret:
            logger.warning("GITHUB_WEBHOOK_SECRET not configured — webhook signature verification disabled")
            return True
        
        expected = "sha256=" + hmac.new(
            secret.encode("utf-8"),
            payload_body,
            hashlib.sha256,
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)
    
    async def process_event(
        self, event_type: str, payload: dict
    ) -> dict:
        """
        Route a GitHub webhook event to the appropriate handler.
        
        Args:
            event_type: GitHub event type (X-GitHub-Event header)
            payload: Parsed JSON payload
        
        Returns:
            Processing result dict
        """
        handlers = {
            "pull_request": self._handle_pull_request,
            "push": self._handle_push,
            "pull_request_review": self._handle_review,
        }
        
        handler = handlers.get(event_type)
        if not handler:
            return {"status": "ignored", "event": event_type}
        
        return await handler(payload)
    
    async def _handle_pull_request(self, payload: dict) -> dict:
        """
        Handle pull_request events (opened, closed, merged, synchronize).
        Auto-syncs PR data and optionally triggers AI review.
        """
        action = payload.get("action", "")
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})
        
        pr_number = pr.get("number")
        repo_full_name = repo.get("full_name", "")
        owner, repo_name = repo_full_name.split("/") if "/" in repo_full_name else ("", "")
        pr_title = pr.get("title", "")
        pr_author = pr.get("user", {}).get("login", "")
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Normalize PR data for storage
        pr_data = {
            "id": f"PR-{pr_number}-{repo_name}",
            "number": pr_number,
            "title": pr_title,
            "author": pr_author,
            "state": pr.get("state"),
            "merged": pr.get("merged", False),
            "repo_owner": owner,
            "repo_name": repo_name,
            "url": pr.get("html_url"),
            "created_at": pr.get("created_at"),
            "updated_at": now,
            "action": action,
        }
        
        # Upsert PR data
        await self.pr_repo.upsert(
            {"id": pr_data["id"]},
            pr_data,
        )
        
        # Log activity
        event_summary = {
            "opened": f"{pr_author} opened PR #{pr_number}: {pr_title}",
            "closed": f"PR #{pr_number} was closed: {pr_title}",
            "merged": f"PR #{pr_number} was merged: {pr_title}",
            "synchronize": f"{pr_author} pushed to PR #{pr_number}: {pr_title}",
            "reopened": f"PR #{pr_number} was reopened: {pr_title}",
        }
        
        await self.activity_repo.insert({
            "id": f"ACT-{uuid.uuid4().hex[:8].upper()}",
            "event_type": f"pr_{action}",
            "item_type": "pr",
            "item_id": pr_data["id"],
            "actor_id": pr_author,
            "actor_name": pr_author,
            "summary": event_summary.get(action, f"PR #{pr_number} {action}"),
            "details": {"pr_number": pr_number, "repo": repo_full_name, "action": action},
            "created_at": now,
        })
        
        # Trigger AI review on new/updated PRs
        should_review = action in ("opened", "synchronize", "reopened")
        
        if should_review:
            try:
                from domain.services.github_service import GitHubService
                github_service = GitHubService()
                await github_service.sync_pull_request(
                    owner=owner,
                    repo=repo_name,
                    pr_number=pr_number,
                    project_id=f"webhook-{repo_name}",
                    use_ai=True,
                    use_deep_analysis=False,
                    triggered_by=f"webhook-{action}",
                )
            except Exception:
                pass  # Non-critical — PR data is already saved
        
        return {
            "status": "processed",
            "event": "pull_request",
            "action": action,
            "pr_number": pr_number,
            "ai_review_triggered": should_review,
        }
    
    async def _handle_push(self, payload: dict) -> dict:
        """Handle push events — log commit activity."""
        repo = payload.get("repository", {})
        pusher = payload.get("pusher", {}).get("name", "unknown")
        commits = payload.get("commits", [])
        ref = payload.get("ref", "")
        branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref
        
        now = datetime.now(timezone.utc).isoformat()
        
        await self.activity_repo.insert({
            "id": f"ACT-{uuid.uuid4().hex[:8].upper()}",
            "event_type": "push",
            "item_type": "commit",
            "actor_id": pusher,
            "actor_name": pusher,
            "summary": f"{pusher} pushed {len(commits)} commit(s) to {branch}",
            "details": {
                "branch": branch,
                "commit_count": len(commits),
                "repo": repo.get("full_name"),
                "commits": [
                    {"sha": c.get("id", "")[:7], "message": c.get("message", "")[:100]}
                    for c in commits[:5]  # limit to 5 for storage
                ],
            },
            "created_at": now,
        })
        
        return {
            "status": "processed",
            "event": "push",
            "branch": branch,
            "commits": len(commits),
        }
    
    async def _handle_review(self, payload: dict) -> dict:
        """Handle pull_request_review events — track review status + notify."""
        action = payload.get("action", "")
        review = payload.get("review", {})
        pr = payload.get("pull_request", {})
        
        reviewer = review.get("user", {}).get("login", "")
        pr_author = pr.get("user", {}).get("login", "")
        pr_number = pr.get("number")
        review_state = review.get("state", "")  # approved, changes_requested, commented
        
        now = datetime.now(timezone.utc).isoformat()
        
        await self.activity_repo.insert({
            "id": f"ACT-{uuid.uuid4().hex[:8].upper()}",
            "event_type": "pr_reviewed",
            "item_type": "pr",
            "item_id": f"PR-{pr_number}",
            "actor_id": reviewer,
            "actor_name": reviewer,
            "summary": f"{reviewer} {review_state.replace('_', ' ')} PR #{pr_number}",
            "details": {
                "pr_number": pr_number,
                "review_state": review_state,
                "reviewer": reviewer,
            },
            "created_at": now,
        })
        
        # Notify PR author about the review
        if pr_author and pr_author != reviewer:
            state_labels = {
                "approved": "approved",
                "changes_requested": "requested changes on",
                "commented": "commented on",
            }
            label = state_labels.get(review_state, review_state)
            
            await self.notification_service.notify(
                user_id=pr_author,
                notification_type="pr_review_received",
                title=f"PR #{pr_number} reviewed",
                body=f"{reviewer} {label} your PR #{pr_number}: {pr.get('title', '')}",
                link=f"/pr/{pr_number}",
            )
        
        return {
            "status": "processed",
            "event": "pull_request_review",
            "action": action,
            "review_state": review_state,
        }
