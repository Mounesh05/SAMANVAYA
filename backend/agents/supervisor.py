"""Bounded LangGraph routing with isolated state and explicit failure outcomes."""

from copy import deepcopy
from functools import lru_cache
from typing import Any, Dict

from langgraph.graph import END, START, StateGraph

from .state import AgentState
from .code_agent import code_analysis_node
from .qa_agent import qa_analysis_node
from .devops_agent import devops_analysis_node
from .meeting_agent import meeting_insights_node
from .cicd_agent import cicd_analysis_node
from .hr_agent import hr_assistant_node

AGENT_REGISTRY = {
    'code_review': code_analysis_node,
    'qa_analysis': qa_analysis_node,
    'devops_risk': devops_analysis_node,
    'meeting_insights': meeting_insights_node,
    'cicd_analysis': cicd_analysis_node,
    'hr_assistant': hr_assistant_node,
}

_OUTPUT_FIELDS = (
    'analysis', 'recommendations', 'risk_level', 'confidence', 'quality_score',
    'quality_breakdown', 'failure_risk', 'critical_issues', 'review_focus',
    'evidence_risk_score', 'evidence_quality_score', 'risk_factors', 'quality_factors',
    'affected_component', 'prevention', 'urgency', 'next_agent',
)


def _prepare(state):
    updates = {field: None for field in _OUTPUT_FIELDS}
    errors = list(state.get('errors') or [])
    if not isinstance(state.get('evidence'), dict):
        errors.append('Agent evidence must be an object')
    if state.get('context') is not None and not isinstance(state['context'], dict):
        errors.append('Agent context must be an object')
    if state.get('task_type') not in AGENT_REGISTRY:
        errors.append(f"Unknown task type: {state.get('task_type')}")
    return {**updates, 'errors': errors, 'context': state.get('context') or {},
            'agent_history': list(state.get('agent_history') or [])}


def _route(state):
    if state.get('errors'):
        return 'finish'
    
    # Route HR users to HR assistant
    user_context = state.get('user_context', {})
    user_role = user_context.get('role', '').upper()
    
    if user_role == 'HR':
        # HR users always go to hr_assistant regardless of task_type
        return 'hr_assistant'
    
    # Other users route to their requested task_type
    return state['task_type']


def _specialist(task_type):
    def execute(state):
        try:
            result = AGENT_REGISTRY[task_type](deepcopy(state))
            if not isinstance(result, dict):
                raise ValueError('Agent must return a state update')
            return result
        except Exception as error:
            return {'errors': list(state.get('errors') or []) + [f'{task_type} failed: {type(error).__name__}']}
    return execute


def _finish(state):
    errors = list(state.get('errors') or [])
    if not errors and (not isinstance(state.get('analysis'), str) or not state['analysis'].strip()):
        errors.append('Agent produced no validated analysis')
    if errors:
        return {**{field: None for field in _OUTPUT_FIELDS}, 'errors': errors}
    return {'errors': []}


@lru_cache(maxsize=1)
def get_agent_graph():
    builder = StateGraph(AgentState)
    builder.add_node('prepare', _prepare)
    builder.add_node('finish', _finish)
    builder.add_edge(START, 'prepare')
    builder.add_conditional_edges('prepare', _route, {name: name for name in (*AGENT_REGISTRY, 'finish')})
    for task_type in AGENT_REGISTRY:
        builder.add_node(task_type, _specialist(task_type))
        builder.add_edge(task_type, 'finish')
    builder.add_edge('finish', END)
    # Single-request graphs do not share conversation memory or checkpoints.
    # Durable evaluation jobs and the run audit remain in MongoDB.
    return builder.compile()


def invoke_agent(task_type: str, state: Dict[str, Any]) -> Dict[str, Any]:
    initial = deepcopy(state)
    initial['task_type'] = task_type
    result = get_agent_graph().invoke(initial, config={'recursion_limit': 6})
    return {**initial, **result}


async def ainvoke_agent(task_type: str, state: Dict[str, Any]) -> Dict[str, Any]:
    initial = deepcopy(state)
    initial['task_type'] = task_type
    # LangGraph runs synchronous specialist nodes in its executor; API handlers
    # await the graph and keep their event loop available for other requests.
    result = await get_agent_graph().ainvoke(initial, config={'recursion_limit': 6})
    return {**initial, **result}
