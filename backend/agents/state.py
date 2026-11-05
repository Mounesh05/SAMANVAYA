"""
Shared state definitions for AI agents
"""

from typing import TypedDict, Literal, Optional, Dict, Any, List


class AgentState(TypedDict, total=False):
    """
    State passed to agent nodes.
    """
    task_type: Literal["code_review", "qa_analysis", "devops_risk", "meeting_insights", "cicd_analysis", "hr_assistant"]
    evidence: Dict[str, Any]
    context: Optional[Dict[str, Any]]
    user_context: Optional[Dict[str, Any]]  # NEW: User authorization context
    analysis: Optional[str]
    recommendations: Optional[List[str]]
    risk_level: Optional[Literal["low", "medium", "high", "critical"]]
    confidence: Optional[float]
    agent_history: List[str]
    errors: List[str]
    quality_score: Optional[float]
    quality_breakdown: Optional[Dict[str, Any]]
    failure_risk: Optional[float]
    critical_issues: Optional[List[str]]
    review_focus: Optional[str]
    evidence_risk_score: Optional[float]
    evidence_quality_score: Optional[float]
    risk_factors: Optional[List[Any]]
    quality_factors: Optional[List[Any]]
    affected_component: Optional[str]
    prevention: Optional[str]
    urgency: Optional[str]
    next_agent: Optional[str]
    quality_result: Dict[str, Any]
    risk_result: Dict[str, Any]
