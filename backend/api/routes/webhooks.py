"""
GitHub Webhooks API endpoint.
Receives and processes GitHub webhook events securely.

Setup in GitHub:
  1. Go to repo -> Settings -> Webhooks -> Add webhook
  2. Payload URL: https://your-domain.com/api/webhooks/github
  3. Content type: application/json
  4. Secret: set GITHUB_WEBHOOK_SECRET in your .env
  5. Events: Pull requests, Pushes, Pull request reviews, Deployments, Workflow runs

UPDATED: Now uses WebhookEventProcessor for real-time intelligence pipeline.
"""

import json
from fastapi import APIRouter, HTTPException, Request, Header, BackgroundTasks
from domain.services.webhook_service import WebhookService
from domain.services.webhook_event_processor import WebhookEventProcessor
import logging

router = APIRouter()
webhook_service = WebhookService()
event_processor = WebhookEventProcessor()
logger = logging.getLogger(__name__)


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
):
    """
    Receive GitHub webhook events and process through intelligence pipeline.

    Supported events:
    - pull_request (opened, closed, merged, synchronize, reopened)
    - push
    - pull_request_review (approved, changes_requested, commented)
    - pull_request_review_comment
    - issues (opened, closed, labeled)
    - issue_comment
    - deployment
    - deployment_status
    - workflow_run (GitHub Actions)
    - check_run (CI checks)

    Security: validates X-Hub-Signature-256 HMAC signature.
    
    Processing:
    - Event is immediately accepted and queued
    - Real-time processing pipeline runs asynchronously:
      1. Risk analysis
      2. AI recommendations
      3. Role-based notifications
      4. Traceability updates
    """
    if not x_github_event:
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Event header")

    # Read raw body for HMAC verification
    body_bytes = await request.body()

    # Verify signature
    sig = x_hub_signature_256 or ""
    if not webhook_service.verify_signature(body_bytes, sig):
        logger.warning(f"Invalid webhook signature for event {x_github_event}")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Parse payload
    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    logger.info(f"Received GitHub webhook: {x_github_event}.{payload.get('action', '')}")

    # Process event through new intelligence pipeline
    result = await event_processor.process_github_event(
        event_type=x_github_event,
        payload=payload,
        signature=sig
    )
    
    return result


@router.get("/github/health")
async def webhook_health():
    """Check webhook endpoint is reachable (useful for GitHub ping event)."""
    from core.config import settings
    return {
        "status": "ready",
        "secret_configured": bool(settings.GITHUB_WEBHOOK_SECRET),
        "supported_events": [
            "pull_request", "push", "pull_request_review",
            "pull_request_review_comment", "issues", "issue_comment",
            "deployment", "deployment_status", "workflow_run", "check_run"
        ],
        "features": [
            "Real-time risk analysis",
            "AI-powered recommendations",
            "Role-based notifications",
            "Event-driven coordination"
        ]
    }


@router.get("/events")
async def list_webhook_events(
    repository: str = None,
    status: str = None,
    limit: int = 50
):
    """
    List webhook events (for debugging and monitoring).
    
    Args:
        repository: Filter by repository (owner/repo)
        status: Filter by status (pending, processing, completed, failed)
        limit: Max events to return
    """
    from repositories.webhook_event_repository import WebhookEventRepository
    
    repo = WebhookEventRepository()
    
    if repository:
        events = await repo.find_by_repository(repository, limit)
    elif status:
        events = await repo.find_by_status(status, limit)
    else:
        # Get all recent events
        events = await repo.find_by_status("completed", limit)
    
    return {
        "events": events,
        "count": len(events)
    }


@router.get("/events/{event_id}")
async def get_webhook_event(event_id: str):
    """Get detailed information about a specific webhook event."""
    from repositories.webhook_event_repository import WebhookEventRepository
    
    repo = WebhookEventRepository()
    event = await repo.find_by_id(event_id)
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return event
