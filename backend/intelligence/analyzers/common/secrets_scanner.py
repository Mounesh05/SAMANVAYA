"""
Universal Secrets & Credentials Scanner.
Language-agnostic regex patterns for hardcoded API keys, tokens, and passwords.

Extracted from the old security_scanner.py into a shared module so all
language analyzers can use the same detection without code duplication.

Runs on every file type regardless of language.
"""

import re
from pathlib import Path
from typing import List, Set, Tuple

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
     r"""(?i)['"]?(?:password|passwd|pwd)['"]?\s*[:=]\s*['"][^'"]{8,}['"]""",
     SeverityEnum.HIGH,
     "Hardcoded password detected"),

    ("api_key_generic",
     r"""(?i)['"]?(?:api[_\-]?|auth[_\-]?|access[_\-]?)?key['"]?\s*[:=]\s*['"](?!(?:AKIA|gh[pousr]_|glpat-|sk_live_|rk_live_|xox[baprs]-))[a-zA-Z0-9_\-]{20,}['"]""",
     SeverityEnum.HIGH,
     "Generic API key detected"),

    ("secret_key_generic",
     r"""(?i)['"]?secret[_\-]?key['"]?\s*[:=]\s*['"][^'"]{12,}['"]""",
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
SKIP_EXTENSIONS: Set[str] = {
    # Media and image formats
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".ico", ".webp", ".tiff",
    # Fonts
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    # Archives and compressed binaries
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    # Compiled and bytecode
    ".jar", ".war", ".ear", ".class", ".pyc", ".pyo", ".pyd", ".so", ".dll", ".dylib", ".exe",
    # Documents
    ".pdf", ".docx", ".xlsx", ".pptx",
    # Lockfile extensions
    ".lock", ".lockb", ".lockfile",
}

SKIP_FILENAMES: Set[str] = {
    # Node / JavaScript / TypeScript
    "package-lock.json",
    "npm-shrinkwrap.json",
    "pnpm-lock.yaml",
    "pnpm-lock.yml",
    "yarn.lock",
    "bun.lockb",
    "bun.lock",
    "shrinkwrap.yaml",
    # .NET / C#
    "packages.lock.json",
    # PHP
    "composer.lock",
    # Python
    "poetry.lock",
    "pipfile.lock",
    "pdm.lock",
    # Rust
    "cargo.lock",
    # Ruby
    "gemfile.lock",
    # Gradle / Java
    "gradle.lockfile",
    "buildscript-gradle.lockfile",
    # iOS / Swift
    "podfile.lock",
    "package.resolved",
    # Elixir
    "mix.lock",
    # Nix
    "flake.lock",
    # Deno
    "deno.lock",
    # Dotfiles
    ".lock",
    ".lockb",
    ".lockfile",
}

LOCKFILE_COMPOUND_SUFFIXES: Tuple[str, ...] = (
    "-lock.json",
    ".lock.json",
    "-lock.yaml",
    ".lock.yaml",
    "-lock.yml",
    ".lock.yml",
)

# ── Test Fixture and Dummy Credential Detection ──────────────────────────────
DUMMY_KEYWORD_PATTERNS = re.compile(
    r"(?i)(?:example|dummy|mock|fake|placeholder|sample|00000000|11111111|xxxxxxxx|test_secret|test-secret|test_pass|test-pass|test_pwd|changeme|change_me)"
)

TRIVIAL_PASSWORDS: Set[str] = {
    "password", "password123", "password1", "admin123", "secret123",
    "12345678", "123456789", "qwertyuiop", "letmein123",
}


def _is_lockfile(path: Path) -> bool:
    """Check if file is a dependency lockfile by filename, suffix, or compound pattern."""
    filename = path.name.lower()
    suffix = path.suffix.lower()
    if filename in SKIP_FILENAMES or filename in {".lock", ".lockb", ".lockfile"}:
        return True
    if suffix in {".lock", ".lockb", ".lockfile"}:
        return True
    if filename.endswith(LOCKFILE_COMPOUND_SUFFIXES):
        return True
    return False


def _should_skip_file(path: Path) -> bool:
    """Determine whether a file should be skipped during secret scanning."""
    suffix = path.suffix.lower()
    if suffix in SKIP_EXTENSIONS:
        return True
    if _is_lockfile(path):
        return True
    return False


def _extract_secret_value(pattern_name: str, match_text: str) -> str:
    """Extract the credential value portion from a regex match."""
    if pattern_name in ("password_assignment", "api_key_generic", "secret_key_generic"):
        parts = re.split(r"[:=]", match_text, maxsplit=1)
        val_part = parts[1] if len(parts) > 1 else match_text
        m = re.search(r"""['"]([^'"]+)['"]""", val_part)
        if m:
            return m.group(1)
    elif pattern_name == "aws_secret_key":
        m = re.search(r"""[A-Za-z0-9/+=]{40}""", match_text)
        if m:
            return m.group(0)
    elif pattern_name == "db_conn_string":
        m = re.search(r"""://([^:]+):([^@]+)@""", match_text)
        if m:
            return f"{m.group(1)}:{m.group(2)}"
    return match_text


def _is_obvious_test_fixture(pattern_name: str, match_text: str, line: str, file_path: str) -> bool:
    """
    Determine if a detected credential match is an obvious test fixture.

    Genuine credentials in test directories are NOT classified as fixtures
    unless they exhibit explicit placeholder or dummy markers.
    """
    # 1. AWS official documentation example key IDs and secret keys
    if "AKIAIOSFODNN7EXAMPLE" in match_text or "EXAMPLEKEY" in match_text:
        return True

    val = _extract_secret_value(pattern_name, match_text)

    # 2. Match text / extracted value itself contains obvious dummy indicators
    if DUMMY_KEYWORD_PATTERNS.search(val):
        return True

    # 3. Contextual indicators in test files / test paths
    path_lower = file_path.lower()
    in_test_path = any(t in path_lower for t in ("test", "spec", "fixture", "mock"))
    if in_test_path:
        # Check trivial passwords in test files
        if val.lower() in TRIVIAL_PASSWORDS:
            return True
        # For password assignments or generic keys in test paths, check if variable name is explicitly dummy/mock/fake
        if pattern_name in ("password_assignment", "api_key_generic", "secret_key_generic"):
            idx = line.find(match_text)
            parts = re.split(r"[:=]", match_text, maxsplit=1)
            var_part = parts[0]
            if idx != -1:
                pre_assignment = line[: idx + len(var_part)]
                m = re.search(r"['\"]?([a-zA-Z0-9_\-]+)['\"]?\s*$", pre_assignment)
                if m:
                    var_part = m.group(1)
            if DUMMY_KEYWORD_PATTERNS.search(var_part):
                return True

    return False


def _redact_all_secrets(line: str) -> str:
    """Sequentially redact all known secret patterns across the entire line."""
    redacted = line
    for pattern_name, pattern, _, _ in SECRET_PATTERNS:
        redacted = re.sub(pattern, f"[REDACTED:{pattern_name.upper()}]", redacted)
    return redacted


def scan_secrets(
    files: List[str],
    repo_path: str,
) -> List[Finding]:
    """
    Scan all provided files for hardcoded secrets and credentials.

    Severity Semantics:
      - Genuine credentials retain their registered severity (CRITICAL, HIGH, MEDIUM).
      - Obvious test fixtures and documented dummy values (e.g. AWS example keys,
        placeholders with 'fake', 'dummy', 'mock') are downgraded to SeverityEnum.LOW
        with rule ID suffix '-FIXTURE' and message prefixed by '[Test Fixture]'.
        This avoids alert fatigue while ensuring genuine leaks in test files remain CRITICAL/HIGH.
      - All returned code snippets are completely redacted across the entire line prior to slicing and storage.

    Args:
        files: File paths relative to repo_path
        repo_path: Absolute repo root

    Returns:
        List of Finding objects for each detected secret
    """
    findings: List[Finding] = []

    for rel_path in files:
        abs_path = Path(repo_path) / rel_path

        # Skip non-existent files, directories, lockfiles, and binary noise
        if not abs_path.is_file() or _should_skip_file(abs_path):
            continue

        try:
            content = abs_path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
        except (OSError, UnicodeDecodeError):
            continue

        for line_num, line in enumerate(lines, start=1):
            matching_patterns = []
            for pattern_name, pattern, base_severity, description in SECRET_PATTERNS:
                matches = list(re.finditer(pattern, line))
                if matches:
                    matching_patterns.append((pattern_name, pattern, base_severity, description, matches))

            if not matching_patterns:
                continue

            # Sequentially redact all detected secrets across the entire line before creating snippets
            redacted_line = _redact_all_secrets(line)
            snippet = redacted_line.strip()
            if len(snippet) > 200:
                open_idx = snippet[:200].rfind("[")
                close_idx = snippet[:200].rfind("]")
                if open_idx > close_idx and snippet.startswith("[REDACTED:", open_idx):
                    snippet = snippet[:open_idx]
                else:
                    snippet = snippet[:200]

            for pattern_name, _, base_severity, description, matches in matching_patterns:
                seen_matches = set()
                for match in matches:
                    match_text = match.group(0)
                    if match_text in seen_matches:
                        continue
                    seen_matches.add(match_text)

                    is_fixture = _is_obvious_test_fixture(pattern_name, match_text, line, rel_path)
                    severity = SeverityEnum.LOW if is_fixture else base_severity
                    rule_id = (
                        f"SEC-SECRET-{pattern_name.upper()}-FIXTURE"
                        if is_fixture
                        else f"SEC-SECRET-{pattern_name.upper()}"
                    )
                    msg = (
                        f"[Test Fixture] {description} (dummy/placeholder)"
                        if is_fixture
                        else description
                    )

                    findings.append(Finding(
                        file_path=rel_path,
                        line_number=line_num,
                        rule_id=rule_id,
                        category="security",
                        severity=severity,
                        source_tool="secrets-scanner",
                        message=msg,
                        code_snippet=snippet,
                    ))

    return findings
