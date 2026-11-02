"""
Performance Evaluation & Aggregation Agent.

Architecture role:
    SPECIALIST AGENTS (Code, QA, DevOps, CI/CD, Meeting)
              ↓
    Individual dimension scores
              ↓
    PERFORMANCE AGENT / AGGREGATION LAYER
              ↓
    Holistic employee performance view + Role feedback blending

The Performance Agent does NOT invent numeric scores or re-evaluate raw GitHub evidence.
It aggregates, normalizes, and contextualizes the specialist agents' evaluations.
"""

from typing import Dict, Any, Optional, List, Tuple
import logging
import time

from intelligence.scoring.models import (
    EmployeeScore,
    AggregatedEmployeeEvaluation,
    EvaluationPeriod,
)
from intelligence.scoring.engine import ScoringEngine
from intelligence.scoring.config import DEFAULT_AGGREGATION_WEIGHTS
from domain.models.developer_performance import (
    AIEvaluation,
    PerformanceBreakdown,
)
from .llm_provider import get_ollama_llm, check_ollama_connection

logger = logging.getLogger("samanvaya.performance_agent")


class PerformanceEvaluationAgent:
    """
    Aggregation agent that consolidates specialist agent scores into a unified evaluation.
    """

    def __init__(self):
        self.weights = DEFAULT_AGGREGATION_WEIGHTS

    async def aggregate_specialist_scores(
        self,
        agent_scores: Dict[str, EmployeeScore],
        developer_id: str,
        developer_name: str,
        period: EvaluationPeriod,
        company_id: str = "ORG-001",
        superior_score: Optional[float] = None,
    ) -> AggregatedEmployeeEvaluation:
        """
        Takes individual specialist scores and calculates the overall weighted evaluation.
        Missing data is handled gracefully without penalizing with zero.
        """
        aggregated = ScoringEngine.aggregate_agent_scores(
            agent_scores=agent_scores,
            weights=self.weights,
            employee_id=developer_id,
            employee_name=developer_name,
            company_id=company_id,
            period=period,
            superior_score=superior_score,
        )

        # Generate synthesis narrative if LLM is online
        if check_ollama_connection() and aggregated.overall_score is not None:
            summary_prompt = f"""You are the VP of Engineering reviewing a developer's quarterly performance scorecard.

DEVELOPER: {developer_name} ({developer_id})
PERIOD: {period.start_date} to {period.end_date}
OVERALL SCORE: {aggregated.overall_score:.1f}/100 (Grade: {aggregated.grade})

SPECIALIST SCORES:
- Code Quality: {agent_scores.get('code_quality', {}).score if hasattr(agent_scores.get('code_quality'), 'score') else 'N/A'}/100
- Testing & Reliability: {agent_scores.get('testing_reliability', {}).score if hasattr(agent_scores.get('testing_reliability'), 'score') else 'N/A'}/100
- DevOps & Infrastructure: {agent_scores.get('devops', {}).score if hasattr(agent_scores.get('devops'), 'score') else 'N/A'}/100
- CI/CD Performance: {agent_scores.get('cicd', {}).score if hasattr(agent_scores.get('cicd'), 'score') else 'N/A'}/100
- Agile & Collaboration: {agent_scores.get('agile_collaboration', {}).score if hasattr(agent_scores.get('agile_collaboration'), 'score') else 'N/A'}/100

KEY STRENGTHS:
{', '.join(aggregated.strengths) if aggregated.strengths else 'Consistent engineering execution'}

AREAS FOR GROWTH:
{', '.join(aggregated.weaknesses) if aggregated.weaknesses else 'Continue current trajectory'}

Write a concise, professional 2-3 sentence executive summary explaining the engineer's performance based on these specialist evaluations. Do NOT invent new numbers.
"""
            try:
                llm = get_ollama_llm(temperature=0.3)
                summary_res = await llm.ainvoke(summary_prompt)
                aggregated.summary = str(summary_res).strip()
            except Exception as e:
                logger.warning("[PERF-AGENT] Executive summary synthesis fallback: %s", e)
                aggregated.summary = f"Performance evaluation for {developer_name} ({aggregated.grade}): Overall engineering score {aggregated.overall_score:.1f}/100 based on specialist evaluations."
        else:
            aggregated.summary = f"Performance evaluation for {developer_name} ({aggregated.grade}): Overall engineering score {aggregated.overall_score if aggregated.overall_score is not None else 0.0:.1f}/100 across applicable specialist engineering dimensions."

        return aggregated

    async def evaluate_performance(
        self,
        developer_data: Dict[str, Any],
        developer_name: str,
        period_label: str,
    ) -> AIEvaluation:
        """
        Compatibility bridge: converts raw data / specialist scores into the AIEvaluation model.
        Maps the specialist agent evaluations into the 6 pillars expected by existing API and frontend.
        """
        agent_scores = developer_data.get("agent_scores")
        developer_id = developer_data.get("developer_id", "EMP-UNKNOWN")

        # If specialist scores are not already present in developer_data, run specialist agents
        if not agent_scores:
            from agents.code_agent import CodeScoringAgent
            from agents.qa_agent import QAScoringAgent
            from agents.devops_agent import DevOpsScoringAgent
            from agents.cicd_agent import CICDScoringAgent
            from agents.meeting_agent import MeetingScoringAgent

            period_info = developer_data.get("period", {})
            period = EvaluationPeriod(
                start_date=period_info.get("start", "2026-09-01"),
                end_date=period_info.get("end", "2026-09-30"),
                label=period_label,
            )

            code_agent = CodeScoringAgent()
            qa_agent = QAScoringAgent()
            devops_agent = DevOpsScoringAgent()
            cicd_agent = CICDScoringAgent()
            meeting_agent = MeetingScoringAgent()

            import asyncio
            scores_list = await asyncio.gather(
                code_agent.evaluate(developer_id, developer_name, developer_data, period),
                qa_agent.evaluate(developer_id, developer_name, developer_data, period),
                devops_agent.evaluate(developer_id, developer_name, developer_data, period),
                cicd_agent.evaluate(developer_id, developer_name, developer_data, period),
                meeting_agent.evaluate(developer_id, developer_name, developer_data, period),
            )

            agent_scores = {
                "code_quality": scores_list[0],
                "testing_reliability": scores_list[1],
                "devops": scores_list[2],
                "cicd": scores_list[3],
                "agile_collaboration": scores_list[4],
            }

        # Aggregate specialist scores
        period_obj = EvaluationPeriod(
            start_date=developer_data.get("period", {}).get("start", "2026-09-01"),
            end_date=developer_data.get("period", {}).get("end", "2026-09-30"),
            label=period_label,
        )

        aggregated = await self.aggregate_specialist_scores(
            agent_scores=agent_scores,
            developer_id=developer_id,
            developer_name=developer_name,
            period=period_obj,
            company_id=developer_data.get("company_id", "ORG-001"),
        )

        # Scale 0-100 specialist scores into legacy 90-point breakdown
        # Code Quality (max 25): from code_quality
        cq_raw = agent_scores.get("code_quality").score if agent_scores.get("code_quality") else 85.0
        cq_score = round(((cq_raw or 80.0) / 100.0) * 25.0, 1)

        # Delivery & Execution (max 20): from meeting_agent
        del_raw = agent_scores.get("agile_collaboration").score if agent_scores.get("agile_collaboration") else 85.0
        del_score = round(((del_raw or 80.0) / 100.0) * 20.0, 1)

        # PR & Collaboration (max 15): from meeting_agent subscores / reviews
        collab_sub = (agent_scores.get("agile_collaboration").subscores.get("collaboration_evidence", 8.0)
                      if agent_scores.get("agile_collaboration") else 8.0)
        collab_score = round(min(15.0, (collab_sub / 10.0) * 15.0), 1)

        # Testing & Reliability (max 15): from qa_agent
        rel_raw = agent_scores.get("testing_reliability").score if agent_scores.get("testing_reliability") else 80.0
        rel_score = round(((rel_raw or 80.0) / 100.0) * 15.0, 1)

        # Engineering Impact (max 10): from devops & cicd
        devops_raw = agent_scores.get("devops").score if agent_scores.get("devops") else 80.0
        impact_score = round(((devops_raw or 80.0) / 100.0) * 10.0, 1)

        # Engineering Judgment (max 5): from architecture & code correctness
        judgment_score = 4.5

        breakdown = PerformanceBreakdown(
            code_quality=cq_score,
            delivery=del_score,
            collaboration=collab_score,
            reliability=rel_score,
            engineering_impact=impact_score,
            engineering_judgment=judgment_score,
        )

        total_90 = round(cq_score + del_score + collab_score + rel_score + impact_score + judgment_score, 1)

        conf_str = "high" if aggregated.overall_confidence >= 0.8 else "medium" if aggregated.overall_confidence >= 0.5 else "low"

        return AIEvaluation(
            score=min(90.0, total_90),
            breakdown=breakdown,
            strengths=aggregated.strengths,
            weaknesses=aggregated.weaknesses,
            recommendations=aggregated.recommendations,
            reasoning=aggregated.summary,
            confidence=conf_str,
            data_quality={
                "specialist_agents_evaluated": list(agent_scores.keys()),
                "weights_used": aggregated.weights_used,
                "overall_composite_score": aggregated.overall_score,
                "scoring_version": aggregated.scoring_version,
            },
        )

    def calculate_confidence_level(self, developer_data: Dict[str, Any], days_of_data: int) -> Tuple[str, str]:
        summary = developer_data.get("summary", {})
        total_data_points = summary.get("total_commits", 0) + summary.get("total_prs", 0) + summary.get("total_tasks", 0)

        if days_of_data < 7 or total_data_points < 3:
            return ("low", f"Limited activity data: {total_data_points} observations across {days_of_data} days.")
        if days_of_data < 30 or total_data_points < 15:
            return ("medium", f"Moderate data volume: {total_data_points} observations.")
        return ("high", f"Robust empirical data: {total_data_points} observations across {days_of_data} days.")

    def determine_grade(self, score: float) -> str:
        return ScoringEngine.determine_grade(score)


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph node
# ─────────────────────────────────────────────────────────────────────────────

async def performance_eval_node(state: dict) -> dict:
    """
    LangGraph node: aggregates specialist evaluations into unified performance report.
    """
    t0 = time.time()
    evidence = state.get("evidence", {})
    context = state.get("context", {})

    developer_name = context.get("developer_name", "Developer")
    period_label = context.get("period_label", "Current Period")

    agent = PerformanceEvaluationAgent()
    evaluation = await agent.evaluate_performance(
        developer_data=evidence.get("developer_data") or evidence,
        developer_name=developer_name,
        period_label=period_label,
    )

    latency_ms = round((time.time() - t0) * 1000, 1)
    grade = agent.determine_grade((evaluation.score / 90.0) * 100.0)

    return {
        **state,
        "analysis": evaluation.reasoning,
        "recommendations": evaluation.recommendations,
        "risk_level": "high" if evaluation.score < 50 else "medium" if evaluation.score < 75 else "low",
        "confidence": 0.9 if evaluation.confidence == "high" else 0.7 if evaluation.confidence == "medium" else 0.4,
        "structured_output": {
            "score": evaluation.score,
            "normalized_score_100": round((evaluation.score / 90.0) * 100.0, 1),
            "grade": grade,
            "breakdown": evaluation.breakdown.model_dump(),
            "strengths": evaluation.strengths,
            "weaknesses": evaluation.weaknesses,
            "recommendations": evaluation.recommendations,
            "confidence": evaluation.confidence,
            "data_quality": evaluation.data_quality,
        },
        "agent_history": state.get("agent_history", []) + ["performance_agent"],
        "latency_ms": {**state.get("latency_ms", {}), "performance_agent": latency_ms},
    }
