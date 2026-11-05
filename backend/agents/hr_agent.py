"""
HR Agent - HR-safe assistant for employee directory, performance outcomes, transfers
Operates with filtered data, NO access to technical details or source code.
"""

from typing import Dict, Any
from .state import AgentState
from .llm_provider import get_ollama_llm
from .parsers import parse_response, AgentAnalysisResult
from core.permissions import Permission


def hr_assistant_node(state: AgentState) -> Dict[str, Any]:
    """
    HR-safe AI assistant: employee directory, performance outcomes, transfers.
    
    CAPABILITIES:
    - Search employee directory
    - Summarize approved performance outcomes (NO technical details)
    - Identify pending transfer requests
    - Draft HR communications
    - Identify compliance gaps
    
    RESTRICTIONS:
    - CANNOT read source code
    - CANNOT access GitHub PRs/commits
    - CANNOT access CI/CD logs
    - CANNOT modify team memberships
    - CANNOT assign projects/tasks
    
    Args:
        state: Contains evidence and user_context
    
    Returns:
        Updated state with HR-focused analysis
    """
    user_context = state.get('user_context', {})
    user_perms = user_context.get('permissions', [])
    
    # Permission check - HR assistant requires VIEW_EMPLOYEE_DIRECTORY
    if Permission.VIEW_EMPLOYEE_DIRECTORY.value not in user_perms:
        return {
            **state,
            "errors": state.get("errors", []) + ["Insufficient permissions for HR assistant"],
            "agent_history": state.get("agent_history", []) + ["hr_assistant"],
        }
    
    evidence = state.get("evidence", {})
    context = state.get("context", {})
    
    # Build HR-focused evidence summary (NO technical details)
    hr_summary = _build_hr_evidence_summary(evidence, context)
    
    prompt = f"""You are an HR assistant AI helping with employee management and compliance.

## HR Context
{hr_summary}

## Instructions
Analyze the HR data above and provide insights. Focus on:
- Employee performance summaries (scores and outcomes only, NO technical details)
- Transfer requests and organizational changes
- Compliance and policy adherence
- HR communications and recommendations

IMPORTANT: Do NOT include technical details like code, PRs, commits, or CI/CD logs.

Return ONLY a valid JSON object with this exact structure:

{{
  "analysis": "<HR-focused analysis>",
  "recommendations": ["<HR recommendation 1>", "<HR recommendation 2>"],
  "risk_level": "<critical|high|medium|low>",
  "confidence": <number 0.0-1.0>
}}

Return ONLY the JSON object. No prose before or after."""

    try:
        llm = get_ollama_llm(temperature=0.2, response_format=AgentAnalysisResult.model_json_schema())
        response = llm.invoke(prompt)
        
        parsed = parse_response(response, AgentAnalysisResult)
        
        return {
            **state,
            "analysis": parsed.analysis,
            "recommendations": parsed.recommendations,
            "risk_level": parsed.risk_level,
            "confidence": parsed.confidence,
            "agent_history": state.get("agent_history", []) + ["hr_assistant"],
            "next_agent": None,
        }
    
    except Exception as e:
        return {
            **state,
            "errors": state.get("errors", []) + [f"HR agent error: {str(e)}"],
            "agent_history": state.get("agent_history", []) + ["hr_assistant"],
            "next_agent": None,
        }


def _build_hr_evidence_summary(evidence: Dict[str, Any], context: Dict[str, Any]) -> str:
    """
    Build HR-appropriate evidence summary.
    Filters out all technical details (code, PRs, commits, logs).
    """
    parts = []
    
    # Employee information (if present)
    if context.get('employee_name'):
        parts.append(f"Employee: {context['employee_name']}")
    
    if context.get('department'):
        parts.append(f"Department: {context['department']}")
    
    # Performance summary (scores only, NO technical details)
    if evidence.get('performance_summary'):
        perf = evidence['performance_summary']
        if isinstance(perf, dict):
            if perf.get('overall_score'):
                parts.append(f"\nPerformance Score: {perf['overall_score']}")
            if perf.get('grade'):
                parts.append(f"Grade: {perf['grade']}")
            if perf.get('strengths'):
                parts.append(f"Strengths: {', '.join(perf['strengths'][:3])}")
            if perf.get('areas_for_improvement'):
                parts.append(f"Areas for Improvement: {', '.join(perf['areas_for_improvement'][:3])}")
    
    # Transfer requests
    if evidence.get('transfer_requests'):
        transfers = evidence['transfer_requests']
        if isinstance(transfers, list):
            parts.append(f"\nPending Transfers: {len(transfers)}")
    
    # Compliance data
    if evidence.get('compliance_status'):
        parts.append(f"\nCompliance Status: {evidence['compliance_status']}")
    
    # Team information
    if evidence.get('team_info'):
        team = evidence['team_info']
        if isinstance(team, dict):
            if team.get('team_name'):
                parts.append(f"\nTeam: {team['team_name']}")
            if team.get('team_size'):
                parts.append(f"Team Size: {team['team_size']}")
    
    if not parts:
        parts.append("No HR-relevant data available")
    
    return "\n".join(parts)
