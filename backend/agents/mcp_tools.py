"""
MCP Tool Registry — Model Context Protocol tool definitions for all agents.

Architecture position:
    Supervisor/Agents -> MCPToolRegistry -> MCP Servers -> External Systems

MCP (Model Context Protocol) provides a standardised tool interface so that:
  - Any agent can invoke any tool by name, without coupling to implementation
  - Tools can be remote MCP servers or local function calls
  - All tool invocations are logged to AgentState.mcp_tool_calls for auditability

Tool categories:
    DATA_TOOLS   - MongoDB reads (projects, users, teams, performance, reports)
    CACHE_TOOLS  - Redis short-term memory (get / set / invalidate)
    CODE_TOOLS   - GitHub API proxy (PR diff, file content, CI status)
    PERF_TOOLS   - Performance metrics aggregation
    REPORT_TOOLS - Report retrieval + synthesis helpers
"""

import time
import logging
import hashlib
from typing import Any, Dict, List, Optional, Callable, Awaitable

logger = logging.getLogger("samanvaya.mcp")


# ─────────────────────────────────────────────────────────────────────────────
# Tool descriptor (mirrors MCP JSON-RPC tool schema)
# ─────────────────────────────────────────────────────────────────────────────
class MCPTool:
    def __init__(
        self,
        name: str,
        description: str,
        handler: Callable[..., Awaitable[Dict[str, Any]]],
        category: str = "general",
        required_roles: Optional[List[str]] = None,
    ):
        self.name = name
        self.description = description
        self.handler = handler
        self.category = category
        self.required_roles = required_roles or []   # empty = any role


# ─────────────────────────────────────────────────────────────────────────────
# Redis helper (no-op if redis is not available)
# ─────────────────────────────────────────────────────────────────────────────
_redis_client = None

def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis.asyncio as aioredis
        from core.config import settings
        redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379")
        _redis_client = aioredis.from_url(redis_url, decode_responses=True)
        logger.info("[MCP-CACHE] Redis connected at %s", redis_url)
    except Exception as exc:
        logger.warning("[MCP-CACHE] Redis unavailable (%s) — cache disabled", exc)
        _redis_client = None
    return _redis_client


# ─────────────────────────────────────────────────────────────────────────────
# MongoDB helper
# ─────────────────────────────────────────────────────────────────────────────
def _get_db():
    try:
        from core.database import get_database
        return get_database()
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Individual Tool Handlers
# ─────────────────────────────────────────────────────────────────────────────

async def _tool_get_company_projects(company_id: str, **_) -> Dict[str, Any]:
    """Fetch all active projects for a company from MongoDB."""
    t0 = time.time()
    try:
        from core.database import get_collection
        col = await get_collection("projects")
        docs = await col.find({"company_id": company_id}, {"_id": 0}).to_list(100)
        return {
            "projects": docs,
            "count": len(docs),
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }
    except Exception as exc:
        return {"projects": [], "count": 0, "error": str(exc)}


async def _tool_get_team_velocity(company_id: str, team_id: Optional[str] = None, **_) -> Dict[str, Any]:
    """Fetch sprint velocity and burndown data."""
    t0 = time.time()
    try:
        from core.database import get_collection
        query = {"company_id": company_id}
        if team_id:
            query["team_id"] = team_id
        col = await get_collection("sprints")
        docs = await col.find(query, {"_id": 0}).sort("created_at", -1).to_list(10)
        avg_velocity = (
            sum(d.get("velocity", 0) for d in docs) / max(len(docs), 1)
        )
        return {
            "sprints": docs,
            "avg_velocity": round(avg_velocity, 1),
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }
    except Exception as exc:
        return {"sprints": [], "avg_velocity": 0, "error": str(exc)}


async def _tool_get_performance_data(company_id: str, user_id: Optional[str] = None, **_) -> Dict[str, Any]:
    """Retrieve HR performance records."""
    t0 = time.time()
    try:
        from core.database import get_collection
        query = {"company_id": company_id}
        if user_id:
            query["user_id"] = user_id
        col = await get_collection("hr_performance")
        docs = await col.find(query, {"_id": 0}).to_list(200)
        avg_score = (
            sum(d.get("score", 0) for d in docs) / max(len(docs), 1)
        )
        high_risk = [d for d in docs if d.get("risk_level") == "high"]
        return {
            "records": docs,
            "count": len(docs),
            "avg_score": round(avg_score, 1),
            "high_risk_count": len(high_risk),
            "high_risk_names": [d.get("name") for d in high_risk],
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }
    except Exception as exc:
        return {"records": [], "avg_score": 0, "error": str(exc)}


async def _tool_get_users(company_id: str, role: Optional[str] = None, **_) -> Dict[str, Any]:
    """Fetch users for a company with optional role filter."""
    t0 = time.time()
    try:
        from core.database import get_collection
        query = {"company_id": company_id}
        if role:
            query["role"] = role
        col = await get_collection("users")
        docs = await col.find(query, {"_id": 0, "password": 0}).to_list(500)
        return {
            "users": docs,
            "count": len(docs),
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }
    except Exception as exc:
        return {"users": [], "count": 0, "error": str(exc)}


async def _tool_cache_get(key: str, **_) -> Dict[str, Any]:
    """Redis GET — retrieve cached agent result."""
    r = _get_redis()
    if r is None:
        return {"hit": False, "value": None}
    try:
        val = await r.get(key)
        return {"hit": val is not None, "value": val}
    except Exception as exc:
        return {"hit": False, "value": None, "error": str(exc)}


async def _tool_cache_set(key: str, value: str, ttl: int = 300, **_) -> Dict[str, Any]:
    """Redis SET — cache agent result for TTL seconds (default 5 min)."""
    r = _get_redis()
    if r is None:
        return {"stored": False}
    try:
        await r.setex(key, ttl, value)
        return {"stored": True, "ttl": ttl}
    except Exception as exc:
        return {"stored": False, "error": str(exc)}


async def _tool_get_audit_logs(company_id: str, limit: int = 50, **_) -> Dict[str, Any]:
    """Fetch recent audit log entries for transparency dashboard."""
    t0 = time.time()
    try:
        from core.database import get_collection
        col = await get_collection("audit_logs")
        docs = await col.find(
            {"company_id": company_id}, {"_id": 0}
        ).sort("timestamp", -1).to_list(limit)
        return {
            "logs": docs,
            "count": len(docs),
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }
    except Exception as exc:
        return {"logs": [], "count": 0, "error": str(exc)}


async def _tool_get_reports(company_id: str, role: Optional[str] = None, **_) -> Dict[str, Any]:
    """Retrieve reports for a company with optional role filter."""
    t0 = time.time()
    try:
        from core.database import get_collection
        collections = ["reports"]
        if role == "CEO":
            collections.append("ceo_reports")
        elif role == "HR":
            collections.append("hr_reports")
        else:
            collections += ["ceo_reports", "hr_reports"]
        all_docs = []
        for cname in collections:
            col = await get_collection(cname)
            docs = await col.find({"company_id": company_id}, {"_id": 0}).to_list(50)
            all_docs.extend(docs)
        return {
            "reports": all_docs,
            "count": len(all_docs),
            "latency_ms": round((time.time() - t0) * 1000, 1),
        }
    except Exception as exc:
        return {"reports": [], "count": 0, "error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
# Tool Registry
# ─────────────────────────────────────────────────────────────────────────────
class MCPToolRegistry:
    """
    Central registry of all MCP tools available to agents.

    Usage:
        registry = MCPToolRegistry()
        result = await registry.invoke("get_company_projects", company_id="ORG-001")

    Tool invocations are automatically logged to the provided audit_log list.
    """

    def __init__(self):
        self._tools: Dict[str, MCPTool] = {}
        self._register_defaults()

    def _register_defaults(self):
        self.register(MCPTool(
            name="get_company_projects",
            description="Fetch all active projects for a company from MongoDB.",
            handler=_tool_get_company_projects,
            category="data",
        ))
        self.register(MCPTool(
            name="get_team_velocity",
            description="Retrieve sprint velocity and burndown metrics.",
            handler=_tool_get_team_velocity,
            category="data",
        ))
        self.register(MCPTool(
            name="get_performance_data",
            description="Retrieve HR performance records and risk classifications.",
            handler=_tool_get_performance_data,
            category="data",
            required_roles=["CEO", "HR", "LEAD", "ADMIN"],
        ))
        self.register(MCPTool(
            name="get_users",
            description="Fetch all users for a company with optional role filter.",
            handler=_tool_get_users,
            category="data",
        ))
        self.register(MCPTool(
            name="cache_get",
            description="Retrieve a cached agent result from Redis.",
            handler=_tool_cache_get,
            category="cache",
        ))
        self.register(MCPTool(
            name="cache_set",
            description="Store an agent result in Redis with TTL.",
            handler=_tool_cache_set,
            category="cache",
        ))
        self.register(MCPTool(
            name="get_audit_logs",
            description="Fetch recent audit trail entries for transparency dashboard.",
            handler=_tool_get_audit_logs,
            category="data",
            required_roles=["CEO", "ADMIN"],
        ))
        self.register(MCPTool(
            name="get_reports",
            description="Retrieve reports filtered by company and role.",
            handler=_tool_get_reports,
            category="data",
        ))

    def register(self, tool: MCPTool):
        self._tools[tool.name] = tool
        logger.debug("[MCP] Registered tool: %s (%s)", tool.name, tool.category)

    async def invoke(
        self,
        tool_name: str,
        audit_log: Optional[List[Dict[str, Any]]] = None,
        user_role: str = "DEV",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Invoke a registered MCP tool by name.

        Args:
            tool_name:  Name of the registered tool.
            audit_log:  List to append invocation record (from AgentState.mcp_tool_calls).
            user_role:  Caller's role for access check.
            **kwargs:   Tool-specific parameters.

        Returns:
            Tool result dict. Always includes 'latency_ms' and 'tool_name'.
        """
        tool = self._tools.get(tool_name)
        if tool is None:
            err = f"Unknown MCP tool: {tool_name}"
            logger.error("[MCP] %s", err)
            return {"error": err, "tool_name": tool_name}

        # Role check
        if tool.required_roles and user_role not in tool.required_roles:
            err = f"Role '{user_role}' not permitted for tool '{tool_name}'"
            logger.warning("[MCP] ACCESS_DENIED %s", err)
            return {"error": err, "tool_name": tool_name}

        t0 = time.time()
        logger.info("[MCP] INVOKE tool=%s role=%s kwargs=%s", tool_name, user_role, list(kwargs.keys()))
        try:
            result = await tool.handler(user_role=user_role, **kwargs)
        except Exception as exc:
            latency = round((time.time() - t0) * 1000, 1)
            result = {"error": str(exc), "latency_ms": latency}
            logger.error("[MCP] TOOL_ERROR tool=%s err=%s latency=%.0fms",
                         tool_name, exc, latency)

        result["tool_name"] = tool_name
        if audit_log is not None:
            audit_log.append({
                "tool": tool_name,
                "kwargs": {k: str(v)[:80] for k, v in kwargs.items()},
                "latency_ms": result.get("latency_ms", round((time.time() - t0) * 1000, 1)),
                "success": "error" not in result,
            })
        return result

    def list_tools(self, category: Optional[str] = None) -> List[Dict[str, str]]:
        """Return all registered tools (optionally filtered by category)."""
        tools = self._tools.values()
        if category:
            tools = [t for t in tools if t.category == category]
        return [{"name": t.name, "description": t.description, "category": t.category}
                for t in tools]


# ─────────────────────────────────────────────────────────────────────────────
# Singleton
# ─────────────────────────────────────────────────────────────────────────────
_registry: Optional[MCPToolRegistry] = None

def get_mcp_registry() -> MCPToolRegistry:
    global _registry
    if _registry is None:
        _registry = MCPToolRegistry()
    return _registry


# ─────────────────────────────────────────────────────────────────────────────
# Cache-key helper
# ─────────────────────────────────────────────────────────────────────────────
def make_cache_key(task_type: str, company_id: str, context: Dict[str, Any]) -> str:
    """Generate a stable Redis cache key from task inputs."""
    raw = f"{task_type}:{company_id}:{sorted(context.items())}"
    return "agent:" + hashlib.sha256(raw.encode()).hexdigest()[:16]
