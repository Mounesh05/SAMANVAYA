"""
Meeting Agent - Sprint insights, standup prep, retrospective analysis.
Uses JSON-mode prompting + shared parsers for robust LLM output handling.
"""

from typing import Dict, Any
from .state import AgentState
from .llm_provider import get_ollama_llm
from .parsers import safe_parse, AgentAnalysisResult


def meeting_insights_node(state: AgentState) -> Dict[str, Any]:
    """
    Meeting agent - interprets sprint/team evidence for meetings.
    
    Args:
        state: Contains evidence from Intelligence Engine
        
    Returns:
        Updated state with meeting insights and recommendations
    """
    evidence = state.get("evidence", {})
    context = state.get("context", {})
    
    meeting_type = context.get('meeting_type', 'standup')
    prompt = f"""You are an agile coach providing {meeting_type} insights.

## Sprint Evidence
Velocity: {evidence.get('sprint_velocity', 'N/A')} pts | Trend: {evidence.get('velocity_trend', 'stable')}
Completed: {evidence.get('completed_stories', 0)}/{evidence.get('total_stories', 0)} stories
Burndown: {evidence.get('burndown_status', 'on_track')}
Blocked: {evidence.get('blocked_stories', 0)} | WIP: {evidence.get('wip_count', 0)}
Sprint Risk: {evidence.get('sprint_risk_level', 'low')}
At-Risk Stories: {evidence.get('at_risk_stories', [])}
Sprint: {context.get('sprint_name', 'N/A')} | Days Left: {context.get('days_remaining', 'N/A')}

## Instructions
Return ONLY a valid JSON object:
{{
  "analysis": "<key sprint/team insights for {meeting_type}>",
  "recommendations": ["<talking point/action 1>", "<talking point/action 2>", "<talking point/action 3>"],
  "risk_level": "<critical|high|medium|low>",
  "confidence": <0.0-1.0>
}}
Return ONLY JSON. No prose."""

    fallback = AgentAnalysisResult()

    try:
        llm = get_ollama_llm(temperature=0.5)
        response = llm.invoke(prompt)
        parsed = safe_parse(response, AgentAnalysisResult, fallback)

        return {
            **state,
            "analysis": parsed.analysis,
            "recommendations": parsed.recommendations,
            "risk_level": parsed.risk_level,
            "confidence": parsed.confidence,
            "agent_history": state.get("agent_history", []) + ["meeting_agent"],
            "next_agent": None,
        }

    except Exception as e:
        return {
            **state,
            "errors": state.get("errors", []) + [f"Meeting agent error: {str(e)}"],
            "agent_history": state.get("agent_history", []) + ["meeting_agent"],
            "next_agent": None,
        }
