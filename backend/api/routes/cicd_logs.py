"""
CI/CD Log Analysis API Routes
Endpoints for analyzing build, test, and deployment logs with AI
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from pydantic import BaseModel, Field

from intelligence.log_analyzer import LogAnalyzer
from agents.supervisor import invoke_agent
from agents.llm_provider import check_ollama_connection
from core.dependencies import get_current_user, require_roles
from repositories.ai_run_repository import AIRunRepository
from core.database import db

router = APIRouter(tags=["CI/CD Logs"])


class LogAnalysisRequest(BaseModel):
    """Request to analyze CI/CD logs."""
    log_content: str = Field(..., description="Full log content or excerpt")
    log_type: str = Field(..., description="build|test|deployment")
    
    # Build-specific fields
    exit_code: int | None = Field(default=None, description="Process exit code")
    build_step: str | None = Field(default=None, description="Failed build step")
    
    # Test-specific fields
    tests_run: int | None = Field(default=None)
    tests_passed: int | None = Field(default=None)
    tests_failed: int | None = Field(default=None)
    
    # Deployment-specific fields
    deployment_status: str | None = Field(default=None, description="success|failed|rolled_back")
    environment: str | None = Field(default=None, description="staging|production")
    
    # Common fields
    duration_seconds: float | None = Field(default=None)
    pipeline_name: str | None = Field(default=None)
    commit_hash: str | None = Field(default=None)
    branch: str | None = Field(default=None)
    
    # AI analysis options
    use_ai: bool = Field(default=True, description="Use AI agent for interpretation")


class LogAnalysisResponse(BaseModel):
    """CI/CD log analysis result."""
    # Layer 5 (Intelligence Engine) output
    log_type: str
    risk_score: int
    risk_level: str
    error_count: int | None = None
    warning_count: int | None = None
    failure_patterns: list[str] | None = None
    failure_type: str | None = None
    
    # Layer 6 (AI Agent) output
    ai_analysis: str | None = None
    root_cause: str | None = None
    affected_component: str | None = None
    fix_recommendations: list[str] | None = None
    prevention: str | None = None
    urgency: str | None = None
    confidence: float | None = None
    
    # Metadata
    execution_time_ms: float
    ai_run_id: str | None = None


@router.post("/analyze", response_model=LogAnalysisResponse)
async def analyze_cicd_log(
    request: LogAnalysisRequest,
    current_user: dict = Depends(require_roles("DEVELOPER", "LEAD", "QA", "DEVOPS")),
):
    """
    Analyze CI/CD logs with Intelligence Engine + optional AI interpretation.
    
    Workflow:
    1. Layer 5 (Intelligence Engine) parses log and extracts facts
    2. Layer 6 (AI Agent) interprets evidence and provides recommendations
    
    Example:
        POST /api/cicd-logs/analyze
        {
            "log_content": "ERROR: npm ERR! code ELIFECYCLE...",
            "log_type": "build",
            "exit_code": 1,
            "build_step": "npm install",
            "duration_seconds": 45.2,
            "use_ai": true
        }
    """
    import time
    start_time = time.time()
    
    # Layer 5: Intelligence Engine analyzes log
    log_analyzer = LogAnalyzer()
    
    if request.log_type == "build":
        evidence = log_analyzer.analyze_build_log(
            log_content=request.log_content,
            exit_code=request.exit_code or 0,
            duration_seconds=request.duration_seconds or 0,
            build_step=request.build_step or "unknown",
        )
    elif request.log_type == "test":
        evidence = log_analyzer.analyze_test_log(
            log_content=request.log_content,
            tests_run=request.tests_run or 0,
            tests_passed=request.tests_passed or 0,
            tests_failed=request.tests_failed or 0,
            duration_seconds=request.duration_seconds or 0,
        )
    elif request.log_type == "deployment":
        evidence = log_analyzer.analyze_deployment_log(
            log_content=request.log_content,
            deployment_status=request.deployment_status or "unknown",
            environment=request.environment or "unknown",
            duration_seconds=request.duration_seconds or 0,
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid log_type. Must be: build|test|deployment")
    
    # Prepare response with Layer 5 results
    response_data = {
        "log_type": evidence["log_type"],
        "risk_score": evidence["risk_score"],
        "risk_level": evidence["risk_level"],
        "error_count": evidence.get("error_count"),
        "warning_count": evidence.get("warning_count"),
        "failure_patterns": evidence.get("failure_patterns"),
        "failure_type": evidence.get("failure_type"),
        "execution_time_ms": 0,  # Will update later
    }
    
    # Layer 6: AI Agent interprets evidence (if requested)
    if request.use_ai:
        if not check_ollama_connection():
            raise HTTPException(
                status_code=503,
                detail="Ollama service not available. AI analysis requires Ollama running."
            )
        
        try:
            ai_state = {
                "task_type": "cicd_analysis",
                "evidence": evidence,
                "context": {
                    "log_type": request.log_type,
                    "pipeline_name": request.pipeline_name,
                    "commit_hash": request.commit_hash,
                    "branch": request.branch,
                },
                "agent_history": [],
                "errors": [],
            }
            
            ai_result = invoke_agent("cicd_analysis", ai_state)
            
            response_data.update({
                "ai_analysis": ai_result.get("analysis"),
                "root_cause": ai_result.get("analysis"),  # Same for now
                "affected_component": ai_result.get("affected_component"),
                "fix_recommendations": ai_result.get("recommendations"),
                "prevention": ai_result.get("prevention"),
                "urgency": ai_result.get("urgency"),
                "confidence": ai_result.get("confidence"),
            })
            
            # Save AI run
            ai_run_repo = AIRunRepository()
            from domain.models.ai_run import AIRun
            ai_run = AIRun(
                agent_type="cicd_analysis",
                input_data={"evidence": evidence, "context": ai_state["context"]},
                output_data={
                    "analysis": ai_result.get("analysis"),
                    "recommendations": ai_result.get("recommendations"),
                    "urgency": ai_result.get("urgency"),
                },
                status="completed",
                execution_time_ms=(time.time() - start_time) * 1000,
                model_name="ollama",
                triggered_by=current_user["email"],
            )
            run_id = await ai_run_repo.create(ai_run)
            response_data["ai_run_id"] = run_id
            
        except Exception as e:
            # AI failed, but Layer 5 results are still valid
            response_data["ai_analysis"] = f"AI analysis failed: {str(e)}"
    
    response_data["execution_time_ms"] = (time.time() - start_time) * 1000
    
    return LogAnalysisResponse(**response_data)


@router.post("/analyze-file")
async def analyze_log_file(
    file: UploadFile = File(...),
    log_type: str = "build",
    use_ai: bool = True,
    current_user: dict = Depends(get_current_user),
):
    """
    Upload and analyze a CI/CD log file.
    
    Supports: .log, .txt files
    Max size: 5MB
    """
    # Read file content
    content = await file.read()
    
    # Check size (5MB limit)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Log file too large (max 5MB)")
    
    try:
        log_content = content.decode('utf-8')
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 text")
    
    # Analyze using existing endpoint logic
    request = LogAnalysisRequest(
        log_content=log_content,
        log_type=log_type,
        use_ai=use_ai,
    )
    
    return await analyze_cicd_log(request, current_user)


@router.get("/patterns")
async def get_failure_patterns(
    current_user: dict = Depends(get_current_user),
):
    """
    Get list of common failure patterns detected by the system.
    
    Returns:
        Dictionary of pattern types and their descriptions
    """
    return {
        "patterns": {
            "test_failures": "Tests failed during execution",
            "timeout": "Process exceeded time limit",
            "out_of_memory": "Memory allocation failed",
            "network_error": "Network connection issues",
            "dependency_error": "Package installation failed",
            "compilation_error": "Code compilation failed",
        },
        "flaky_indicators": {
            "timing": "Timing-related failures (async, promises)",
            "race_condition": "Concurrent execution issues",
            "network": "Network-related failures",
            "random": "Random or non-deterministic behavior",
        }
    }


@router.get("/health")
async def cicd_analysis_health():
    """Health check for CI/CD log analysis system."""
    ollama_ok = check_ollama_connection()
    
    return {
        "status": "healthy" if ollama_ok else "degraded",
        "ollama_connected": ollama_ok,
        "layer_5_available": True,  # Log parser always available
        "layer_6_available": ollama_ok,  # AI requires Ollama
        "message": "Both layers operational" if ollama_ok else "Layer 5 only (AI disabled)",
    }
