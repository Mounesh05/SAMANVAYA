"""
Webhook Event domain model.
Tracks all incoming webhook events and their processing status.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone


class WebhookEvent(BaseModel):
    """
    Webhook event record - tracks processing pipeline.
    """
    
    id: str = Field(..., description="Unique event ID")
    event_type: str = Field(..., description="GitHub event type (pull_request, push, etc.)")
    event_action: Optional[str] = Field(None, description="Event action (opened, closed, etc.)")
    
    # Source information
    source: str = Field(default="github", description="Webhook source (github, gitlab, etc.)")
    repository: str = Field(..., description="Full repo name (owner/repo)")
    project_id: Optional[str] = Field(None, description="Associated Samanvaya project")
    
    # Payload
    payload: Dict[str, Any] = Field(default_factory=dict, description="Raw webhook payload")
    
    # Processing status
    status: str = Field(default="pending", description="pending|processing|completed|failed")
    processing_started_at: Optional[str] = Field(None, description="When processing started")
    processing_completed_at: Optional[str] = Field(None, description="When processing completed")
    
    # Processing results
    triggers_executed: List[str] = Field(default_factory=list, description="List of triggers executed")
    risks_detected: List[str] = Field(default_factory=list, description="Risk IDs detected")
    notifications_sent: List[str] = Field(default_factory=list, description="Notification IDs sent")
    recommendations_created: List[str] = Field(default_factory=list, description="Recommendation IDs created")
    
    # Error tracking
    error: Optional[str] = Field(None, description="Error message if failed")
    retry_count: int = Field(default=0, description="Number of retry attempts")
    
    # Metadata
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Event received timestamp"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "WH-ABC123",
                "event_type": "pull_request",
                "event_action": "opened",
                "source": "github",
                "repository": "acme/backend",
                "project_id": "PROJ-001",
                "status": "completed",
                "triggers_executed": ["risk_analysis", "ai_review", "notification"],
                "risks_detected": ["RISK-001"],
                "notifications_sent": ["NOTIF-001", "NOTIF-002"],
                "created_at": "2026-09-01T10:00:00Z"
            }
        }
