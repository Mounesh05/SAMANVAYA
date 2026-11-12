"""
Incident domain models (CR-001: anyone with CREATE_INCIDENT can report one).

Triage and resolution (investigating/resolved/closed) belong to DevOps and are
defined in CR-003; this model only covers reporting and reading.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

IncidentSeverity = Literal["low", "medium", "high", "critical"]


class IncidentCreate(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=8000)
    severity: IncidentSeverity = "medium"
    service: Optional[str] = Field(default=None, max_length=200)


class Incident(IncidentCreate):
    id: str
    status: str = "open"  # open|investigating|resolved|closed (triage: CR-003)
    reporter_id: str
    reporter_name: str = ""
    created_at: str = ""
