"""
AI Run domain models.
AI Runs represent agent executions with evidence, analysis, and recommendations.
"""

from pydantic import BaseModel, Field
from typing import Any, Optional, Dict, List
from datetime import datetime


class AIRun(BaseModel):
    """
    Complete AI run record with evidence and LLM results.
    Stores the full agent execution for audit and analysis.
    """
    
    id: Optional[str] = None
    agent_type: str = Field(..., description="code_review|qa_analysis|devops_risk|meeting_insights|cicd_analysis")
    
    # Input (from Intelligence Engine)
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Evidence + context")
    
    # Output (from AI Agent)
    output_data: Dict[str, Any] = Field(default_factory=dict, description="Analysis + recommendations")
    
    # Execution metadata
    status: str = Field(default="pending", description="pending|running|completed|failed")
    error_message: Optional[str] = None
    execution_time_ms: Optional[float] = None
    model_name: Optional[str] = Field(default="ollama", description="LLM provider/model")
    
    # Audit
    triggered_by: str = Field(..., description="User email who triggered")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = {
        "protected_namespaces": (),
        "json_schema_extra": {
            "example": {
                "agent_type": "code_review",
                "input_data": {
                    "evidence": {"complexity_score": 45, "risk_level": "medium"},
                    "context": {"pr_title": "Add auth"}
                },
                "output_data": {
                    "analysis": "Code complexity is moderate...",
                    "recommendations": ["Add unit tests", "Refactor auth logic"],
                    "risk_level": "medium",
                    "confidence": 0.85
                },
                "status": "completed",
                "execution_time_ms": 1250.5,
                "model_name": "ollama/llama3.2",
                "triggered_by": "dev@example.com"
            }
        }
    }


# Legacy aliases for backward compatibility
AIRunRequest = AIRun
AIRunResponse = AIRun
