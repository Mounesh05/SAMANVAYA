"""
Entity Relationship - Evidence Graph Core Model.

This is the foundation of Phase 1.2: Traceability System.

The evidence graph connects all entities in the system:
  Task → PR → Commits → Files → Tests → CI Runs → Deployments → Bugs → Incidents

This enables questions like:
- "Which tasks are in this PR?"
- "Which PRs modified this file?"
- "What's the blast radius of this change?"
- "Which deployments included this PR?"
- "What bugs were caused by this PR?"
- "Which tests cover this code path?"

Bidirectional navigation allows traversing the graph in any direction.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum


class EntityType(str, Enum):
    """All entity types in the system."""
    PROJECT = "project"
    SPRINT = "sprint"
    STORY = "story"
    TASK = "task"
    PULL_REQUEST = "pull_request"
    COMMIT = "commit"
    FILE = "file"
    BUG = "bug"
    INCIDENT = "incident"
    DEPLOYMENT = "deployment"
    CI_RUN = "ci_run"
    TEST = "test"
    RISK = "risk"
    WEBHOOK_EVENT = "webhook_event"
    AI_RUN = "ai_run"
    CODE_QUALITY_REPORT = "code_quality_report"
    RECOMMENDATION = "recommendation"
    NOTIFICATION = "notification"


class RelationshipType(str, Enum):
    """Types of relationships between entities."""
    # Hierarchy
    CONTAINS = "contains"  # Project contains Sprint, Sprint contains Story
    PART_OF = "part_of"  # Story part of Sprint, Task part of Story
    
    # Work relationships
    IMPLEMENTS = "implements"  # PR implements Task/Story
    ADDRESSES = "addresses"  # PR addresses Bug
    FIXES = "fixes"  # PR fixes Bug
    
    # Code relationships
    MODIFIES = "modifies"  # PR/Commit modifies File
    TESTS = "tests"  # Test tests File
    DEPENDS_ON = "depends_on"  # File depends on File
    
    # CI/CD relationships
    BUILDS = "builds"  # CI Run builds PR
    DEPLOYS = "deploys"  # Deployment deploys PR
    INCLUDES = "includes"  # Deployment includes PR
    
    # Risk relationships
    CAUSES = "causes"  # PR causes Bug/Incident
    DETECTED_BY = "detected_by"  # Risk detected by AI Run
    MITIGATES = "mitigates"  # PR mitigates Risk
    
    # Analysis relationships
    ANALYZES = "analyzes"  # AI Run analyzes PR
    GENERATES = "generates"  # AI Run generates Recommendation
    TRIGGERS = "triggers"  # Webhook Event triggers AI Run
    NOTIFIES = "notifies"  # Event notifies User
    
    # Assignment
    ASSIGNED_TO = "assigned_to"  # Task assigned to User
    AUTHORED_BY = "authored_by"  # PR authored by User
    REVIEWED_BY = "reviewed_by"  # PR reviewed by User


class EntityRelationship(BaseModel):
    """
    A directed relationship between two entities in the evidence graph.
    
    Example: PR-123 (source) --implements--> TASK-456 (target)
    """
    
    id: str = Field(..., description="Unique relationship ID")
    
    # Source entity (from)
    source_type: EntityType = Field(..., description="Type of source entity")
    source_id: str = Field(..., description="ID of source entity")
    
    # Target entity (to)
    target_type: EntityType = Field(..., description="Type of target entity")
    target_id: str = Field(..., description="ID of target entity")
    
    # Relationship
    relationship_type: RelationshipType = Field(..., description="Type of relationship")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional relationship data")
    confidence: float = Field(default=1.0, description="Confidence score (0-1) for inferred relationships")
    
    # Tracking
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="When relationship was created"
    )
    created_by: str = Field(default="system", description="Who/what created this relationship")
    verified: bool = Field(default=False, description="Whether relationship was manually verified")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "REL-ABC123",
                "source_type": "pull_request",
                "source_id": "PR-001",
                "target_type": "task",
                "target_id": "TASK-456",
                "relationship_type": "implements",
                "metadata": {
                    "pr_number": 123,
                    "task_title": "Add user authentication",
                    "mentioned_in_pr_description": True
                },
                "confidence": 0.95,
                "created_at": "2026-09-01T10:00:00Z",
                "created_by": "webhook-processor",
                "verified": False
            }
        }


class EntityNode(BaseModel):
    """
    A node in the evidence graph representing any entity.
    
    This is a lightweight reference to the actual entity.
    """
    
    entity_type: EntityType
    entity_id: str
    entity_name: str = Field(default="", description="Human-readable name")
    
    # Cached metadata for quick access
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Graph metrics (computed)
    inbound_count: int = Field(default=0, description="Number of incoming relationships")
    outbound_count: int = Field(default=0, description="Number of outgoing relationships")
    
    # Risk indicators
    is_hotspot: bool = Field(default=False, description="Entity is frequently involved in incidents")
    risk_score: int = Field(default=0, description="Aggregated risk score")


class TraceabilityPath(BaseModel):
    """
    A path through the evidence graph connecting two entities.
    
    Example: TASK-456 → PR-123 → COMMIT-789 → FILE-main.py → BUG-101
    """
    
    start_entity: EntityNode
    end_entity: EntityNode
    path: List[EntityRelationship] = Field(default_factory=list)
    path_length: int = Field(default=0, description="Number of hops")
    path_types: List[str] = Field(default_factory=list, description="Relationship types in path")


class BlastRadius(BaseModel):
    """
    The blast radius of a change - all entities potentially affected.
    
    Used for impact analysis: "What could break if we merge this PR?"
    """
    
    center_entity: EntityNode
    radius: int = Field(default=2, description="How many hops from center")
    
    # Affected entities by type
    affected_files: List[EntityNode] = Field(default_factory=list)
    affected_tests: List[EntityNode] = Field(default_factory=list)
    affected_services: List[EntityNode] = Field(default_factory=list)
    dependent_prs: List[EntityNode] = Field(default_factory=list)
    related_bugs: List[EntityNode] = Field(default_factory=list)
    
    # Risk metrics
    total_affected_entities: int = Field(default=0)
    high_risk_entities: int = Field(default=0, description="Hotspot files, critical services")
    risk_score: int = Field(default=0, description="Overall blast radius risk")


class HotspotFile(BaseModel):
    """
    A file that is frequently modified and has incident history.
    
    These are high-risk files that need extra review attention.
    """
    
    file_path: str
    repository: str
    
    # Activity metrics
    modification_count: int = Field(default=0, description="Times modified in last 90 days")
    pr_count: int = Field(default=0, description="PRs that modified this file")
    author_count: int = Field(default=0, description="Unique authors")
    
    # Incident history
    incident_count: int = Field(default=0, description="Incidents caused by changes to this file")
    bug_count: int = Field(default=0, description="Bugs related to this file")
    rollback_count: int = Field(default=0, description="Deployments rolled back due to this file")
    
    # Complexity
    lines_of_code: int = Field(default=0)
    cyclomatic_complexity: int = Field(default=0)
    
    # Risk scoring
    hotspot_score: int = Field(default=0, description="0-100, higher = more dangerous")
    last_incident_date: Optional[str] = Field(None, description="Most recent incident")
    
    # Recommendations
    requires_senior_review: bool = Field(default=False)
    requires_additional_testing: bool = Field(default=False)
