"""
LLM Provider - Ollama Integration
Provides local LLM access without API costs
"""

import logging
import httpx
from typing import Optional
from langchain_core.language_models import BaseLLM
from core.config import settings

logger = logging.getLogger(__name__)

try:
    from langchain_ollama import OllamaLLM
except ImportError:
    from langchain_community.llms import Ollama as OllamaLLM


def get_ollama_llm(
    model: Optional[str] = None,
    temperature: float = 0.7,
    base_url: Optional[str] = None,
) -> BaseLLM:
    """
    Get Ollama LLM instance for agent usage.
    """
    return OllamaLLM(
        model=model or settings.OLLAMA_MODEL,
        temperature=temperature,
        base_url=base_url or settings.OLLAMA_BASE_URL,
        timeout=120,
    )


def check_ollama_connection() -> bool:
    """
    Health check for Ollama server availability.
    Uses the /api/tags endpoint instead of running inference.
    """
    try:
        base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        response = httpx.get(f"{base_url}/api/tags", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False
