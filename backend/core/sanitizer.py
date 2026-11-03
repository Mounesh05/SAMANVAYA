"""
Secret Redaction & Log Sanitization Module.
Filters credentials, private keys, passwords, and sensitive tokens from logs and payloads
before persistence and before passing to LLM prompts.
"""

import re
from typing import Any, Dict, List, Union

# Common patterns for sensitive data
SENSITIVE_PATTERNS = [
    # Private Keys (RSA, EC, OpenSSH, PGP)
    (re.compile(r"-----BEGIN [A-Z\s]+PRIVATE KEY-----[^-]+-----END [A-Z\s]+PRIVATE KEY-----", re.MULTILINE | re.DOTALL), "[REDACTED_PRIVATE_KEY]"),
    
    # GitHub Tokens
    (re.compile(r"\b(ghp|gho|ghu|ghs|ghr|github_pat)_[a-zA-Z0-9_]{36,255}\b"), "[REDACTED_GITHUB_TOKEN]"),
    
    # JWT Tokens
    (re.compile(r"\beyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b"), "[REDACTED_JWT]"),
    
    # AWS Access Keys & Secrets
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_AWS_KEY]"),
    (re.compile(r"(?i)(?:aws_secret_access_key|aws_secret_key)\s*[:=]\s*['\"]?([a-zA-Z0-9/+=]{40})['\"]?"), r"\1=[REDACTED_AWS_SECRET]"),
    
    # Database URIs with credentials
    (re.compile(r"(?i)(mongodb(?:\+srv)?|postgres(?:ql)?|mysql|redis)://([^:]+):([^@]+)@"), r"\1://[REDACTED_USER]:[REDACTED_PASSWORD]@"),
    
    # Generic password / secret / token assignments in CLI or env logs
    (re.compile(r"(?i)\b(password|passwd|secret|token|api_key|apikey|auth_token|client_secret)\s*[:=]\s*['\"]?([^'\"\s,;]+)['\"]?"), r"\1=[REDACTED_SECRET]"),
    
    # Authorization Headers
    (re.compile(r"(?i)\bBearer\s+[a-zA-Z0-9_\-\.]{20,}\b"), "Bearer [REDACTED_BEARER_TOKEN]"),
    (re.compile(r"(?i)\bBasic\s+[a-zA-Z0-9+/=]{15,}\b"), "Basic [REDACTED_BASIC_AUTH]"),
]


def sanitize_text(text: str) -> str:
    """Redact sensitive credentials and tokens from text strings."""
    if not isinstance(text, str):
        return text
    sanitized = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def sanitize_data(data: Union[Dict, List, Any]) -> Any:
    """Recursively redact sensitive data from nested dicts, lists, and strings."""
    if isinstance(data, str):
        return sanitize_text(data)
    elif isinstance(data, dict):
        sanitized_dict = {}
        for k, v in data.items():
            # Check if key itself indicates a sensitive credential
            if any(s in str(k).lower() for s in ["password", "secret", "token", "private_key", "api_key", "pat"]):
                sanitized_dict[k] = "[REDACTED_CONFIDENTIAL]"
            else:
                sanitized_dict[k] = sanitize_data(v)
        return sanitized_dict
    elif isinstance(data, (list, tuple, set)):
        return [sanitize_data(item) for item in data]
    return data

