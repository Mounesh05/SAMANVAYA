"""
Hard-coded secret detection for any text file (all languages, config files).

Three detectors, from most to least specific:

1. Known formats       regexes for keys with a recognisable shape
                        (AWS, GitHub, GitLab, Stripe, Slack, SendGrid, JWT,
                        private-key blocks, database URLs with a password)
2. Keyword assignment  a literal value assigned to a clearly secret name
                        (password, passwd, pwd, secret, token, api_key,
                        access_key, private_key, client_secret ...); flagged
                        unless the value is a placeholder, a reference or a
                        sentence. Same idea as detect-secrets' KeywordDetector.
3. High entropy        for weaker name hints (key, auth, credential, cookie,
                        session, salt, signature, bearer, dsn ...) only random-
                        looking values: Shannon entropy >= 4.5 bits/char for
                        base64-style strings, >= 3.0 for hex (detect-secrets'
                        defaults), at least 16 characters.

Placeholders are never flagged: CHANGE_ME, your-key-here, <token>, ${VAR},
{{ var }}, xxx, ****, example/sample/dummy values, all-caps constant names,
password hashes ($2b$..., $argon2...), paths and URLs without credentials.

Findings in test files (tests/, test_*.py, *_test.py, *.spec.*, fixtures) are
downgraded to low severity and marked `in_test`, not dropped.

The secret value itself is never stored: snippets show the first 3 characters.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Dict, List, Optional, Sequence, Tuple

# (name, regex, severity, description) - names kept from the original scanner
KNOWN_PATTERNS: List[Tuple[str, str, str, str]] = [
    ("aws_access_key", r"AKIA[0-9A-Z]{16}", "critical", "AWS Access Key ID detected"),
    ("aws_secret_key", r"(?i)aws[_\-\s]?secret[_\-\s]?(?:access[_\-\s]?)?key[\s\"'=:]+[A-Za-z0-9/+=]{40}",
     "critical", "AWS Secret Access Key detected"),
    ("github_token", r"gh[pousr]_[A-Za-z0-9_]{36,255}", "critical", "GitHub token detected"),
    ("gitlab_token", r"glpat-[A-Za-z0-9\-_]{20}", "critical", "GitLab Personal Access Token detected"),
    ("stripe_secret", r"sk_live_[a-zA-Z0-9]{24,}", "critical", "Stripe live secret key detected"),
    ("stripe_restricted", r"rk_live_[a-zA-Z0-9]{24,}", "high", "Stripe restricted key detected"),
    ("slack_token", r"xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,32}", "high", "Slack token detected"),
    ("private_key", r"-----BEGIN\s(?:RSA|EC|DSA|OPENSSH|PGP)?\s?PRIVATE\sKEY(?:\sBLOCK)?-----", "critical",
     "Private key block detected"),
    ("jwt_token", r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}", "medium",
     "JWT token hard-coded in source"),
    ("db_conn_string", r"(?i)(?:mysql|postgres(?:ql)?|mongodb(?:\+srv)?|redis|amqp)://[^:/\s]+:[^@\s]{4,}@",
     "critical", "Database connection string with credentials detected"),
    ("sendgrid_key", r"SG\.[a-zA-Z0-9_\-]{22}\.[a-zA-Z0-9_\-]{43}", "high", "SendGrid API key detected"),
]
_KNOWN = [(name, re.compile(rx), sev, desc) for name, rx, sev, desc in KNOWN_PATTERNS]

# name classes for the keyword detector -> (rule name, CWE, minimum length, description)
_STRONG_KEYWORDS: List[Tuple[re.Pattern, str, int, int, str]] = [
    (re.compile(r"(?i)(passw(or)?d|passwd|pwd|passphrase)"), "password_assignment", 259, 6, "Hard-coded password"),
    (re.compile(r"(?i)(client[_-]?secret|secret[_-]?key|secret|private[_-]?key|signing[_-]?key)"),
     "secret_key_generic", 798, 8, "Hard-coded secret"),
    (re.compile(r"(?i)(api[_-]?key|apikey|access[_-]?key|access[_-]?token|auth[_-]?token|refresh[_-]?token|token)"),
     "api_key_generic", 798, 8, "Hard-coded API key or token"),
]
_WEAK_HINT = re.compile(r"(?i)(key|auth|credential|cookie|session|salt|signature|\bsig\b|bearer|cert|dsn|license)")

# name = "value" | name: "value" | "name": "value" | name="value" | name => "value"
_QUOTED_ASSIGNMENT = re.compile(
    r"""(?P<name>[A-Za-z_][A-Za-z0-9_.\-]*)["']?\s*(?::=|=>|=|:)\s*[bru]{0,2}(?P<q>["'])(?P<value>[^"'\n]{4,})(?P=q)"""
)
# Unquoted values only count in config files; in code the right-hand side of
# `name = value` is a variable or call, not a literal.
# .env / shell / Dockerfile style: NAME=value
_ENV_ASSIGNMENT = re.compile(
    r"""^\s*(?:export\s+|ENV\s+|ARG\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>[^\s#'"]{4,})\s*(?:#.*)?$"""
)
# YAML style: name: value
_YAML_ASSIGNMENT = re.compile(
    # first character must not start a YAML tag/anchor/alias/block (! & * | >) or flow collection
    r"""^\s*-?\s*(?P<name>[A-Za-z_][A-Za-z0-9_.\-]*)\s*:\s*(?P<value>[^\s#'"{}\[\]&*!|>][^\s#'"]{3,})\s*(?:#.*)?$"""
)
_ENV_SUFFIXES = {".env", ".ini", ".cfg", ".conf", ".properties"}
_YAML_SUFFIXES = {".yml", ".yaml"}


def _config_kind(path: str) -> Optional[str]:
    """"env", "yaml" or None (source code: quoted literals only)."""
    p = PurePosixPath(path.replace("\\", "/"))
    name = p.name.lower()
    if name.startswith(".env") or name.endswith(".env") or p.suffix.lower() in _ENV_SUFFIXES or name == "dockerfile":
        return "env"
    if p.suffix.lower() in _YAML_SUFFIXES:
        return "yaml"
    return None

_PLACEHOLDER_PARTS = (
    "change_me", "changeme", "change-me", "change me", "your_", "your-", "yourkey", "<", ">", "${", "{{", "%(",
    "xxx", "***", "...", "example", "sample", "dummy", "placeholder", "replace", "todo", "fixme", "insert",
    "redacted", "not_set", "notset", "not-set", "fake", "mock", "secret_here", "key_here", "token_here",
)
_PLACEHOLDER_WORDS = {"none", "null", "nil", "undefined", "true", "false", "password", "secret", "token",
                      "string", "test", "testing", "default", "empty", "required", "optional", "unknown"}
_HASH_PREFIXES = ("$2a$", "$2b$", "$2y$", "$argon2", "$pbkdf2", "pbkdf2_", "$scrypt", "sha256$")
_HEX = set("0123456789abcdefABCDEF")
_TEST_PARTS = {"tests", "test", "__tests__", "testing", "fixtures", "spec", "mocks"}


def shannon_entropy(value: str) -> float:
    """Bits of information per character."""
    if not value:
        return 0.0
    counts = Counter(value)
    n = len(value)
    return -sum(c / n * math.log2(c / n) for c in counts.values())


def is_high_entropy(value: str, min_length: int = 16) -> bool:
    if len(value) < min_length:
        return False
    limit = 3.0 if set(value) <= _HEX else 4.5
    return shannon_entropy(value) >= limit


def is_placeholder(value: str) -> bool:
    v = value.strip()
    low = v.lower()
    if low in _PLACEHOLDER_WORDS or any(part in low for part in _PLACEHOLDER_PARTS):
        return True
    if len(set(v)) <= 2:                       # "aaaaaaaa", "--------"
        return True
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", v):     # an all-caps constant / env var NAME
        return True
    if v.startswith(_HASH_PREFIXES):            # a password hash, not a password
        return True
    if v.startswith(("/", "./", "../", "~/", "C:\\", "file:")):
        return True
    if re.match(r"^[a-z][a-z0-9+.-]*://", low) and "@" not in v:  # URL without credentials
        return True
    if v.startswith(("os.", "process.env", "env(", "getenv", "settings.", "config.")):
        return True
    return False


def is_test_path(path: str) -> bool:
    p = PurePosixPath(path.replace("\\", "/"))
    name = p.name.lower()
    return (
        any(part.lower() in _TEST_PARTS for part in p.parts[:-1])
        or name.startswith("test_") or name.endswith(("_test.py", "_tests.py"))
        or ".test." in name or ".spec." in name or name == "conftest.py"
    )


def redact(line: str, value: str) -> str:
    shown = value[:3] if len(value) > 6 else ""
    return line.replace(value, f"{shown}…[REDACTED]").strip()[:200]


@dataclass(frozen=True)
class SecretFinding:
    rule: str           # known pattern name, or password_assignment / secret_key_generic /
                        # api_key_generic / high_entropy_string
    severity: str       # critical | high | medium | low
    cwe: int            # 798 hard-coded credentials, 259 hard-coded password
    path: str
    line: int
    message: str
    snippet: str        # redacted
    in_test: bool = False
    detector: str = "known"   # known | keyword | entropy

    def to_dict(self) -> Dict[str, object]:
        return dict(self.__dict__)


def _keyword_rule(name: str) -> Optional[Tuple[str, int, int, str]]:
    for pattern, rule, cwe, min_len, description in _STRONG_KEYWORDS:
        if pattern.search(name):
            return rule, cwe, min_len, description
    return None


def detect_secrets(text: str, path: str = "<string>") -> List[SecretFinding]:
    """All secret findings in one file's text, at most one per line and value."""
    in_test = is_test_path(path)
    config = _config_kind(path)
    unquoted = _ENV_ASSIGNMENT if config == "env" else _YAML_ASSIGNMENT if config == "yaml" else None
    findings: List[SecretFinding] = []

    def add(rule: str, severity: str, cwe: int, line_no: int, message: str, snippet: str, detector: str) -> None:
        if in_test:
            severity = "low"
        findings.append(SecretFinding(rule, severity, cwe, path, line_no, message, snippet, in_test, detector))

    for line_no, line in enumerate(text.splitlines(), start=1):
        if len(line) > 2000:  # minified / generated content
            continue
        covered: List[Tuple[int, int]] = []
        for name, rx, severity, description in _KNOWN:
            for match in rx.finditer(line):
                covered.append(match.span())
                add(name, severity, 798, line_no, description, redact(line, match.group(0)), "known")

        candidates: List[Tuple[str, str, int]] = []
        for match in _QUOTED_ASSIGNMENT.finditer(line):
            candidates.append((match.group("name"), match.group("value"), match.start("value")))
        plain = unquoted.match(line) if unquoted is not None and not candidates else None
        if plain:
            candidates.append((plain.group("name"), plain.group("value"), plain.start("value")))

        for name, value, start in candidates:
            if any(s <= start < e for s, e in covered) or is_placeholder(value) or re.search(r"\s", value.strip()):
                continue
            keyword = _keyword_rule(name)
            if keyword:
                rule, cwe, min_len, description = keyword
                if len(value) >= min_len:
                    add(rule, "high", cwe, line_no, f"{description} in `{name}`", redact(line, value), "keyword")
                continue
            if _WEAK_HINT.search(name) and is_high_entropy(value):
                add("high_entropy_string", "medium", 798, line_no,
                    f"High-entropy value assigned to `{name}` looks like a secret", redact(line, value), "entropy")
    return findings
