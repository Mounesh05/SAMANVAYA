"""
GitHub Webhooks API endpoint (Option 1: Primary Automated Integration).
Receives and processes GitHub App & repository webhook events securely.

Supported Events:
- Developer: push, pull_request, pull_request_review
- DevOps: workflow_run, deployment_status, check_run, check_suite
- QA: workflow_run, check_run, check_suite
"""

import json
from fastapi import APIRouter, HTTPException, Request, Header
from domain.services.webhook_service import WebhookService
from core.config import settings

router = APIRouter()
webhook_service = WebhookService()


@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
    x_github_delivery: str = Header(None, alias="X-GitHub-Delivery"),
):
    """
    Receive GitHub webhook events with HMAC-SHA256 signature verification
    and X-GitHub-Delivery deduplication.
    """
    if not x_github_event:
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Event header")

    # Read raw body for constant-time HMAC-SHA256 verification
    body_bytes = await request.body()

    # Verify signature
    sig = x_hub_signature_256 or ""
    if not webhook_service.verify_signature(body_bytes, sig):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Parse JSON payload
    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Process event across Developer, DevOps, or QA pipelines
    result = await webhook_service.process_event(
        event_type=x_github_event,
        payload=payload,
        delivery_id=x_github_delivery,
    )
    return result


@router.get("/github/health")
async def webhook_health():
    """Check webhook endpoint and GitHub App readiness."""
    from integrations.github.app_auth import get_github_app_auth
    app_auth = get_github_app_auth()

    return {
        "status": "ready",
        "secret_configured": bool(settings.GITHUB_WEBHOOK_SECRET),
        "github_app_configured": app_auth.is_configured(),
        "app_id": getattr(settings, "GITHUB_APP_ID", "") or "not_configured",
        "supported_events": [
            "push",
            "pull_request",
            "pull_request_review",
            "workflow_run",
            "deployment_status",
            "check_run",
            "check_suite",
        ],
        "pipelines_supported": ["developer", "devops", "qa"],
    }
