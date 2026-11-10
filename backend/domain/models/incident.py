"""
Incident models (production problems), used by the Incidents page and the
DORA metrics (change fail rate, failed deployment recovery time).
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

IncidentStatus = Literal["open", "investigating", "resolved", "closed"]
IncidentSeverity = Literal["low", "medium", "high", "critical"]
# "change": caused by a deployment / code change (counts for DORA recovery time)
# "external": e.g. a cloud or data-centre outage (excluded from DORA since 2023)
IncidentCause = Literal["change", "external", "unknown"]


class IncidentCreate(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    severity: IncidentSeverity = "medium"
    service: Optional[str] = Field(default=None, max_length=100)
    assignee_id: Optional[str] = Field(default=None, max_length=100)
    started_at: Optional[str] = None                     # defaults to now
    caused_by_deployment_id: Optional[str] = Field(default=None, max_length=100)
    cause: Optional[IncidentCause] = None                # "change" when a deployment is linked


class IncidentUpdate(BaseModel):
    status: Optional[IncidentStatus] = None
    severity: Optional[IncidentSeverity] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    service: Optional[str] = Field(default=None, max_length=100)
    assignee_id: Optional[str] = Field(default=None, max_length=100)
    caused_by_deployment_id: Optional[str] = Field(default=None, max_length=100)
    fixed_by_deployment_id: Optional[str] = Field(default=None, max_length=100)
    cause: Optional[IncidentCause] = None
    resolution: Optional[str] = Field(default=None, max_length=5000)


class Incident(BaseModel):
    id: str
    project_id: str
    title: str
    description: Optional[str] = None
    severity: IncidentSeverity = "medium"
    service: Optional[str] = None
    assignee_id: Optional[str] = None
    status: IncidentStatus = "open"
    cause: IncidentCause = "unknown"
    caused_by_deployment_id: Optional[str] = None
    fixed_by_deployment_id: Optional[str] = None
    resolution: Optional[str] = None
    started_at: str
    resolved_at: Optional[str] = None
    closed_at: Optional[str] = None
    created_at: str
    created_by: Optional[str] = None
    updated_at: Optional[str] = None
