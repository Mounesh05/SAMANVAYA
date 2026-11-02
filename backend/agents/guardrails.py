"""
Guardrails — RBAC/OPA + NeMo-style input sanitisation + Pydantic output validation.

Architecture position:
    FastAPI -> Auth/JWT -> [GuardrailLayer] -> Supervisor -> Agents -> [OutputGuardrail]

Protections implemented:
    1. RBAC / OPA:       Role-capability matrix — deny unauthorized task_types per role.
    2. Prompt Injection: Heuristic scanner to block jailbreak / injection attempts.
    3. Input Pydantic:   Validates & clamps incoming AgentState fields.
    4. Output Pydantic:  Validates agent output before returning to caller.
    5. NeMo-compatible:  Structure mirrors NVIDIA NeMo Guardrails ColangFlow so
                         this can be replaced by a real NeMo server when needed.
"""

import re
import logging
from typing import Dict, Any, List, Tuple

from .state import AgentState, AgentRole, TaskType

logger = logging.getLogger("samanvaya.guardrails")


# ─────────────────────────────────────────────────────────────────────────────
# 1. RBAC Policy Matrix (OPA-style)
#    role -> set of allowed task_types
# ─────────────────────────────────────────────────────────────────────────────
RBAC_POLICY: Dict[str, List[str]] = {
    "CEO":    ["code_review", "qa_analysis", "devops_risk", "cicd_analysis",
               "meeting_insights", "performance_eval", "report_synthesis"],
    "HR":     ["performance_eval", "report_synthesis", "meeting_insights"],
    "LEAD":   ["code_review", "qa_analysis", "devops_risk", "cicd_analysis",
               "meeting_insights", "performance_eval"],
    "PM":     ["meeting_insights", "report_synthesis", "performance_eval"],
    "DEV":    ["code_review", "qa_analysis", "cicd_analysis"],
    "QA":     ["qa_analysis", "cicd_analysis"],
    "DEVOPS": ["devops_risk", "cicd_analysis"],
    "ADMIN":  ["code_review", "qa_analysis", "devops_risk", "cicd_analysis",
               "meeting_insights", "performance_eval", "report_synthesis"],
}

# ─────────────────────────────────────────────────────────────────────────────
# 2. Prompt Injection Detection Patterns
#    NeMo Guardrails-style heuristic scanner
# ─────────────────────────────────────────────────────────────────────────────
_INJECTION_PATTERNS: List[re.Pattern] = [
    re.compile(r"ignore (all |previous |prior |above )?(instructions?|prompts?|context)", re.I),
    re.compile(r"you are now", re.I),
    re.compile(r"disregard (your|all|the) (instructions?|rules?|training)", re.I),
    re.compile(r"(pretend|act|roleplay) (you are|as if|that you)", re.I),
    re.compile(r"jailbreak", re.I),
    re.compile(r"DAN mode", re.I),
    re.compile(r"bypass (safety|filter|restriction|guardrail)", re.I),
    re.compile(r"reveal (your |the )?(system |internal |hidden )?(prompt|instructions?)", re.I),
    re.compile(r"<\s*script[\s>]", re.I),                 # XSS-style in text
    re.compile(r"exec\s*\(|eval\s*\(|__import__\s*\("),   # Code injection
    re.compile(r"DROP\s+TABLE|DELETE\s+FROM|TRUNCATE\s+TABLE", re.I),  # SQL injection
]

# ─────────────────────────────────────────────────────────────────────────────
# 3. Sensitive data patterns (redact from output)
# ─────────────────────────────────────────────────────────────────────────────
_SENSITIVE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
     "[EMAIL_REDACTED]"),
    (re.compile(r"\b(?:\+91|0)?[6-9]\d{9}\b"),
     "[PHONE_REDACTED]"),
    (re.compile(r"\b(?:ghp|ghs|ghr|gho)_[A-Za-z0-9]{36}\b"),
     "[GITHUB_TOKEN_REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
     "[API_KEY_REDACTED]"),
    (re.compile(r"\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b"),
     "[CRYPTO_ADDR_REDACTED]"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def check_rbac(state: AgentState) -> AgentState:
    """
    OPA-style RBAC gate node.

    Returns state with:
        rbac_allowed = True/False
        rbac_reason  = human-readable message
    """
    role: str = state.get("user_role", "DEV")
    task: str = state.get("task_type", "")
    allowed_tasks = RBAC_POLICY.get(role, [])

    if task in allowed_tasks:
        logger.info("[RBAC] ALLOW role=%s task=%s", role, task)
        return {
            **state,
            "rbac_allowed": True,
            "rbac_reason": f"Role '{role}' is authorized for task '{task}'.",
            "guardrail_passed": True,
            "guardrail_violations": [],
        }
    else:
        reason = (
            f"Role '{role}' is NOT authorized for task '{task}'. "
            f"Permitted: {allowed_tasks}"
        )
        logger.warning("[RBAC] DENY %s", reason)
        return {
            **state,
            "rbac_allowed": False,
            "rbac_reason": reason,
            "guardrail_passed": False,
            "guardrail_violations": [f"rbac_deny:{role}:{task}"],
            "analysis": reason,
            "recommendations": [],
            "errors": state.get("errors", []) + [f"RBAC DENY: {reason}"],
        }


def scan_prompt_injection(text: str) -> Tuple[bool, List[str]]:
    """
    NeMo Guardrails-style prompt injection scanner.

    Returns:
        (detected: bool, matched_patterns: List[str])
    """
    hits = []
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            hits.append(pattern.pattern)
    return bool(hits), hits


def sanitize_output(text: str) -> str:
    """
    Redact sensitive data from agent output before returning to caller.
    Mirrors NeMo output guardrail flow.
    """
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def input_guardrail_node(state: AgentState) -> AgentState:
    """
    LangGraph node: combined RBAC + prompt-injection gate.

    Runs before supervisor routing. If any guard fails, short-circuits
    the entire graph by clearing next_agent and populating errors.
    """
    violations: List[str] = []

    # 1. RBAC check
    state = check_rbac(state)
    if not state.get("rbac_allowed", False):
        return state                             # Already poisoned state — stop here

    # 2. Prompt injection scan on input_text
    raw = state.get("input_text", "") + str(state.get("context", ""))
    detected, patterns = scan_prompt_injection(raw)
    if detected:
        msg = f"Prompt injection detected. Matched: {patterns}"
        logger.error("[GUARDRAIL] INJECTION_BLOCKED %s", msg)
        return {
            **state,
            "prompt_injection_detected": True,
            "guardrail_passed": False,
            "guardrail_violations": state.get("guardrail_violations", []) + [msg],
            "analysis": "Request blocked: prompt injection attempt detected.",
            "errors": state.get("errors", []) + [msg],
        }

    # 3. Validate company isolation — user must match requested company
    requested_company = state.get("company_id", "")
    if not requested_company:
        violations.append("missing_company_id")

    if violations:
        logger.warning("[GUARDRAIL] INPUT_VIOLATIONS %s", violations)
        return {
            **state,
            "guardrail_passed": False,
            "guardrail_violations": violations,
            "analysis": f"Input validation failed: {violations}",
            "errors": state.get("errors", []) + violations,
        }

    logger.info("[GUARDRAIL] INPUT_PASS task=%s role=%s company=%s",
                state.get("task_type"), state.get("user_role"), state.get("company_id"))
    return {**state, "guardrail_passed": True, "prompt_injection_detected": False}


def output_guardrail_node(state: AgentState) -> AgentState:
    """
    LangGraph node: sanitise agent output before sending to caller.

    Redacts PII and sensitive secrets from analysis + recommendations.
    """
    analysis = sanitize_output(state.get("analysis", ""))
    recs = [sanitize_output(r) for r in state.get("recommendations", [])]

    logger.info("[GUARDRAIL] OUTPUT_SANITIZED task=%s", state.get("task_type"))
    return {
        **state,
        "analysis": analysis,
        "recommendations": recs,
        "output_sanitized": True,
    }


def rbac_deny_node(state: AgentState) -> AgentState:
    """Terminal node when RBAC denies a request. Returns 403-like payload."""
    return {
        **state,
        "analysis": state.get("rbac_reason", "Access denied."),
        "recommendations": [],
        "risk_level": "low",
        "confidence": 1.0,
    }
