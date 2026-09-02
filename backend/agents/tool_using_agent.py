"""
Tool-Using Agent Framework 

Agents that can use tools to investigate, retrieve evidence, and take actions.
Built on LangChain for structured tool calling.
"""

from typing import Dict, Any, List, Optional, Callable
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AgentTool:
    """Definition of a tool an agent can use."""
    
    def __init__(
        self,
        name: str,
        description: str,
        function: Callable,
        parameters: Dict[str, Any],
        requires_approval: bool = False
    ):
        self.name = name
        self.description = description
        self.function = function
        self.parameters = parameters
        self.requires_approval = requires_approval
    
    async def execute(self, **kwargs) -> Any:
        """Execute tool with parameters."""
        return await self.function(**kwargs)


class AgentCapability(str, Enum):
    """Agent capabilities."""
    READ_CODE = "read_code"
    ANALYZE_METRICS = "analyze_metrics"
    QUERY_DATABASE = "query_database"
    RETRIEVE_EVIDENCE = "retrieve_evidence"
    GENERATE_REPORT = "generate_report"
    CREATE_RECOMMENDATION = "create_recommendation"
    TRIGGER_WORKFLOW = "trigger_workflow"


class ToolUsingAgent:
    """
    Base class for tool-using agents.
    
    Agents can:
    - Use tools to gather information
    - Reason about evidence
    - Make recommendations
    - Request human approval for actions
    """
    
    def __init__(self, name: str, role: str, capabilities: List[AgentCapability]):
        self.name = name
        self.role = role
        self.capabilities = capabilities
        self.tools: Dict[str, AgentTool] = {}
        self.execution_history: List[Dict[str, Any]] = []
    
    def register_tool(self, tool: AgentTool):
        """Register a tool this agent can use."""
        if tool.requires_approval and AgentCapability.TRIGGER_WORKFLOW not in self.capabilities:
            logger.warning(f"Tool {tool.name} requires approval but agent lacks permission")
            return
        
        self.tools[tool.name] = tool
        logger.info(f"Agent {self.name} registered tool: {tool.name}")
    
    async def plan_and_execute(
        self,
        task: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Plan steps to accomplish task and execute using tools.
        
        Args:
            task: Task description
            context: Context information
        
        Returns:
            {
                "result": Any,
                "steps_taken": List[Dict],
                "tools_used": List[str],
                "requires_human_approval": bool,
                "reasoning": str
            }
        """
        logger.info(f"Agent {self.name} planning task: {task}")
        
        # Step 1: Plan
        plan = await self._create_plan(task, context)
        
        # Step 2: Execute plan
        result = await self._execute_plan(plan, context)
        
        # Step 3: Record execution
        self.execution_history.append({
            "task": task,
            "plan": plan,
            "result": result,
            "timestamp": "2024-01-01T00:00:00Z"  # TODO: Use actual timestamp
        })
        
        return result
    
    async def _create_plan(
        self,
        task: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Create execution plan for task.
        
        This is where LLM reasoning would happen in production.
        For now, use rule-based planning.
        """
        plan = []
        
        # Example planning logic
        if "analyze" in task.lower():
            plan.append({
                "step": 1,
                "action": "retrieve_evidence",
                "tool": "query_database",
                "params": {"entity_type": context.get("entity_type")}
            })
            plan.append({
                "step": 2,
                "action": "analyze",
                "tool": "analyze_metrics",
                "params": {}
            })
            plan.append({
                "step": 3,
                "action": "generate_report",
                "tool": "generate_report",
                "params": {}
            })
        
        return plan
    
    async def _execute_plan(
        self,
        plan: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute planned steps."""
        steps_taken = []
        tools_used = []
        requires_approval = False
        intermediate_results = {}
        
        for step in plan:
            tool_name = step.get("tool")
            tool = self.tools.get(tool_name)
            
            if not tool:
                logger.warning(f"Tool {tool_name} not available")
                continue
            
            # Check if requires approval
            if tool.requires_approval:
                requires_approval = True
                # In production: request human approval here
                continue
            
            # Execute tool
            try:
                params = step.get("params", {})
                result = await tool.execute(**params)
                intermediate_results[tool_name] = result
                tools_used.append(tool_name)
                
                steps_taken.append({
                    "step": step["step"],
                    "tool": tool_name,
                    "success": True
                })
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                steps_taken.append({
                    "step": step["step"],
                    "tool": tool_name,
                    "success": False,
                    "error": str(e)
                })
        
        return {
            "result": intermediate_results,
            "steps_taken": steps_taken,
            "tools_used": tools_used,
            "requires_human_approval": requires_approval,
            "reasoning": "Executed plan successfully"  # TODO: Add actual reasoning
        }
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names."""
        return list(self.tools.keys())


class CodeAnalysisAgent(ToolUsingAgent):
    """Agent specialized in code analysis."""
    
    def __init__(self):
        super().__init__(
            name="CodeAnalysisAgent",
            role="code_analysis",
            capabilities=[
                AgentCapability.READ_CODE,
                AgentCapability.ANALYZE_METRICS,
                AgentCapability.RETRIEVE_EVIDENCE,
                AgentCapability.GENERATE_REPORT
            ]
        )
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register code analysis specific tools."""
        
        async def analyze_complexity(file_path: str) -> Dict[str, Any]:
            """Analyze code complexity."""
            # TODO: Implement actual complexity analysis
            return {"complexity": 10, "file": file_path}
        
        async def find_security_issues(file_path: str) -> List[Dict[str, Any]]:
            """Find security vulnerabilities."""
            # TODO: Implement security scanning
            return []
        
        async def get_test_coverage(file_path: str) -> float:
            """Get test coverage for file."""
            # TODO: Implement coverage check
            return 0.85
        
        self.register_tool(AgentTool(
            name="analyze_complexity",
            description="Analyze code complexity metrics",
            function=analyze_complexity,
            parameters={"file_path": "string"},
            requires_approval=False
        ))
        
        self.register_tool(AgentTool(
            name="find_security_issues",
            description="Scan for security vulnerabilities",
            function=find_security_issues,
            parameters={"file_path": "string"},
            requires_approval=False
        ))
        
        self.register_tool(AgentTool(
            name="get_test_coverage",
            description="Get test coverage percentage",
            function=get_test_coverage,
            parameters={"file_path": "string"},
            requires_approval=False
        ))


class RiskAssessmentAgent(ToolUsingAgent):
    """Agent specialized in risk assessment."""
    
    def __init__(self):
        super().__init__(
            name="RiskAssessmentAgent",
            role="risk_assessment",
            capabilities=[
                AgentCapability.ANALYZE_METRICS,
                AgentCapability.QUERY_DATABASE,
                AgentCapability.RETRIEVE_EVIDENCE,
                AgentCapability.CREATE_RECOMMENDATION
            ]
        )
        self._register_default_tools()
    

        
        self.register_tool(AgentTool(
            name="predict_failure_probability",
            description="Predict failure probability using ML",
            function=predict_failure_probability,
            parameters={"pr_id": "string"},
            requires_approval=False
        ))
        
        self.register_tool(AgentTool(
            name="retrieve_historical_patterns",
            description="Get historical risk patterns",
            function=retrieve_historical_patterns,
            parameters={"entity_type": "string", "entity_id": "string"},
            requires_approval=False
        ))
