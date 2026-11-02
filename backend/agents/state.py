"""
AgentState — Canonical shared state for the LangGraph Supervisor pipeline.

Architecture:
    FastAPI -> Auth/RBAC -> Supervisor (LangGraph) -> [Agent Nodes]
                                                         -> Guardrails
                                                         -> MCP Tools
                                                         -> Memory (MongoDB + Redis)
                                                         -> LiteLLM Gateway

Every field is documented with its source and consumer.
"""

from typing import TypedDict, Literal, Optional, Dict, Any, List, Annotated
import operator


# ─────────────────────────────────────────────────────────────────────────────
# Allowed task types (controls supervisor routing)
# ─────────────────────────────────────────────────────────────────────────────
TaskType = Literal[
    "code_review",
    "qa_analysis",
    "devops_risk",
    "cicd_analysis",
    "meeting_insights",
    "performance_eval",
    "report_synthesis",
]

RiskLevel = Literal["low", "medium", "high", "critical"]
AgentRole = Literal["CEO", "HR", "LEAD", "PM", "DEV", "QA", "DEVOPS", "ADMIN"]


# ─────────────────────────────────────────────────────────────────────────────
# Core AgentState — passed through every node in the LangGraph graph
# ─────────────────────────────────────────────────────────────────────────────
class AgentState(TypedDict, total=False):
    """
    Shared mutable state propagated through the LangGraph supervisor graph.

    Fields are grouped into:
        [INPUT]      - Set by the API caller before graph invocation
        [AUTH]       - Set by RBAC/OPA guardrail at graph entry
        [ROUTING]    - Set by supervisor router
        [EVIDENCE]   - Rich context injected by MCP tools / Intelligence Engine
        [MEMORY]     - Retrieved from Redis short-term / MongoDB long-term memory
        [OUTPUT]     - Written by specialist agent nodes
        [GUARDRAILS] - Written by NeMo / Pydantic validators
        [TELEMETRY]  - Timing, cost, token counts per node
    """

    # ── [INPUT] ──────────────────────────────────────────────────────────────
    task_type: TaskType                       # Which specialist agent to invoke
    task_id: str                              # UUID for dedup + audit trail
    user_id: str                              # Authenticated user ID (JWT sub)
    user_role: AgentRole                      # RBAC role from JWT claims
    company_id: str                           # Multi-tenant isolation key
    input_text: str                           # Raw user request / document
    context: Dict[str, Any]                   # PR metadata, sprint info, etc.

    # ── [AUTH / RBAC] ────────────────────────────────────────────────────────
    rbac_allowed: bool                        # OPA policy decision
    rbac_reason: str                          # Human-readable deny reason
    prompt_injection_detected: bool          # Prompt injection flag
    guardrail_passed: bool                    # NeMo / Pydantic gate result
    guardrail_violations: List[str]           # List of violated policy names

    # ── [EVIDENCE] ───────────────────────────────────────────────────────────
    evidence: Dict[str, Any]                  # From Intelligence Engine / MCP tools
    mcp_tool_calls: List[Dict[str, Any]]      # Log of all MCP tool invocations
    rag_context: str                          # Retrieved documents from Qdrant/MongoDB

    # ── [MEMORY] ─────────────────────────────────────────────────────────────
    redis_hit: bool                           # True if result served from Redis cache
    cache_key: str                            # Redis cache key for this request
    conversation_history: List[Dict[str, Any]]  # Long-term memory from MongoDB

    # ── [ROUTING] ────────────────────────────────────────────────────────────
    next_agent: Optional[str]                 # Supervisor override for next node
    retry_count: int                          # How many times this task has retried

    # ── [OUTPUT] — Written by specialist agents ───────────────────────────────
    analysis: str                             # Agent's narrative analysis
    recommendations: List[str]               # Actionable recommendations
    risk_level: RiskLevel                     # Assessed risk classification
    confidence: float                         # 0.0–1.0 confidence in output
    structured_output: Dict[str, Any]         # Agent-specific structured result
    agent_history: List[str]                  # Trail of nodes that processed state

    # ── [GUARDRAILS OUTPUT] ───────────────────────────────────────────────────
    output_sanitized: bool                    # True if output was cleaned

    # ── [TELEMETRY] ──────────────────────────────────────────────────────────
    latency_ms: Dict[str, float]             # Per-node latency: {"code_agent": 14230}
    token_counts: Dict[str, int]              # Per-node token usage
    llm_model_used: str                       # Model name that ran inference
    errors: List[str]                         # Error accumulator (non-fatal)
