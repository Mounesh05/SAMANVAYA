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
    RoleEvaluation,
    PMFeedback,
    LeadFeedback,
    QAFeedback,
    DevOpsFeedback,
    CEOFeedback,
    HRFeedback
)
from repositories.performance_repository import PerformanceRepository
from domain.models.performance_scoring import legacy_metadata_for_record
from intelligence.contribution_credit import (
    combine_hybrid_credit,
)

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
        """
        Add structured feedback from a specific role.
        
        Args:
            performance_id: Performance evaluation ID
            role: Role providing feedback (pm, lead, qa, devops, ceo, hr)
            feedback: Structured feedback with 1-5 ratings
        
        Returns:
            Updated performance with new role feedback
        """
        
        # Get existing performance
        performance_data = await self.performance_repo.get_by_id(performance_id)
        target_update_id = performance_id
        if not performance_data:
            from repositories.user_repository import UserRepository
            user_repo = UserRepository()
            target_user = await user_repo.find_by_employee_id(performance_id)
            if not target_user:
                raise ValueError(f"Performance evaluation or employee '{performance_id}' not found")
            target_role = target_user.get("role", "").upper()
            if target_role in ("CEO", "HR"):
                raise ValueError(f"Cannot evaluate {target_role} role. Performance evaluations only apply to engineering contributors.")
            now_utc = datetime.utcnow()
            from domain.models.developer_performance import PerformanceBreakdown, AIEvaluation
            init_perf = DeveloperPerformance(
                developer_id=target_user["employee_id"],
                developer_name=target_user.get("name", target_user["employee_id"]),
                project_id=target_user.get("team_id") or "ENGINEERING",
                period_type="quarter",
                period_start=now_utc,
                period_end=now_utc,
                period_label=f"{now_utc.year}-Q{(now_utc.month - 1) // 3 + 1}",
                ai_evaluation=AIEvaluation(
                    score=0.0,
                    breakdown=PerformanceBreakdown(
                        code_quality=0.0, delivery=0.0, collaboration=0.0, reliability=0.0, engineering_impact=0.0, engineering_judgment=0.0
                    ),
                    strengths=[], weaknesses=[], recommendations=[], reasoning="Initialized for role feedback.", confidence="low"
                ),
                role_evaluation=RoleEvaluation(),
                final_score=0.0,
                grade="Under Review",
                confidence_level="low",
                confidence_reason="Role feedback initialized",
            )
            inserted_id = await self.performance_repo.create(init_perf.model_dump())
            init_perf.id = inserted_id
            performance = init_perf
            target_update_id = inserted_id
        else:
            performance = DeveloperPerformance(**performance_data)
            target_update_id = str(performance_data.get("_id", performance_id))
        
        # Add role-specific feedback
        if role == "pm":
            performance.role_evaluation.pm = PMFeedback(**feedback)
        elif role == "lead":
            performance.role_evaluation.lead = LeadFeedback(**feedback)
        elif role == "qa":
            performance.role_evaluation.qa = QAFeedback(**feedback)
        elif role == "devops":
            performance.role_evaluation.devops = DevOpsFeedback(**feedback)
        elif role == "ceo":
            performance.role_evaluation.ceo = CEOFeedback(**feedback)
        elif role == "hr":
            performance.role_evaluation.hr = HRFeedback(**feedback)
        else:
            raise ValueError(f"Invalid role: {role}")
        
        # Recalculate role contribution
        role_scores = self._calculate_role_scores(performance.role_evaluation)
        performance.role_evaluation.average_score = role_scores['average']
        performance.role_evaluation.contribution = role_scores['contribution']
        
        previous_credit = (
            performance.contribution_credit.model_dump()
            if performance.contribution_credit
            else None
        )
        objective_credit = (
            performance.contribution_credit.model_dump()
            if performance.contribution_credit
            else {
                "score": performance.final_score,
                "components": {},
                "missing_evidence": ["historical_evaluation"],
                "evidence_counts": {},
            }
        )
        human_score = role_scores["average"] if role_scores["role_count"] else None
        updated_credit = combine_hybrid_credit(
            objective_credit,
            ai_score=performance.ai_evaluation.score,
            human_score=human_score,
            ai_available=not performance.ai_evaluation.data_quality.get(
                "ai_evaluation_failed", False
            ),
        )
        performance.contribution_credit = updated_credit
        performance.final_score = updated_credit["score"]
        if previous_credit:
            performance.credit_history.append({
                "score": previous_credit["score"],
                "methodology_version": previous_credit.get("methodology_version"),
                "recorded_at": datetime.utcnow().isoformat(),
                "reason": f"before_{role}_feedback",
            })
        performance.grade = self.evaluation_agent.determine_grade(performance.final_score)
        
        # Update in database
        await self.performance_repo.update(target_update_id, performance.model_dump())
        
        return performance
    
    def _calculate_role_scores(self, role_eval: RoleEvaluation) -> Dict[str, float]:
        """
        Calculate role feedback scores.
        
        Each role rates on 1-5 scale across 4 criteria.
        Average all criteria, normalize to 0-100, then average across roles.
        """
        role_scores = []
        
        # PM
        if role_eval.pm:
            pm_avg = (
                role_eval.pm.criterion_1 +
                role_eval.pm.criterion_2 +
                role_eval.pm.criterion_3 +
                role_eval.pm.criterion_4
            ) / 4  # Average of 4 criteria (1-5 scale)
            pm_score = (pm_avg / 5) * 100  # Normalize to 0-100
            role_scores.append(pm_score)
        
        # Lead
        if role_eval.lead:
            lead_avg = (
                role_eval.lead.criterion_1 +
                role_eval.lead.criterion_2 +
                role_eval.lead.criterion_3 +
                role_eval.lead.criterion_4
            ) / 4
            lead_score = (lead_avg / 5) * 100
            role_scores.append(lead_score)
        
        # QA
        if role_eval.qa:
            qa_avg = (
                role_eval.qa.criterion_1 +
                role_eval.qa.criterion_2 +
                role_eval.qa.criterion_3 +
                role_eval.qa.criterion_4
            ) / 4
            qa_score = (qa_avg / 5) * 100
            role_scores.append(qa_score)
        
        # DevOps
        if role_eval.devops:
            devops_avg = (
                role_eval.devops.criterion_1 +
                role_eval.devops.criterion_2 +
                role_eval.devops.criterion_3 +
                role_eval.devops.criterion_4
            ) / 4
            devops_score = (devops_avg / 5) * 100
            role_scores.append(devops_score)
        
        # CEO
        if role_eval.ceo:
            ceo_avg = (
                role_eval.ceo.criterion_1 +
                role_eval.ceo.criterion_2 +
                role_eval.ceo.criterion_3 +
                role_eval.ceo.criterion_4
            ) / 4
            ceo_score = (ceo_avg / 5) * 100
            role_scores.append(ceo_score)
        
        # HR
        if role_eval.hr:
            if role_eval.hr.normalized_score is not None:
                hr_score = role_eval.hr.normalized_score
            else:
                criteria = [
                    c for c in (
                        role_eval.hr.criterion_1,
                        role_eval.hr.criterion_2,
                        role_eval.hr.criterion_3,
                        role_eval.hr.criterion_4,
                    ) if c is not None
                ]
                if criteria:
                    hr_avg = sum(criteria) / len(criteria)
                    hr_score = (hr_avg / 5.0) * 100.0
                else:
                    hr_score = None
            if hr_score is not None:
                role_scores.append(hr_score)
        
        # Calculate average
        if role_scores:
            average_score = sum(role_scores) / len(role_scores)
            contribution = (average_score / 100) * 10  # Convert to 0-10
        else:
            average_score = 0
            contribution = 0
        
        return {
            'average': average_score,
            'contribution': contribution,
            'role_count': len(role_scores)
        }
    
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
