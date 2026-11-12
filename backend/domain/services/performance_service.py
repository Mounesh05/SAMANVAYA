"""
Developer Performance Service
Orchestrates the complete performance evaluation process:
1. Data aggregation
2. Advisory AI explanation
3. Optional role feedback collection
4. Deterministic contribution-credit calculation
5. Trend analysis
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from intelligence.developer_data_aggregator import DeveloperDataAggregator
from agents.performance_agent import PerformanceEvaluationAgent
from domain.models.developer_performance import (
    DeveloperPerformance,
    DeveloperPerformanceCreate,
    RoleEvaluation
)
from repositories.performance_repository import PerformanceRepository
from domain.models.performance_scoring import legacy_metadata_for_record

logger = logging.getLogger(__name__)


class PeriodScoringPending(ValueError):
    def __init__(self):
        super().__init__("Canonical period scoring is pending; use scoped advisory interpretations")
        self.detail = {"status": "POLICY_PENDING", "message": str(self),
                       "interpretation_endpoint": "/api/performance/interpretations"}


class PerformanceService:
    """
    Main service for developer performance evaluation.
    
    Orchestrates:
    - Data collection from multiple sources
    - Evidence aggregation
    - Advisory AI explanation
    - Deterministic contribution-credit calculation
    - Optional human feedback and grading
    - Trend analysis
    """
    
    def __init__(self, github_token: Optional[str] = None):
        self.data_aggregator = DeveloperDataAggregator(github_token)
        self.evaluation_agent = PerformanceEvaluationAgent()
        self.performance_repo = PerformanceRepository()

    @property
    def repository(self) -> PerformanceRepository:
        return self.performance_repo

    @staticmethod
    async def authorize_evidence(request, actor):
        """Resolve current-account and exact scope checks without collecting data."""
        import re
        from fastapi import HTTPException
        from core.database import col
        from core.permissions import Permission, get_user_permissions
        from domain.models.performance_evidence import EvidencePreviewRequest, EvidenceScope

        request = EvidencePreviewRequest.model_validate(request)
        projection = {"_id": 0, "employee_id": 1, "role": 1, "org_id": 1, "is_active": 1,
                      "project_ids": 1, "team_id": 1, "github_username": 1}
        current = await col("users").find_one({"employee_id": actor.get("employee_id")}, projection)
        engineering_roles = {"DEVELOPER", "QA", "DEVOPS", "LEAD", "PM"}
        if (not current or current.get("is_active") is not True or current.get("role") not in engineering_roles
                or not current.get("org_id") or Permission.VIEW_AI_EVALUATION not in get_user_permissions(current["role"], False)):
            raise HTTPException(403, "Current account is not permitted to inspect engineering evidence")
        project = await col("projects").find_one({"id": request.project_id, "org_id": current["org_id"]},
            {"_id": 0, "id": 1, "org_id": 1, "team_id": 1})
        subject = await col("users").find_one({"employee_id": request.employee_id, "org_id": current["org_id"]}, projection)
        if not project or not subject:
            raise HTTPException(403, "Evidence scope is unavailable or unauthorized")

        def assigned(account):
            projects = account.get("project_ids")
            return ((isinstance(projects, list) and request.project_id in projects)
                    or bool(account.get("team_id") and account.get("team_id") == project.get("team_id")))

        if (not assigned(current) or not assigned(subject) or subject.get("role") not in engineering_roles
                or (current["employee_id"] != subject["employee_id"] and current["role"] not in {"LEAD", "PM"})):
            raise HTTPException(403, "Evidence scope is unavailable or unauthorized")
        config_unavailable = False
        try:
            configs = await col("github_project_configs").find({"project_id": request.project_id,
                "$or": [{"org_id": current["org_id"]}, {"org_id": {"$exists": False}}]},
                {"_id": 0, "repository_owner": 1, "repository_name": 1}).limit(3).to_list(3)
        except Exception:
            configs, config_unavailable = [], True
        repositories = {f"{c.get('repository_owner', '')}/{c.get('repository_name', '')}" for c in configs}
        repository = next(iter(repositories)) if len(repositories) == 1 and len(configs) < 3 else None
        if repository and not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}", repository):
            repository = None
        scope = EvidenceScope(organization_id=current["org_id"], employee_id=subject["employee_id"],
            project_id=request.project_id, repository=repository,
            repository_mapping_status="UNAVAILABLE" if config_unavailable else "AVAILABLE" if repository
                else "AMBIGUOUS" if configs else "MISSING",
            period_start=request.period_start, period_end=request.period_end)
        return scope, subject, current

    @staticmethod
    async def inspect_evidence(request, actor):
        from datetime import timezone
        from domain.models.performance_evidence import EvidencePreview
        from domain.services.period_evidence import validated_period_manifest
        from intelligence.performance_evidence import evidence_digest

        scope, subject, _ = await PerformanceService.authorize_evidence(request, actor)
        candidates, connectors = await DeveloperDataAggregator().collect_scoring_evidence(scope, subject)
        snapshot = validated_period_manifest(scope, candidates, captured_at=datetime.now(timezone.utc), connectors=connectors)
        return EvidencePreview(snapshot=snapshot, digest=evidence_digest(snapshot))

    async def evaluate_developer(
        self,
        request: DeveloperPerformanceCreate,
        developer_name: str,
        developer_email: str,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None,
        evaluated_by: str = "system"
    ) -> DeveloperPerformance:
        """Retired numeric entry point; no model output can create a period rating."""
        raise PeriodScoringPending()

    async def add_role_feedback(
        self,
        performance_id: str,
        role: str,
        feedback: Dict[str, Any]
    ) -> DeveloperPerformance:
        """Legacy feedback cannot mutate numerical or historical assessments."""
        from domain.services.performance_human_service import HumanScoringPending
        raise HumanScoringPending(ceo=role.lower() == "ceo")

    @staticmethod
    def compose_human_reviews(policy, reviews, engineering=None):
        from intelligence.performance_human import aggregate_human_reviews
        return aggregate_human_reviews(policy, reviews, engineering)

    def _calculate_role_scores(self, role_eval: RoleEvaluation):
        """Legacy fields have no approved anchors, assignments or completeness policy."""
        result = self.compose_human_reviews(None, ())
        return {"average": result.calculation.human_score, "contribution": None, "role_count": 0}
    
    async def get_developer_performance(
        self,
        developer_id: str,
        period_label: Optional[str] = None
    ) -> Optional[DeveloperPerformance]:
        """
        Get performance evaluation for a developer.
        
        Args:
            developer_id: Developer's user ID
            period_label: Specific period (optional, returns latest if not specified)
        
        Returns:
            DeveloperPerformance or None
        """
        if period_label:
            data = await self.performance_repo.get_by_developer_and_period(
                developer_id, period_label
            )
        else:
            data = await self.performance_repo.get_latest_by_developer(developer_id)
        
        if data:
            return DeveloperPerformance(**data)
        return None
    
    async def get_performance_trend(
        self,
        developer_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get historical performance trend for a developer.
        
        Args:
            developer_id: Developer's user ID
            limit: Number of periods to return
        
        Returns:
            List of performance records ordered by date
        """
        performances = await self.performance_repo.get_by_developer(
            developer_id, limit=limit
        )
        
        trend_data = []
        for perf_data in performances:
            trend_data.append({
                "period_label": perf_data.get("period_label"),
                "period_start": perf_data.get("period_start"),
                "final_score": perf_data.get("final_score"),
                "grade": perf_data.get("grade"),
                "ai_score": perf_data.get("ai_evaluation", {}).get("score", 0),
                "role_score": perf_data.get("role_evaluation", {}).get("contribution", 0),
                "scoring": legacy_metadata_for_record(perf_data).model_dump(mode="json"),
            })
        
        return trend_data
    
    async def get_team_performance(
        self,
        project_id: str,
        period_label: str
    ) -> List[Dict[str, Any]]:
        """
        Get performance summary for all developers in a project.
        
        Args:
            project_id: Project ID
            period_label: Period to get data for
        
        Returns:
            List of developer performance summaries
        """
        performances = await self.performance_repo.get_by_project_and_period(
            project_id, period_label
        )
        
        team_data = []
        for perf_data in performances:
            team_data.append({
                "developer_id": perf_data.get("developer_id"),
                "developer_name": perf_data.get("developer_name"),
                "final_score": perf_data.get("final_score"),
                "grade": perf_data.get("grade"),
                "trend": perf_data.get("trend"),
                "created_at": perf_data.get("created_at"),  # Add this for last_evaluated
                "strengths": perf_data.get("ai_evaluation", {}).get("strengths", []),
                "weaknesses": perf_data.get("ai_evaluation", {}).get("weaknesses", []),
                "scoring": legacy_metadata_for_record(perf_data).model_dump(mode="json"),
            })
        
        # Sort by score descending
        team_data.sort(key=lambda x: x['final_score'], reverse=True)
        
        return team_data
