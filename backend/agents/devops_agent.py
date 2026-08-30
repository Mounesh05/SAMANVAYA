"""
DevOps Agent - Deployment risk and infrastructure recommendations.
Uses JSON-mode prompting + shared parsers for robust LLM output handling.
"""

from typing import Dict, Any
from .state import AgentState
from .llm_provider import get_ollama_llm
from .parsers import safe_parse, AgentAnalysisResult


SYSTEM_PROMPT = """You are a DevOps engineer analyzing deployment risk and infrastructure.

Your role:
- Interpret deployment risk evidence
- Recommend CI/CD and infrastructure improvements
- Identify deployment blockers and mitigation strategies

You receive EVIDENCE from the Intelligence Engine.
DO NOT recalculate - interpret the provided metrics.

Focus on:
1. Deployment risk factors (breaking changes, missing tests, large PRs)
2. CI/CD pipeline health and improvements
3. Infrastructure concerns (dependencies, migrations, config)
4. Rollback and monitoring strategies

Be specific about deployment readiness and mitigation steps."""


def devops_analysis_node(state: AgentState) -> Dict[str, Any]:
    """
    DevOps agent - interprets deployment risk and provides recommendations.
    
    Args:
        state: Contains evidence from Intelligence Engine
        
    Returns:
        Updated state with DevOps analysis and recommendations
    """
    evidence = state.get("evidence", {})
    context = state.get("context", {})
    
    prompt = f"""You are a DevOps engineer analyzing deployment risk.

## Evidence
Deployment Risk Score: {evidence.get('deployment_risk_score', 0)}/100
Breaking Changes: {evidence.get('breaking_changes', 0)}
DB Migrations: {evidence.get('db_migrations', 0)}
Build Status: {evidence.get('build_status', 'unknown')}
Test Pass Rate: {evidence.get('test_pass_rate', 'N/A')}%
Failed Checks: {evidence.get('failed_checks', [])}
Large PR: {evidence.get('is_large_pr', False)}
PR Title: {context.get('pr_title', 'N/A')}

## Instructions
Return ONLY a valid JSON object:
{{
  "analysis": "<deployment readiness and key risks>",
  "recommendations": ["<rec 1>", "<rec 2>", "<rec 3>"],
  "risk_level": "<critical|high|medium|low>",
  "confidence": <0.0-1.0>
}}
Return ONLY JSON. No prose."""

    fallback = AgentAnalysisResult()

    try:
        llm = get_ollama_llm(temperature=0.3)
        response = llm.invoke(prompt)
        parsed = safe_parse(response, AgentAnalysisResult, fallback)

        return {
            **state,
            "analysis": parsed.analysis,
            "recommendations": parsed.recommendations,
            "risk_level": parsed.risk_level,
            "confidence": parsed.confidence,
            "agent_history": state.get("agent_history", []) + ["devops_agent"],
            "next_agent": None,
        }

    except Exception as e:
        return {
            **state,
            "errors": state.get("errors", []) + [f"DevOps agent error: {str(e)}"],
            "agent_history": state.get("agent_history", []) + ["devops_agent"],
            "next_agent": None,
        }


def _parse_response(response: str) -> tuple[str, list[str], str, float]:
    """Parse structured LLM response."""
    lines = response.strip().split("\n")
    
    analysis = ""
    recommendations = []
    risk_level = "medium"
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
