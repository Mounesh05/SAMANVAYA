"""
GitHub Webhooks API endpoint.
Receives and processes GitHub webhook events securely.

Setup in GitHub:
  1. Go to repo → Settings → Webhooks → Add webhook
  2. Payload URL: https://your-domain.com/api/webhooks/github
  3. Content type: application/json
  4. Secret: set GITHUB_WEBHOOK_SECRET in your .env
  5. Events: Pull requests, Pushes, Pull request reviews
"""

import json
from fastapi import APIRouter, HTTPException, Request, Header
from domain.services.webhook_service import WebhookService

router = APIRouter()
webhook_service = WebhookService()


@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
):
    """
    Receive GitHub webhook events.

    Supported events:
    - pull_request (opened, closed, merged, synchronize, reopened)
    - push
    - pull_request_review (approved, changes_requested, commented)

    Security: validates X-Hub-Signature-256 HMAC signature.
    """
    if not x_github_event:
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Event header")

    # Read raw body for HMAC verification
    body_bytes = await request.body()

    # Verify signature
    sig = x_hub_signature_256 or ""
    if not webhook_service.verify_signature(body_bytes, sig):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Parse payload
    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Process event
    result = await webhook_service.process_event(x_github_event, payload)
    return result


@router.get("/github/health")
async def webhook_health():
    """Check webhook endpoint is reachable (useful for GitHub ping event)."""
    from core.config import settings
    return {
        "status": "ready",
        "secret_configured": bool(settings.GITHUB_WEBHOOK_SECRET),
        "supported_events": ["pull_request", "push", "pull_request_review"],
    }
