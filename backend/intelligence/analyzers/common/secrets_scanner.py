"""
Universal Secrets & Credentials Scanner (all languages and config files).

Thin adapter: detection lives in intelligence/metrics/secrets.py (known key
formats + keyword assignments + Shannon-entropy check, placeholder
allowlist, test-file downgrade). This module keeps the original interface:
`scan_secrets(files, repo_path) -> List[Finding]` with rule ids
"SEC-SECRET-<NAME>", category "security", source tool "secrets-scanner".

Only files that resolve inside `repo_path` are read.
"""

from pathlib import Path
from typing import List

from intelligence.evidence.models import Finding, SeverityEnum
from intelligence.metrics.secrets import detect_secrets

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot",
    ".zip", ".tar", ".gz", ".jar", ".war", ".class",
    ".pdf", ".docx", ".xlsx",
    ".pyc", ".pyo",
    ".lock",   # yarn.lock, package-lock.json: too noisy
}
MAX_FILE_BYTES = 2_000_000

_SEVERITY = {
    "critical": SeverityEnum.CRITICAL,
    "high": SeverityEnum.HIGH,
    "medium": SeverityEnum.MEDIUM,
    "low": SeverityEnum.LOW,
}
_FIX = {
    259: "Remove the password from the code; load it from an environment variable or a secrets manager, and rotate it.",
    798: "Remove the credential from the code; load it from an environment variable or a secrets manager, and rotate it.",
}


def scan_secrets(files: List[str], repo_path: str) -> List[Finding]:
    """Scan the given files (relative to repo_path) for hard-coded secrets."""
    root = Path(repo_path).resolve()
    findings: List[Finding] = []
    for rel_path in files:
        try:
            abs_path = (root / rel_path).resolve()
        except (OSError, RuntimeError, ValueError):
            continue
        if root not in abs_path.parents or abs_path.suffix.lower() in SKIP_EXTENSIONS:
            continue  # outside the repository, or binary / noisy
        try:
            if not abs_path.is_file() or abs_path.stat().st_size > MAX_FILE_BYTES:
                continue
            content = abs_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        shown_path = abs_path.relative_to(root).as_posix()
        for secret in detect_secrets(content, shown_path):
            findings.append(Finding(
                file_path=shown_path,
                line_number=secret.line,
                rule_id=f"SEC-SECRET-{secret.rule.upper()}",
                category="security",
                severity=_SEVERITY.get(secret.severity, SeverityEnum.MEDIUM),
                source_tool="secrets-scanner",
                message=secret.message + (" (test file)" if secret.in_test else ""),
                code_snippet=secret.snippet,
                suggested_fix=_FIX.get(secret.cwe),
                cwe=secret.cwe,
            ))
    return findings
