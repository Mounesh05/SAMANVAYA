"""
Traceability API Routes.

Provides access to the evidence graph for:
- Viewing entity relationships
- Impact analysis (blast radius)
- Root cause analysis
- Hotspot detection
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
from domain.services.traceability_service import TraceabilityService
from domain.models.entity_relationship import EntityType, RelationshipType

router = APIRouter()
traceability_service = TraceabilityService()


@router.get("/pr/{pr_id}/relationships")
async def get_pr_relationships(pr_id: str):
    """Get all entities related to a PR."""
    try:
        relationships = await traceability_service.get_pr_relationships(pr_id)
        return {
            "pr_id": pr_id,
            "relationships": relationships
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pr/{pr_id}/blast-radius")
async def get_pr_blast_radius(pr_id: str, max_hops: int = 2):
    """Calculate blast radius of a PR - what could break if merged."""
    try:
        blast_radius = await traceability_service.calculate_blast_radius(
            pr_id=pr_id,
            max_hops=max_hops
        )
        return blast_radius.dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}/prs")
async def get_task_prs(task_id: str):
    """Get all PRs that implement a task."""
    try:
        prs = await traceability_service.get_task_related_prs(task_id)
        return {
            "task_id": task_id,
            "prs": [pr.dict() for pr in prs],
            "count": len(prs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file/history")
async def get_file_history(
    file_path: str,
    repository: str,
    limit: int = 50
):
    """Get complete history of a file."""
    try:
        history = await traceability_service.get_file_history(
            file_path=file_path,
            repository=repository,
            limit=limit
        )
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/relationships")
async def create_relationship(
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    relationship_type: str,
    metadata: Optional[dict] = None,
    confidence: float = 1.0
):
    """Manually create a relationship between entities."""
    try:
        source_type_enum = EntityType(source_type)
        target_type_enum = EntityType(target_type)
        relationship_type_enum = RelationshipType(relationship_type)
        
        rel_id = await traceability_service.create_relationship(
            source_type=source_type_enum,
            source_id=source_id,
            target_type=target_type_enum,
            target_id=target_id,
            relationship_type=relationship_type_enum,
            metadata=metadata,
            confidence=confidence,
            created_by="manual-user"
        )
        
        return {
            "relationship_id": rel_id,
            "status": "created"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid enum value: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{entity_type}/{entity_id}/connections")
async def get_entity_connections(entity_type: str, entity_id: str):
    """Get all connections for any entity."""
    try:
        entity_type_enum = EntityType(entity_type)
        
        from repositories.entity_relationship_repository import EntityRelationshipRepository
        rel_repo = EntityRelationshipRepository()
        
        rels = await rel_repo.find_bidirectional(entity_type_enum, entity_id)
        metrics = await rel_repo.get_entity_metrics(entity_type_enum, entity_id)
        
        return {
            "entity": {
                "type": entity_type,
                "id": entity_id
            },
            "metrics": metrics,
            "relationships": rels
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
