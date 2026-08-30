"""
LLM Provider - Ollama Integration
Provides local LLM access without API costs
"""

from typing import Optional
from langchain_core.language_models import BaseLLM
from core.config import settings

# Try new import first, fall back to community if not available
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
    
    Args:
        model: Model name (defaults to settings.OLLAMA_MODEL)
        temperature: Sampling temperature (0.0-1.0)
        base_url: Ollama server URL (defaults to settings.OLLAMA_BASE_URL)
    
    Returns:
        Configured Ollama LLM instance
        
    Example:
        llm = get_ollama_llm(model="llama3.2", temperature=0.3)
        response = llm.invoke("Analyze this code quality...")
    """
    return OllamaLLM(
        model=model or settings.OLLAMA_MODEL,
        temperature=temperature,
        base_url=base_url or settings.OLLAMA_BASE_URL,
    )


def check_ollama_connection() -> bool:
    """
    Health check for Ollama server availability.
    
    Returns:
        True if Ollama is reachable, False otherwise
    """
    try:
        llm = get_ollama_llm()
        # Simple test prompt
        llm.invoke("test", stop=[""])
        return True
    except Exception:
        return False
