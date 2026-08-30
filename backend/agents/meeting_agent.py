"""
Meeting Agent - Sprint insights, standup prep, retrospective analysis.
Uses JSON-mode prompting + shared parsers for robust LLM output handling.
"""

from typing import Dict, Any
from .state import AgentState
from .llm_provider import get_ollama_llm
from .parsers import safe_parse, AgentAnalysisResult


SYSTEM_PROMPT = """You are an agile coach analyzing sprint and team performance.

Your role:
- Interpret sprint velocity, burndown, and team metrics
- Provide standup talking points and blockers
- Generate retrospective insights and action items

You receive EVIDENCE from the Intelligence Engine.
DO NOT recalculate - interpret the provided metrics.

Focus on:
1. Sprint health (velocity trends, scope changes, risk)
2. Team performance patterns (WIP limits, review cycles, blockers)
3. Actionable insights for standups and retrospectives
4. Process improvements based on evidence

Be specific about what's going well and what needs attention."""


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


def _parse_response(response: str) -> tuple[str, list[str], str, float]:
    """Parse structured LLM response."""
    lines = response.strip().split("\n")
    
    analysis = ""
    recommendations = []
    risk_level = "low"
    confidence = 0.7
    current_section = None
    
    for line in lines:
        line = line.strip()
        
        if line.startswith("ANALYSIS:"):
            current_section = "analysis"
            analysis = line.replace("ANALYSIS:", "").strip()
        elif line.startswith("RECOMMENDATIONS:"):
            current_section = "recommendations"
        elif line.startswith("RISK_LEVEL:"):
            risk_level = line.replace("RISK_LEVEL:", "").strip().lower()
        elif line.startswith("CONFIDENCE:"):
            try:
                confidence = float(line.replace("CONFIDENCE:", "").strip())
            except ValueError:
                confidence = 0.7
        elif current_section == "analysis" and line:
            analysis += " " + line
        elif current_section == "recommendations" and line.startswith("-"):
            recommendations.append(line.lstrip("- ").strip())
    
    return analysis, recommendations, risk_level, confidence
