"""
LiteLLM Gateway — Unified LLM provider routing Ollama (local) through LiteLLM.

Architecture role:
    Supervisor/Agents -> LiteLLMGateway -> LiteLLM -> Ollama (qwen2.5-coder:7b)

Benefits of LiteLLM layer:
  - Standardised OpenAI-compatible interface for all agents
  - Built-in retry + fallback (e.g. qwen2.5-coder:7b -> llama3.2 on timeout)
  - Token counting, cost tracking (even for local models)
  - Streaming support
  - Model aliasing: "samanvaya-code" -> "ollama/qwen2.5-coder:7b"
"""

import time
import logging
from typing import Optional, Dict, Any, List
from functools import lru_cache

from core.config import settings

logger = logging.getLogger("samanvaya.llm_gateway")


# ─────────────────────────────────────────────────────────────────────────────
# LiteLLM import with graceful fallback to direct Ollama
# ─────────────────────────────────────────────────────────────────────────────
try:
    import litellm
    litellm.set_verbose = False                  # suppress noise; we log ourselves
    litellm.drop_params = True                   # ignore unsupported params silently
    _LITELLM_AVAILABLE = True
    logger.info("[LLMGateway] LiteLLM loaded — routing via litellm proxy")
except ImportError:
    _LITELLM_AVAILABLE = False
    logger.warning("[LLMGateway] LiteLLM not installed — falling back to direct httpx")

# Fallback: direct httpx Ollama call when litellm is absent
import httpx


# ─────────────────────────────────────────────────────────────────────────────
# Model alias registry
# ─────────────────────────────────────────────────────────────────────────────
MODEL_ALIASES: Dict[str, str] = {
    # Logical name              -> LiteLLM model string (local Ollama)
    "samanvaya-code":          "ollama/qwen2.5-coder:7b",
    "samanvaya-qa":            "ollama/qwen2.5-coder:7b",
    "samanvaya-devops":        "ollama/qwen2.5-coder:7b",
    "samanvaya-cicd":          "ollama/qwen2.5-coder:7b",
    "samanvaya-meeting":       "ollama/qwen2.5-coder:7b",
    "samanvaya-performance":   "ollama/qwen2.5-coder:7b",
    "samanvaya-report":        "ollama/qwen2.5-coder:7b",
    # Add cloud fallbacks when needed, e.g.:
    # "samanvaya-report-cloud": "gpt-4o-mini",
}

# Temperature presets per task class
TEMP_PRESETS: Dict[str, float] = {
    "code_review":      0.15,   # Precise, deterministic
    "qa_analysis":      0.20,
    "devops_risk":      0.20,
    "cicd_analysis":    0.15,
    "meeting_insights": 0.45,   # Allow some creativity
    "performance_eval": 0.25,
    "report_synthesis": 0.35,
    "default":          0.30,
}


# ─────────────────────────────────────────────────────────────────────────────
# Gateway class
# ─────────────────────────────────────────────────────────────────────────────
class LiteLLMGateway:
    """
    Single entry-point for all agent LLM calls.

    Usage:
        gateway = LiteLLMGateway()
        result = await gateway.complete(
            model_alias="samanvaya-code",
            messages=[{"role": "user", "content": prompt}],
            task_type="code_review",
        )
        text  = result["content"]
        tokens = result["total_tokens"]
        latency = result["latency_ms"]
    """

    def __init__(self, base_url: Optional[str] = None):
        self.ollama_base = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.default_model = getattr(settings, "OLLAMA_MODEL", "qwen2.5-coder:7b")

    def _resolve_model(self, alias: str) -> str:
        """Resolve a logical alias to a LiteLLM model string."""
        if alias in MODEL_ALIASES:
            return MODEL_ALIASES[alias]
        # If caller passed a raw model name, prefix for Ollama
        if "/" not in alias:
            return f"ollama/{alias}"
        return alias

    async def complete(
        self,
        messages: List[Dict[str, str]],
        model_alias: str = "samanvaya-code",
        task_type: str = "default",
        temperature: Optional[float] = None,
        max_tokens: int = 2048,
        timeout: int = 90,
    ) -> Dict[str, Any]:
        """
        Send a chat completion request through LiteLLM -> Ollama.

        Returns:
            {
                "content":      str,   # LLM text response
                "model":        str,   # Resolved model name
                "total_tokens": int,
                "latency_ms":   float,
                "success":      bool,
            }
        """
        resolved_model = self._resolve_model(model_alias)
        temp = temperature if temperature is not None else TEMP_PRESETS.get(task_type, 0.30)
        t0 = time.time()

        logger.info(
            "[LLMGateway] INVOKE model=%s task=%s max_tokens=%d temp=%.2f",
            resolved_model, task_type, max_tokens, temp
        )

        if _LITELLM_AVAILABLE:
            return await self._litellm_complete(
                resolved_model, messages, temp, max_tokens, timeout, t0
            )
        else:
            return await self._direct_ollama_complete(
                resolved_model, messages, temp, max_tokens, timeout, t0
            )

    # ── LiteLLM path ─────────────────────────────────────────────────────────
    async def _litellm_complete(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        timeout: int,
        t0: float,
    ) -> Dict[str, Any]:
        try:
            resp = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                request_timeout=timeout,
                api_base=self.ollama_base,
            )
            latency = (time.time() - t0) * 1000
            content = resp.choices[0].message.content or ""
            tokens = getattr(resp.usage, "total_tokens", 0)

            logger.info(
                "[LLMGateway] OK model=%s tokens=%d latency=%.0fms",
                model, tokens, latency
            )
            return {
                "content": content,
                "model": model,
                "total_tokens": tokens,
                "latency_ms": round(latency, 1),
                "success": True,
            }
        except Exception as exc:
            latency = (time.time() - t0) * 1000
            logger.error("[LLMGateway] LiteLLM ERROR %s after %.0fms", exc, latency)
            return await self._direct_ollama_complete(
                model, messages, temperature, max_tokens, timeout, t0
            )

    # ── Direct httpx Ollama fallback ─────────────────────────────────────────
    async def _direct_ollama_complete(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        timeout: int,
        t0: float,
    ) -> Dict[str, Any]:
        """Bypass LiteLLM and call Ollama /api/chat directly."""
        # Resolve raw model name for Ollama (strip "ollama/" prefix)
        raw_model = model.replace("ollama/", "")
        url = f"{self.ollama_base}/api/chat"
        payload = {
            "model": raw_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data.get("message", {}).get("content", "")
                latency = (time.time() - t0) * 1000
                logger.info(
                    "[LLMGateway] DIRECT-OLLAMA OK model=%s latency=%.0fms",
                    raw_model, latency
                )
                return {
                    "content": content,
                    "model": raw_model,
                    "total_tokens": data.get("eval_count", 0),
                    "latency_ms": round(latency, 1),
                    "success": True,
                }
        except Exception as exc:
            latency = (time.time() - t0) * 1000
            logger.error("[LLMGateway] DIRECT-OLLAMA ERROR %s after %.0fms", exc, latency)
            return {
                "content": "",
                "model": raw_model,
                "total_tokens": 0,
                "latency_ms": round(latency, 1),
                "success": False,
                "error": str(exc),
            }

    # ── Sync convenience wrapper for legacy agents that call llm.invoke() ────
    def invoke_sync(
        self,
        prompt: str,
        model_alias: str = "samanvaya-code",
        task_type: str = "default",
        temperature: Optional[float] = None,
    ) -> str:
        """
        Synchronous wrapper around direct Ollama /api/generate.
        Used by legacy agent nodes that cannot use async.
        """
        import requests
        raw_model = self._resolve_model(model_alias).replace("ollama/", "")
        temp = temperature if temperature is not None else TEMP_PRESETS.get(task_type, 0.30)
        t0 = time.time()
        try:
            resp = requests.post(
                f"{self.ollama_base}/api/generate",
                json={"model": raw_model, "prompt": prompt, "stream": False,
                      "options": {"temperature": temp}},
                timeout=90,
            )
            resp.raise_for_status()
            content = resp.json().get("response", "")
            latency = (time.time() - t0) * 1000
            logger.info("[LLMGateway] SYNC-INVOKE OK model=%s latency=%.0fms",
                        raw_model, latency)
            return content
        except Exception as exc:
            logger.error("[LLMGateway] SYNC-INVOKE ERROR %s", exc)
            return ""


# ─────────────────────────────────────────────────────────────────────────────
# Singleton accessor
# ─────────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_gateway() -> LiteLLMGateway:
    """Return the shared LiteLLM gateway singleton."""
    return LiteLLMGateway()


# ─────────────────────────────────────────────────────────────────────────────
# Backward-compatible: get_ollama_llm() — wraps gateway.invoke_sync()
# ─────────────────────────────────────────────────────────────────────────────
class _OllamaCompat:
    """Thin shim so existing agents calling get_ollama_llm().invoke(prompt) still work."""

    def __init__(self, model_alias: str, temperature: float):
        self._alias = model_alias
        self._temp = temperature
        self._gw = get_gateway()

    def invoke(self, prompt: str) -> str:
        return self._gw.invoke_sync(prompt, model_alias=self._alias, temperature=self._temp)

    async def ainvoke(self, prompt: str) -> str:
        import asyncio
        result = await get_gateway().complete(
            messages=[{"role": "user", "content": prompt}],
            model_alias=self._alias,
            temperature=self._temp,
        )
        return result["content"]


def get_ollama_llm(
    model: Optional[str] = None,
    temperature: float = 0.30,
    base_url: Optional[str] = None,
) -> _OllamaCompat:
    """
    Backward-compatible shim.  Returns an object with .invoke() / .ainvoke()
    that routes through the LiteLLM gateway.
    """
    alias = f"ollama/{model}" if model else "samanvaya-code"
    return _OllamaCompat(model_alias=alias, temperature=temperature)


def check_ollama_connection() -> bool:
    """Health-check: ping the Ollama server."""
    try:
        import requests
        r = requests.get(
            f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=5
        )
        return r.status_code == 200
    except Exception:
        return False
