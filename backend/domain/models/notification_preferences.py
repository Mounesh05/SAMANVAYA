"""
Notification Preferences - Phase 1.4

User preferences for notification delivery and aggregation.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum


class DigestFrequency(str, Enum):
    """How often to aggregate notifications."""
    IMMEDIATE = "immediate"      # No aggregation, send immediately
    HOURLY = "hourly"           # Aggregate into hourly digest
    DAILY = "daily"             # Once per day digest
    WEEKLY = "weekly"           # Weekly summary


class NotificationPreferences(BaseModel):
    """User notification preferences."""
    
    user_id: str
    
    # Channel preferences (in-app only)
    enable_in_app: bool = Field(default=True, description="In-app notifications")
    
    # Digest settings
    digest_frequency: DigestFrequency = Field(
        default=DigestFrequency.IMMEDIATE,
        description="Notification aggregation frequency"
    )
    digest_time_utc: Optional[str] = Field(
        default="09:00",
        description="Time for daily/weekly digest (HH:MM UTC)"
    )
    
    # Priority filtering
    min_priority: str = Field(
        default="normal",
        description="Minimum priority to notify (urgent, high, normal, low)"
    )
    
    # Category filters
    mute_categories: List[str] = Field(
        default_factory=list,
        description="Notification categories to mute"
    )
    
    # Do Not Disturb
    dnd_enabled: bool = Field(default=False, description="Do Not Disturb mode")
    dnd_start_utc: Optional[str] = Field(default="22:00", description="DND start time (HH:MM UTC)")
    dnd_end_utc: Optional[str] = Field(default="08:00", description="DND end time (HH:MM UTC)")
    
    # Role-specific overrides
    role_overrides: Dict[str, Any] = Field(
        default_factory=dict,
        description="Role-specific notification settings"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "EMP-001",
                "enable_in_app": True,
                "digest_frequency": "immediate",
                "min_priority": "normal",
                "mute_categories": ["pr_opened"],
                "dnd_enabled": True,
                "dnd_start_utc": "22:00",
                "dnd_end_utc": "08:00"
            }
        }
