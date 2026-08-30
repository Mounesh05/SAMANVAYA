"""
Shared state definitions for LangGraph agents
"""

from typing import TypedDict, Literal, Optional, Dict, Any, List


class AgentState(TypedDict):
    """
    Shared state passed between agents in the supervisor graph.
    
    The supervisor routes tasks to specialized agents based on task_type.
    Each agent interprets evidence from the Intelligence Engine (Layer 5).
    """
    # Input
    task_type: Literal["code_review", "qa_analysis", "devops_risk", "meeting_insights"]
    evidence: Dict[str, Any]  # From Intelligence Engine
    context: Optional[Dict[str, Any]]  # Additional context (sprint, PR, etc.)
    
    # Routing
    next_agent: Optional[str]
    
    # Output
    analysis: Optional[str]
    recommendations: Optional[List[str]]
    risk_level: Optional[Literal["low", "medium", "high", "critical"]]
    confidence: Optional[float]
    
    # Metadata
    agent_history: List[str]  # Track which agents processed this
    errors: List[str]
