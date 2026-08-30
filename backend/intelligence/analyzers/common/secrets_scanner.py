"""
Universal Secrets & Credentials Scanner.
Language-agnostic regex patterns for hardcoded API keys, tokens, and passwords.

Extracted from the old security_scanner.py into a shared module so all
language analyzers can use the same detection without code duplication.

Runs on every file type regardless of language.
"""

import re
from pathlib import Path
from typing import Any, Dict, List

from intelligence.evidence.models import Finding, SeverityEnum


# ── Secret Pattern Registry ───────────────────────────────────────────────────
# Each entry: (pattern_name, regex, severity, description)

SECRET_PATTERNS: List[tuple] = [
    # Cloud providers
    ("aws_access_key",
     r"AKIA[0-9A-Z]{16}",
     SeverityEnum.CRITICAL,
     "AWS Access Key ID detected"),

    ("aws_secret_key",
     r"(?i)aws[_\-\s]?secret[_\-\s]?(?:access[_\-\s]?)?key[\s\"'=:]+[A-Za-z0-9/+=]{40}",
     SeverityEnum.CRITICAL,
     "AWS Secret Access Key detected"),

    # Version control tokens
    ("github_token",
     r"gh[pousr]_[A-Za-z0-9_]{36,255}",
     SeverityEnum.CRITICAL,
     "GitHub Personal Access Token detected"),

    ("gitlab_token",
     r"glpat-[A-Za-z0-9\-_]{20}",
     SeverityEnum.CRITICAL,
     "GitLab Personal Access Token detected"),

    # Payment processors
    ("stripe_secret",
     r"sk_live_[a-zA-Z0-9]{24,}",
     SeverityEnum.CRITICAL,
     "Stripe live secret key detected"),

    ("stripe_restricted",
     r"rk_live_[a-zA-Z0-9]{24,}",
     SeverityEnum.HIGH,
     "Stripe restricted key detected"),

    # Communications
    ("slack_token",
     r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,32}",
     SeverityEnum.HIGH,
     "Slack Bot/App token detected"),

    # Cryptographic
    ("private_key",
     r"-----BEGIN\s(?:RSA|EC|DSA|OPENSSH)\sPRIVATE\sKEY-----",
     SeverityEnum.CRITICAL,
     "Private key block detected"),

    ("jwt_token",
     r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}",
     SeverityEnum.MEDIUM,
     "JWT token hardcoded in source"),

    # Generic patterns
    ("password_assignment",
     r"""(?i)(?:password|passwd|pwd)\s*[:=]\s*['"][^'"]{8,}['"]""",
     SeverityEnum.HIGH,
     "Hardcoded password detected"),

    ("api_key_generic",
     r"""(?i)api[_\-]?key\s*[:=]\s*['"][a-zA-Z0-9_\-]{20,}['"]""",
     SeverityEnum.HIGH,
     "Generic API key detected"),

    ("secret_key_generic",
     r"""(?i)secret[_\-]?key\s*[:=]\s*['"][^'"]{12,}['"]""",
     SeverityEnum.HIGH,
     "Generic secret key detected"),

    # Database connection strings with credentials
    ("db_conn_string",
     r"(?i)(?:mysql|postgresql|mongodb|redis):\/\/[^:]+:[^@]{4,}@",
     SeverityEnum.CRITICAL,
     "Database connection string with credentials detected"),

    # SendGrid / Twilio
    ("sendgrid_key",
     r"SG\.[a-zA-Z0-9_\-]{22}\.[a-zA-Z0-9_\-]{43}",
     SeverityEnum.HIGH,
     "SendGrid API key detected"),
]

# ── Files to skip during secrets scanning ─────────────────────────────────────
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".tar", ".gz", ".jar", ".war", ".class",
    ".pdf", ".docx", ".xlsx",
    ".pyc", ".pyo",
    ".lock",   # yarn.lock, package-lock.json — too noisy
}


def scan_secrets(
    files: List[str],
    repo_path: str,
) -> List[Finding]:
    """
    Scan all provided files for hardcoded secrets and credentials.

    Args:
        files: File paths relative to repo_path
        repo_path: Absolute repo root

    Returns:
        List of Finding objects for each detected secret
    """
    findings: List[Finding] = []

    for rel_path in files:
        abs_path = Path(repo_path) / rel_path

        # Skip binary / noise files
        if abs_path.suffix.lower() in SKIP_EXTENSIONS:
            continue

        try:
            content = abs_path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        for line_num, line in enumerate(lines, start=1):
            for pattern_name, pattern, severity, description in SECRET_PATTERNS:
                if re.search(pattern, line):
                    # Redact the actual secret value before storing
                    redacted = re.sub(
                        pattern,
                        f"[REDACTED:{pattern_name.upper()}]",
                        line,
                    ).strip()

                    findings.append(Finding(
                        file_path=rel_path,
                        line_number=line_num,
                        rule_id=f"SEC-SECRET-{pattern_name.upper()}",
                        category="security",
                        severity=severity,
                        source_tool="secrets-scanner",
                        message=description,
                        code_snippet=redacted[:200],
                    ))

    return findings
