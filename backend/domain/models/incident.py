"""
Incident domain models.

CR-001: anyone with CREATE_INCIDENT reports one.
CR-014: TRIAGE_INCIDENT holders (DevOps, Lead, PM) acknowledge, assign,
re-grade, resolve and close incidents; every step is time-stamped and kept on
the incident's timeline.
"""

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

IncidentSeverity = Literal["low", "medium", "high", "critical"]
IncidentStatus = Literal["open", "investigating", "resolved", "closed"]

# CR-014 lifecycle: acknowledge, resolve, close; a resolved incident can be reopened.
TRANSITIONS: Dict[str, set] = {
    "open": {"investigating"},
    "investigating": {"resolved"},
    "resolved": {"closed", "investigating"},
    "closed": set(),
}
NEEDS_POSTMORTEM = {"high", "critical"}  # D3-A: review before closing
OWNER_ROLES = {"DEVELOPER", "DEVOPS", "LEAD", "QA"}  # D2-A: engineering roles


class IncidentCreate(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=8000)
    severity: IncidentSeverity = "medium"
    service: Optional[str] = Field(default=None, max_length=200)


class TimelineEntry(BaseModel):
    at: str
    by: str
    by_name: str = ""
    action: str
    changes: Dict[str, List[Optional[str]]] = Field(default_factory=dict)  # field: [old, new]
    note: Optional[str] = None


class Incident(IncidentCreate):
    id: str
    status: IncidentStatus = "open"
    reporter_id: str
    reporter_name: str = ""
    created_at: str = ""
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    resolution_summary: Optional[str] = None
    postmortem: Optional[str] = None
    acknowledged_at: Optional[str] = None
    resolved_at: Optional[str] = None
    closed_at: Optional[str] = None
    timeline: List[TimelineEntry] = Field(default_factory=list)


class IncidentUpdate(BaseModel):
    """CR-014 triage change. Send only what changes; `note` is added to the timeline."""
    status: Optional[IncidentStatus] = None
    severity: Optional[IncidentSeverity] = None
    assignee_id: Optional[str] = Field(default=None, max_length=100)
    note: Optional[str] = Field(default=None, max_length=2000)
    resolution_summary: Optional[str] = Field(default=None, max_length=4000)
    postmortem: Optional[str] = Field(default=None, max_length=8000)
