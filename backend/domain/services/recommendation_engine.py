"""
Recommendation Engine - Role-Aware Actionable Intelligence.
Phase 1.3: Transforms evidence and analysis into specific, prioritized recommendations.
"""

import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone, timedelta

from domain.models.recommendation import (
    Recommendation, RecommendationPriority, RecommendationCategory,
    RecommendationStatus
)
from repositories.recommendation_repository import RecommendationRepository
import logging

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """Generates role-specific, actionable recommendations from intelligence analysis."""
    
    def __init__(self):
        self.repo = RecommendationRepository()
    
    async def generate_pr_recommendations(
        self,
        pr_id: str,
        pr_data: Dict[str, Any],
        risk_analysis: Dict[str, Any],
        ai_analysis: Optional[Dict[str, Any]] = None,
        code_quality_report: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None
    ) -> List[str]:
        """
        Generate recommendations for a PR based on all available intelligence.
        
        Returns:
            List of recommendation IDs
        """
        recommendations = []
        
        risk_level = risk_analysis.get("risk_level", "unknown")
        risk_score = risk_analysis.get("risk_score", 0)
        
        # 1. Risk-based recommendations
        if risk_level in ("high", "critical") or risk_score >= 70:
            recommendations.extend(
                await self._generate_high_risk_recommendations(
                    pr_id, pr_data, risk_analysis, project_id
                )
            )
        
        # 2. AI analysis recommendations
        if ai_analysis:
            recommendations.extend(
                await self._generate_ai_recommendations(
                    pr_id, pr_data, ai_analysis, project_id
                )
            )
        
        # 3. Code quality recommendations
        if code_quality_report:
            recommendations.extend(
                await self._generate_quality_recommendations(
                    pr_id, pr_data, code_quality_report, project_id
                )
            )
        
        return recommendations
    
    async def _generate_high_risk_recommendations(
        self,
        pr_id: str,
        pr_data: Dict[str, Any],
        risk_analysis: Dict[str, Any],
        project_id: Optional[str]
    ) -> List[str]:
        """Generate recommendations for high-risk PRs."""
        recs = []
        
        risk_level = risk_analysis.get("risk_level", "unknown")
        risk_factors = risk_analysis.get("risk_factors", [])
        
        # Rec 1: Request senior review
        rec_id = await self._create_recommendation(
            entity_type="pull_request",
            entity_id=pr_id,
            project_id=project_id,
            title="Request senior engineer review",
            description=f"This PR has {risk_level} risk level due to: {', '.join(risk_factors[:3])}",
            action="Tag a senior engineer for code review before merging",
            category=RecommendationCategory.PROCESS,
            priority=RecommendationPriority.HIGH if risk_level == "high" else RecommendationPriority.CRITICAL,
            reasoning=f"Risk analysis flagged {len(risk_factors)} risk factors",
            target_roles=["tech_lead", "developer"],
            target_user_id=pr_data.get("author"),
            estimated_impact="high",
            estimated_effort="low",
            confidence=0.95
        )
        recs.append(rec_id)
        
        # Rec 2: Add more tests if needed
        risk_factors_text = " ".join(risk_factors).lower()
        if "test" in risk_factors_text or "coverage" in risk_factors_text:
            rec_id = await self._create_recommendation(
                entity_type="pull_request",
                entity_id=pr_id,
                project_id=project_id,
                title="Add unit tests before merge",
                description="Insufficient test coverage detected for code changes",
                action="Write unit tests covering the main code paths modified in this PR",
                category=RecommendationCategory.TESTING,
                priority=RecommendationPriority.HIGH,
                reasoning="Code changes without tests increase deployment risk",
                target_roles=["developer", "qa"],
                target_user_id=pr_data.get("author"),
                estimated_impact="high",
                estimated_effort="medium",
                confidence=0.9
            )
            recs.append(rec_id)
        
        return recs
    
    async def _generate_ai_recommendations(
        self,
        pr_id: str,
        pr_data: Dict[str, Any],
        ai_analysis: Dict[str, Any],
        project_id: Optional[str]
    ) -> List[str]:
        """Generate recommendations from AI analysis."""
        recs = []
        
        ai_recommendations = ai_analysis.get("recommendations", [])
        critical_issues = ai_analysis.get("critical_issues", [])
        confidence = ai_analysis.get("confidence", 0.7)
        
        # Convert AI recommendations to structured recommendations
        for idx, ai_rec in enumerate(ai_recommendations[:5]):  # Limit to top 5
            category, priority = self._infer_category_priority(ai_rec)
            
            rec_id = await self._create_recommendation(
                entity_type="pull_request",
                entity_id=pr_id,
                project_id=project_id,
                title=ai_rec[:100],
                description=ai_rec,
                action=ai_rec,
                category=category,
                priority=priority,
                reasoning="AI analysis of code quality and patterns",
                target_roles=["developer"],
                target_user_id=pr_data.get("author"),
                estimated_impact="medium",
                estimated_effort="medium",
                confidence=confidence
            )
            recs.append(rec_id)
        
        # Critical issues get separate high-priority recommendations
        for issue in critical_issues[:3]:
            rec_id = await self._create_recommendation(
                entity_type="pull_request",
                entity_id=pr_id,
                project_id=project_id,
                title=f"Critical: {issue[:80]}",
                description=issue,
                action=f"Address this critical issue before merging: {issue}",
                category=RecommendationCategory.CODE_QUALITY,
                priority=RecommendationPriority.CRITICAL,
                reasoning="Flagged as critical by AI analysis",
                target_roles=["developer", "tech_lead"],
                target_user_id=pr_data.get("author"),
                estimated_impact="high",
                estimated_effort="medium",
                confidence=confidence
            )
            recs.append(rec_id)
        
        return recs
    
    async def _generate_quality_recommendations(
        self,
        pr_id: str,
        pr_data: Dict[str, Any],
        quality_report: Dict[str, Any],
        project_id: Optional[str]
    ) -> List[str]:
        """Generate recommendations from code quality report."""
        recs = []
        
        security_findings = quality_report.get("security_findings", {})
        complexity_metrics = quality_report.get("complexity_metrics", {})
        
        # Security recommendations
        critical_security = security_findings.get("critical_count", 0)
        if critical_security > 0:
            rec_id = await self._create_recommendation(
                entity_type="pull_request",
                entity_id=pr_id,
                project_id=project_id,
                title=f"Fix {critical_security} critical security issue(s)",
                description="Critical security vulnerabilities detected by static analysis",
                action="Review and fix all critical security findings before merging",
                category=RecommendationCategory.SECURITY,
                priority=RecommendationPriority.CRITICAL,
                reasoning="Security vulnerabilities pose immediate risk",
                target_roles=["developer", "security"],
                target_user_id=pr_data.get("author"),
                estimated_impact="critical",
                estimated_effort="high",
                confidence=0.95
            )
            recs.append(rec_id)
        
        return recs
    
    async def _create_recommendation(
        self,
        entity_type: str,
        entity_id: str,
        project_id: Optional[str],
        title: str,
        description: str,
        action: str,
        category: RecommendationCategory,
        priority: RecommendationPriority,
        reasoning: str,
        target_roles: List[str],
        target_user_id: Optional[str],
        estimated_impact: str,
        estimated_effort: str,
        confidence: float
    ) -> str:
        """Create and store a recommendation."""
        
        expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        
        recommendation = Recommendation(
            id=f"REC-{uuid.uuid4().hex[:8].upper()}",
            entity_type=entity_type,
            entity_id=entity_id,
            project_id=project_id,
            title=title,
            description=description,
            action=action,
            category=category,
            priority=priority,
            reasoning=reasoning,
            target_roles=target_roles,
            target_user_id=target_user_id,
            estimated_impact=estimated_impact,
            estimated_effort=estimated_effort,
            confidence=confidence,
            generated_by="recommendation-engine",
            expires_at=expires_at
        )
        
        rec_id = await self.repo.insert(recommendation.dict())
        logger.info(f"Created recommendation {rec_id}: {title}")
        
        return rec_id
    
    def _infer_category_priority(
        self,
        recommendation_text: str
    ) -> Tuple[RecommendationCategory, RecommendationPriority]:
        """Infer category and priority from recommendation text."""
        text_lower = recommendation_text.lower()
        
        # Infer category
        if any(word in text_lower for word in ["test", "coverage", "unit test"]):
            category = RecommendationCategory.TESTING
        elif any(word in text_lower for word in ["security", "vulnerability", "exploit"]):
            category = RecommendationCategory.SECURITY
        elif any(word in text_lower for word in ["performance", "slow", "optimization"]):
            category = RecommendationCategory.PERFORMANCE
        elif any(word in text_lower for word in ["architecture", "design", "structure"]):
            category = RecommendationCategory.ARCHITECTURE
        else:
            category = RecommendationCategory.CODE_QUALITY
        
        # Infer priority
        if any(word in text_lower for word in ["critical", "urgent", "immediately", "must"]):
            priority = RecommendationPriority.CRITICAL
        elif any(word in text_lower for word in ["important", "should", "high"]):
            priority = RecommendationPriority.HIGH
        elif any(word in text_lower for word in ["consider", "could", "might"]):
            priority = RecommendationPriority.MEDIUM
        else:
            priority = RecommendationPriority.MEDIUM
        
        return category, priority
    
    # Public query methods
    
    async def get_recommendations_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all recommendations for an entity."""
        return await self.repo.find_by_entity(entity_type, entity_id, status)
    
    async def get_recommendations_for_user(
        self,
        user_id: str,
        status: Optional[str] = "pending"
    ) -> List[Dict[str, Any]]:
        """Get all recommendations for a user."""
        return await self.repo.find_by_user(user_id, status)
    
    async def get_recommendations_for_role(
        self,
        role: str,
        project_id: Optional[str] = None,
        status: Optional[str] = "pending"
    ) -> List[Dict[str, Any]]:
        """Get all recommendations for a role."""
        return await self.repo.find_by_role(role, project_id, status)
    
    async def accept_recommendation(
        self,
        recommendation_id: str,
        user_id: str,
        notes: Optional[str] = None
    ) -> bool:
        """User accepts a recommendation."""
        return await self.repo.update_status(
            recommendation_id,
            RecommendationStatus.ACCEPTED.value,
            user_id,
            notes
        )
    
    async def reject_recommendation(
        self,
        recommendation_id: str,
        user_id: str,
        reason: Optional[str] = None
    ) -> bool:
        """User rejects a recommendation."""
        return await self.repo.update_status(
            recommendation_id,
            RecommendationStatus.REJECTED.value,
            user_id,
            reason
        )
    
    async def mark_implemented(
        self,
        recommendation_id: str,
        user_id: str,
        pr_id: Optional[str] = None
    ) -> bool:
        """Mark recommendation as implemented."""
        updated = await self.repo.update_status(
            recommendation_id,
            RecommendationStatus.IMPLEMENTED.value,
            user_id
        )
        
        if updated and pr_id:
            await self.repo.link_to_pr(recommendation_id, pr_id)
        
        return updated

