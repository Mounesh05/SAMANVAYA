"""
CI/CD Log Analysis Agent
Analyzes build, test, and deployment logs to identify issues and provide recommendations.
Uses AI to understand error patterns, flaky tests, and deployment failures.
"""

from typing import Dict, Any, List
from .state import AgentState
from .llm_provider import get_ollama_llm
from .parsers import safe_parse, response_text, CICDFailureResult, AgentResponseError, failed_response


SYSTEM_PROMPT = """You are a DevOps engineer specializing in CI/CD pipeline troubleshooting.

Your expertise:
- Analyzing build/test/deployment logs
- Identifying root causes of failures
- Detecting flaky tests and intermittent issues
- Finding performance bottlenecks
- Recommending specific fixes

You receive LOG EXCERPTS (not full logs) from the Intelligence Engine.
Focus on actionable insights and specific line numbers when possible.

Be concise and specific. Developers need quick answers, not long explanations."""


def cicd_analysis_node(state: AgentState) -> Dict[str, Any]:
    """
    CI/CD Log Analysis agent - interprets build/test/deployment logs.
    
    Args:
        state: Contains log excerpts and failure evidence from Intelligence Engine
        
    Returns:
        Updated state with log analysis, root causes, and fix recommendations
    """
    evidence = state.get("evidence", {})
    context = state.get("context", {})
    
    # Extract log information
    log_type = context.get("log_type", "build")  # build|test|deployment
    log_excerpt = evidence.get("log_excerpt", "")
    failure_summary = evidence.get("failure_summary", {})
    
    prompt = f"""{SYSTEM_PROMPT}

## CI/CD Failure Analysis

**Log Type:** {log_type}
**Pipeline:** {context.get('pipeline_name', 'N/A')}
**Commit:** {context.get('commit_hash', 'N/A')}
**Branch:** {context.get('branch', 'N/A')}

### Failure Summary from Intelligence Engine

**Exit Code:** {failure_summary.get('exit_code', 'N/A')}
**Duration:** {failure_summary.get('duration_seconds', 'N/A')} seconds
**Failed Step:** {failure_summary.get('failed_step', 'N/A')}
**Error Count:** {failure_summary.get('error_count', 0)}
**Warning Count:** {failure_summary.get('warning_count', 0)}

### Failure Patterns Detected

{_format_failure_patterns(failure_summary.get('failure_patterns', []))}

### Recent Log Excerpt (Error Context)

```
{log_excerpt}
```

### Historical Context

**Recent Failures:** {evidence.get('recent_failure_count', 0)} in last 10 runs
**Flaky Test Indicator:** {evidence.get('is_flaky', False)}
**First Seen:** {evidence.get('first_failure_date', 'Unknown')}

## Your Task

Analyze this CI/CD failure and provide:

1. **Root Cause**: What caused the failure? (1-2 sentences)
2. **Affected Component**: Which part of the system failed?
3. **Fix Recommendations**: Specific steps to resolve (3-5 bullet points)
4. **Prevention**: How to prevent this in the future
5. **Urgency**: Critical|High|Medium|Low

Return ONLY a JSON object:
{{
  "root_cause": "<one sentence root cause>",
  "affected_component": "<component name>",
  "fix_recommendations": ["<specific fix>"],
  "prevention": "<how to prevent this>",
  "urgency": "<critical|high|medium|low>",
  "confidence": <number 0.0-1.0>
}}
"""
    
    try:
        llm = get_ollama_llm(temperature=0.2)  # Lower temp for technical analysis
        response = llm.invoke(prompt)
        
        # Parse response
        analysis = _parse_cicd_response(response)
        
        return {
            **state,
            "analysis": analysis.get("root_cause"),
            "recommendations": analysis.get("fix_recommendations"),
            "affected_component": analysis.get("affected_component"),
            "prevention": analysis.get("prevention"),
            "urgency": analysis.get("urgency"),
            "confidence": analysis.get("confidence"),
            "agent_history": state.get("agent_history", []) + ["cicd_agent"],
            "next_agent": None,
        }
        
    except Exception as e:
        return failed_response(state, "cicd_agent", e)


def _format_failure_patterns(patterns: List[str]) -> str:
    """Format failure patterns for the prompt."""
    if not patterns:
        return "No specific patterns detected"
    
    formatted = []
    for i, pattern in enumerate(patterns, 1):
        formatted.append(f"  {i}. {pattern}")
    
    return "\n".join(formatted)


def _parse_cicd_response(response: str) -> Dict[str, Any]:
    """JSON v1 plus a strict adapter for the supported legacy section protocol."""
    text = response_text(response)
    if not text.startswith("ROOT_CAUSE:"):
        parsed = safe_parse(text, CICDFailureResult)
    else:
        labels = {
            "ROOT_CAUSE": "root_cause",
            "AFFECTED_COMPONENT": "affected_component",
            "FIX_RECOMMENDATIONS": "fix_recommendations",
            "PREVENTION": "prevention",
            "URGENCY": "urgency",
            "CONFIDENCE": "confidence",
        }
        result, section = {}, None
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            label, separator, value = line.partition(":")
            if separator and label in labels:
                section = labels[label]
                if section in result:
                    raise AgentResponseError("Duplicate legacy section")
                result[section] = [] if section == "fix_recommendations" else value.strip()
                if section == "fix_recommendations" and value.strip():
                    raise AgentResponseError("Unsupported inline legacy list")
            elif section == "fix_recommendations" and line.startswith("-"):
                result[section].append(line.lstrip("- ").strip())
            elif section in {"root_cause", "affected_component", "prevention"}:
                result[section] += " " + line
            else:
                raise AgentResponseError("Unsupported legacy section")
        try:
            if "confidence" in result:
                result["confidence"] = float(result["confidence"])
            if "urgency" in result:
                result["urgency"] = result["urgency"].lower()
            parsed = CICDFailureResult.model_validate(result)
        except ValueError as error:
            raise AgentResponseError("Invalid legacy CI/CD response") from error
    return parsed.model_dump(exclude={"schema_version"})


def analyze_test_flakiness(
    test_name: str,
    recent_results: List[bool],
    failure_logs: List[str],
) -> Dict[str, Any]:
    """
    Specialized analysis for flaky tests.
    
    Args:
        test_name: Name of the test
        recent_results: List of pass/fail (True/False) for last N runs
        failure_logs: Log excerpts from failures
        
    Returns:
        Analysis of flaky test patterns
    """
    pass_count = sum(recent_results)
    fail_count = len(recent_results) - pass_count
    flaky_score = (fail_count / max(len(recent_results), 1)) * 100
    
    # Detect patterns
    is_intermittent = pass_count > 0 and fail_count > 0
    consecutive_fails = _count_consecutive_failures(recent_results)
    
    prompt = f"""Analyze this flaky test:

Test: {test_name}
Pass Rate: {(pass_count/max(len(recent_results), 1))*100:.1f}%
Recent Results: {' '.join(['✅' if r else '❌' for r in recent_results[-10:]])}
Consecutive Failures: {consecutive_fails}

Recent Failure Logs:
{chr(10).join(failure_logs[:3])}

Identify the root cause of flakiness and recommend fixes."""
    
    llm = get_ollama_llm(temperature=0.2)
    response = llm.invoke(prompt)
    
    return {
        "test_name": test_name,
        "flaky_score": flaky_score,
        "is_flaky": is_intermittent,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "analysis": response,
        "severity": "high" if flaky_score > 30 else "medium",
    }


def _count_consecutive_failures(results: List[bool]) -> int:
    """Count consecutive failures at the end of results list."""
    count = 0
    for result in reversed(results):
        if not result:
            count += 1
        else:
            break
    return count
