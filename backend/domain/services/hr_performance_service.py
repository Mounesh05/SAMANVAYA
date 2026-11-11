"""
Service for HR Performance Assessments and 90% AI + 10% Human Evaluation Aggregation.
Enforces rubric scales, evidence requirements for negative assessments, bias prevention,
and configurable human weight aggregation.
"""

from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone
import uuid
import logging
from domain.models.hr_performance import (
    HRAssessment,
    HRAssessmentDimensionItem,
    HRAssessmentCreate,
    HumanEvaluationPolicy,
    HumanEvaluationCompleteness,
    HRDimensionKey,
    ComplianceStatus,
)
from domain.models.developer_performance import DeveloperPerformance, HRFeedback, RoleEvaluation
from repositories.hr_performance_repository import (
    HRAssessmentRepository,
    EvaluationPolicyRepository,
    DEFAULT_HUMAN_EVALUATION_POLICY,
)
from repositories.performance_repository import PerformanceRepository
from agents.performance_agent import PerformanceEvaluationAgent
from core.audit import log_audit, AuditAction

logger = logging.getLogger(__name__)


class HRPerformanceService:
    """Orchestrates HR workplace evaluations and human score aggregation."""

    def __init__(self):
        self.assessment_repo = HRAssessmentRepository()
        self.policy_repo = EvaluationPolicyRepository()
        self.performance_repo = PerformanceRepository()
        self.evaluation_agent = PerformanceEvaluationAgent()

    def calculate_hr_dimension_score(self, item: HRAssessmentDimensionItem) -> Optional[float]:
        """
        Normalize a single dimension rating (1-4) to 0-100 scale.
        N/O (Not Observed) returns None and is NEVER converted to 0.
        """
        if item.is_not_observed or item.rating is None:
            return None
        # 1 -> 25.0, 2 -> 50.0, 3 -> 75.0, 4 -> 100.0
        return round((float(item.rating) / 4.0) * 100.0, 2)

    def calculate_overall_hr_score(
        self,
        dimensions: Dict[str, HRAssessmentDimensionItem]
    ) -> Tuple[Optional[float], List[str]]:
        """
        Calculate overall HR assessment score from observed dimensions.
        Returns:
            (overall_score, validation_errors)
        """
        errors = []
        observed_scores = []

        for dim_key, item in dimensions.items():
            # Validate evidence requirements for negative ratings (1 or 2)
            if item.rating in (1, 2) and not item.is_not_observed:
                evidence = (item.evidence_description or "").strip()
                if len(evidence) < 15:
                    errors.append(
                        f"Dimension '{dim_key}' has rating {item.rating} which requires documented "
                        "substantiated evidence description (minimum 15 characters)."
                    )
            
            score = self.calculate_hr_dimension_score(item)
            if score is not None:
                observed_scores.append(score)

        if not observed_scores:
            # All items were N/O or unscored; not penalized, score is None
            return None, errors

        overall = round(sum(observed_scores) / len(observed_scores), 2)
        return overall, errors

    async def get_or_create_policy(self) -> Dict[str, Any]:
        """Retrieve current active human evaluation policy."""
        return await self.policy_repo.get_active_policy()

    async def configure_policy(
        self,
        role_weights: Dict[str, float],
        configured_by: str,
        notes: Optional[str] = None
    ) -> HumanEvaluationPolicy:
        """
        Configure human evaluation component weights across eligible roles.
        Validates:
        - Weights must sum to 1.0 (with small tolerance)
        - Roles must be valid evaluator roles
        - Preserves the overall 90% AI + 10% Human model
        """
        if not role_weights:
            raise ValueError("Role weights dictionary cannot be empty")

        total_weight = sum(role_weights.values())
        if not (0.99 <= total_weight <= 1.01):
            raise ValueError(f"Role weights must sum to 1.0 (got {total_weight:.4f})")

        valid_roles = {"lead", "pm", "hr", "qa", "devops", "ceo", "scrum_master"}
        for role, weight in role_weights.items():
            if role.lower() not in valid_roles:
                raise ValueError(f"Invalid evaluator role: {role}")
            if weight < 0:
                raise ValueError(f"Weight for role {role} cannot be negative")

        current_policy = await self.get_or_create_policy()
        current_version = current_policy.get("version", "1.0.0")
        try:
            parts = [int(p) for p in current_version.split(".")]
            parts[-1] += 1
            new_version = ".".join(str(p) for p in parts)
        except Exception:
            new_version = f"{current_version}.1"

        new_policy = HumanEvaluationPolicy(
            policy_id=f"POLICY-V{new_version}",
            version=new_version,
            is_active=True,
            ai_weight=0.90,
            human_weight=0.10,
            role_weights={r.lower(): round(w, 4) for r, w in role_weights.items()},
            configured_by=configured_by,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            notes=notes
        )

        saved = await self.policy_repo.save_policy(new_policy.model_dump())
        await log_audit(
            action=AuditAction.EVALUATION_POLICY_CONFIGURED,
            actor={"employee_id": configured_by, "role": "ADMIN"},
            resource_type="evaluation_policy",
            resource_id=new_policy.policy_id,
            details={"version": new_version, "role_weights": new_policy.role_weights}
        )
        return HumanEvaluationPolicy(**saved)

    def calculate_aggregated_human_score(
        self,
        performance: DeveloperPerformance,
        policy: Dict[str, Any]
    ) -> Tuple[Optional[float], Dict[str, Optional[float]]]:
        """
        Calculate weighted human evaluation score (0-100) from submitted role feedback.
        Uses active policy weights and normalizes among available reviewers.
        """
        role_weights: Dict[str, float] = policy.get("role_weights", {})
        role_eval = performance.role_evaluation
        role_scores: Dict[str, Optional[float]] = {}

        # 1. PM
        if role_eval.pm:
            pm_avg = (
                role_eval.pm.criterion_1 +
                role_eval.pm.criterion_2 +
                role_eval.pm.criterion_3 +
                role_eval.pm.criterion_4
            ) / 4.0
            role_scores["pm"] = (pm_avg / 5.0) * 100.0
        else:
            role_scores["pm"] = None

        # 2. Lead
        if role_eval.lead:
            lead_avg = (
                role_eval.lead.criterion_1 +
                role_eval.lead.criterion_2 +
                role_eval.lead.criterion_3 +
                role_eval.lead.criterion_4
            ) / 4.0
            role_scores["lead"] = (lead_avg / 5.0) * 100.0
        else:
            role_scores["lead"] = None

        # 3. QA
        if role_eval.qa:
            qa_avg = (
                role_eval.qa.criterion_1 +
                role_eval.qa.criterion_2 +
                role_eval.qa.criterion_3 +
                role_eval.qa.criterion_4
            ) / 4.0
            role_scores["qa"] = (qa_avg / 5.0) * 100.0
        else:
            role_scores["qa"] = None

        # 4. DevOps
        if role_eval.devops:
            devops_avg = (
                role_eval.devops.criterion_1 +
                role_eval.devops.criterion_2 +
                role_eval.devops.criterion_3 +
                role_eval.devops.criterion_4
            ) / 4.0
            role_scores["devops"] = (devops_avg / 5.0) * 100.0
        else:
            role_scores["devops"] = None

        # 5. CEO
        if role_eval.ceo:
            ceo_avg = (
                role_eval.ceo.criterion_1 +
                role_eval.ceo.criterion_2 +
                role_eval.ceo.criterion_3 +
                role_eval.ceo.criterion_4
            ) / 4.0
            role_scores["ceo"] = (ceo_avg / 5.0) * 100.0
        else:
            role_scores["ceo"] = None

        # 6. HR
        if role_eval.hr:
            if role_eval.hr.normalized_score is not None:
                role_scores["hr"] = role_eval.hr.normalized_score
            else:
                # Fallback to criteria if present
                c_vals = [
                    v for v in (
                        role_eval.hr.criterion_1,
                        role_eval.hr.criterion_2,
                        role_eval.hr.criterion_3,
                        role_eval.hr.criterion_4
                    ) if v is not None
                ]
                if c_vals:
                    role_scores["hr"] = (sum(c_vals) / len(c_vals) / 5.0) * 100.0
                else:
                    role_scores["hr"] = None
        else:
            role_scores["hr"] = None

        # Aggregate only roles that have a score
        active_role_weights = {}
        for role, score in role_scores.items():
            if score is not None and role in role_weights:
                active_role_weights[role] = role_weights[role]

        if not active_role_weights:
            return None, role_scores

        total_weight = sum(active_role_weights.values())
        if total_weight <= 0:
            return None, role_scores

        weighted_sum = sum(
            role_scores[role] * (weight / total_weight)
            for role, weight in active_role_weights.items()
        )
        return round(weighted_sum, 2), role_scores

    async def save_hr_assessment_draft(
        self,
        performance_id: str,
        data: HRAssessmentCreate,
        user: dict
    ) -> HRAssessment:
        """Create or update HR assessment draft without affecting final score."""
        performance_dict = await self.performance_repo.get_by_id(performance_id)
        developer_id = None
        actual_performance_id = performance_id

        if performance_dict:
            developer_id = performance_dict.get("developer_id")
            actual_performance_id = str(performance_dict.get("_id", performance_id))
        else:
            # Check if performance_id is an employee ID
            from repositories.user_repository import UserRepository
            user_repo = UserRepository()
            target_user = await user_repo.find_by_employee_id(performance_id)
            if not target_user:
                raise ValueError(f"Performance evaluation or employee '{performance_id}' not found")

            target_role = target_user.get("role", "").upper()
            if target_role in ("CEO", "HR"):
                raise ValueError(f"Cannot evaluate {target_role} role. Performance evaluations only apply to engineering contributors.")

            developer_id = target_user.get("employee_id")
            actual_performance_id = f"PERF-{developer_id}"

        existing = await self.assessment_repo.get_by_performance_id(performance_id)
        if not existing and developer_id:
            existing = await self.assessment_repo.get_by_performance_id(developer_id)

        assessment_id = existing.get("assessment_id") if existing else f"HR-EVAL-{uuid.uuid4().hex[:8].upper()}"

        policy = await self.get_or_create_policy()
        overall_score, _ = self.calculate_overall_hr_score(data.dimensions)

        assessment = HRAssessment(
            assessment_id=assessment_id,
            performance_id=actual_performance_id,
            developer_id=developer_id,
            evaluator_id=user.get("employee_id", user.get("id", "")),
            evaluator_name=user.get("name", "HR Evaluator"),
            evaluator_role="HR",
            status="draft",
            dimensions=data.dimensions,
            overall_hr_score=overall_score,
            policy_version=policy.get("version", "1.0.0"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            general_comments=data.general_comments
        )

        saved = await self.assessment_repo.save_assessment(assessment.model_dump())
        await log_audit(
            action=AuditAction.HR_ASSESSMENT_CREATED,
            actor=user,
            resource_type="hr_assessment",
            resource_id=assessment_id,
            details={"developer_id": developer_id, "performance_id": actual_performance_id, "status": "draft"}
        )
        return HRAssessment(**saved)

    async def submit_hr_assessment(
        self,
        performance_id: str,
        data: HRAssessmentCreate,
        user: dict
    ) -> DeveloperPerformance:
        """
        Submit finalized HR assessment.
        Validates evidence for negative ratings, recalculates human score
        and overall 90% AI + 10% Human score.
        """
        performance_dict = await self.performance_repo.get_by_id(performance_id)
        developer_id = None
        target_emp = None
        actual_performance_id = performance_id

        from repositories.user_repository import UserRepository
        user_repo = UserRepository()

        if performance_dict:
            developer_id = performance_dict.get("developer_id")
            actual_performance_id = str(performance_dict.get("_id", performance_id))
        else:
            # Check if performance_id is an employee ID
            target_emp = await user_repo.find_by_employee_id(performance_id)
            if not target_emp:
                raise ValueError(f"Performance evaluation or employee '{performance_id}' not found")
            target_role = target_emp.get("role", "").upper()
            if target_role in ("CEO", "HR"):
                raise ValueError(f"Cannot evaluate {target_role} role. Performance evaluations only apply to engineering contributors.")
            developer_id = target_emp.get("employee_id")
            actual_performance_id = f"PERF-{developer_id}"

        overall_hr_score, validation_errors = self.calculate_overall_hr_score(data.dimensions)
        if validation_errors:
            raise ValueError("; ".join(validation_errors))

        policy = await self.get_or_create_policy()
        existing = await self.assessment_repo.get_by_performance_id(performance_id)
        if not existing and developer_id:
            existing = await self.assessment_repo.get_by_performance_id(developer_id)

        assessment_id = existing.get("assessment_id") if existing else f"HR-EVAL-{uuid.uuid4().hex[:8].upper()}"

        now_utc = datetime.now(timezone.utc)
        assessment = HRAssessment(
            assessment_id=assessment_id,
            performance_id=actual_performance_id,
            developer_id=developer_id,
            evaluator_id=user.get("employee_id", user.get("id", "")),
            evaluator_name=user.get("name", "HR Evaluator"),
            evaluator_role="HR",
            status="submitted",
            dimensions=data.dimensions,
            overall_hr_score=overall_hr_score,
            policy_version=policy.get("version", "1.0.0"),
            created_at=existing.get("created_at", now_utc) if existing else now_utc,
            updated_at=now_utc,
            submitted_at=now_utc,
            general_comments=data.general_comments
        )

        await self.assessment_repo.save_assessment(assessment.model_dump())

        # Build HRFeedback object
        hr_feedback = HRFeedback(
            criterion_1=data.dimensions.get(HRDimensionKey.PROFESSIONAL_CONDUCT.value, HRAssessmentDimensionItem(dimension="")).rating or 3,
            criterion_2=data.dimensions.get(HRDimensionKey.WORKPLACE_ETHICS.value, HRAssessmentDimensionItem(dimension="")).rating or 3,
            criterion_3=data.dimensions.get(HRDimensionKey.POLICY_COMPLIANCE.value, HRAssessmentDimensionItem(dimension="")).rating or 3,
            criterion_4=data.dimensions.get(HRDimensionKey.WORKPLACE_ACCOUNTABILITY.value, HRAssessmentDimensionItem(dimension="")).rating or 3,
            assessment_id=assessment_id,
            status="submitted",
            dimensions={k: v.model_dump() for k, v in data.dimensions.items()},
            normalized_score=overall_hr_score,
            policy_version=policy.get("version", "1.0.0"),
            evaluator_id=user.get("employee_id", user.get("id", "")),
            evaluator_name=user.get("name", "HR Evaluator"),
            submitted_at=now_utc,
            comments=data.general_comments
        )

        if not performance_dict:
            if not target_emp:
                target_emp = await user_repo.find_by_employee_id(developer_id)
            dev_name = target_emp.get("name", developer_id) if target_emp else developer_id
            team_id = target_emp.get("team_id") or "ENGINEERING" if target_emp else "ENGINEERING"
            current_quarter = f"{now_utc.year}-Q{(now_utc.month - 1) // 3 + 1}"

            role_eval = RoleEvaluation(
                hr=hr_feedback,
                average_score=overall_hr_score or 0.0,
                contribution=round(((overall_hr_score or 0.0) / 100.0) * 10.0, 2),
            )
            human_weight = policy.get("human_weight", 0.10)
            final_score = round(((overall_hr_score or 0.0) / 100.0) * (human_weight * 100.0), 2)
            grade = self.evaluation_agent.determine_grade(final_score if final_score > 0 else 75.0)

            from domain.models.developer_performance import PerformanceBreakdown, AIEvaluation
            performance = DeveloperPerformance(
                developer_id=developer_id,
                developer_name=dev_name,
                project_id=team_id,
                period_type="quarter",
                period_start=now_utc,
                period_end=now_utc,
                period_label=current_quarter,
                ai_evaluation=AIEvaluation(
                    score=0.0,
                    breakdown=PerformanceBreakdown(
                        code_quality=0.0,
                        delivery=0.0,
                        collaboration=0.0,
                        reliability=0.0,
                        engineering_impact=0.0,
                        engineering_judgment=0.0,
                    ),
                    strengths=["Workplace assessment completed by HR."],
                    weaknesses=[],
                    recommendations=["Pending AI engineering evaluation run."],
                    reasoning="HR workplace evaluation recorded. Engineering AI evaluation pending.",
                    confidence="medium",
                    data_quality={"status": "initial_with_hr_assessment"},
                ),
                role_evaluation=role_eval,
                final_score=final_score,
                grade=grade,
                confidence_level="medium",
                confidence_reason="HR workplace evaluation submitted; awaiting AI contribution calculation",
                data_points={},
                created_at=now_utc,
                updated_at=now_utc,
                evaluated_by=user.get("employee_id", "hr"),
                hr_assessment=assessment.model_dump(),
                human_evaluation_policy_version=policy.get("version", "1.0.0"),
            )
            inserted_id = await self.performance_repo.create(performance.model_dump())
            performance.id = inserted_id
        else:
            performance = DeveloperPerformance(**performance_dict)
            performance.role_evaluation.hr = hr_feedback
            performance.hr_assessment = assessment.model_dump()
            performance.human_evaluation_policy_version = policy.get("version", "1.0.0")

            # Recalculate human score using active policy
            human_score, _ = self.calculate_aggregated_human_score(performance, policy)
            if human_score is not None:
                performance.role_evaluation.average_score = human_score
                performance.role_evaluation.contribution = round((human_score / 100.0) * 10.0, 2)

            # 90% AI + 10% Human combination
            ai_score = performance.ai_evaluation.score
            ai_weight = policy.get("ai_weight", 0.90)
            human_weight = policy.get("human_weight", 0.10)

            if human_score is not None:
                final_score = round((ai_score * ai_weight) + (human_score * human_weight), 2)
            else:
                final_score = ai_score

            performance.final_score = final_score
            performance.grade = self.evaluation_agent.determine_grade(final_score)
            performance.updated_at = now_utc

            target_update_id = str(performance_dict.get("_id", performance_id))
            await self.performance_repo.update(target_update_id, performance.model_dump())

        await log_audit(
            action=AuditAction.HR_ASSESSMENT_SUBMITTED,
            actor=user,
            resource_type="hr_assessment",
            resource_id=assessment_id,
            details={
                "developer_id": developer_id,
                "performance_id": actual_performance_id,
                "overall_hr_score": overall_hr_score,
                "final_score": performance.final_score,
            }
        )
        return performance

    async def check_human_evaluation_completeness(
        self,
        performance_id: str
    ) -> HumanEvaluationCompleteness:
        """Check completeness of human evaluations across configured roles."""
        performance_dict = await self.performance_repo.get_by_id(performance_id)
        if not performance_dict:
            from repositories.user_repository import UserRepository
            user_repo = UserRepository()
            target_user = await user_repo.find_by_employee_id(performance_id)
            if not target_user:
                raise ValueError(f"Performance evaluation or employee '{performance_id}' not found")
            now_utc = datetime.now(timezone.utc)
            from domain.models.developer_performance import PerformanceBreakdown, AIEvaluation
            performance = DeveloperPerformance(
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
                    strengths=[], weaknesses=[], recommendations=[], reasoning="Completeness check container", confidence="low"
                ),
                role_evaluation=RoleEvaluation(),
                final_score=0.0,
                grade="Under Review",
                confidence_level="low",
                confidence_reason="Pending",
            )
        else:
            performance = DeveloperPerformance(**performance_dict)

        policy = await self.get_or_create_policy()
        configured_weights = policy.get("role_weights", {})
        required_roles = [r for r, w in configured_weights.items() if w > 0]

        human_score, role_scores = self.calculate_aggregated_human_score(performance, policy)
        submitted_roles = [r for r, s in role_scores.items() if s is not None and r in required_roles]
        pending_roles = [r for r in required_roles if r not in submitted_roles]

        is_complete = len(pending_roles) == 0

        return HumanEvaluationCompleteness(
            performance_id=performance_id,
            developer_id=performance.developer_id,
            period_label=performance.period_label,
            policy_version=policy.get("version", "1.0.0"),
            required_roles=required_roles,
            submitted_roles=submitted_roles,
            pending_roles=pending_roles,
            is_complete=is_complete,
            human_score=human_score,
            role_scores=role_scores,
            details={"weights": configured_weights}
        )

