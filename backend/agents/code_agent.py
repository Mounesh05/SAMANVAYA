"""
Code Agent - Interprets PR evidence from Intelligence Engine
Provides code quality insights, review recommendations using DEEP ANALYSIS.

Uses JSON-mode prompting + shared parsers for robust LLM output handling.
"""

from typing import Dict, Any
from .state import AgentState
from .llm_provider import get_ollama_llm
from .parsers import safe_parse, CodeAnalysisResult


def code_analysis_node(state: AgentState) -> Dict[str, Any]:
    """
    Enhanced code review agent - interprets comprehensive evidence and provides recommendations.

    Args:
        state: Contains evidence from Intelligence Engine (all analyzers)

    Returns:
        Updated state with detailed analysis, quality scores, and recommendations
    """
    evidence = state.get("evidence", {})
    context = state.get("context", {})

    # Extract evidence summary (human-readable format from evidence builder)
    evidence_summary = evidence.get("evidence_summary", "")
    if not evidence_summary:
        evidence_summary = _build_evidence_text(evidence, context)

    # JSON-mode prompt — LLM must return a single JSON object
    prompt = f"""You are a senior software engineer performing an AI code review.

## Evidence Package
{evidence_summary}

## Instructions
Analyse the evidence above and return ONLY a valid JSON object with this exact structure:

{{
  "quality_score": <number 0-100>,
  "failure_risk": <number 0-100>,
  "risk_level": "<critical|high|medium|low>",
  "confidence": <number 0.0-1.0>,
  "analysis": "<detailed technical analysis>",
  "critical_issues": ["<issue 1>", "<issue 2>"],
  "recommendations": ["<rec 1>", "<rec 2>", "<rec 3>"],
  "review_focus": "<files/functions that need careful review>",
  "quality_breakdown": {{
    "correctness": <0-20>,
    "maintainability": <0-20>,
    "security": <0-20>,
    "testing": <0-15>,
    "performance": <0-10>,
    "architecture": <0-10>,
    "readability": <0-5>
  }}
}}

Return ONLY the JSON object. No prose before or after."""

    fallback = CodeAnalysisResult()

    try:
        llm = get_ollama_llm(temperature=0.2)
        response = llm.invoke(prompt)

        parsed = safe_parse(response, CodeAnalysisResult, fallback)

        return {
            **state,
            "analysis": parsed.analysis,
            "recommendations": parsed.recommendations,
            "risk_level": parsed.risk_level,
            "confidence": parsed.confidence,
            "quality_score": parsed.quality_score,
            "quality_breakdown": parsed.quality_breakdown,
            "failure_risk": parsed.failure_risk,
            "critical_issues": parsed.critical_issues,
            "review_focus": parsed.review_focus,
            # Attach formula-based evidence scores alongside AI interpretation
            "evidence_risk_score": evidence.get("overall_risk_score", 0),
            "evidence_quality_score": evidence.get("quality_score", 0),
            "risk_factors": evidence.get("risk_factors", []),
            "quality_factors": evidence.get("quality_factors", []),
            "agent_history": state.get("agent_history", []) + ["code_agent_enhanced"],
            "next_agent": None,
        }

    except Exception as e:
        return {
            **state,
            "errors": state.get("errors", []) + [f"Code agent error: {str(e)}"],
            "agent_history": state.get("agent_history", []) + ["code_agent_enhanced"],
            "next_agent": None,
        }


def _build_evidence_text(evidence: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Build evidence text from raw evidence dict (fallback)."""
    parts = []
    
    parts.append(f"PR: {context.get('pr_title', 'Untitled')}")
    parts.append(f"Files changed: {evidence.get('files_analyzed', 0)}")
    
    # Static analysis
    static = evidence.get("static_analysis", {})
    if static:
        parts.append(f"\nStatic Analysis: {static.get('errors', 0)} errors, {static.get('warnings', 0)} warnings")
    
    # Security
    security = evidence.get("security", {})
    if security:
        parts.append(f"Security: {security.get('critical_issues', 0)} critical, {security.get('high_issues', 0)} high")
    
    # Complexity
    complexity = evidence.get("complexity", {})
    if complexity:
        parts.append(f"Complexity: avg {complexity.get('average_complexity', 0)}, max {complexity.get('max_complexity', 0)}")
    
    # Tests
    tests = evidence.get("tests", {})
    if tests:
        cov = tests.get("coverage", {}).get("line_coverage")
        parts.append(f"Test Coverage: {cov}%" if cov else "Test Coverage: Unknown")
    
    return "\n".join(parts)
