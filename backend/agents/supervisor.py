"""
Supervisor Agent - LangGraph orchestrator
Routes tasks to specialized agents based on task_type
"""

from typing import Literal
from langgraph.graph import StateGraph, END
from .state import AgentState
from .code_agent import code_analysis_node
from .qa_agent import qa_analysis_node
from .devops_agent import devops_analysis_node
from .meeting_agent import meeting_insights_node
from .cicd_agent import cicd_analysis_node


def supervisor_router(state: AgentState) -> Literal["code_agent", "qa_agent", "devops_agent", "meeting_agent", "cicd_agent", "end"]:
    """
    Route to the appropriate agent based on task_type.
    
    Args:
        state: Current agent state with task_type
        
    Returns:
        Next node to execute
    """
    task_type = state.get("task_type")
    
    route_map = {
        "code_review": "code_agent",
        "qa_analysis": "qa_agent",
        "devops_risk": "devops_agent",
        "meeting_insights": "meeting_agent",
        "cicd_analysis": "cicd_agent",
    }
    
    return route_map.get(task_type, "end")


def create_supervisor_graph() -> StateGraph:
    """
    Create LangGraph supervisor for agent orchestration.
    
    The supervisor routes tasks to specialized agents:
    - code_agent: PR code review and quality analysis
    - qa_agent: Test coverage and QA recommendations
    - devops_agent: Deployment risk and infrastructure
    - meeting_agent: Sprint insights and team performance
    
    Returns:
        Compiled StateGraph ready for execution
        
    Example:
        graph = create_supervisor_graph()
        result = graph.invoke({
            "task_type": "code_review",
            "evidence": {...},  # from Intelligence Engine
            "context": {"pr_title": "Add feature X"},
            "agent_history": [],
            "errors": [],
        })
    """
    # Create graph
    workflow = StateGraph(AgentState)
    
    # Add agent nodes
    workflow.add_node("code_agent", code_analysis_node)
    workflow.add_node("qa_agent", qa_analysis_node)
    workflow.add_node("devops_agent", devops_analysis_node)
    workflow.add_node("meeting_agent", meeting_insights_node)
    workflow.add_node("cicd_agent", cicd_analysis_node)
    
    # Set entry point with conditional routing
    workflow.set_conditional_entry_point(
        supervisor_router,
        {
            "code_agent": "code_agent",
            "qa_agent": "qa_agent",
            "devops_agent": "devops_agent",
            "meeting_agent": "meeting_agent",
            "cicd_agent": "cicd_agent",
            "end": END,
        }
    )
    
    # All agents terminate after execution (no chaining)
    workflow.add_edge("code_agent", END)
    workflow.add_edge("qa_agent", END)
    workflow.add_edge("devops_agent", END)
    workflow.add_edge("meeting_agent", END)
    workflow.add_edge("cicd_agent", END)
    
    return workflow.compile()
