"""
QA Agent - Test coverage and quality assurance recommendations.
Uses JSON-mode prompting + shared parsers for robust LLM output handling.
"""

from typing import Dict, Any
from .state import AgentState
from .llm_provider import get_ollama_llm
from .parsers import safe_parse, AgentAnalysisResult


SYSTEM_PROMPT = """You are a QA engineer analyzing test and quality metrics.

Your role:
- Interpret test coverage and quality evidence
- Recommend testing strategies and improvements
- Identify quality gaps and risks

You receive EVIDENCE from the Intelligence Engine.
DO NOT recalculate - interpret the provided metrics.

Focus on:
1. Test coverage gaps (files, branches, lines)
2. Test quality patterns (flaky tests, slow tests)
3. Quality assurance process improvements
4. Risk mitigation through testing

Be specific about what tests to add and why."""


def qa_analysis_node(state: AgentState) -> Dict[str, Any]:
    """
    QA agent - interprets test/quality evidence and provides recommendations.
    
    Args:
        state: Contains evidence from Intelligence Engine
        
    Returns:
        Updated state with QA analysis and recommendations
    """
    evidence = state.get("evidence", {})
    context = state.get("context", {})
    
    prompt = f"""You are a QA engineer analyzing test coverage and quality.

## Evidence
Test Coverage: {evidence.get('test_coverage_pct', 'N/A')}%
Coverage Delta: {evidence.get('coverage_delta', 'N/A')}%
Tests Added: {evidence.get('tests_added', 0)}
Files Without Tests: {evidence.get('files_without_tests', 0)}
QA Risk Level: {evidence.get('qa_risk_level', 'unknown')}
Missing Coverage: {evidence.get('missing_coverage_areas', [])}

## Instructions
Return ONLY a valid JSON object:
{{
  "analysis": "<key quality insights>",
  "recommendations": ["<test rec 1>", "<test rec 2>", "<test rec 3>"],
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
            "agent_history": state.get("agent_history", []) + ["qa_agent"],
            "next_agent": None,
        }

    except Exception as e:
        return {
            **state,
            "errors": state.get("errors", []) + [f"QA agent error: {str(e)}"],
            "agent_history": state.get("agent_history", []) + ["qa_agent"],
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
