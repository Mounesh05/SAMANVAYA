"""
Shared state definitions for AI agents
"""

from typing import TypedDict, Literal, Optional, Dict, Any, List


class AgentState(TypedDict, total=False):
    """
    State passed to agent nodes.
    """
    task_type: Literal["code_review", "qa_analysis", "devops_risk", "meeting_insights", "cicd_analysis"]
    evidence: Dict[str, Any]
    context: Optional[Dict[str, Any]]
    analysis: Optional[str]
    recommendations: Optional[List[str]]
    risk_level: Optional[Literal["low", "medium", "high", "critical"]]
    confidence: Optional[float]
    agent_history: List[str]
    errors: List[str]
