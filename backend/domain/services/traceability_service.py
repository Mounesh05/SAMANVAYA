"""
Traceability Service â€” Evidence Graph Intelligence.

This service builds and maintains the evidence graph, enabling:
1. Automatic relationship detection from PR descriptions, commit messages
2. Blast radius analysis for impact assessment
3. Hotspot file tracking
4. Bidirectional navigation (Task â†’ PR â†’ Files â†’ Bugs)
5. Root cause analysis (Bug â†’ PRs â†’ Files â†’ Authors)

This is the core of Phase 1.2.
"""

import uuid
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from domain.models.entity_relationship import (
    EntityType, RelationshipType, EntityRelationship,
    EntityNode, BlastRadius, HotspotFile, TraceabilityPath
)
from repositories.entity_relationship_repository import EntityRelationshipRepository
from repositories.pr_repository import PRRepository
from repositories.task_repository import TaskRepository
from repositories.story_repository import StoryRepository
import logging

logger = logging.getLogger(__name__)


class TraceabilityService:
    """
    Manages the evidence graph and provides traceability intelligence.
    """
    
    def __init__(self):
        self.rel_repo = EntityRelationshipRepository()
        self.pr_repo = PRRepository()
        self.task_repo = TaskRepository()
        self.story_repo = StoryRepository()
    
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # Relationship Creation
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    
    async def create_relationship(
        self,
        source_type: EntityType,
        source_id: str,
        target_type: EntityType,
        target_id: str,
        relationship_type: RelationshipType,
        metadata: Optional[Dict[str, Any]] = None,
        confidence: float = 1.0,
        created_by: str = "system"
    ) -> str:
        """
        Create a relationship between two entities.
        
        Returns:
            Relationship ID
        """
        # Check if relationship already exists
        exists = await self.rel_repo.exists(
            source_type, source_id, target_type, target_id, relationship_type
        )
        
        if exists:
            logger.debug(f"Relationship already exists: {source_id} --{relationship_type}--> {target_id}")
            return None
        
        relationship = EntityRelationship(
            id=f"REL-{uuid.uuid4().hex[:8].upper()}",
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relationship_type=relationship_type,
            metadata=metadata or {},
            confidence=confidence,
            created_by=created_by,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        rel_id = await self.rel_repo.insert(relationship.dict())
        logger.info(f"Created relationship: {source_id} --{relationship_type}--> {target_id}")
        
        return rel_id
    
    async def link_pr_to_tasks(
        self,
        pr_id: str,
        pr_description: str,
        pr_title: str,
        project_id: str
    ) -> List[str]:
        """
        Automatically detect and link PR to tasks mentioned in description/title.
        
        Patterns matched:
        - TASK-123, #123, closes #123, fixes TASK-456
        - Implements TASK-123
        - Addresses BUG-789
        
        Returns:
            List of relationship IDs created
        """
        relationship_ids = []
        
        # Combine title and description for searching
        text = f"{pr_title} {pr_description}"
        
        # Pattern 1: TASK-XXX or BUG-XXX format
        pattern_explicit = r'\b(TASK|STORY|BUG)-(\d+)\b'
        matches = re.findall(pattern_explicit, text, re.IGNORECASE)
        
        for entity_type_str, number in matches:
            entity_type_str = entity_type_str.upper()
            entity_id = f"{entity_type_str}-{number}"
            
            # Determine entity type
            if entity_type_str == "TASK":
                target_type = EntityType.TASK
            elif entity_type_str == "STORY":
                target_type = EntityType.STORY
            elif entity_type_str == "BUG":
                target_type = EntityType.BUG
            else:
                continue
            
            # Verify entity exists
            exists = await self._verify_entity_exists(target_type, entity_id, project_id)
            if not exists:
                logger.warning(f"Entity {entity_id} mentioned in PR but not found in project")
                continue
            
            # Determine relationship type based on context
            rel_type = self._infer_relationship_type(text, entity_id, entity_type_str)
            
            # Create relationship
            rel_id = await self.create_relationship(
                source_type=EntityType.PULL_REQUEST,
                source_id=pr_id,
                target_type=target_type,
                target_id=entity_id,
                relationship_type=rel_type,
                metadata={
                    "detected_from": "pr_description",
                    "matched_text": f"{entity_type_str}-{number}"
                },
                confidence=0.95,
                created_by="traceability-service"
            )
            
            if rel_id:
                relationship_ids.append(rel_id)
        
        # Pattern 2: #XXX format (GitHub issue/task numbers)
        pattern_hash = r'#(\d+)'
        hash_matches = re.findall(pattern_hash, text)
        
        for number in hash_matches:
            # Try to match to task by searching in project
            task = await self.task_repo.find_by_number(project_id, int(number))
            
            if task:
                rel_id = await self.create_relationship(
                    source_type=EntityType.PULL_REQUEST,
                    source_id=pr_id,
                    target_type=EntityType.TASK,
                    target_id=task["id"],
                    relationship_type=RelationshipType.IMPLEMENTS,
                    metadata={
                        "detected_from": "pr_description",
                        "matched_text": f"#{number}"
                    },
                    confidence=0.85,
                    created_by="traceability-service"
                )
                
                if rel_id:
                    relationship_ids.append(rel_id)
        
        return relationship_ids
    
    async def link_pr_to_files(
        self,
        pr_id: str,
        changed_files: List[str],
        repository: str
    ) -> List[str]:
        """
        Link PR to all files it modifies.
        
        Returns:
            List of relationship IDs
        """
        relationship_ids = []
        
        for file_path in changed_files:
            # Create file entity ID
            file_id = f"FILE-{repository.replace('/', '-')}-{file_path.replace('/', '-')}"
            
            rel_id = await self.create_relationship(
                source_type=EntityType.PULL_REQUEST,
                source_id=pr_id,
                target_type=EntityType.FILE,
                target_id=file_id,
                relationship_type=RelationshipType.MODIFIES,
                metadata={
                    "file_path": file_path,
                    "repository": repository
                },
                confidence=1.0,
                created_by="traceability-service"
            )
            
            if rel_id:
                relationship_ids.append(rel_id)
        
        return relationship_ids
    
    async def link_pr_to_ci_run(
        self,
        pr_id: str,
        ci_run_id: str,
        ci_status: str,
        ci_url: Optional[str] = None
    ) -> str:
        """Link PR to CI/CD run."""
        return await self.create_relationship(
            source_type=EntityType.CI_RUN,
            source_id=ci_run_id,
            target_type=EntityType.PULL_REQUEST,
            target_id=pr_id,
            relationship_type=RelationshipType.BUILDS,
            metadata={
                "ci_status": ci_status,
                "ci_url": ci_url
            },
            confidence=1.0,
            created_by="ci-integration"
        )
    
    async def link_pr_to_deployment(
        self,
        pr_id: str,
        deployment_id: str,
        environment: str,
        deployed_at: str
    ) -> str:
        """Link PR to deployment."""
        return await self.create_relationship(
            source_type=EntityType.DEPLOYMENT,
            source_id=deployment_id,
            target_type=EntityType.PULL_REQUEST,
            target_id=pr_id,
            relationship_type=RelationshipType.INCLUDES,
            metadata={
                "environment": environment,
                "deployed_at": deployed_at
            },
            confidence=1.0,
            created_by="deployment-tracker"
        )
    
    async def link_bug_to_pr(
        self,
        bug_id: str,
        pr_id: str,
        relationship_type: RelationshipType = RelationshipType.CAUSES
    ) -> str:
        """
        Link bug to PR.
        
        relationship_type:
        - CAUSES: PR caused the bug
        - FIXES: PR fixes the bug
        """
        return await self.create_relationship(
            source_type=EntityType.PULL_REQUEST,
            source_id=pr_id,
            target_type=EntityType.BUG,
            target_id=bug_id,
            relationship_type=relationship_type,
            confidence=0.9,
            created_by="bug-tracker"
        )
    
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # Graph Queries
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    
    async def get_pr_relationships(self, pr_id: str) -> Dict[str, List[EntityNode]]:
        """
        Get all entities related to a PR.
        
        Returns:
            {
                "tasks": [...],
                "stories": [...],
                "files": [...],
                "bugs": [...],
                "ci_runs": [...],
                "deployments": [...]
            }
        """
        rels = await self.rel_repo.find_bidirectional(EntityType.PULL_REQUEST, pr_id)
        
        result = {
            "tasks": [],
            "stories": [],
            "files": [],
            "bugs": [],
            "ci_runs": [],
            "deployments": [],
            "commits": []
        }
        
        # Process outbound (PR -> other entities)
        for rel in rels["outbound"]:
            target_type = rel["target_type"]
            target_id = rel["target_id"]
            
            node = EntityNode(
                entity_type=EntityType(target_type),
                entity_id=target_id,
                metadata=rel.get("metadata", {})
            )
            
            if target_type == EntityType.TASK.value:
                result["tasks"].append(node)
            elif target_type == EntityType.STORY.value:
                result["stories"].append(node)
            elif target_type == EntityType.FILE.value:
                result["files"].append(node)
            elif target_type == EntityType.BUG.value:
                result["bugs"].append(node)
        
        # Process inbound (other entities -> PR)
        for rel in rels["inbound"]:
            source_type = rel["source_type"]
            source_id = rel["source_id"]
            
            node = EntityNode(
                entity_type=EntityType(source_type),
                entity_id=source_id,
                metadata=rel.get("metadata", {})
            )
            
            if source_type == EntityType.CI_RUN.value:
                result["ci_runs"].append(node)
            elif source_type == EntityType.DEPLOYMENT.value:
                result["deployments"].append(node)
            elif source_type == EntityType.COMMIT.value:
                result["commits"].append(node)
        
        return result
    
    async def get_task_related_prs(self, task_id: str) -> List[EntityNode]:
        """Get all PRs that implement a task."""
        rels = await self.rel_repo.find_inbound(
            target_type=EntityType.TASK,
            target_id=task_id,
            source_type=EntityType.PULL_REQUEST
        )
        
        return [
            EntityNode(
                entity_type=EntityType.PULL_REQUEST,
                entity_id=rel["source_id"],
                metadata=rel.get("metadata", {})
            )
            for rel in rels
        ]
    
    async def get_file_history(
        self,
        file_path: str,
        repository: str,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get complete history of a file.
        
        Returns:
            {
                "file_id": "FILE-...",
                "prs": [...],  # PRs that modified this file
                "bugs": [...],  # Bugs related to this file
                "incident_count": 5,
                "is_hotspot": true
            }
        """
        file_id = f"FILE-{repository.replace('/', '-')}-{file_path.replace('/', '-')}"
        
        # Find all PRs that modified this file
        rels = await self.rel_repo.find_inbound(
            target_type=EntityType.FILE,
            target_id=file_id,
            source_type=EntityType.PULL_REQUEST
        )
        
        prs = [
            EntityNode(
                entity_type=EntityType.PULL_REQUEST,
                entity_id=rel["source_id"],
                metadata=rel.get("metadata", {})
            )
            for rel in rels
        ]
        
        # Count incidents (TODO: implement when bug tracking is connected)
        incident_count = 0
        is_hotspot = len(prs) > 10  # Simple heuristic
        
        return {
            "file_id": file_id,
            "file_path": file_path,
            "repository": repository,
            "prs": prs,
            "modification_count": len(prs),
            "incident_count": incident_count,
            "is_hotspot": is_hotspot
        }
    
    async def calculate_blast_radius(
        self,
        pr_id: str,
        max_hops: int = 2
    ) -> BlastRadius:
        """
        Calculate the blast radius of a PR.
        
        This answers: "What could break if we merge this PR?"
        """
        center = EntityNode(
            entity_type=EntityType.PULL_REQUEST,
            entity_id=pr_id
        )
        
        # Get all entities within N hops
        affected = await self.rel_repo.get_blast_radius(
            EntityType.PULL_REQUEST,
            pr_id,
            max_hops=max_hops
        )
        
        # Categorize affected entities
        affected_files = []
        affected_tests = []
        affected_services = []
        dependent_prs = []
        related_bugs = []
        
        for entity in affected:
            entity_type = EntityType(entity["entity_type"])
            entity_id = entity["entity_id"]
            
            node = EntityNode(
                entity_type=entity_type,
                entity_id=entity_id,
                metadata={"distance": entity["distance"]}
            )
            
            if entity_type == EntityType.FILE:
                affected_files.append(node)
            elif entity_type == EntityType.TEST:
                affected_tests.append(node)
            elif entity_type == EntityType.PULL_REQUEST:
                dependent_prs.append(node)
            elif entity_type == EntityType.BUG:
                related_bugs.append(node)
        
        # Calculate risk score based on blast radius
        total_affected = len(affected)
        high_risk_count = len([f for f in affected_files if f.metadata.get("is_hotspot")])
        
        risk_score = min(100, total_affected * 5 + high_risk_count * 10)
        
        return BlastRadius(
            center_entity=center,
            radius=max_hops,
            affected_files=affected_files,
            affected_tests=affected_tests,
            affected_services=affected_services,
            dependent_prs=dependent_prs,
            related_bugs=related_bugs,
            total_affected_entities=total_affected,
            high_risk_entities=high_risk_count,
            risk_score=risk_score
        )
    
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # Hotspot Detection
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    
    async def identify_hotspot_files(
        self,
        repository: str,
        threshold: int = 10
    ) -> List[HotspotFile]:
        """
        Identify hotspot files (frequently modified, high incident rate).
        
        Args:
            repository: Repository to analyze
            threshold: Minimum modification count to be considered hotspot
        
        Returns:
            List of hotspot files sorted by risk
        """
        # This requires aggregation across all files
        # For now, return placeholder
        # TODO: Implement proper hotspot detection with incident correlation
        return []
    
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    # Helper Methods
    # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
    
    def _infer_relationship_type(
        self,
        text: str,
        entity_id: str,
        entity_type: str
    ) -> RelationshipType:
        """
        Infer relationship type from context.
        
        Examples:
        - "Fixes TASK-123" â†’ FIXES
        - "Implements TASK-123" â†’ IMPLEMENTS
        - "Addresses BUG-456" â†’ ADDRESSES
        """
        text_lower = text.lower()
        
        # Check for fix/resolve keywords
        if re.search(rf'\b(fix|fixes|fixed|resolve|resolves|resolved|close|closes|closed)\s+{re.escape(entity_id.lower())}', text_lower):
            if entity_type == "BUG":
                return RelationshipType.FIXES
            else:
                return RelationshipType.IMPLEMENTS
        
        # Check for implement keywords
        if re.search(rf'\b(implement|implements|implemented|add|adds|added)\s+{re.escape(entity_id.lower())}', text_lower):
            return RelationshipType.IMPLEMENTS
        
        # Check for address keywords
        if re.search(rf'\b(address|addresses|addressed)\s+{re.escape(entity_id.lower())}', text_lower):
            return RelationshipType.ADDRESSES
        
        # Default
        if entity_type == "BUG":
            return RelationshipType.ADDRESSES
        else:
            return RelationshipType.IMPLEMENTS
    
    async def _verify_entity_exists(
        self,
        entity_type: EntityType,
        entity_id: str,
        project_id: str
    ) -> bool:
        """Verify that an entity exists in the database."""
        try:
            if entity_type == EntityType.TASK:
                entity = await self.task_repo.find_by_id(entity_id)
                return entity is not None and entity.get("project_id") == project_id
            elif entity_type == EntityType.STORY:
                entity = await self.story_repo.find_by_id(entity_id)
                return entity is not None and entity.get("project_id") == project_id
            # TODO: Add bug repository check
            return False
        except Exception as e:
            logger.error(f"Error verifying entity {entity_id}: {str(e)}")
            return False

