"""
Traceability API Routes.

Provides access to the evidence graph for:
- Viewing entity relationships
- Impact analysis (blast radius)
- Root cause analysis
- Hotspot detection

All endpoints require JWT authentication.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from domain.services.traceability_service import TraceabilityService
from domain.models.entity_relationship import EntityType, RelationshipType
from core.dependencies import get_current_user
from core.authorization import verify_task_access, verify_project_access, has_org_access

router = APIRouter()
traceability_service = TraceabilityService()


async def _verify_pr_access(pr_id: str, current_user: dict) -> str:
    """
    Verify user has access to a PR and validate PR-to-project mapping.
    
    Returns the PR's project_id if access is granted.
    Raises HTTPException if PR not found or access denied.
    """
    from repositories.pr_repository import PRRepository
    from repositories.project_repository import ProjectRepository
    
    pr_repo = PRRepository()
    pr = await pr_repo.find_by_id(pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail="PR not found")
    
    project_id = pr.get("project_id")
    if not project_id:
        # PR has no project_id - this is allowed for unlinked PRs
        # Require org access for unlinked PRs
        if not has_org_access(current_user):
            raise HTTPException(
                status_code=403,
                detail="PR is not linked to a project"
            )
        return None
    
    # Validate that the project exists and the PR belongs to it
    # by checking that the PR's repository matches the project's code_repo_url
    project_repo = ProjectRepository()
    project = await project_repo.find_by_id(project_id)
    if not project:
        # Project_id in PR is invalid - this is a data integrity issue
        # Require org access
        if not has_org_access(current_user):
            raise HTTPException(
                status_code=403,
                detail="PR's project reference is invalid"
            )
        return None
    
    # Verify the PR's repository matches the project's repository
    pr_repo_url = pr.get("repository", "")
    project_repo_url = project.get("code_repo_url", "")
    
    # Basic validation: check if repository names match
    # (More sophisticated validation could be added here)
    if pr_repo_url and project_repo_url:
        # Extract repo name from URLs (e.g., "owner/repo" from full URL)
        pr_repo_name = pr_repo_url.split("/")[-2:] if "/" in pr_repo_url else [pr_repo_url]
        project_repo_name = project_repo_url.split("/")[-2:] if "/" in project_repo_url else [project_repo_url]
        
        if pr_repo_name != project_repo_name:
            # Repository mismatch - data integrity issue
            # Require org access to view mismatched data
            if not has_org_access(current_user):
                raise HTTPException(
                    status_code=403,
                    detail="PR repository does not match project repository"
                )
            return project_id
    
    # Verification passed - check project access
    await verify_project_access(current_user, project_id)
    return project_id


@router.get("/pr/{pr_id}/relationships")
async def get_pr_relationships(
    pr_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get all entities related to a PR."""
    # Authorization: verify user has access to the PR's project
    await _verify_pr_access(pr_id, current_user)
    
    try:
        relationships = await traceability_service.get_pr_relationships(pr_id)
        return {
            "pr_id": pr_id,
            "relationships": relationships
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/pr/{pr_id}/blast-radius")
async def get_pr_blast_radius(
    pr_id: str,
    max_hops: int = 2,
    current_user: dict = Depends(get_current_user),
):
    """Calculate blast radius of a PR - what could break if merged."""
    # Authorization: verify user has access to the PR's project
    await _verify_pr_access(pr_id, current_user)
    
    try:
        blast_radius = await traceability_service.calculate_blast_radius(
            pr_id=pr_id,
            max_hops=max_hops
        )
        return blast_radius.dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/task/{task_id}/prs")
async def get_task_prs(
    task_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get all PRs that implement a task."""
    # Authorization: verify user has access to the task
    await verify_task_access(current_user, task_id)
    
    try:
        prs = await traceability_service.get_task_related_prs(task_id)
        return {
            "task_id": task_id,
            "prs": [pr.dict() for pr in prs],
            "count": len(prs)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/file/history")
async def get_file_history(
    file_path: str,
    repository: str,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    """Get complete history of a file."""
    # Authorization: verify user has access to the repository's project
    # Map repository to project and verify project access
    from repositories.project_repository import ProjectRepository
    project_repo = ProjectRepository()
    projects = await project_repo.find_all({})
    
    project_id = None
    for project in projects:
        repo_url = project.get("code_repo_url", "")
        if repository in repo_url or repo_url.endswith(repository):
            project_id = project["id"]
            break
    
    if not project_id:
        # Repository not linked to any project - require org access
        if not has_org_access(current_user):
            raise HTTPException(
                status_code=403,
                detail="Repository not found or insufficient permissions"
            )
    else:
        # Verify user has access to the project
        await verify_project_access(current_user, project_id)
    
    try:
        history = await traceability_service.get_file_history(
            file_path=file_path,
            repository=repository,
            limit=limit
        )
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/relationships")
async def create_relationship(
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    relationship_type: str,
    metadata: Optional[dict] = None,
    confidence: float = 1.0,
    current_user: dict = Depends(get_current_user),
):
    """Manually create a relationship between entities."""
    # Authorization: verify user has access to create relationships
    # Verify access to both source and target entities
    try:
        source_type_enum = EntityType(source_type)
        target_type_enum = EntityType(target_type)
        relationship_type_enum = RelationshipType(relationship_type)
        
        # Verify access to source entity
        if source_type_enum == EntityType.TASK:
            await verify_task_access(current_user, source_id)
        elif source_type_enum == EntityType.PR:
            await _verify_pr_access(source_id, current_user)
        
        # Verify access to target entity
        if target_type_enum == EntityType.TASK:
            await verify_task_access(current_user, target_id)
        elif target_type_enum == EntityType.PR:
            await _verify_pr_access(target_id, current_user)
        
        rel_id = await traceability_service.create_relationship(
            source_type=source_type_enum,
            source_id=source_id,
            target_type=target_type_enum,
            target_id=target_id,
            relationship_type=relationship_type_enum,
            metadata=metadata,
            confidence=confidence,
            created_by=current_user["employee_id"]
        )
        
        return {
            "relationship_id": rel_id,
            "status": "created"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid enum value: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/entity/{entity_type}/{entity_id}/connections")
async def get_entity_connections(
    entity_type: str,
    entity_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get all connections for any entity."""
    try:
        entity_type_enum = EntityType(entity_type)
        
        # Authorization: verify user has access to the entity
        if entity_type_enum == EntityType.TASK:
            await verify_task_access(current_user, entity_id)
        elif entity_type_enum == EntityType.PR:
            await _verify_pr_access(entity_id, current_user)
        else:
            # For other entity types (FILE, COMMIT, DEPLOYMENT, etc.),
            # require org access as we don't have project-scoped authorization
            if not has_org_access(current_user):
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions to view {entity_type} connections"
                )
        
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
        raise HTTPException(status_code=500, detail="Internal server error")
