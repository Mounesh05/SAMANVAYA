"""
AI Agents Layer — LangGraph + LiteLLM + Ollama + MCP Tools + Guardrails + Memory

Full architecture:
    FastAPI (API Gateway)
        -> Auth/JWT (core.security)
        -> input_guardrail_node   [RBAC/OPA + NeMo-style prompt injection + Pydantic]
        -> memory_read_node       [Redis (hot) + MongoDB (long-term) RAG retrieval]
        -> supervisor_router      [conditional routing to 7 specialist agents]
        -> [Agent Node]           [LiteLLM -> Ollama qwen2.5-coder:7b + MCP tools]
        -> output_guardrail_node  [PII redaction, output sanitisation]
        -> memory_write_node      [Redis cache + MongoDB persistence]
        -> END

Agents:
    code_agent        - PR code quality, security & maintainability review
    qa_agent          - Test coverage gaps & QA strategy recommendations
    devops_agent      - Deployment risk, CI/CD health & infrastructure
    cicd_agent        - Build/test/deploy log root-cause analysis
    meeting_agent     - Sprint velocity, standup prep & retrospective insights
    performance_agent - AI developer performance evaluation (6 dimensions)
    report_agent      - Executive/HR PDF report synthesis (ReAct + ReportLab)

Key cross-cutting components:
    LiteLLMGateway    - Unified LLM routing with model aliases + fallback
    MCPToolRegistry   - MCP tool registry for MongoDB, Redis, GitHub tools
    Guardrails        - RBAC matrix, injection scanner, Pydantic validators
    Memory            - Redis (5-min TTL) + MongoDB (permanent) agent memory
    run_agent()       - High-level async entry-point for FastAPI routes
"""

# ── LLM Gateway ───────────────────────────────────────────────────────────────
from .llm_provider import get_ollama_llm, get_gateway, check_ollama_connection, LiteLLMGateway

# ── State ─────────────────────────────────────────────────────────────────────
from .state import AgentState

# ── Supervisor ────────────────────────────────────────────────────────────────
from .supervisor import create_supervisor_graph, run_agent

# ── Agent Nodes ───────────────────────────────────────────────────────────────
from .code_agent import code_analysis_node
from .qa_agent import qa_analysis_node
from .devops_agent import devops_analysis_node
from .meeting_agent import meeting_insights_node
from .cicd_agent import cicd_analysis_node
from .performance_agent import performance_eval_node
from .report_agent import report_synthesis_node

# ── Guardrails ────────────────────────────────────────────────────────────────
from .guardrails import (
    input_guardrail_node,
    output_guardrail_node,
    check_rbac,
    scan_prompt_injection,
    sanitize_output,
    RBAC_POLICY,
)

# ── MCP Tools ─────────────────────────────────────────────────────────────────
from .mcp_tools import get_mcp_registry, MCPToolRegistry, make_cache_key

# ── Memory ────────────────────────────────────────────────────────────────────
from .memory import (
    memory_read_node,
    memory_write_node,
    redis_get,
    redis_set,
    redis_invalidate,
    mongo_save_result,
    mongo_get_history,
    build_rag_context,
)

# ── Report ReAct Agent (standalone PDF generation) ────────────────────────────
from .report_react_agent import ReportReActAgent


__all__ = [
    # LLM
    "get_ollama_llm", "get_gateway", "check_ollama_connection", "LiteLLMGateway",
    # State
    "AgentState",
    # Supervisor
    "create_supervisor_graph", "run_agent",
    # Agents
    "code_analysis_node", "qa_analysis_node", "devops_analysis_node",
    "meeting_insights_node", "cicd_analysis_node",
    "performance_eval_node", "report_synthesis_node",
    # Guardrails
    "input_guardrail_node", "output_guardrail_node",
    "check_rbac", "scan_prompt_injection", "sanitize_output", "RBAC_POLICY",
    # MCP
    "get_mcp_registry", "MCPToolRegistry", "make_cache_key",
    # Memory
    "memory_read_node", "memory_write_node",
    "redis_get", "redis_set", "redis_invalidate",
    "mongo_save_result", "mongo_get_history", "build_rag_context",
    # Report
    "ReportReActAgent",
]
