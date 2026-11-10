"""
Adversarial Challenger Test Suite for Milestone 2 (Task 1.3: Python Language Analyzer).
Stress-tests Feature 16 (Flake8 parsing and linting) and Feature 17 (Architecture AST import rules).
"""

import ast
import inspect
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from intelligence.analyzers.python.analyzer import PythonAnalyzer
from intelligence.evidence.models import CodeQualityEvidence, SeverityEnum


def sync_run(coro):
    """
    Run a coroutine synchronously by recursively stepping through yielded child coroutines.
    Avoids Windows IOCP event loop deadlocks during pytest execution.
    """
    try:
        val = None
        while True:
            sub = coro.send(val)
            val = sync_run(sub) if inspect.iscoroutine(sub) else sub
    except StopIteration as e:
        return e.value


# ==============================================================================
# FEATURE 17: Architecture AST Import Rules Stress Tests
# ==============================================================================


class TestFeature17AdversarialArchitectureRules:
    """Adversarial stress-testing of AST-based architecture import rules."""

    def test_forbidden_imports_in_comments_and_docstrings_zero_false_positives(self, tmp_path):
        """Comments, docstrings, and multiline strings must NEVER trigger import violations."""
        analyzer = PythonAnalyzer()

        clean_file = tmp_path / "api" / "service.py"
        clean_file.parent.mkdir(parents=True, exist_ok=True)
        clean_file.write_text(
            '"""\n'
            "API Service Module\n"
            "Architecture rules forbid: import database\n"
            "Do NOT do: from database import get_db\n"
            '"""\n'
            "# import database\n"
            "# from database.session import engine\n"
            "# from ..database import session\n"
            "\n"
            "def get_user_data():\n"
            "    '''\n"
            "    Docstring example:\n"
            "    from database import query\n"
            "    import database as db\n"
            "    '''\n"
            "    query = 'SELECT * FROM database WHERE id = 1'\n"
            '    sql = "from database import session is forbidden"\n'
            '    msg = f"Connecting to {query} without import database"\n'
            '    raw_sql = r"from database import table"\n'
            '    byte_str = b"import database"\n'
            "    return {'status': 'ok', 'sql': sql, 'msg': msg}\n",
            encoding="utf-8",
        )

        evidence = analyzer._architecture(["api/service.py"], str(tmp_path))
        assert len(evidence.layer_violations) == 0, (
            f"Expected 0 violations for comments and strings, got {evidence.layer_violations}"
        )

    def test_formatted_fstrings_with_nested_expressions_zero_false_positives(self, tmp_path):
        """Complex f-strings with nested formatting or expressions must not trigger AST violations."""
        analyzer = PythonAnalyzer()

        api_file = tmp_path / "api" / "format_check.py"
        api_file.parent.mkdir(parents=True, exist_ok=True)
        api_file.write_text(
            "target = 'database'\n"
            "query = f'import {target}'\n"
            "stmt = f'from {target} import session'\n"
            "nested = f'{f\"nested import {target}\"}'\n"
            "debug_log = f'Forbidden: from . import {target} in api'\n",
            encoding="utf-8",
        )

        evidence = analyzer._architecture(["api/format_check.py"], str(tmp_path))
        assert len(evidence.layer_violations) == 0

    def test_relative_imports_various_dot_depths(self):
        """Relative imports with varying dot depths (., .., ...) must be accurately detected."""
        # Single dot depth: from . import database
        tree1 = ast.parse("from . import database")
        assert PythonAnalyzer._ast_has_import_violation(tree1, "database") is True
        assert PythonAnalyzer._ast_has_import_violation(tree1, "models") is False

        # Single dot depth with subsegment: from .database import get_db
        tree1_sub = ast.parse("from .database import get_db")
        assert PythonAnalyzer._ast_has_import_violation(tree1_sub, "database") is True

        # Double dot depth: from .. import database
        tree2 = ast.parse("from .. import database")
        assert PythonAnalyzer._ast_has_import_violation(tree2, "database") is True
        assert PythonAnalyzer._ast_has_import_violation(tree2, "models") is False

        # Double dot depth with subsegment: from ..database.session import engine
        tree2_sub = ast.parse("from ..database.session import engine")
        assert PythonAnalyzer._ast_has_import_violation(tree2_sub, "database") is True

        # Triple dot depth: from ...sub import database
        tree3 = ast.parse("from ...sub import database")
        assert PythonAnalyzer._ast_has_import_violation(tree3, "database") is True
        assert PythonAnalyzer._ast_has_import_violation(tree3, "sub") is True
        assert PythonAnalyzer._ast_has_import_violation(tree3, "models") is False

        # Triple dot depth with subsegment: from ...database.models import User
        tree3_sub = ast.parse("from ...database.models import User")
        assert PythonAnalyzer._ast_has_import_violation(tree3_sub, "database") is True
        assert PythonAnalyzer._ast_has_import_violation(tree3_sub, "models") is True

        # Quadruple dot depth: from .... import database
        tree4 = ast.parse("from .... import database")
        assert PythonAnalyzer._ast_has_import_violation(tree4, "database") is True

        # Relative import: from ...sub import db (checking db)
        tree_db = ast.parse("from ...sub import db")
        assert PythonAnalyzer._ast_has_import_violation(tree_db, "db") is True
        assert PythonAnalyzer._ast_has_import_violation(tree_db, "sub.db") is True
        assert PythonAnalyzer._ast_has_import_violation(tree_db, "sub") is True

    def test_aliased_imports_detected(self):
        """Aliased imports (import x as y, from x import y as z) must still trigger violations."""
        # import app.database as my_db
        tree1 = ast.parse("import app.database as my_db")
        assert PythonAnalyzer._ast_has_import_violation(tree1, "database") is True

        # from app.database import get_db as db_conn
        tree2 = ast.parse("from app.database import get_db as db_conn")
        assert PythonAnalyzer._ast_has_import_violation(tree2, "database") is True

        # from . import database as db
        tree3 = ast.parse("from . import database as db")
        assert PythonAnalyzer._ast_has_import_violation(tree3, "database") is True

        # import database as db
        tree4 = ast.parse("import database as db")
        assert PythonAnalyzer._ast_has_import_violation(tree4, "database") is True

        # from routes import models as mdl
        tree5 = ast.parse("from routes import models as mdl")
        assert PythonAnalyzer._ast_has_import_violation(tree5, "models") is True

    def test_similar_directory_names_not_mistakenly_flagged(self, tmp_path):
        """Directories with similar prefix/suffix (my_api/, api_v2/, rapid_api/) must not match api/."""
        analyzer = PythonAnalyzer()

        # Files in similar-named directories importing database
        files = [
            "my_api/service.py",
            "api_v2/service.py",
            "src/rapid_api/service.py",
            "api_utils/service.py",
            "routes_v2/controller.py",
            "my_routes/controller.py",
        ]
        for f in files:
            p = tmp_path / f
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("import database\nfrom models import User\n", encoding="utf-8")

        # Files in actual layer directories
        actual_files = [
            "api/service.py",
            "routes/controller.py",
        ]
        for f in actual_files:
            p = tmp_path / f
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("import database\nfrom models import User\n", encoding="utf-8")

        evidence = analyzer._architecture(files + actual_files, str(tmp_path))

        flagged_files = {v["file"] for v in evidence.layer_violations}
        # Only actual_files should be flagged, not similar names
        assert "my_api/service.py" not in flagged_files
        assert "api_v2/service.py" not in flagged_files
        assert "src/rapid_api/service.py" not in flagged_files
        assert "api_utils/service.py" not in flagged_files
        assert "routes_v2/controller.py" not in flagged_files
        assert "my_routes/controller.py" not in flagged_files

        # Ensure genuine violations ARE flagged
        assert "api/service.py" in flagged_files
        assert "routes/controller.py" in flagged_files

    def test_matches_layer_boundary_semantics(self):
        """Boundary matching semantics for _matches_layer."""
        # Exact match
        assert PythonAnalyzer._matches_layer("api/sub/file.py", "api/") is True
        assert PythonAnalyzer._matches_layer("src/api/file.py", "api/") is True
        assert PythonAnalyzer._matches_layer("backend/v1/api/handlers/file.py", "api/") is True

        # Similar prefixes/suffixes should NOT match
        assert PythonAnalyzer._matches_layer("my_api/file.py", "api/") is False
        assert PythonAnalyzer._matches_layer("api_v2/file.py", "api/") is False
        assert PythonAnalyzer._matches_layer("rapid_api/file.py", "api/") is False
        assert PythonAnalyzer._matches_layer("api.py", "api/") is False
        assert PythonAnalyzer._matches_layer("src/api.py", "api/") is False

        # Windows backslashes
        assert PythonAnalyzer._matches_layer(r"src\api\file.py", "api/") is True
        assert PythonAnalyzer._matches_layer(r"my_api\file.py", "api/") is False

    def test_syntax_errors_empty_files_binary_content_graceful_handling(self, tmp_path):
        """Syntax errors, empty files, and binary content must be handled without crashing."""
        analyzer = PythonAnalyzer()

        # 1. Syntax error
        syntax_err_file = tmp_path / "api" / "syntax_err.py"
        syntax_err_file.parent.mkdir(parents=True, exist_ok=True)
        syntax_err_file.write_text("def broken_syntax(x, y:\n    return x +", encoding="utf-8")

        # 2. Completely empty file
        empty_file = tmp_path / "api" / "empty.py"
        empty_file.write_text("", encoding="utf-8")

        # 3. Binary file with null bytes
        binary_file = tmp_path / "api" / "binary.py"
        binary_file.write_bytes(b"\x00\x01\x02\xff\xfe\x00\x00\x50\x4b\x03\x04")

        # 4. Non-existent file
        non_existent = "api/non_existent.py"

        files = [
            "api/syntax_err.py",
            "api/empty.py",
            "api/binary.py",
            non_existent,
        ]

        # Should execute cleanly without raising any exception
        evidence = analyzer._architecture(files, str(tmp_path))
        assert len(evidence.layer_violations) == 0

    def test_subsequence_matching_edge_cases(self):
        """Contiguous subsequence matching edge cases."""
        # Empty inputs
        assert PythonAnalyzer._is_subsequence([], ["a", "b"]) is False
        assert PythonAnalyzer._is_subsequence(["a"], []) is False
        assert PythonAnalyzer._is_subsequence(["a", "b", "c"], ["a", "b"]) is False

        # Substring of word must NOT match (exact segment matching)
        assert PythonAnalyzer._is_subsequence(["database"], ["database_tools"]) is False
        assert PythonAnalyzer._is_subsequence(["database"], ["my_database"]) is False

        # Exact match
        assert PythonAnalyzer._is_subsequence(["database"], ["database"]) is True
        assert PythonAnalyzer._is_subsequence(["app", "database"], ["app", "database"]) is True

        # Non-contiguous should NOT match
        assert PythonAnalyzer._is_subsequence(["a", "c"], ["a", "b", "c"]) is False


# ==============================================================================
# FEATURE 16: Flake8 Linting & Regex Parsing Stress Tests
# ==============================================================================


class TestFeature16AdversarialFlake8Parsing:
    """Adversarial stress-testing of Flake8 regex and JSON output parsing."""

    def test_windows_drive_paths_and_paths_with_spaces(self):
        """Flake8 text parser must handle Windows drive letters and paths with spaces."""
        output = (
            r"M:\project\file.py:10:5: ASYNC101 use asyncio.sleep instead of time.sleep" "\n"
            r"C:\dir with spaces\test.py:10:5: ASYNC101 async function without await" "\n"
            r"D:\path\to\code.py:100: BLK100 Black would reformat this file" "\n"
            r"E:\some\nested\dir\file.py:1:1: RUF001 String contains ambiguous unicode" "\n"
            r"C:\project\main.py : 45 : 12 : TRY001 consider exception chaining" "\n"
            r"F:\repo\src\app.py:99:999: B950 line too long (105 > 100)" "\n"
            r"\\network\share\file.py:20:1: W503 line break before binary operator"
        )
        findings = PythonAnalyzer._parse_flake8(output, [])
        assert len(findings) == 7

        assert findings[0].file_path == r"M:\project\file.py"
        assert findings[0].line_number == 10
        assert findings[0].rule_id == "FLAKE8-ASYNC101"
        assert findings[0].message == "use asyncio.sleep instead of time.sleep"

        assert findings[1].file_path == r"C:\dir with spaces\test.py"
        assert findings[1].line_number == 10
        assert findings[1].rule_id == "FLAKE8-ASYNC101"

        assert findings[2].file_path == r"D:\path\to\code.py"
        assert findings[2].line_number == 100
        assert findings[2].rule_id == "FLAKE8-BLK100"

        assert findings[3].file_path == r"E:\some\nested\dir\file.py"
        assert findings[3].line_number == 1
        assert findings[3].rule_id == "FLAKE8-RUF001"

        assert findings[4].file_path == r"C:\project\main.py"
        assert findings[4].line_number == 45
        assert findings[4].rule_id == "FLAKE8-TRY001"

        assert findings[5].file_path == r"F:\repo\src\app.py"
        assert findings[5].line_number == 99
        assert findings[5].rule_id == "FLAKE8-B950"

        assert findings[6].file_path == r"\\network\share\file.py"
        assert findings[6].line_number == 20
        assert findings[6].rule_id == "FLAKE8-W503"

    def test_modern_multi_letter_error_codes(self):
        """Flake8 plugins with multi-letter codes (BLK, ASYNC, TRY, RUF, B, W, E, F)."""
        output = (
            "app/tasks.py:12:1: BLK100 Black would reformat this file\n"
            "app/tasks.py:15:4: ASYNC101 Async call inside sync function\n"
            "app/errors.py:22:9: TRY001 Exception not chained\n"
            "app/utils.py:5:1: RUF001 Ambiguous character\n"
            "app/style.py:80:1: B950 Line too long\n"
            "app/style.py:85:1: W503 Line break before binary operator\n"
            "app/syntax.py:1:1: E999 SyntaxError\n"
            "app/syntax.py:10:1: F401 Unused import\n"
        )
        findings = PythonAnalyzer._parse_flake8(output, [])
        assert len(findings) == 8

        # Check rule IDs
        rule_ids = [f.rule_id for f in findings]
        assert rule_ids == [
            "FLAKE8-BLK100",
            "FLAKE8-ASYNC101",
            "FLAKE8-TRY001",
            "FLAKE8-RUF001",
            "FLAKE8-B950",
            "FLAKE8-W503",
            "FLAKE8-E999",
            "FLAKE8-F401",
        ]

        # Check severity mappings: E and F are HIGH, others are MEDIUM
        assert findings[6].severity == SeverityEnum.HIGH  # E999
        assert findings[7].severity == SeverityEnum.HIGH  # F401
        assert findings[0].severity == SeverityEnum.MEDIUM  # BLK100
        assert findings[1].severity == SeverityEnum.MEDIUM  # ASYNC101
        assert findings[2].severity == SeverityEnum.MEDIUM  # TRY001
        assert findings[4].severity == SeverityEnum.MEDIUM  # B950
        assert findings[5].severity == SeverityEnum.MEDIUM  # W503

        # Check category mappings: E, F, W are syntax; others are maintainability
        assert findings[5].category == "syntax"  # W503
        assert findings[6].category == "syntax"  # E999
        assert findings[7].category == "syntax"  # F401
        assert findings[0].category == "maintainability"  # BLK100
        assert findings[1].category == "maintainability"  # ASYNC101

    def test_flake8_json_empty_and_nested_dictionaries(self):
        """JSON output from flake8-json: empty dicts, empty lists, nested structures."""
        # Empty list
        assert PythonAnalyzer._parse_flake8("[]", []) == []

        # Empty dict
        assert PythonAnalyzer._parse_flake8("{}", []) == []

        # Dict with empty issues list
        assert PythonAnalyzer._parse_flake8('{"src/app.py": []}', []) == []

        # Dict with multiple files and issues
        json_dict = (
            '{\n'
            '  "src/app.py": [\n'
            '    {"code": "E501", "line_number": 42, "text": "line too long"},\n'
            '    {"code": "F401", "line_number": 3, "text": "os imported but unused"}\n'
            '  ],\n'
            '  "src/util.py": [\n'
            '    {"code": "ASYNC101", "line": 15, "message": "unawaited coroutine"}\n'
            '  ]\n'
            '}'
        )
        findings = PythonAnalyzer._parse_flake8(json_dict, [])
        assert len(findings) == 3
        paths = [f.file_path for f in findings]
        assert "src/app.py" in paths
        assert "src/util.py" in paths

    def test_flake8_json_malformed_and_edge_case_payloads(self):
        """JSON output with malformed syntax, unexpected schemas, or bad values."""
        # Malformed JSON falling back cleanly without crash
        assert PythonAnalyzer._parse_flake8('{"unclosed": [', []) == []

        # Dict with non-list value
        assert PythonAnalyzer._parse_flake8('{"src/app.py": "not a list"}', []) == []

        # Dict with non-dict items in issue list
        assert PythonAnalyzer._parse_flake8('{"src/app.py": [null, 123, "str"]}', []) == []

        # List with non-dict items
        assert PythonAnalyzer._parse_flake8('[null, 123, "str"]', []) == []

        # List with empty dict items (default values applied)
        findings = PythonAnalyzer._parse_flake8('[{}]', [])
        assert len(findings) == 1
        assert findings[0].rule_id == "FLAKE8-E000"
        assert findings[0].line_number == 1

        # Dict with issue with missing code
        findings_no_code = PythonAnalyzer._parse_flake8('{"src/app.py": [{"line_number": 5}]}', [])
        assert len(findings_no_code) == 1
        assert findings_no_code[0].rule_id == "FLAKE8-E000"

    def test_flake8_json_whitespace_code_adversarial_edge_case(self):
        """
        Adversarial Edge Case Finding:
        When code is whitespace-only (e.g. '   '), str('   ' or 'E000').strip() produces ''
        causing code[0] to raise IndexError because IndexError is not in the handled exceptions.
        This test documents the empirical reproduction of this boundary behavior.
        """
        with pytest.raises(IndexError):
            PythonAnalyzer._parse_flake8('{"src/app.py": [{"code": "   "}]}', [])

        with pytest.raises(IndexError):
            PythonAnalyzer._parse_flake8('[{"code": "   "}]', [])

    def test_flake8_clean_stdout_produces_zero_findings_no_quality_degradation(self):
        """Clean Flake8 output ("") must produce 0 findings and NOT degrade quality."""
        # Empty string
        assert PythonAnalyzer._parse_flake8("", []) == []
        # Whitespace-only string
        assert PythonAnalyzer._parse_flake8("   \n\t  ", []) == []

        # Test full _lint execution when flake8 returns clean ""
        py_mod = sys.modules[PythonAnalyzer.__module__]
        analyzer = PythonAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-repo", primary_language="python")

        async def fake_run_clean(cmd, cwd=None):
            return ""

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: t == "flake8"):
            with patch.object(py_mod, "_run", fake_run_clean):
                findings = sync_run(analyzer._lint(["file.py"], ["/repo/file.py"], "/repo", evidence))

                assert findings == []
                assert "flake8" in evidence.tools_executed
                assert "ast-syntax-fallback" not in evidence.tools_executed
                assert evidence.analysis_quality.confidence == 1.0
                assert len(evidence.analysis_quality.degraded_dimensions) == 0

    def test_flake8_failure_degrades_quality_and_falls_back_to_ast(self):
        """When Flake8 execution fails (returns None), quality degrades and AST fallback executes."""
        py_mod = sys.modules[PythonAnalyzer.__module__]
        analyzer = PythonAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-repo", primary_language="python")

        async def fake_run_none(cmd, cwd=None):
            return None

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: t == "flake8"):
            with patch.object(py_mod, "_run", fake_run_none):
                with patch.object(analyzer, "_ast_syntax_check", return_value=[]):
                    findings = sync_run(analyzer._lint(["file.py"], ["/repo/file.py"], "/repo", evidence))

                    assert "ast-syntax-fallback" in evidence.tools_executed
                    assert evidence.analysis_quality.confidence < 1.0
                    assert any("flake8-failed" in s for s in evidence.tools_skipped)
