"""
Empirical Adversarial Stress Test Suite for Secrets Scanner (Task 1.2).
Author: Challenger 1 (teamwork_challenger_m1_1)
"""

import re
from pathlib import Path
from tempfile import TemporaryDirectory
import pytest
from secrets_fixtures import synthetic_token

from intelligence.analyzers.common.secrets_scanner import (
    scan_secrets,
    _is_lockfile,
    _should_skip_file,
    _redact_all_secrets,
    _is_obvious_test_fixture,
    SECRET_PATTERNS,
)
from intelligence.evidence.models import SeverityEnum


class TestAdversarialMultiSecretStress:
    """Stress testing lines with 5+ distinct secrets, high secret density, and permutations."""

    def test_twelve_distinct_secrets_on_single_line(self):
        """Construct a line containing 12 distinct secret patterns simultaneously."""
        secrets_dict = {
            "aws_access_key": "AKIA1234567890ABCDEF",
            "aws_secret_key": ("aws_secret_access_key = '" + synthetic_token("aws-secret", 1) + "'"),
            "github_token": (synthetic_token("github", 2)),
            "gitlab_token": (synthetic_token("gitlab", 3)),
            "stripe_secret": (synthetic_token("stripe", 4)),
            "stripe_restricted": (synthetic_token("stripe-restricted", 5)),
            "slack_token": (synthetic_token("slack", 6)),
            "jwt_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
            "password_assignment": "password = 'SuperSecretUnredactedPass123!'",
            "api_key_generic": "api_key = 'abcdef123456789012345678'",
            "secret_key_generic": "secret_key = 'extremelysecretgenericvalue'",
            "sendgrid_key": (synthetic_token("sendgrid", 7)),
        }

        # Combine all onto a single line
        line = " ; ".join(secrets_dict.values())
        redacted = _redact_all_secrets(line)

        # Verify no raw values or sensitive tokens appear anywhere in the redacted string
        raw_sensitive_values = [
            "AKIA1234567890ABCDEF",
            (synthetic_token("aws-secret", 1)),
            (synthetic_token("github", 2)),
            (synthetic_token("gitlab", 3)),
            (synthetic_token("stripe", 4)),
            (synthetic_token("stripe-restricted", 5)),
            (synthetic_token("slack", 6)),
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
            "SuperSecretUnredactedPass123!",
            "abcdef123456789012345678",
            "extremelysecretgenericvalue",
            synthetic_token("sendgrid", 7),
        ]

        for raw_val in raw_sensitive_values:
            assert raw_val not in redacted, f"Raw value {raw_val} leaked into redacted line: {redacted}"

        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "multi_secret.py"
            file_path.write_text(line, encoding="utf-8")

            findings = scan_secrets(["multi_secret.py"], tmp_dir)
            assert len(findings) >= 5, f"Expected at least 5 findings, got {len(findings)}"

            for f in findings:
                for raw_val in raw_sensitive_values:
                    assert raw_val not in f.code_snippet, f"Snippet leaked {raw_val}: {f.code_snippet}"
                    assert raw_val not in f.message
                    assert raw_val not in f.rule_id

    def test_json_and_nested_strings(self):
        """Test secrets embedded in JSON structures and nested quote strings."""
        json_line = '{"api_key": "abcdef123456789012345678", "password": "super_secret_password_123"}'
        redacted = _redact_all_secrets(json_line)

        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "config.json"
            f.write_text(json_line, encoding="utf-8")
            findings = scan_secrets(["config.json"], tmp_dir)
            assert len(findings) >= 1, "Expected generic secrets in JSON configuration to be detected and redacted"

    def test_interleaved_and_repeated_secrets_same_line(self):
        """Line with repeated identical secrets interleaved with distinct secrets."""
        github = synthetic_token("github", 8, fixture=True)
        stripe = synthetic_token("stripe", 9, fixture=True)
        line = (f"k1 = '{github}', k2 = 'AKIA1111111111111111', "
                f"k3 = '{github}', k4 = '{stripe}', k5 = 'AKIA1111111111111111'")
        redacted = _redact_all_secrets(line)
        assert (synthetic_token("github", 8, fixture=True)) not in redacted
        assert "AKIA1111111111111111" not in redacted
        assert (synthetic_token("stripe", 9, fixture=True)) not in redacted


class TestAdversarialLongLinesAndReDoS:
    """Stress testing lines >10,000 chars, boundary conditions, and ReDoS resilience."""

    def test_line_length_15000_chars_secrets_at_extremes(self):
        """Construct a 15,000 char line with secrets at beginning, middle, and end."""
        prefix = "a" * 5000
        secret1 = "AKIA2222222222222222"
        mid = "b" * 5000
        secret2 = (synthetic_token("github", 10))
        suffix = "c" * 5000
        secret3 = (synthetic_token("stripe", 11))

        huge_line = f"{prefix}{secret1}{mid}{secret2}{suffix}{secret3}"
        assert len(huge_line) > 15000

        redacted = _redact_all_secrets(huge_line)
        assert secret1 not in redacted
        assert secret2 not in redacted
        assert secret3 not in redacted

        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "huge_line.py"
            file_path.write_text(huge_line, encoding="utf-8")

            findings = scan_secrets(["huge_line.py"], tmp_dir)
            assert len(findings) == 3

            for f in findings:
                # Snippet is truncated to 200 chars. Ensure no secret fragment leaks
                assert secret1 not in f.code_snippet
                assert secret2 not in f.code_snippet
                assert secret3 not in f.code_snippet
                assert len(f.code_snippet) <= 200

    def test_secret_spanning_boundary_200(self):
        """Secret placed exactly across character 200 on a long line."""
        padding = "x" * 190
        # Secret starts at char 190 and extends to char 210
        secret = "AKIA9999999999999999"
        long_line = padding + secret + ("y" * 1000)

        redacted = _redact_all_secrets(long_line)
        assert secret not in redacted

        snippet = redacted.strip()[:200]
        assert secret not in snippet
        # Ensure partial secret bytes are not present in snippet
        assert "AKIA" not in snippet or "[REDACTED:AWS_ACCESS_KEY]" in snippet

    def test_redos_pattern_safety_under_adversarial_input(self):
        """Feed adversarial repetition strings designed to trigger polynomial/exponential backtracking."""
        adversarial_inputs = [
            "password = '" + "a" * 10000,
            "api_key = '" + "a" * 10000,
            "aws_secret_access_key = " + "a" * 10000,
            "mysql://" + "user:" * 1000 + "pass@",
            "SG." + "a" * 50 + "." + "b" * 50,
            "-----BEGIN RSA PRIVATE KEY-----" + "A" * 10000,
        ]
        for adv_str in adversarial_inputs:
            # Should evaluate practically instantaneously (< 0.2s per input)
            _ = _redact_all_secrets(adv_str)


class TestAdversarialMultilineSnippets:
    """Testing multiline constructs, CRLF endings, and block credentials."""

    def test_private_key_multiline_block(self):
        """Private key header followed by multiline base64 block and footer."""
        key_content = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA0m4w4YF7H\n"
            "AbCdEf1234567890/+\n"
            "-----END RSA PRIVATE KEY-----\n"
        )
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "id_rsa"
            file_path.write_text(key_content, encoding="utf-8")

            findings = scan_secrets(["id_rsa"], tmp_dir)
            assert len(findings) == 1
            f = findings[0]
            assert f.rule_id == "SEC-SECRET-PRIVATE_KEY"
            assert f.severity == SeverityEnum.CRITICAL
            assert "-----BEGIN RSA PRIVATE KEY-----" not in f.code_snippet
            assert "[REDACTED:PRIVATE_KEY]" in f.code_snippet

    def test_crlf_line_endings_preserved_and_redacted(self):
        """Files with Windows CRLF newlines."""
        content = "key = 'AKIA1111111111111111'\r\npassword = 'super_secret_password_1'\r\n"
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "crlf.py"
            file_path.write_bytes(content.encode("utf-8"))

            findings = scan_secrets(["crlf.py"], tmp_dir)
            assert len(findings) >= 2
            for f in findings:
                assert "\r" not in f.code_snippet
                assert "AKIA1111111111111111" not in f.code_snippet
                assert "super_secret_password_1" not in f.code_snippet


class TestAdversarialLockfileEdgeCases:
    """Stress testing lockfile recognition vs legitimate source code files."""

    @pytest.mark.parametrize(
        "lockfile_name",
        [
            "packages.lock.json",
            "npm-shrinkwrap.json",
            "bun.lockb",
            "subproject-lock.json",
            "pnpm-lock.yaml",
            "pnpm-lock.yml",
            "yarn.lock",
            "composer.lock",
            "cargo.lock",
            "gemfile.lock",
            "gradle.lockfile",
            "buildscript-gradle.lockfile",
            "podfile.lock",
            "package.resolved",
            "mix.lock",
            "flake.lock",
            "deno.lock",
            "shrinkwrap.yaml",
            "pipfile.lock",
            "poetry.lock",
            "pdm.lock",
            "foo.lockfile",
            "my-app-lock.json",
            "service.lock.yaml",
        ],
    )
    def test_obscure_and_compound_lockfiles_skipped(self, lockfile_name: str):
        path = Path(lockfile_name)
        assert _is_lockfile(path) is True
        assert _should_skip_file(path) is True

    @pytest.mark.parametrize(
        "valid_code_file",
        [
            "package.json",
            "settings.lock.py",
            "lock_test.js",
            "lock.py",
            "flakelock.py",
            "api_token.lock.ts",
            "unlock.json",
            "block.json",
            "clock.yaml",
            "padlock.yml",
            "locked_accounts.py",
            "interlock.rs",
            "locker.go",
            "block_cipher.c",
            "deadlock_detector.cpp",
        ],
    )
    def test_valid_code_files_not_mistaken_for_lockfiles(self, valid_code_file: str):
        path = Path(valid_code_file)
        assert _is_lockfile(path) is False
        assert _should_skip_file(path) is False

        # Verify that secrets inside valid code files are scanned and detected
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / valid_code_file
            file_path.write_text("aws_key = 'AKIA1111111111111111'", encoding="utf-8")

            findings = scan_secrets([valid_code_file], tmp_dir)
            assert len(findings) == 1, f"Expected secret detected in valid code file {valid_code_file}"

    def test_dotfile_lockfile_edge_case(self):
        """Test dotfile forms like '.lockfile', '.lock', and '.lockb'."""
        dot_lockfile = Path(".lockfile")
        dot_lock = Path(".lock")
        dot_lockb = Path(".lockb")

        # Empirical challenge: Obscure lockfile named exactly '.lockfile', '.lock', '.lockb'
        assert _is_lockfile(dot_lockfile) is True, "Expected .lockfile to be recognized as lockfile"
        assert _should_skip_file(dot_lockfile) is True, "Expected .lockfile to be skipped"
        assert _is_lockfile(dot_lock) is True, "Expected .lock to be recognized as lockfile"
        assert _should_skip_file(dot_lock) is True, "Expected .lock to be skipped"
        assert _is_lockfile(dot_lockb) is True, "Expected .lockb to be recognized as lockfile"
        assert _should_skip_file(dot_lockb) is True, "Expected .lockb to be skipped"


class TestAdversarialFixtureDetectionEdgeCases:
    """Stress testing test fixture detection, dummy key edge cases, and genuine leaks."""

    def test_aws_official_dummy_keys(self):
        """AWS official example credentials must be downgraded to LOW with -FIXTURE suffix."""
        examples = [
            "AKIAIOSFODNN7EXAMPLE",
            ("aws_secret_access_key = '" + synthetic_token("aws-secret", 12, fixture=True) + "'"),
        ]
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "aws_config.py"
            file_path.write_text("\n".join(examples), encoding="utf-8")

            findings = scan_secrets(["aws_config.py"], tmp_dir)
            assert len(findings) == 2
            for f in findings:
                assert f.severity == SeverityEnum.LOW
                assert f.rule_id.endswith("-FIXTURE")
                assert f.message.startswith("[Test Fixture]")

    def test_mixed_case_dummy_indicators(self):
        """Tokens with mixed-case dummy keywords like 'FaKe', 'dUmMy', 'eXaMpLe'."""
        lines = [
            ("token = '" + synthetic_token("github", 13, fixture=True) + "'"),
            ("key = '" + synthetic_token("stripe", 14, fixture=True) + "'"),
            "password = 'MyExAmPlEpAsSwOrD123!'",
        ]
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "test_dummy.py"
            file_path.write_text("\n".join(lines), encoding="utf-8")

            findings = scan_secrets(["test_dummy.py"], tmp_dir)
            assert len(findings) >= 2
            for f in findings:
                assert f.severity == SeverityEnum.LOW
                assert f.rule_id.endswith("-FIXTURE")

    def test_genuine_secret_in_test_directory_retains_critical(self):
        """Real high-entropy secret in tests/ directory must NOT be suppressed or downgraded."""
        secret_line = ("client_secret = '" + synthetic_token("github", 15) + "'")
        with TemporaryDirectory() as tmp_dir:
            test_dir = Path(tmp_dir) / "tests" / "unit"
            test_dir.mkdir(parents=True)
            file_path = test_dir / "test_auth.py"
            file_path.write_text(secret_line, encoding="utf-8")

            findings = scan_secrets(["tests/unit/test_auth.py"], tmp_dir)
            assert len(findings) == 1
            f = findings[0]
            assert f.severity == SeverityEnum.CRITICAL
            assert not f.rule_id.endswith("-FIXTURE")
            assert not f.message.startswith("[Test Fixture]")

    def test_password_with_special_characters_in_production_file(self):
        """Complex passwords with special characters in prod code are HIGH severity."""
        prod_line = "db_password = 'P@ssw0rd!#$Complex12345^&*()'"
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "src" / "db.py"
            file_path.parent.mkdir(parents=True)
            file_path.write_text(prod_line, encoding="utf-8")

            findings = scan_secrets(["src/db.py"], tmp_dir)
            assert len(findings) == 1
            f = findings[0]
            assert f.severity == SeverityEnum.HIGH
            assert not f.rule_id.endswith("-FIXTURE")

    def test_same_line_fixture_and_genuine_cloud_key(self):
        """A line having both an AWS example key and a real AWS key."""
        line = "dummy = 'AKIAIOSFODNN7EXAMPLE' and real = 'AKIA1234567890ABCDEF'"
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "keys.py"
            file_path.write_text(line, encoding="utf-8")

            findings = scan_secrets(["keys.py"], tmp_dir)
            assert len(findings) == 2

            severities = {f.severity for f in findings}
            rule_ids = {f.rule_id for f in findings}

            assert SeverityEnum.LOW in severities
            assert SeverityEnum.CRITICAL in severities
            assert "SEC-SECRET-AWS_ACCESS_KEY-FIXTURE" in rule_ids
            assert "SEC-SECRET-AWS_ACCESS_KEY" in rule_ids

    def test_boundary_truncation_across_offsets_produces_zero_broken_tags(self):
        """Verify across offsets 160-224 that snippet slicing produces no broken or unclosed tags."""
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "offsets.py"
            for offset in range(160, 225):
                pad = "X" * offset
                line = f"{pad}AKIA2GHIJK3LMNOPQRST" + ("Y" * 50) + "\n"
                file_path.write_text(line, encoding="utf-8")
                findings = scan_secrets(["offsets.py"], tmp_dir)
                assert len(findings) == 1
                snippet = findings[0].code_snippet
                assert len(snippet) <= 200
                last_open = snippet.rfind("[")
                last_close = snippet.rfind("]")
                assert last_open <= last_close, f"Broken tag at offset {offset}: {snippet}"

    def test_contextual_mock_keywords_do_not_downgrade_genuine_secrets(self):
        """Mock method calls or inline comments containing 'mock'/'sample' must not downgrade genuine secrets."""
        test_cases = [
            'mock_auth.login(password="SuperSecretPassword!12345")',
            'password = "SuperSecretPassword!12345"  # mock endpoint test',
            'mock_server.start(api_key="AIzaSyD1234567890abcdefghijklmnopqrstuv")',
            'sample_app.init(secret_key="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6")',
        ]
        with TemporaryDirectory() as tmp_dir:
            test_path = Path(tmp_dir) / "tests" / "test_auth_mock.py"
            test_path.parent.mkdir(parents=True, exist_ok=True)
            for line in test_cases:
                test_path.write_text(f"{line}\n", encoding="utf-8")
                findings = scan_secrets(["tests/test_auth_mock.py"], tmp_dir)
                assert len(findings) >= 1
                for f in findings:
                    assert f.severity == SeverityEnum.HIGH
                    assert not f.rule_id.endswith("-FIXTURE")
