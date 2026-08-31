"""
Agent Supervisor - Routes tasks to specialized agents
Simple router without LangGraph dependency.
"""

from typing import Dict, Any
from .code_agent import code_analysis_node
from .qa_agent import qa_analysis_node
from .devops_agent import devops_analysis_node
from .meeting_agent import meeting_insights_node
from .cicd_agent import cicd_analysis_node


AGENT_REGISTRY = {
    "code_review": code_analysis_node,
    "qa_analysis": qa_analysis_node,
    "devops_risk": devops_analysis_node,
    "meeting_insights": meeting_insights_node,
    "cicd_analysis": cicd_analysis_node,
}


def invoke_agent(task_type: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Route task to the appropriate agent and return result.

    Args:
        task_type: One of code_review, qa_analysis, devops_risk, meeting_insights, cicd_analysis
        state: Agent state with evidence, context, etc.

    Returns:
        Updated state with analysis results
    """
    agent_node = AGENT_REGISTRY.get(task_type)
    if not agent_node:
        return {
            **state,
            "errors": state.get("errors", []) + [f"Unknown task type: {task_type}"],
            "agent_history": state.get("agent_history", []),
        }

    return agent_node(state)
