"""
Agent Memory — Redis (short-term) + MongoDB (long-term) memory layer.

Architecture position:
    Supervisor -> [MemoryNode] -> Redis (hot cache, 5-min TTL)
                               -> MongoDB.agent_memory (persistent conversation history)

Design:
  - Before invoking LLM: retrieve relevant past context (RAG over MongoDB history)
  - After agent completes: write result to Redis + MongoDB for future recall
  - TTL strategy:
        Redis   -> 5 minutes  (same-session dedup, fast recall)
        MongoDB -> permanent  (audit trail, cross-session learning)
"""

import json
import time
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger("samanvaya.memory")

# ─────────────────────────────────────────────────────────────────────────────
# Redis client (lazy init)
# ─────────────────────────────────────────────────────────────────────────────
_redis = None

async def _get_redis_client():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis.asyncio as aioredis
        from core.config import settings
        url = getattr(settings, "REDIS_URL", "redis://localhost:6379")
        _redis = aioredis.from_url(url, decode_responses=True)
        await _redis.ping()
        logger.info("[MEMORY] Redis connected: %s", url)
    except Exception as exc:
        logger.warning("[MEMORY] Redis unavailable (%s) — memory runs MongoDB-only", exc)
        _redis = None
    return _redis


# ─────────────────────────────────────────────────────────────────────────────
# MongoDB memory collection helper
# ─────────────────────────────────────────────────────────────────────────────
async def _get_memory_col():
    try:
        from core.database import get_collection
        return await get_collection("agent_memory")
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Redis short-term memory
# ─────────────────────────────────────────────────────────────────────────────
REDIS_TTL = 300  # 5 minutes

async def redis_get(key: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a cached agent result from Redis.
    Returns None if key missing, expired, or Redis unavailable.
    """
    r = await _get_redis_client()
    if r is None:
        return None
    try:
        raw = await r.get(key)
        if raw:
            logger.debug("[MEMORY] Redis HIT key=%s", key)
            return json.loads(raw)
        logger.debug("[MEMORY] Redis MISS key=%s", key)
        return None
    except Exception as exc:
        logger.warning("[MEMORY] Redis GET error: %s", exc)
        return None


async def redis_set(key: str, value: Dict[str, Any], ttl: int = REDIS_TTL) -> bool:
    """Cache an agent result in Redis."""
    r = await _get_redis_client()
    if r is None:
        return False
    try:
        await r.setex(key, ttl, json.dumps(value, default=str))
        logger.debug("[MEMORY] Redis SET key=%s ttl=%ds", key, ttl)
        return True
    except Exception as exc:
        logger.warning("[MEMORY] Redis SET error: %s", exc)
        return False


async def redis_invalidate(pattern: str) -> int:
    """Delete all Redis keys matching a pattern (e.g. 'agent:ORG-001:*')."""
    r = await _get_redis_client()
    if r is None:
        return 0
    try:
        keys = await r.keys(pattern)
        if keys:
            await r.delete(*keys)
        logger.info("[MEMORY] Invalidated %d Redis keys for pattern=%s", len(keys), pattern)
        return len(keys)
    except Exception as exc:
        logger.warning("[MEMORY] Redis INVALIDATE error: %s", exc)
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# MongoDB long-term memory
# ─────────────────────────────────────────────────────────────────────────────

async def mongo_save_result(
    task_type: str,
    company_id: str,
    user_id: str,
    task_id: str,
    result: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Persist an agent result to MongoDB agent_memory collection.

    Schema:
        {
            task_type, company_id, user_id, task_id,
            analysis, recommendations, risk_level, confidence,
            context, created_at, agent_history, errors
        }
    """
    col = await _get_memory_col()
    if col is None:
        return False
    try:
        doc = {
            "task_type":       task_type,
            "company_id":      company_id,
            "user_id":         user_id,
            "task_id":         task_id,
            "analysis":        result.get("analysis", ""),
            "recommendations": result.get("recommendations", []),
            "risk_level":      result.get("risk_level", "medium"),
            "confidence":      result.get("confidence", 0.0),
            "llm_model":       result.get("llm_model_used", ""),
            "latency_ms":      result.get("latency_ms", {}),
            "token_counts":    result.get("token_counts", {}),
            "agent_history":   result.get("agent_history", []),
            "errors":          result.get("errors", []),
            "context":         context or {},
            "created_at":      datetime.now(timezone.utc).isoformat(),
        }
        await col.insert_one(doc)
        logger.info("[MEMORY] MongoDB SAVED task=%s company=%s", task_type, company_id)
        return True
    except Exception as exc:
        logger.warning("[MEMORY] MongoDB SAVE error: %s", exc)
        return False


async def mongo_get_history(
    company_id: str,
    task_type: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Retrieve recent agent memory from MongoDB for RAG context injection.

    Returns most-recent N records (newest first).
    """
    col = await _get_memory_col()
    if col is None:
        return []
    try:
        query: Dict[str, Any] = {"company_id": company_id}
        if task_type:
            query["task_type"] = task_type
        if user_id:
            query["user_id"] = user_id
        docs = (
            await col.find(query, {"_id": 0})
            .sort("created_at", -1)
            .to_list(limit)
        )
        logger.debug("[MEMORY] MongoDB HISTORY retrieved %d records", len(docs))
        return docs
    except Exception as exc:
        logger.warning("[MEMORY] MongoDB HISTORY error: %s", exc)
        return []


async def build_rag_context(
    company_id: str,
    task_type: str,
    limit: int = 5,
) -> str:
    """
    Build a RAG (Retrieval-Augmented Generation) context string from
    recent MongoDB memory entries.

    The context is injected into the agent's LLM prompt so it can
    reason about historical patterns.
    """
    history = await mongo_get_history(
        company_id=company_id,
        task_type=task_type,
        limit=limit,
    )
    if not history:
        return ""

    parts = ["### Relevant Historical Context (last sessions):"]
    for i, entry in enumerate(history, 1):
        ts = entry.get("created_at", "")[:16]
        analysis = (entry.get("analysis") or "")[:300]
        risk = entry.get("risk_level", "?")
        recs = "; ".join((entry.get("recommendations") or [])[:2])
        parts.append(
            f"[Session {i} | {ts} | risk={risk}]\n"
            f"Analysis: {analysis}\n"
            f"Top Recs: {recs}"
        )
    return "\n\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph memory nodes
# ─────────────────────────────────────────────────────────────────────────────
async def memory_read_node(state: dict) -> dict:
    """
    LangGraph node: read from Redis cache + MongoDB history before agent runs.

    Sets:
        state.redis_hit           = True if cache hit
        state.rag_context         = Historical RAG string for LLM prompt enrichment
        state.conversation_history = Raw MongoDB entries
    """
    from .mcp_tools import make_cache_key

    task_type  = state.get("task_type", "")
    company_id = state.get("company_id", "")
    context    = state.get("context", {})

    # 1. Redis cache lookup
    cache_key = make_cache_key(task_type, company_id, context)
    cached = await redis_get(cache_key)
    if cached:
        logger.info("[MEMORY] Cache HIT -> skipping agent for task=%s", task_type)
        return {
            **state,
            **cached,
            "redis_hit": True,
            "cache_key": cache_key,
        }

    # 2. MongoDB RAG context
    rag_ctx = await build_rag_context(company_id, task_type)
    history = await mongo_get_history(company_id, task_type, limit=5)

    return {
        **state,
        "redis_hit": False,
        "cache_key": cache_key,
        "rag_context": rag_ctx,
        "conversation_history": history,
    }


async def memory_write_node(state: dict) -> dict:
    """
    LangGraph node: persist agent result to Redis + MongoDB after agent runs.
    """
    if state.get("redis_hit"):
        return state  # already from cache — don't double-write

    cache_key  = state.get("cache_key", "")
    task_type  = state.get("task_type", "")
    company_id = state.get("company_id", "")
    user_id    = state.get("user_id", "system")
    task_id    = state.get("task_id", "")

    payload = {
        "analysis":        state.get("analysis", ""),
        "recommendations": state.get("recommendations", []),
        "risk_level":      state.get("risk_level", "medium"),
        "confidence":      state.get("confidence", 0.0),
        "latency_ms":      state.get("latency_ms", {}),
        "token_counts":    state.get("token_counts", {}),
        "agent_history":   state.get("agent_history", []),
        "llm_model_used":  state.get("llm_model_used", ""),
        "errors":          state.get("errors", []),
    }

    # Write to Redis (short-term)
    if cache_key:
        await redis_set(cache_key, payload)

    # Write to MongoDB (long-term)
    await mongo_save_result(
        task_type  = task_type,
        company_id = company_id,
        user_id    = user_id,
        task_id    = task_id,
        result     = payload,
        context    = state.get("context", {}),
    )

    return state
