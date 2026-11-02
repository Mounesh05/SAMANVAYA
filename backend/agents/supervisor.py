"""
Supervisor — LangGraph orchestrator wiring all architecture layers.

Full pipeline:
    FastAPI (API Gateway)
        -> Auth/JWT (core.security)
        -> input_guardrail_node   [RBAC + prompt-injection + Pydantic]
        -> memory_read_node       [Redis cache hit? skip agents entirely]
        -> supervisor_router      [routes to specialist agent]
        -> [Agent Node]           [LiteLLM -> Ollama via LiteLLM Gateway + MCP tools]
        -> output_guardrail_node  [PII redaction, NeMo-style]
        -> memory_write_node      [Redis + MongoDB persistence]
        -> END

Agents registered:
    code_agent        - PR code quality & security
    qa_agent          - Test coverage & quality assurance
    devops_agent      - Deployment risk & infrastructure
    cicd_agent        - CI/CD log root-cause analysis
    meeting_agent     - Sprint insights & standup prep
    performance_agent - Developer performance evaluation
    report_agent      - Executive/HR report synthesis (ReAct + PDF)

Graph also has two bypass nodes:
    rbac_deny         - Short-circuit for unauthorized requests
    cache_hit         - Short-circuit when Redis returns a valid cached result
"""

import time
import uuid
import logging
from typing import Literal, Dict, Any, Optional

from langgraph.graph import StateGraph, END

from .state import AgentState
from .guardrails import input_guardrail_node, output_guardrail_node, rbac_deny_node
from .memory import memory_read_node, memory_write_node
from .code_agent import code_analysis_node
from .qa_agent import qa_analysis_node
from .devops_agent import devops_analysis_node
from .meeting_agent import meeting_insights_node
from .cicd_agent import cicd_analysis_node
from .performance_agent import performance_eval_node
from .report_agent import report_synthesis_node

logger = logging.getLogger("samanvaya.supervisor")


# ─────────────────────────────────────────────────────────────────────────────
# Routing constants
# ─────────────────────────────────────────────────────────────────────────────
RouteDecision = Literal[
    "code_agent",
    "qa_agent",
    "devops_agent",
    "cicd_agent",
    "meeting_agent",
    "performance_agent",
    "report_agent",
    "rbac_deny",
    "cache_hit",
    "end",
]

TASK_ROUTE_MAP: Dict[str, str] = {
    "code_review":      "code_agent",
    "qa_analysis":      "qa_agent",
    "devops_risk":      "devops_agent",
    "cicd_analysis":    "cicd_agent",
    "meeting_insights": "meeting_agent",
    "performance_eval": "performance_agent",
    "report_synthesis": "report_agent",
}


# ─────────────────────────────────────────────────────────────────────────────
# Post-guardrail router
# ─────────────────────────────────────────────────────────────────────────────
def post_guardrail_router(state: AgentState) -> RouteDecision:
    """
    Runs after input_guardrail_node.

    Decision tree:
        1. Guardrail failed (RBAC deny / injection)  -> rbac_deny
        2. Redis cache hit                            -> cache_hit
        3. task_type known                            -> specialist agent
        4. Unknown task_type                          -> end
    """
    if not state.get("guardrail_passed", True):
        logger.warning("[SUPERVISOR] Routing to rbac_deny (guardrail failed)")
        return "rbac_deny"

    if state.get("redis_hit", False):
        logger.info("[SUPERVISOR] Routing to cache_hit (Redis cache served)")
        return "cache_hit"

    task_type = state.get("task_type", "")
    route = TASK_ROUTE_MAP.get(task_type, "end")
    logger.info("[SUPERVISOR] Routing task_type='%s' -> %s", task_type, route)
    return route


def cache_hit_node(state: AgentState) -> AgentState:
    """Terminal node: return cached result without running an agent."""
    logger.info("[SUPERVISOR] Cache HIT node — returning Redis-cached result")
    return {**state, "agent_history": state.get("agent_history", []) + ["cache_hit"]}


# ─────────────────────────────────────────────────────────────────────────────
# Telemetry wrapper (adds per-node latency to state)
# ─────────────────────────────────────────────────────────────────────────────
def _timed(name: str, fn):
    """Wrap a node function with latency tracking."""
    def wrapped(state: AgentState) -> AgentState:
        t0 = time.time()
        result = fn(state)
        ms = round((time.time() - t0) * 1000, 1)
        latency = dict(state.get("latency_ms", {}))
        latency[name] = ms
        logger.info("[TELEMETRY] node=%s latency=%.0fms", name, ms)
        return {**result, "latency_ms": latency}
    return wrapped


async def _timed_async(name: str, fn, state: AgentState) -> AgentState:
    t0 = time.time()
    result = await fn(state)
    ms = round((time.time() - t0) * 1000, 1)
    latency = dict(state.get("latency_ms", {}))
    latency[name] = ms
    logger.info("[TELEMETRY] node=%s latency=%.0fms", name, ms)
    return {**result, "latency_ms": latency}


# ─────────────────────────────────────────────────────────────────────────────
# Build the compiled LangGraph
# ─────────────────────────────────────────────────────────────────────────────
def create_supervisor_graph() -> StateGraph:
    """
    Assemble and compile the full LangGraph supervisor.

    Returns:
        Compiled LangGraph ready for .invoke() / .ainvoke()

    Usage example:
        graph = create_supervisor_graph()
        result = graph.invoke({
            "task_type":   "code_review",
            "task_id":     str(uuid.uuid4()),
            "user_id":     "user-123",
            "user_role":   "DEV",
            "company_id":  "ORG-001",
            "input_text":  "Review this PR for security issues",
            "context":     {"pr_title": "Add auth middleware", "pr_number": 42},
            "evidence":    {...},
            "agent_history": [],
            "errors":      [],
        })
    """
    graph = StateGraph(AgentState)

    # ── 1. Guardrail + Memory pre-processing nodes ────────────────────────────
    graph.add_node("input_guardrail", input_guardrail_node)
    graph.add_node("memory_read",     memory_read_node)

    # ── 2. Specialist agent nodes ─────────────────────────────────────────────
    graph.add_node("code_agent",        _timed("code_agent",        code_analysis_node))
    graph.add_node("qa_agent",          _timed("qa_agent",          qa_analysis_node))
    graph.add_node("devops_agent",      _timed("devops_agent",      devops_analysis_node))
    graph.add_node("cicd_agent",        _timed("cicd_agent",        cicd_analysis_node))
    graph.add_node("meeting_agent",     _timed("meeting_agent",     meeting_insights_node))
    graph.add_node("performance_agent", performance_eval_node)   # already async-aware
    graph.add_node("report_agent",      report_synthesis_node)

    # ── 3. Post-processing nodes ───────────────────────────────────────────────
    graph.add_node("output_guardrail",  output_guardrail_node)
    graph.add_node("memory_write",      memory_write_node)
    graph.add_node("rbac_deny",         rbac_deny_node)
    graph.add_node("cache_hit",         cache_hit_node)

    # ── 4. Entry point: always start with input guardrail ────────────────────
    graph.set_entry_point("input_guardrail")

    # ── 5. After guardrail -> memory read ─────────────────────────────────────
    graph.add_edge("input_guardrail", "memory_read")

    # ── 6. After memory read -> conditional route ─────────────────────────────
    graph.add_conditional_edges(
        "memory_read",
        post_guardrail_router,
        {
            "code_agent":        "code_agent",
            "qa_agent":          "qa_agent",
            "devops_agent":      "devops_agent",
            "cicd_agent":        "cicd_agent",
            "meeting_agent":     "meeting_agent",
            "performance_agent": "performance_agent",
            "report_agent":      "report_agent",
            "rbac_deny":         "rbac_deny",
            "cache_hit":         "cache_hit",
            "end":               END,
        },
    )

    # ── 7. Each agent -> output guardrail ─────────────────────────────────────
    for agent_node in [
        "code_agent", "qa_agent", "devops_agent", "cicd_agent",
        "meeting_agent", "performance_agent", "report_agent",
    ]:
        graph.add_edge(agent_node, "output_guardrail")

    # Cache hit also goes through output guardrail before returning
    graph.add_edge("cache_hit", "output_guardrail")

    # RBAC deny terminates immediately (no memory write for blocked requests)
    graph.add_edge("rbac_deny", END)

    # ── 8. Output guardrail -> memory write -> END ────────────────────────────
    graph.add_edge("output_guardrail", "memory_write")
    graph.add_edge("memory_write", END)

    return graph.compile()


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: run_agent() — typed entry-point used by FastAPI routes
# ─────────────────────────────────────────────────────────────────────────────
_graph = None

def _get_graph():
    global _graph
    if _graph is None:
        _graph = create_supervisor_graph()
    return _graph


async def run_agent(
    task_type: str,
    user_id: str,
    user_role: str,
    company_id: str,
    evidence: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    input_text: str = "",
) -> Dict[str, Any]:
    """
    High-level async entry-point for FastAPI route handlers.

    Args:
        task_type:   One of the 7 supported task types.
        user_id:     Authenticated user ID (from JWT).
        user_role:   Role from JWT claims.
        company_id:  Multi-tenant isolation key.
        evidence:    Pre-built evidence package from Intelligence Engine.
        context:     Optional metadata (sprint, PR info, report title, etc.).
        input_text:  Raw user query (used for prompt injection scanning).

    Returns:
        Final AgentState dict with analysis, recommendations, risk_level, etc.
    """
    graph = _get_graph()
    task_id = str(uuid.uuid4())

    initial_state: AgentState = {
        "task_type":         task_type,
        "task_id":           task_id,
        "user_id":           user_id,
        "user_role":         user_role,
        "company_id":        company_id,
        "input_text":        input_text,
        "context":           context or {},
        "evidence":          evidence,
        "agent_history":     [],
        "errors":            [],
        "mcp_tool_calls":    [],
        "latency_ms":        {},
        "token_counts":      {},
        "rag_context":       "",
        "conversation_history": [],
    }

    logger.info(
        "[SUPERVISOR] run_agent START task_id=%s task=%s role=%s company=%s",
        task_id, task_type, user_role, company_id
    )

    t0 = time.time()
    result = await graph.ainvoke(initial_state)
    total_ms = round((time.time() - t0) * 1000, 1)

    logger.info(
        "[SUPERVISOR] run_agent DONE task_id=%s total=%.0fms agents=%s errors=%d",
        task_id, total_ms, result.get("agent_history", []), len(result.get("errors", []))
    )
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Core Employee-Level Multi-Agent Evaluation Orchestration
# ─────────────────────────────────────────────────────────────────────────────
async def evaluate_employee(
    employee_id: str,
    start_date: str,
    end_date: str,
    company_id: str = "ORG-001",
    evaluator_id: str = "system",
    period_label: Optional[str] = None,
    cached_context: Optional[Dict[str, Any]] = None,
    skip_llm: bool = False,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Coordinates the multi-agent employee evaluation workflow:
    1. Validate evaluation period.
    2. Build employee evaluation context via EvidenceCollector.
    3. Run specialist agents independently in parallel (asyncio.gather).
    4. Collect structured results and validate scores.
    5. Aggregate scores through Performance Aggregator.
    6. Generate report presentation.
    7. Persist evaluation and audit trail in MongoDB.
    8. Return individual dimension scores and aggregated scorecard.

    Args:
        verbose: If True, include per-agent reasoning, confidence intervals,
                 evidence summaries, and timing metrics in the response.
    """
    import asyncio
    from intelligence.evidence_collector import EvidenceCollector
    from intelligence.identity_mapper import IdentityMapper
    from intelligence.scoring.models import EvaluationPeriod
    from agents.code_agent import CodeScoringAgent
    from agents.qa_agent import QAScoringAgent
    from agents.devops_agent import DevOpsScoringAgent
    from agents.cicd_agent import CICDScoringAgent
    from agents.meeting_agent import MeetingScoringAgent
    from agents.performance_agent import PerformanceEvaluationAgent
    from agents.report_agent import EmployeeReportGenerator
    from core.database import col

    t0 = time.time()
    logger.info(
        "[SUPERVISOR] evaluate_employee START employee=%s period=[%s to %s] company=%s",
        employee_id, start_date, end_date, company_id
    )

    # 1. Resolve employee identity
    id_mapper = IdentityMapper()
    identity = await id_mapper.get_identity(employee_id)
    employee_name = identity.name if identity else employee_id

    period = EvaluationPeriod(
        start_date=start_date,
        end_date=end_date,
        label=period_label or f"{start_date[:7]}",
    )

    # 2. Build shared evidence package
    collector = EvidenceCollector()
    evidence_package = await collector.collect_package(
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date,
        period_label=period.label,
        cached_context=cached_context,
    )
    evidence_dict = evidence_package.to_dict()

    # 3. Instantiate specialist scoring agents
    code_agent = CodeScoringAgent()
    qa_agent = QAScoringAgent()
    devops_agent = DevOpsScoringAgent()
    cicd_agent = CICDScoringAgent()
    meeting_agent = MeetingScoringAgent()

    # 4. Run independent scoring agents in parallel
    logger.info("[SUPERVISOR] Dispatching 5 specialist agents in parallel for %s", employee_id)
    scores_list = await asyncio.gather(
        code_agent.evaluate(employee_id, employee_name, evidence_dict, period, skip_llm=skip_llm),
        qa_agent.evaluate(employee_id, employee_name, evidence_dict, period, skip_llm=skip_llm),
        devops_agent.evaluate(employee_id, employee_name, evidence_dict, period, skip_llm=skip_llm),
        cicd_agent.evaluate(employee_id, employee_name, evidence_dict, period, skip_llm=skip_llm),
        meeting_agent.evaluate(employee_id, employee_name, evidence_dict, period, skip_llm=skip_llm),
    )

    agent_scores = {
        "code_quality": scores_list[0],
        "testing_reliability": scores_list[1],
        "devops": scores_list[2],
        "cicd": scores_list[3],
        "agile_collaboration": scores_list[4],
    }

    # 5. Validate scores strictly
    for name, sc in agent_scores.items():
        if sc.score is not None and not (0.0 <= sc.score <= 100.0):
            logger.warning("[SUPERVISOR] Clamping invalid score for %s: %s", name, sc.score)
            sc.score = max(0.0, min(100.0, sc.score))

    # 6. Check if superior evaluation was already recorded for this period to preserve it
    existing_superior = None
    try:
        existing_doc = await col("employee_evaluations").find_one({
            "employee_id": employee_id,
            "period.label": period.label,
        })
        if existing_doc:
            existing_superior = existing_doc.get("superior_score_marks")
    except Exception as e:
        logger.debug("[SUPERVISOR] Existing superior lookup warning: %s", e)

    # Aggregate scores via Performance Layer
    perf_agent = PerformanceEvaluationAgent()
    aggregated_eval = await perf_agent.aggregate_specialist_scores(
        agent_scores=agent_scores,
        developer_id=employee_id,
        developer_name=employee_name,
        period=period,
        company_id=company_id,
        superior_score=existing_superior,
    )

    # 7. Generate report presentation
    presentation = EmployeeReportGenerator.generate_presentation_report(aggregated_eval)

    # 8. Primary output format requested:
    # Individual scores are primary, not collapsed prematurely
    individual_scores = {
        "code_quality": agent_scores["code_quality"].score,
        "testing_reliability": agent_scores["testing_reliability"].score,
        "devops": agent_scores["devops"].score,
        "cicd": agent_scores["cicd"].score,
        "agile_collaboration": agent_scores["agile_collaboration"].score,
    }

    total_ms = round((time.time() - t0) * 1000, 1)

    # Build verbose per-agent metrics
    AGENT_LABELS = {
        "code_quality":        "Code Quality Agent",
        "testing_reliability": "QA & Testing Agent",
        "devops":              "DevOps Agent",
        "cicd":                "CI/CD Agent",
        "agile_collaboration": "Meeting & Agile Agent",
    }

    agent_metrics = {}
    for dim, sc in agent_scores.items():
        sc_dict = sc.model_dump() if hasattr(sc, "model_dump") else dict(sc)
        agent_metrics[dim] = {
            "agent": AGENT_LABELS.get(dim, dim),
            "dimension": dim,
            "score": sc_dict.get("score"),
            "confidence": sc_dict.get("confidence"),
            "grade": sc_dict.get("grade"),
            "risk_level": sc_dict.get("risk_level"),
            "summary": sc_dict.get("summary") or sc_dict.get("reasoning") or sc_dict.get("analysis") or "",
            "recommendations": sc_dict.get("recommendations") or [],
            "evidence_used": sc_dict.get("evidence_used") or sc_dict.get("evidence_summary") or {},
            "skip_llm_used": skip_llm,
            "raw": sc_dict if verbose else None,
        }

    # Evaluation summary
    scored_agents = [m for m in agent_metrics.values() if m["score"] is not None]
    eval_summary = {
        "total_agents": len(agent_metrics),
        "agents_scored": len(scored_agents),
        "agents_skipped": len(agent_metrics) - len(scored_agents),
        "avg_confidence": round(
            sum(m["confidence"] for m in scored_agents if m["confidence"]) /
            max(1, len([m for m in scored_agents if m["confidence"]])), 3
        ) if scored_agents else None,
        "highest_dim": max(agent_metrics, key=lambda k: agent_metrics[k]["score"] or 0),
        "lowest_dim": min(agent_metrics, key=lambda k: agent_metrics[k]["score"] or 0),
        "evaluation_mode": "fast_deterministic" if skip_llm else "full_llm",
        "total_latency_ms": total_ms,
    }

    response_payload = {
        "evaluation_id": aggregated_eval.evaluation_id,
        "employee_id": employee_id,
        "employee_name": employee_name,
        "company_id": company_id,
        "period": {
            "start": start_date,
            "end": end_date,
            "label": period.label,
        },
        "scores": individual_scores,
        "overall_score": aggregated_eval.overall_score,
        "grade": aggregated_eval.grade,
        "confidence": aggregated_eval.overall_confidence,
        "agent_score_marks": aggregated_eval.agent_score_marks,
        "superior_score_marks": aggregated_eval.superior_score_marks,
        "final_score": aggregated_eval.final_score,
        # Verbose fields
        "agent_metrics": agent_metrics,
        "evaluation_summary": eval_summary,
        "agent_scores": {k: v.model_dump() for k, v in agent_scores.items()},
        "report": presentation,
        "weights_used": aggregated_eval.weights_used,
        "evaluated_by": evaluator_id,
        "evaluation_latency_ms": total_ms,
        "scoring_version": aggregated_eval.scoring_version,
        "verbose": verbose,
    }

    # 9. Store evaluation results in MongoDB for auditability & dashboard caching
    try:
        eval_doc = dict(response_payload)
        eval_doc["_id"] = aggregated_eval.evaluation_id
        await col("employee_evaluations").update_one(
            {"_id": aggregated_eval.evaluation_id},
            {"$set": eval_doc},
            upsert=True,
        )
        logger.info("[SUPERVISOR] Evaluation persisted to MongoDB employee_evaluations: %s", aggregated_eval.evaluation_id)
    except Exception as exc:
        logger.warning("[SUPERVISOR] MongoDB persistence warning: %s", exc)

    logger.info(
        "[SUPERVISOR] evaluate_employee COMPLETE for %s in %.0fms: overall=%s grade=%s",
        employee_id, total_ms, aggregated_eval.overall_score, aggregated_eval.grade
    )
    return response_payload
