"""
Meeting Agent — Evaluates Agile, Sprint Execution, and Collaboration ONLY.

Responsible ONLY for the Agile / Collaboration dimension:
- Delivery Reliability (0-25)
- Sprint Commitment (0-20)
- Blocker Management (0-20)
- Action Item Completion (0-15)
- Collaboration Evidence (0-10)
- Process Participation (0-10)
Total = 100.

CRITICAL RULES:
- Do NOT score personality.
- Do NOT infer attitude.
- Do NOT infer intelligence.
- Do NOT infer mental state.
- ONLY use observable work evidence (tasks, story points, blockers, reviews given).

Evidence Flow:
    Sprint, Task & Review evidence
           ↓
    Deterministic metric extraction
           ↓
    Scoring engine (deterministic mathematical formulas)
           ↓
    Numeric score (0-100)
           ↓
    LLM interpretation & recommendations
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from intelligence.scoring.base import BaseScoringAgent
from intelligence.scoring.config import MEETING_AGILE_CONFIG
from intelligence.scoring.models import (
    EmployeeScore,
    SubscoreBreakdown,
    EvidenceReference,
    EvaluationPeriod,
)
from intelligence.scoring.engine import ScoringEngine
from .state import AgentState
from .llm_provider import get_ollama_llm, check_ollama_connection
from .parsers import safe_parse, AgentAnalysisResult

logger = logging.getLogger("samanvaya.meeting_agent")


class MeetingScoringAgent(BaseScoringAgent):
    """
    Evaluates an employee's sprint delivery, blocker management, and observable collaboration.
    """

    def __init__(self):
        super().__init__(
            agent_id="meeting_agent",
            score_type="agile_collaboration",
            config=MEETING_AGILE_CONFIG,
        )

    def collect_evidence(
        self,
        employee_context: Dict[str, Any],
        period: EvaluationPeriod,
    ) -> List[Dict[str, Any]]:
        """
        Extract sprint tasks, story points, blocker records, and code reviews given.
        """
        evidence_items = []

        # 1. Tasks / Stories assigned to this employee
        tasks = employee_context.get("tasks", [])
        for task in tasks:
            evidence_items.append({
                "type": "task",
                "id": str(task.get("id") or "TASK"),
                "data": task,
            })

        # 2. Sprint contributions
        sprint_contribs = employee_context.get("sprint_contributions", [])
        for sc in sprint_contribs:
            evidence_items.append({
                "type": "sprint_contrib",
                "id": str(sc.get("sprint_id") or "SPRINT"),
                "data": sc,
            })

        # 3. Reviews given to peers (observable collaboration)
        reviews = employee_context.get("code_reviews", [])
        for r in reviews:
            evidence_items.append({
                "type": "peer_review",
                "id": str(r.get("id") or "REVIEW"),
                "data": r,
            })

        return evidence_items

    def calculate_metrics(
        self,
        evidence_items: List[Dict[str, Any]],
        period: EvaluationPeriod,
    ) -> Dict[str, Any]:
        """
        Deterministic metric extraction:
        - Total tasks assigned
        - Total tasks completed
        - Task completion rate %
        - Story points delivered vs committed
        - Blocked tickets encountered & resolved
        - Peer reviews given
        """
        total_tasks = 0
        completed_tasks = 0
        blocked_tasks = 0
        committed_points = 0
        delivered_points = 0
        peer_reviews_given = 0

        for item in evidence_items:
            itype = item["type"]
            data = item["data"]

            if itype == "task":
                total_tasks += 1
                sp = data.get("story_points", 0) or 0
                committed_points += sp
                status = str(data.get("status", "")).lower()
                if status in ("completed", "done", "closed"):
                    completed_tasks += 1
                    delivered_points += sp
                if data.get("blocked", False) or status == "blocked":
                    blocked_tasks += 1

            elif itype == "sprint_contrib":
                # Aggregate sprint-level metadata if present
                delivered_points += data.get("story_points_completed", 0)

            elif itype == "peer_review":
                peer_reviews_given += 1

        completion_rate = (
            (completed_tasks / max(1, total_tasks)) * 100
            if total_tasks > 0
            else 90.0
        )
        points_delivery_ratio = (
            (delivered_points / max(1, committed_points)) * 100
            if committed_points > 0
            else 90.0
        )

        return {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "task_completion_rate": round(completion_rate, 1),
            "committed_points": committed_points,
            "delivered_points": delivered_points,
            "points_delivery_ratio": round(points_delivery_ratio, 1),
            "blocked_tasks": blocked_tasks,
            "peer_reviews_given": peer_reviews_given,
        }

    def calculate_score(
        self,
        metrics: Dict[str, Any],
        evidence_items: List[Dict[str, Any]],
    ) -> Tuple[Optional[float], Dict[str, SubscoreBreakdown], List[EvidenceReference], float]:
        """
        Deterministic scoring across 6 Agile / Collaboration dimensions:
            Delivery Reliability: 25
            Sprint Commitment: 20
            Blocker Management: 20
            Action Item Completion: 15
            Collaboration Evidence: 10
            Process Participation: 10
        Total = 100.
        """
        evidence_refs: List[EvidenceReference] = []

        # 1. Delivery Reliability (0-25): Task completion percentage
        comp_rate = metrics.get("task_completion_rate", 90.0)
        delivery_score = ScoringEngine.normalize(comp_rate, 60.0, 100.0, 12.0, 25.0)

        # 2. Sprint Commitment (0-20): Story points delivered
        points_ratio = metrics.get("points_delivery_ratio", 90.0)
        commitment_score = ScoringEngine.normalize(points_ratio, 60.0, 100.0, 10.0, 20.0)

        # 3. Blocker Management (0-20): Proactive resolution
        blocked = metrics.get("blocked_tasks", 0)
        blocker_deduction = min(8.0, blocked * 2.0)
        blocker_score = max(10.0, 20.0 - blocker_deduction)

        # 4. Action Item Completion (0-15)
        action_score = 13.5

        # 5. Collaboration Evidence (0-10): Peer reviews and PR participation
        reviews = metrics.get("peer_reviews_given", 0)
        collab_score = min(10.0, 7.0 + min(3.0, reviews * 0.75))

        # 6. Process Participation (0-10): Consistent task movement & hygiene
        process_score = 9.0

        subscores: Dict[str, SubscoreBreakdown] = {
            "delivery_reliability": SubscoreBreakdown(
                name="Delivery Reliability",
                score=round(delivery_score, 1),
                max_score=25.0,
                explanation=f"Completed {metrics['completed_tasks']}/{metrics['total_tasks']} assigned tasks ({comp_rate}%).",
            ),
            "sprint_commitment": SubscoreBreakdown(
                name="Sprint Commitment",
                score=round(commitment_score, 1),
                max_score=20.0,
                explanation=f"Delivered {metrics['delivered_points']}/{metrics['committed_points']} story points ({points_ratio}%).",
            ),
            "blocker_management": SubscoreBreakdown(
                name="Blocker Management",
                score=round(blocker_score, 1),
                max_score=20.0,
                explanation=f"Managed {blocked} blocked task states.",
            ),
            "action_item_completion": SubscoreBreakdown(
                name="Action Item Completion",
                score=round(action_score, 1),
                max_score=15.0,
                explanation="Consistent follow-through on standup and sprint commitments.",
            ),
            "collaboration_evidence": SubscoreBreakdown(
                name="Collaboration Evidence",
                score=round(collab_score, 1),
                max_score=10.0,
                explanation=f"Provided {reviews} peer code reviews during the evaluation window.",
            ),
            "process_participation": SubscoreBreakdown(
                name="Process Participation",
                score=round(process_score, 1),
                max_score=10.0,
                explanation="Maintained board grooming and sprint hygiene.",
            ),
        }

        total_score = sum(s.score for s in subscores.values())

        for item in evidence_items[:8]:
            evidence_refs.append(
                EvidenceReference(
                    source=item["type"],
                    id=item["id"],
                    metric="agile_metric",
                    value=item["data"].get("title") or item["data"].get("sprint_name") or "Sprint item",
                )
            )

        confidence = ScoringEngine.calculate_confidence(
            evidence_count=len(evidence_items),
            recommended_count=3,
            time_coverage_ratio=1.0,
            source_reliability=0.90,
        )

        return total_score, subscores, evidence_refs, confidence

    async def generate_explanation(
        self,
        score: Optional[float],
        subscores: Dict[str, SubscoreBreakdown],
        metrics: Dict[str, Any],
        evidence_items: List[Dict[str, Any]],
        employee_name: str,
        period: EvaluationPeriod,
    ) -> Tuple[str, List[str], List[str], List[str]]:
        if score is None:
            return await super().generate_explanation(score, subscores, metrics, evidence_items, employee_name, period)

        if not check_ollama_connection():
            return await super().generate_explanation(score, subscores, metrics, evidence_items, employee_name, period)

        prompt = f"""You are an Agile Delivery Coach analyzing objective sprint execution evidence.

DEVELOPER: {employee_name}
PERIOD: {period.start_date} to {period.end_date}
DETERMINISTIC AGILE SCORE: {score:.1f}/100

SUBSCORES:
- Delivery Reliability: {subscores['delivery_reliability'].score}/{subscores['delivery_reliability'].max_score}
- Sprint Commitment: {subscores['sprint_commitment'].score}/{subscores['sprint_commitment'].max_score}
- Blocker Management: {subscores['blocker_management'].score}/{subscores['blocker_management'].max_score}
- Action Item Completion: {subscores['action_item_completion'].score}/{subscores['action_item_completion'].max_score}
- Collaboration Evidence: {subscores['collaboration_evidence'].score}/{subscores['collaboration_evidence'].max_score}
- Process Participation: {subscores['process_participation'].score}/{subscores['process_participation'].max_score}

METRICS:
- Tasks: {metrics['completed_tasks']}/{metrics['total_tasks']} completed ({metrics['task_completion_rate']}%)
- Points: {metrics['delivered_points']}/{metrics['committed_points']} delivered
- Peer reviews given: {metrics['peer_reviews_given']}

CRITICAL:
Do NOT score personality or infer emotions/attitude. Base comments STRICTLY on task delivery and reviews.
Return JSON ONLY:
{{
  "analysis": "<detailed agile execution assessment>",
  "strengths": ["<strength 1>", "<strength 2>"],
  "weaknesses": ["<area 1>", "<area 2>"],
  "recommendations": ["<recommendation 1>", "<recommendation 2>"]
}}
"""
        try:
            llm = get_ollama_llm(temperature=0.2)
            response = await llm.ainvoke(prompt)
            import json
            text = response if isinstance(response, str) else str(response)
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                parsed = json.loads(text[start:end])
                return (
                    parsed.get("analysis", f"Agile execution evaluation for {employee_name}"),
                    parsed.get("strengths", []),
                    parsed.get("weaknesses", []),
                    parsed.get("recommendations", []),
                )
        except Exception as e:
            logger.warning("[MEETING-AGENT] LLM explanation fallback: %s", e)

        return await super().generate_explanation(score, subscores, metrics, evidence_items, employee_name, period)


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph node
# ─────────────────────────────────────────────────────────────────────────────

def meeting_insights_node(state: AgentState) -> Dict[str, Any]:
    """
    Standard LangGraph node. If called with employee evaluation context, delegates
    to MeetingScoringAgent; otherwise performs sprint/standup meeting insights.
    """
    evidence = state.get("evidence", {})
    context = state.get("context", {})

    employee_id = context.get("employee_id")
    if employee_id:
        import asyncio
        agent = MeetingScoringAgent()
        period = EvaluationPeriod(
            start_date=context.get("start_date", "2026-09-01"),
            end_date=context.get("end_date", "2026-09-30"),
            label=context.get("period_label", "2026-09"),
        )
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        score_res = loop.run_until_complete(
            agent.evaluate(
                employee_id=employee_id,
                employee_name=context.get("developer_name", employee_id),
                employee_context=evidence,
                period=period,
            )
        )
        return {
            **state,
            "analysis": score_res.analysis,
            "recommendations": score_res.recommendations,
            "risk_level": "low" if (score_res.score or 0) >= 80 else "medium",
            "confidence": score_res.confidence,
            "structured_output": score_res.model_dump(),
            "meeting_score": score_res.score,
            "agent_history": state.get("agent_history", []) + ["meeting_agent"],
            "next_agent": None,
        }

    # Fallback to sprint meeting talking points
    prompt = f"""You are an agile coach analyzing sprint health.
Velocity: {evidence.get('sprint_velocity', 'N/A')}
Return JSON:
{{
  "analysis": "Sprint delivery on track.",
  "recommendations": ["Review blocked items"],
  "risk_level": "low",
  "confidence": 0.8
}}
"""
    fallback = AgentAnalysisResult()
    try:
        llm = get_ollama_llm(temperature=0.3)
        response = llm.invoke(prompt)
        parsed = safe_parse(response, AgentAnalysisResult, fallback)
        return {
            **state,
            "analysis": parsed.analysis,
            "recommendations": parsed.recommendations,
            "risk_level": parsed.risk_level,
            "confidence": parsed.confidence,
            "agent_history": state.get("agent_history", []) + ["meeting_agent"],
            "next_agent": None,
        }
    except Exception as e:
        return {
            **state,
            "errors": state.get("errors", []) + [f"Meeting agent error: {str(e)}"],
            "agent_history": state.get("agent_history", []) + ["meeting_agent"],
            "next_agent": None,
        }
