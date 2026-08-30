"""
Developer Performance Service
Orchestrates the complete performance evaluation process:
1. Data aggregation
2. AI evaluation (90%)
3. Role feedback collection (10%)
4. Final score calculation
5. Trend analysis
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
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


class PerformanceService:
    """
    Main service for developer performance evaluation.
    
    Orchestrates:
    - Data collection from multiple sources
    - AI-driven evaluation (90% of score)
    - Role feedback collection (10% of score)
    - Final score calculation and grading
    - Trend analysis
    """
    
    def __init__(self, github_token: Optional[str] = None):
        self.data_aggregator = DeveloperDataAggregator(github_token)
        self.evaluation_agent = PerformanceEvaluationAgent()
        self.performance_repo = PerformanceRepository()
    
    async def evaluate_developer(
        self,
        request: DeveloperPerformanceCreate,
        developer_name: str,
        developer_email: str,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None,
        evaluated_by: str = "system"
    ) -> DeveloperPerformance:
        """
        Complete developer performance evaluation.
        
        This is the main entry point that:
        1. Collects all developer data
        2. Sends to AI for evaluation (90%)
        3. Collects role feedback (10%)
        4. Calculates final score
        5. Stores and returns result
        
        Args:
            request: Evaluation request with period info
            developer_name: Developer's name
            developer_email: Developer's email for GitHub matching
            repo_owner: GitHub repo owner (optional)
            repo_name: GitHub repo name (optional)
            evaluated_by: Who triggered the evaluation
        
        Returns:
            Complete DeveloperPerformance with scores and insights
        """
        
        # Step 1: Collect all developer data
        print(f"📊 Collecting data for {developer_name} ({request.period_label})...")
        developer_data = await self.data_aggregator.aggregate_developer_data(
            developer_id=request.developer_id,
            developer_email=developer_email,
            project_id=request.project_id,
            period_start=request.period_start,
            period_end=request.period_end,
            repo_owner=repo_owner,
            repo_name=repo_name
        )
        
        # Step 2: AI Evaluation (90% of score)
        print(f"🤖 AI evaluating performance...")
        ai_evaluation = await self.evaluation_agent.evaluate_performance(
            developer_data=developer_data,
            developer_name=developer_name,
            period_label=request.period_label
        )
        
        # Step 3: Role Evaluation (10% of score) - Initialize empty
        # Role feedback is collected separately via API
        role_evaluation = RoleEvaluation(
            average_score=0,
            contribution=0
        )
        
        # Step 4: Calculate final score
        # For now, just AI score (role feedback added later)
        final_score = ai_evaluation.score  # Out of 90
        final_score_percentage = (final_score / 90) * 100  # Convert to 0-100
        
        # Step 5: Calculate confidence
        days_of_data = (request.period_end - request.period_start).days
        confidence_level, confidence_reason = self.evaluation_agent.calculate_confidence_level(
            developer_data, days_of_data
        )
        
        # Step 6: Get grade
        grade = self.evaluation_agent.determine_grade(final_score_percentage)
        
        # Step 7: Get previous score for trend analysis
        previous_performance = await self.performance_repo.get_previous_performance(
            request.developer_id,
            request.period_start
        )
        
        previous_score = None
        score_change = None
        trend = None
        
        if previous_performance:
            previous_score = previous_performance.get("final_score", 0)
            score_change = final_score_percentage - previous_score
            
            if score_change > 5:
                trend = "improving"
            elif score_change < -5:
                trend = "declining"
            else:
                trend = "stable"
        
        # Step 8: Build complete performance object
        performance = DeveloperPerformance(
            developer_id=request.developer_id,
            developer_name=developer_name,
            project_id=request.project_id,
            period_type=request.period_type,
            period_start=request.period_start,
            period_end=request.period_end,
            period_label=request.period_label,
            ai_evaluation=ai_evaluation,
            role_evaluation=role_evaluation,
            final_score=final_score_percentage,
            grade=grade,
            previous_score=previous_score,
            score_change=score_change,
            trend=trend,
            confidence_level=confidence_level,
            confidence_reason=confidence_reason,
            data_points={
                "commits": developer_data['summary']['total_commits'],
                "prs": developer_data['summary']['total_prs'],
                "tasks": developer_data['summary']['total_tasks'],
                "days": days_of_data
            },
            evaluated_by=evaluated_by
        )
        
        # Step 9: Store in database
        await self.performance_repo.create(performance.dict())
        
        print(f"✅ Evaluation complete: {final_score_percentage:.1f}/100 ({grade})")
        
        return performance
    
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
        if not performance_data:
            raise ValueError(f"Performance {performance_id} not found")
        
        performance = DeveloperPerformance(**performance_data)
        
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
        
        # Recalculate final score
        ai_score = performance.ai_evaluation.score  # Out of 90
        role_contribution = role_scores['contribution']  # Out of 10
        
        performance.final_score = ((ai_score / 90) * 90) + ((role_contribution / 10) * 10)
        performance.grade = self.evaluation_agent.determine_grade(performance.final_score)
        
        # Update in database
        await self.performance_repo.update(performance_id, performance.dict())
        
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
            hr_avg = (
                role_eval.hr.criterion_1 +
                role_eval.hr.criterion_2 +
                role_eval.hr.criterion_3 +
                role_eval.hr.criterion_4
            ) / 4
            hr_score = (hr_avg / 5) * 100
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
            })
        
        # Sort by score descending
        team_data.sort(key=lambda x: x['final_score'], reverse=True)
        
        return team_data
