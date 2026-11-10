"""
Comprehensive regression tests for Secrets Scanner (Task 1.2).
Validates:
1. Complete lockfile filtering across ecosystems (explicit names, suffixes, compound patterns, case insensitivity).
2. Sequential redaction across entire lines before snippet slicing, including multiple distinct or identical credentials.
3. Test fixture detection without suppressing genuine leaked credentials in test files.
4. Absolute raw secret prevention in all findings, rule IDs, messages, and snippets.
5. Robust file handling and edge cases.
"""

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


class TestLockfileFiltering:
    """Verifies that all dependency lockfiles are properly excluded while ordinary code is scanned."""

    @pytest.mark.parametrize(
        "filename",
        [
            "package-lock.json",
            "npm-shrinkwrap.json",
            "pnpm-lock.yaml",
            "pnpm-lock.yml",
            "yarn.lock",
            "bun.lockb",
            "bun.lock",
            "shrinkwrap.yaml",
            "packages.lock.json",
            "composer.lock",
            "poetry.lock",
            "pipfile.lock",
            "pdm.lock",
            "cargo.lock",
            "gemfile.lock",
            "gradle.lockfile",
            "buildscript-gradle.lockfile",
            "podfile.lock",
            "package.resolved",
            "mix.lock",
            "flake.lock",
            "deno.lock",
            ".lock",
            ".lockb",
            ".lockfile",
        ],
    )
    def test_explicit_lockfilenames_excluded(self, filename: str):
        with TemporaryDirectory() as tmp_dir:
            lock_path = Path(tmp_dir) / filename
            lock_path.write_text('{"token": "AKIA1111111111111111"}', encoding="utf-8")

            assert _is_lockfile(lock_path) is True
            assert _should_skip_file(lock_path) is True

            findings = scan_secrets([filename], tmp_dir)
            assert len(findings) == 0

    @pytest.mark.parametrize(
        "compound_name",
        [
            "frontend-lock.json",
            "backend.lock.json",
            "client-lock.yaml",
            "service.lock.yaml",
            "api-lock.yml",
            "shared.lock.yml",
            "custom.lockfile",
            "archive.lockb",
        ],
    )
    def test_compound_pattern_lockfiles_excluded(self, compound_name: str):
        with TemporaryDirectory() as tmp_dir:
            lock_path = Path(tmp_dir) / compound_name
            lock_path.write_text('secret = "AKIA1111111111111111"', encoding="utf-8")

            assert _is_lockfile(lock_path) is True
            findings = scan_secrets([compound_name], tmp_dir)
            assert len(findings) == 0

    @pytest.mark.parametrize(
        "cased_name",
        [
            "PACKAGE-LOCK.JSON",
            "Package-Lock.json",
            "Cargo.LOCK",
            "YARN.LOCK",
            "Bun.Lockb",
            "PACKAGES.LOCK.JSON",
        ],
    )
    def test_lockfiles_case_insensitive(self, cased_name: str):
        with TemporaryDirectory() as tmp_dir:
            lock_path = Path(tmp_dir) / cased_name
            lock_path.write_text('token = "AKIA1111111111111111"', encoding="utf-8")

            assert _is_lockfile(lock_path) is True
            findings = scan_secrets([cased_name], tmp_dir)
            assert len(findings) == 0

    @pytest.mark.parametrize(
        "non_lockfile",
        [
            "package.json",
            "config.yaml",
            "settings.yml",
            "secrets.json",
            "credentials.ini",
            "auth.py",
        ],
    )
    def test_non_lockfiles_not_excluded(self, non_lockfile: str):
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / non_lockfile
            file_path.write_text('token = "AKIA1111111111111111"', encoding="utf-8")

            assert _is_lockfile(file_path) is False
            findings = scan_secrets([non_lockfile], tmp_dir)
            assert len(findings) >= 1


class TestSequentialRedaction:
    """Verifies complete full-line sequential redaction prior to snippet slicing."""

    def test_single_credential_redacted(self):
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "config.py"
            file_path.write_text('key = "AKIA1111111111111111"\n', encoding="utf-8")

            findings = scan_secrets(["config.py"], tmp_dir)
            assert len(findings) == 1
            assert "AKIA1111111111111111" not in findings[0].code_snippet
            assert "[REDACTED:AWS_ACCESS_KEY]" in findings[0].code_snippet

    def test_multiple_distinct_credentials_on_same_line_all_redacted(self):
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "multi.py"
            # 3 different secrets on a single line
            aws_key = "AKIA1111111111111111"
            gh_token = (synthetic_token("github", 2))
            stripe_key = (synthetic_token("stripe", 4))
            line = f'a = "{aws_key}" and b = "{gh_token}" and c = "{stripe_key}"\n'
            file_path.write_text(line, encoding="utf-8")

            findings = scan_secrets(["multi.py"], tmp_dir)
            assert len(findings) == 3

            for f in findings:
                assert aws_key not in f.code_snippet
                assert gh_token not in f.code_snippet
                assert stripe_key not in f.code_snippet
                assert "[REDACTED:AWS_ACCESS_KEY]" in f.code_snippet
                assert "[REDACTED:GITHUB_TOKEN]" in f.code_snippet
                assert "[REDACTED:STRIPE_SECRET]" in f.code_snippet

    def test_multiple_same_credentials_on_same_line_all_redacted(self):
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "same.py"
            k1 = "AKIA1111111111111111"
            k2 = "AKIA2222222222222222"
            file_path.write_text(f'primary = "{k1}", backup = "{k2}"\n', encoding="utf-8")

            findings = scan_secrets(["same.py"], tmp_dir)
            assert len(findings) == 2

            for f in findings:
                assert k1 not in f.code_snippet
                assert k2 not in f.code_snippet
                assert f.code_snippet.count("[REDACTED:AWS_ACCESS_KEY]") == 2

    def test_long_line_sliced_after_full_redaction(self):
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "long.py"
            aws_key = "AKIA9999999999999999"
            # Secret placed well beyond character 200
            prefix = "# " + ("A" * 220)
            suffix = "B" * 50
            file_path.write_text(f"{prefix} key = '{aws_key}' {suffix}\n", encoding="utf-8")

            findings = scan_secrets(["long.py"], tmp_dir)
            assert len(findings) == 1
            assert aws_key not in findings[0].code_snippet
            assert len(findings[0].code_snippet) <= 200

    def test_json_quoted_keys_detected_and_redacted(self):
        """Generic secrets with quoted keys in JSON format are detected and redacted."""
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "config.json"
            secret_line = '{"api_key": "abcdef123456789012345678", "password": "super_secret_password_123"}'
            file_path.write_text(secret_line, encoding="utf-8")

            findings = scan_secrets(["config.json"], tmp_dir)
            assert len(findings) >= 2
            rule_ids = {f.rule_id for f in findings}
            assert "SEC-SECRET-API_KEY_GENERIC" in rule_ids
            assert "SEC-SECRET-PASSWORD_ASSIGNMENT" in rule_ids
            for f in findings:
                assert "abcdef123456789012345678" not in f.code_snippet
                assert "super_secret_password_123" not in f.code_snippet
                assert f.severity == SeverityEnum.HIGH

    def test_redaction_boundary_near_char_200_no_severed_tag(self):
        """Redaction tags crossing character 200 are truncated before the tag without unclosed brackets."""
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "boundary.py"
            pad = "X" * 185
            key = "AKIA1234567890ABCDEF"
            file_path.write_text(f"{pad}{key}" + ("Y" * 50) + "\n", encoding="utf-8")

            findings = scan_secrets(["boundary.py"], tmp_dir)
            assert len(findings) == 1
            snippet = findings[0].code_snippet
            assert len(snippet) <= 200
            assert key not in snippet
            # Must not contain severed tag or unclosed bracket
            last_open = snippet.rfind("[")
            last_close = snippet.rfind("]")
            assert last_open <= last_close, f"Unclosed redaction tag found in snippet: {snippet}"


class TestFixtureHandling:
    """Verifies that obvious fixtures are downgraded without suppressing genuine secrets."""

    def test_aws_official_example_key_downgraded_to_low(self):
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "example.py"
            file_path.write_text('key = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8")

            findings = scan_secrets(["example.py"], tmp_dir)
            assert len(findings) == 1
            f = findings[0]
            assert f.severity == SeverityEnum.LOW
            assert f.rule_id == "SEC-SECRET-AWS_ACCESS_KEY-FIXTURE"
            assert "[Test Fixture]" in f.message

    def test_aws_official_example_secret_key_downgraded_to_low(self):
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "example_secret.py"
            file_path.write_text(
                ('aws_secret_access_key = "' + synthetic_token("aws-secret", 12, fixture=True) + '"\n'),
                encoding="utf-8",
            )

            findings = scan_secrets(["example_secret.py"], tmp_dir)
            assert len(findings) == 1
            assert findings[0].severity == SeverityEnum.LOW
            assert findings[0].rule_id == "SEC-SECRET-AWS_SECRET_KEY-FIXTURE"

    def test_dummy_and_mock_keywords_downgraded(self):
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "dummy.py"
            file_path.write_text(
                'api_key = "dummy_api_key_sample_123456789"\n' +
                ('token = "' + synthetic_token("github", 16, fixture=True) + '"\n'),
                encoding="utf-8",
            )

            findings = scan_secrets(["dummy.py"], tmp_dir)
            assert len(findings) == 2
            for f in findings:
                assert f.severity == SeverityEnum.LOW
                assert f.rule_id.endswith("-FIXTURE")

    def test_trivial_password_in_test_file_downgraded(self):
        with TemporaryDirectory() as tmp_dir:
            test_path = Path(tmp_dir) / "tests" / "test_login.py"
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.write_text('password = "password123"\n', encoding="utf-8")

            findings = scan_secrets(["tests/test_login.py"], tmp_dir)
            assert len(findings) == 1
            assert findings[0].severity == SeverityEnum.LOW
            assert findings[0].rule_id == "SEC-SECRET-PASSWORD_ASSIGNMENT-FIXTURE"

    def test_trivial_password_in_production_file_retains_high_severity(self):
        with TemporaryDirectory() as tmp_dir:
            prod_path = Path(tmp_dir) / "backend" / "config.py"
            prod_path.parent.mkdir(parents=True, exist_ok=True)
            prod_path.write_text('password = "password123"\n', encoding="utf-8")

            findings = scan_secrets(["backend/config.py"], tmp_dir)
            assert len(findings) == 1
            assert findings[0].severity == SeverityEnum.HIGH
            assert findings[0].rule_id == "SEC-SECRET-PASSWORD_ASSIGNMENT"

    def test_genuine_secret_in_test_file_retains_critical_severity(self):
        with TemporaryDirectory() as tmp_dir:
            test_path = Path(tmp_dir) / "tests" / "test_auth.py"
            test_path.parent.mkdir(parents=True, exist_ok=True)
            real_key = "AKIA3J5K2L9M7N1P4Q8R"
            test_path.write_text(f'aws_key = "{real_key}"\n', encoding="utf-8")

            findings = scan_secrets(["tests/test_auth.py"], tmp_dir)
            assert len(findings) == 1
            f = findings[0]
            assert f.severity == SeverityEnum.CRITICAL
            assert f.rule_id == "SEC-SECRET-AWS_ACCESS_KEY"
            assert "[Test Fixture]" not in f.message

    def test_mixed_fixture_and_genuine_secret_on_same_line(self):
        with TemporaryDirectory() as tmp_dir:
            test_path = Path(tmp_dir) / "tests" / "test_mixed.py"
            test_path.parent.mkdir(parents=True, exist_ok=True)
            line = 'keys = ["AKIAIOSFODNN7EXAMPLE", "AKIA3J5K2L9M7N1P4Q8R"]\n'
            test_path.write_text(line, encoding="utf-8")

            findings = scan_secrets(["tests/test_mixed.py"], tmp_dir)
            assert len(findings) == 2

            fixture_finding = next(f for f in findings if f.rule_id.endswith("-FIXTURE"))
            real_finding = next(f for f in findings if not f.rule_id.endswith("-FIXTURE"))

            assert fixture_finding.severity == SeverityEnum.LOW
            assert real_finding.severity == SeverityEnum.CRITICAL

            # Both snippets must be completely redacted
            for f in findings:
                assert "AKIAIOSFODNN7EXAMPLE" not in f.code_snippet
                assert "AKIA3J5K2L9M7N1P4Q8R" not in f.code_snippet
                assert f.code_snippet.count("[REDACTED:AWS_ACCESS_KEY]") == 2

    def test_mock_call_with_genuine_secret_retains_high_severity(self):
        """Mock method calls passing high-entropy credentials must NOT be falsely downgraded."""
        with TemporaryDirectory() as tmp_dir:
            test_path = Path(tmp_dir) / "tests" / "test_client.py"
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.write_text('mock_auth.login(password="SuperSecretPassword!12345")\n', encoding="utf-8")

            findings = scan_secrets(["tests/test_client.py"], tmp_dir)
            assert len(findings) == 1
            assert findings[0].severity == SeverityEnum.HIGH
            assert not findings[0].rule_id.endswith("-FIXTURE")

    def test_dummy_variable_identifier_downgraded_in_test_file(self):
        """Variables explicitly prefixed with dummy/fake in test files are downgraded to LOW."""
        with TemporaryDirectory() as tmp_dir:
            test_path = Path(tmp_dir) / "tests" / "test_fixtures.py"
            test_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.write_text('dummy_password = "SuperSecretPassword!12345"\n', encoding="utf-8")

            findings = scan_secrets(["tests/test_fixtures.py"], tmp_dir)
            assert len(findings) == 1
            assert findings[0].severity == SeverityEnum.LOW
            assert findings[0].rule_id == "SEC-SECRET-PASSWORD_ASSIGNMENT-FIXTURE"


class TestRawSecretPrevention:
    """Verifies that no cleartext secret strings appear in any attribute of any Finding."""

    def test_no_raw_secret_leak_across_all_patterns(self):
        test_samples = [
            ("AKIA1234567890123456", 'key = "AKIA1234567890123456"\n'),
            ((synthetic_token("github", 2)), ('t = "' + synthetic_token("github", 2) + '"\n')),
            ((synthetic_token("stripe", 4)), ('s = "' + synthetic_token("stripe", 4) + '"\n')),
            ((synthetic_token("slack", 17)), ('sl = "' + synthetic_token("slack", 17) + '"\n')),
            ((synthetic_token("sendgrid", 7)), ('sg = "' + synthetic_token("sendgrid", 7) + '"\n')),
        ]
        with TemporaryDirectory() as tmp_dir:
            for idx, (secret, content) in enumerate(test_samples):
                fname = f"sample_{idx}.py"
                (Path(tmp_dir) / fname).write_text(content, encoding="utf-8")
                findings = scan_secrets([fname], tmp_dir)
                assert len(findings) >= 1
                for f in findings:
                    assert secret not in f.code_snippet
                    assert secret not in f.rule_id
                    assert secret not in f.message
                    assert secret not in f.category
                    assert secret not in f.source_tool
                    assert secret not in f.file_path


class TestFileHandlingAndEdgeCases:
    """Verifies scanner resilience against edge cases, binary files, and missing paths."""

    def test_binary_files_skipped(self):
        with TemporaryDirectory() as tmp_dir:
            for ext in [".png", ".jpg", ".zip", ".pyc", ".pdf", ".class"]:
                bin_file = Path(tmp_dir) / f"blob{ext}"
                bin_file.write_bytes(b"AKIA1111111111111111\x00\x01\x02")
                findings = scan_secrets([bin_file.name], tmp_dir)
                assert len(findings) == 0

    def test_nonexistent_and_directory_paths_handled_gracefully(self):
        with TemporaryDirectory() as tmp_dir:
            sub_dir = Path(tmp_dir) / "subdir"
            sub_dir.mkdir()

            findings = scan_secrets(["subdir", "nonexistent.py"], tmp_dir)
            assert findings == []

    def test_clean_files_produce_zero_findings(self):
        with TemporaryDirectory() as tmp_dir:
            clean_file = Path(tmp_dir) / "clean.py"
            clean_file.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

            findings = scan_secrets(["clean.py"], tmp_dir)
            assert len(findings) == 0
