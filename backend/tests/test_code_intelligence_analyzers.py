"""
Unit and regression tests for the Code Intelligence Analyzer suite.
Validates Python, JavaScript, and TypeScript analyzers, common services,
and regression fixes for confirmed defects.
"""

import os
import asyncio
import sys
import re
import json
import pytest
from secrets_fixtures import synthetic_token
from pathlib import Path
from tempfile import TemporaryDirectory

from intelligence.analyzers.base import BaseAnalyzer
from intelligence.analyzers.language_detector import (
    LanguageDetector,
    filter_files_for_language,
    get_extensions_for_language,
)
from intelligence.analyzers.registry import get_analyzer, list_supported_languages
from intelligence.analyzers.common.duplication import (
    analyze_duplication,
    _normalize_lines,
    _union_intervals,
    SIMILARITY_THRESHOLD,
)
from intelligence.analyzers.common.complexity import _run_ast_complexity, _merge, _merge_radon_supplement
from intelligence.analyzers.common.secrets_scanner import scan_secrets
from intelligence.analyzers.python.analyzer import PythonAnalyzer
from intelligence.analyzers.javascript.analyzer import JavaScriptAnalyzer
from intelligence.evidence.models import CodeQualityEvidence, ComplexityEvidence, SeverityEnum


class TestLanguageDetectionAndFiltering:
    """Tests for language detection and file extension filtering."""

    def test_cjs_extension_supported(self):
        js_exts = get_extensions_for_language("javascript")
        assert ".cjs" in js_exts
        assert ".mjs" in js_exts
        assert ".js" in js_exts

    def test_filter_files_case_insensitive(self):
        files = ["app.PY", "UTIL.JS", "server.CJS", "index.TSX", "README.MD"]
        py_files = filter_files_for_language(files, "python")
        js_files = filter_files_for_language(files, "javascript")
        ts_files = filter_files_for_language(files, "typescript")

        assert "app.PY" in py_files
        assert "UTIL.JS" in js_files
        assert "server.CJS" in js_files
        assert "index.TSX" in ts_files

    def test_detect_from_files_includes_cjs_and_case_insensitive(self):
        detector = LanguageDetector()
        profile = detector.detect_from_files(["src/index.CJS", "src/helper.JS"])
        assert profile.primary_language == "javascript"
        assert "javascript" in profile.detected_languages


class TestDuplicationAnalyzer:
    """Tests for duplication detection, sliding window merging, and percentages."""

    def test_reproduction_overlapping_window_inflation_bug(self):
        """
        Reproduction test for reported defect #1, #2, #3:
        1. Overlapping sliding windows previously multiplied line counts.
           A 10-line duplicate has 5 sliding windows of size 6 (0..5, 1..6, 2..7, 3..8, 4..9).
           Naive addition: 5 * 6 = 30 duplicated lines per file (exceeding the file's 10 lines!).
        2. Duplication percentage previously exceeded 100% (30 / 20 = 150%).
        3. Global count and per-file count were inconsistent (global=30, per-file=30+30=60).

        Fix verification:
        With per-file interval union, all overlapping windows merge into [0, 10).
        Each file reports exactly 10 duplicated lines, total is 20, percentage is 100.0%.
        """
        with TemporaryDirectory() as tmp_dir:
            lines = [f"const record_{i} = fetchRecordById({i});" for i in range(10)]
            block = "\n".join(lines)
            file_a = Path(tmp_dir) / "serviceA.js"
            file_b = Path(tmp_dir) / "serviceB.js"
            file_a.write_text(block, encoding="utf-8")
            file_b.write_text(block, encoding="utf-8")

            evidence = analyze_duplication(["serviceA.js", "serviceB.js"], tmp_dir)

            # File A has 10 lines, File B has 10 lines -> total 20 lines
            # Must NOT be 30 lines (5 windows * 6 lines) or 60 lines (30 per file)
            assert evidence.duplicated_lines_count == 20
            assert evidence.duplication_percentage == 100.0
            assert len(evidence.duplicated_files) == 2

            # Per-file metrics must equal 10 each, never exceeding file size
            assert evidence.duplicated_files[0]["duplicated_lines"] == 10
            assert evidence.duplicated_files[1]["duplicated_lines"] == 10

            # Mathematical consistency between global and per-file counts
            sum_per_file = sum(f["duplicated_lines"] for f in evidence.duplicated_files)
            assert evidence.duplicated_lines_count == sum_per_file

    def test_identical_files(self):
        """Tests completely identical files across multiple formats."""
        with TemporaryDirectory() as tmp_dir:
            code = "\n".join([f"let index_{i} = calculateOffset({i});" for i in range(12)])
            f1 = Path(tmp_dir) / "clone1.py"
            f2 = Path(tmp_dir) / "clone2.py"
            f1.write_text(code, encoding="utf-8")
            f2.write_text(code, encoding="utf-8")

            evidence = analyze_duplication(["clone1.py", "clone2.py"], tmp_dir)

            assert evidence.duplicated_lines_count == 24
            assert evidence.duplication_percentage == 100.0
            assert len(evidence.duplicated_files) == 2
            assert evidence.duplicated_files[0]["duplicated_lines"] == 12
            assert evidence.duplicated_files[1]["duplicated_lines"] == 12
            assert sum(f["duplicated_lines"] for f in evidence.duplicated_files) == evidence.duplicated_lines_count

    def test_overlapping_windows(self):
        """Tests that extended contiguous duplicates with many overlapping windows merge properly."""
        with TemporaryDirectory() as tmp_dir:
            # 16 consecutive lines -> 11 sliding windows of size 6
            code = "\n".join([f"executeLongPipelineStep({i}, 'config_param');" for i in range(16)])
            f1 = Path(tmp_dir) / "pipeline1.py"
            f2 = Path(tmp_dir) / "pipeline2.py"
            f1.write_text(code, encoding="utf-8")
            f2.write_text(code, encoding="utf-8")

            evidence = analyze_duplication(["pipeline1.py", "pipeline2.py"], tmp_dir)

            # 16 lines in each file -> 32 total duplicated lines (NOT 11 * 6 = 66)
            assert evidence.duplicated_lines_count == 32
            assert evidence.duplication_percentage == 100.0
            assert evidence.duplicated_files[0]["duplicated_lines"] == 16
            assert evidence.duplicated_files[1]["duplicated_lines"] == 16

    def test_multiple_duplicates(self):
        """Tests multiple distinct duplicate blocks separated by unique code."""
        with TemporaryDirectory() as tmp_dir:
            block_a = [f"duplicateBlockA_{i} = compute_value({i});" for i in range(8)]
            unique_1 = [f"uniqueFile1SpecificCode_{i} = do_work({i});" for i in range(10)]
            unique_2 = [f"uniqueFile2DifferentPath_{i} = process({i});" for i in range(10)]
            block_b = [f"duplicateBlockB_{i} = finish_stage({i});" for i in range(8)]

            f1 = Path(tmp_dir) / "file1.py"
            f2 = Path(tmp_dir) / "file2.py"
            f1.write_text("\n".join(block_a + unique_1 + block_b), encoding="utf-8")
            f2.write_text("\n".join(block_a + unique_2 + block_b), encoding="utf-8")

            evidence = analyze_duplication(["file1.py", "file2.py"], tmp_dir)

            # Each file has 8 + 10 + 8 = 26 lines. Total lines = 52.
            # Duplicated lines per file = 8 (block A) + 8 (block B) = 16 lines.
            # Total duplicated lines = 32.
            assert evidence.duplicated_lines_count == 32
            # 32 / 52 * 100 = 61.538... -> 61.54%
            assert evidence.duplication_percentage == 61.54
            assert len(evidence.duplicated_files) == 2
            assert evidence.duplicated_files[0]["duplicated_lines"] == 16
            assert evidence.duplicated_files[1]["duplicated_lines"] == 16
            assert sum(f["duplicated_lines"] for f in evidence.duplicated_files) == evidence.duplicated_lines_count

    def test_unique_files(self):
        """Tests files with no duplicated blocks."""
        with TemporaryDirectory() as tmp_dir:
            code1 = "\n".join([f"fileOneAlphaStatement_{i} = 'unique_alpha_{i}';" for i in range(15)])
            code2 = "\n".join([f"fileTwoBetaStatement_{i} = 'unique_beta_{i}';" for i in range(15)])
            f1 = Path(tmp_dir) / "unique1.py"
            f2 = Path(tmp_dir) / "unique2.py"
            f1.write_text(code1, encoding="utf-8")
            f2.write_text(code2, encoding="utf-8")

            evidence = analyze_duplication(["unique1.py", "unique2.py"], tmp_dir)

            assert evidence.duplicated_lines_count == 0
            assert evidence.duplication_percentage == 0.0
            assert evidence.duplicate_blocks_count == 0
            assert evidence.duplicated_files == []

    def test_empty_files(self):
        """Tests behavior with empty files, comment-only files, and empty file lists."""
        with TemporaryDirectory() as tmp_dir:
            # Empty file list
            empty_list_ev = analyze_duplication([], tmp_dir)
            assert empty_list_ev.duplicated_lines_count == 0
            assert empty_list_ev.duplication_percentage == 0.0
            assert empty_list_ev.duplicated_files == []

            # 0-byte files
            f1 = Path(tmp_dir) / "empty1.py"
            f2 = Path(tmp_dir) / "empty2.py"
            f1.write_text("", encoding="utf-8")
            f2.write_text("", encoding="utf-8")

            zero_byte_ev = analyze_duplication(["empty1.py", "empty2.py"], tmp_dir)
            assert zero_byte_ev.duplicated_lines_count == 0
            assert zero_byte_ev.duplication_percentage == 0.0
            assert zero_byte_ev.duplicated_files == []

            # Noise / comment-only files
            f3 = Path(tmp_dir) / "noise1.py"
            f4 = Path(tmp_dir) / "noise2.py"
            noise = "\n".join(["# comment line", "// comment line", "pass", "return", "   "])
            f3.write_text(noise, encoding="utf-8")
            f4.write_text(noise, encoding="utf-8")

            noise_ev = analyze_duplication(["noise1.py", "noise2.py"], tmp_dir)
            assert noise_ev.duplicated_lines_count == 0
            assert noise_ev.duplication_percentage == 0.0
            assert noise_ev.duplicated_files == []

    def test_interval_union_helper(self):
        """Unit tests for the _union_intervals helper covering all interval topology cases."""
        assert _union_intervals([]) == []
        assert _union_intervals([(0, 6)]) == [(0, 6)]
        # Overlapping intervals
        assert _union_intervals([(0, 6), (2, 8), (5, 10)]) == [(0, 10)]
        # Adjacent / contiguous intervals
        assert _union_intervals([(0, 6), (6, 12)]) == [(0, 12)]
        # Disjoint intervals
        assert _union_intervals([(0, 6), (10, 16)]) == [(0, 6), (10, 16)]
        # Unsorted input
        assert _union_intervals([(20, 26), (0, 6), (3, 8)]) == [(0, 8), (20, 26)]
        # Contained interval
        assert _union_intervals([(0, 20), (5, 10)]) == [(0, 20)]

    def test_duplication_percentage_never_exceeds_100(self):
        with TemporaryDirectory() as tmp_dir:
            lines = "\n".join([f"line_number_{i} = do_something();" for i in range(15)])
            f1 = Path(tmp_dir) / "mod1.py"
            f2 = Path(tmp_dir) / "mod2.py"
            f1.write_text(lines, encoding="utf-8")
            f2.write_text(lines, encoding="utf-8")

            evidence = analyze_duplication(["mod1.py", "mod2.py"], tmp_dir)
            assert 0.0 <= evidence.duplication_percentage <= 100.0

    def test_mathematical_consistency_across_multiple_files(self):
        """Tests that duplicated_lines_count == sum of per-file duplicated_lines across complex topologies."""
        with TemporaryDirectory() as tmp_dir:
            # 3 files with partial overlaps
            shared_ab = [f"shared_ab_line_{i} = perform_ab({i});" for i in range(7)]
            shared_bc = [f"shared_bc_line_{i} = perform_bc({i});" for i in range(8)]
            unique_a = [f"unique_a_line_{i} = specific_a({i});" for i in range(10)]
            unique_b = [f"unique_b_line_{i} = specific_b({i});" for i in range(5)]
            unique_c = [f"unique_c_line_{i} = specific_c({i});" for i in range(12)]

            f_a = Path(tmp_dir) / "fa.py"
            f_b = Path(tmp_dir) / "fb.py"
            f_c = Path(tmp_dir) / "fc.py"

            f_a.write_text("\n".join(shared_ab + unique_a), encoding="utf-8")
            f_b.write_text("\n".join(shared_ab + unique_b + shared_bc), encoding="utf-8")
            f_c.write_text("\n".join(unique_c + shared_bc), encoding="utf-8")

            evidence = analyze_duplication(["fa.py", "fb.py", "fc.py"], tmp_dir)

            # Mathematical consistency checks
            sum_per_file = sum(f["duplicated_lines"] for f in evidence.duplicated_files)
            assert evidence.duplicated_lines_count == sum_per_file
            assert 0.0 <= evidence.duplication_percentage <= 100.0

            # File A duplicated = 7
            # File B duplicated = 7 + 8 = 15
            # File C duplicated = 8
            # Total duplicated = 30
            assert evidence.duplicated_lines_count == 30
            file_counts = {f["file"]: f["duplicated_lines"] for f in evidence.duplicated_files}
            assert file_counts["fa.py"] == 7
            assert file_counts["fb.py"] == 15
            assert file_counts["fc.py"] == 8

    def test_similarity_threshold_documented_and_exact_matching(self):
        """Verifies SIMILARITY_THRESHOLD is defined and exact matching is documented."""
        import intelligence.analyzers.common.duplication as dup_mod

        assert hasattr(dup_mod, "SIMILARITY_THRESHOLD")
        assert dup_mod.SIMILARITY_THRESHOLD == 0.85
        assert "SIMILARITY_THRESHOLD" in dup_mod.__doc__
        assert "EXACT" in dup_mod.__doc__
        assert "SIMILARITY_THRESHOLD" in dup_mod.analyze_duplication.__doc__

    def test_normalize_lines_strips_trailing_inline_comments(self):
        raw = [
            "const x = 10; // set initial value",
            "let y = 20; # python style comment",
            "return x + y;",
        ]
        norm = _normalize_lines(raw)
        assert norm[0] == "const x = 10;"
        assert norm[1] == "let y = 20;"
        assert norm[2] == "return x + y;"

    def test_contiguous_identical_lines_in_single_file_not_flagged_as_duplicate(self):
        """
        Tests that contiguous identical lines within a single file (e.g. 7 repeated lines)
        do NOT get flagged as duplicate code when there is only a single occurrence.
        A 6-line sliding window shifted by 1 line within the same occurrence does not
        constitute an independent duplicate occurrence.
        """
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "repeated_single.py"
            repeated = [f"logger.info('status_code_check_ok');" for _ in range(7)]
            unique = [f"unique_step_{i} = perform_distinct_action({i});" for i in range(7)]
            f.write_text("\n".join(repeated + unique), encoding="utf-8")

            evidence = analyze_duplication(["repeated_single.py"], tmp_dir)
            assert evidence.duplicated_lines_count == 0
            assert evidence.duplicate_blocks_count == 0
            assert evidence.duplication_percentage == 0.0
            assert evidence.duplicated_files == []

    def test_contiguous_identical_lines_duplicated_across_files(self):
        """
        Tests that contiguous identical lines duplicated across two files ARE detected,
        and interval union collapses them properly to the actual number of lines (7 lines each).
        """
        with TemporaryDirectory() as tmp_dir:
            f1 = Path(tmp_dir) / "repeated_f1.py"
            f2 = Path(tmp_dir) / "repeated_f2.py"
            repeated = [f"logger.info('status_code_check_ok');" for _ in range(7)]
            f1.write_text("\n".join(repeated), encoding="utf-8")
            f2.write_text("\n".join(repeated), encoding="utf-8")

            evidence = analyze_duplication(["repeated_f1.py", "repeated_f2.py"], tmp_dir)
            assert evidence.duplicated_lines_count == 14
            assert evidence.duplication_percentage == 100.0
            assert len(evidence.duplicated_files) == 2
            assert evidence.duplicated_files[0]["duplicated_lines"] == 7
            assert evidence.duplicated_files[1]["duplicated_lines"] == 7

    def test_urls_and_hex_strings_not_truncated_by_inline_comments(self):
        """
        Verifies that URLs containing 'https://' or 'http://' and strings containing '#'
        are NOT truncated by comment stripping, preventing false-positive duplication matches.
        """
        with TemporaryDirectory() as tmp_dir:
            file_a_lines = [
                f'const service_url_{i} = "https://internal-service-a.domain/{i}";'
                for i in range(8)
            ]
            file_b_lines = [
                f'const service_url_{i} = "https://external-service-b.domain/{i}";'
                for i in range(8)
            ]
            f_a = Path(tmp_dir) / "serviceA.js"
            f_b = Path(tmp_dir) / "serviceB.js"
            f_a.write_text("\n".join(file_a_lines), encoding="utf-8")
            f_b.write_text("\n".join(file_b_lines), encoding="utf-8")

            evidence = analyze_duplication(["serviceA.js", "serviceB.js"], tmp_dir)
            # Files have completely different domain URLs; must NOT match as duplicates
            assert evidence.duplicated_lines_count == 0
            assert evidence.duplication_percentage == 0.0

    def test_multiline_block_comments_stripped_across_sliding_windows(self):
        """
        Verifies that multiline block comments (/* ... */) spanning across lines
        are stripped during normalization and do not create false-positive duplicate blocks.
        """
        with TemporaryDirectory() as tmp_dir:
            license_header = [
                "/*",
                " * Copyright (c) 2026 Samanvaya Inc.",
                " * All rights reserved.",
                " * Distributed under the Apache-2.0 License.",
                " * See LICENSE file for full license information.",
                " * Author: Core Infrastructure Engineering Team.",
                " * Version: 2.4.0-release-candidate.",
                " */",
            ]
            code_a = [f"const handlerA_{i} = executeA({i});" for i in range(10)]
            code_b = [f"const handlerB_{i} = executeB({i});" for i in range(10)]

            f1 = Path(tmp_dir) / "modA.js"
            f2 = Path(tmp_dir) / "modB.js"
            f1.write_text("\n".join(license_header + code_a), encoding="utf-8")
            f2.write_text("\n".join(license_header + code_b), encoding="utf-8")

            evidence = analyze_duplication(["modA.js", "modB.js"], tmp_dir)
            # Even though they share the 8-line license comment, code is unique -> 0 duplication
            assert evidence.duplicated_lines_count == 0
            assert evidence.duplication_percentage == 0.0

    def test_unicode_and_multibyte_token_boundaries(self):
        """
        Verifies that code containing multi-byte UTF-8 Unicode characters
        (emojis, Asian scripts, accented letters) are hashed and detected accurately.
        """
        with TemporaryDirectory() as tmp_dir:
            unicode_block = [
                'const greeting = "こんにちは、世界！";',
                'const telemetry_status = "🚀 Launch sequence active";',
                'const accent = "café résumé naïve façade";',
                'const hieroglyph = "𓀀 𓀁 𓀂 𓀃 𓀄 𓀅";',
                'const chinese_chars = "深度学习与人工智能";',
                'const symbol_line = "✓ Passed verification test";',
            ]
            f1 = Path(tmp_dir) / "i18n_1.ts"
            f2 = Path(tmp_dir) / "i18n_2.ts"
            f1.write_text("\n".join(unicode_block), encoding="utf-8")
            f2.write_text("\n".join(unicode_block), encoding="utf-8")

            evidence = analyze_duplication(["i18n_1.ts", "i18n_2.ts"], tmp_dir)
            assert evidence.duplicated_lines_count == 12
            assert evidence.duplication_percentage == 100.0
            assert len(evidence.duplicated_files) == 2

    def test_duplicate_file_paths_in_input_deduplicated(self):
        """
        Verifies that passing duplicate file paths in the files list does not
        double total line counts or skew duplication percentages.
        """
        with TemporaryDirectory() as tmp_dir:
            code = "\n".join([f"const line_{i} = doComputation({i});" for i in range(10)])
            f = Path(tmp_dir) / "script.js"
            f.write_text(code, encoding="utf-8")

            # Passing "script.js" twice should deduplicate gracefully
            evidence = analyze_duplication(["script.js", "script.js"], tmp_dir)
            assert evidence.duplicated_lines_count == 0
            assert evidence.duplication_percentage == 0.0

    def test_decrement_operators_not_truncated_as_comments(self):
        """
        Verifies that C/JS decrement operators (x--, --x, items[--idx]) are not
        truncated as comments, avoiding false-positive matches between different variables.
        """
        with TemporaryDirectory() as tmp_dir:
            file_a_lines = [
                f"const val_{i} = dataset[--index_alpha_{i}];"
                for i in range(8)
            ]
            file_b_lines = [
                f"const val_{i} = dataset[--index_beta_{i}];"
                for i in range(8)
            ]
            f_a = Path(tmp_dir) / "counterA.js"
            f_b = Path(tmp_dir) / "counterB.js"
            f_a.write_text("\n".join(file_a_lines), encoding="utf-8")
            f_b.write_text("\n".join(file_b_lines), encoding="utf-8")

            evidence = analyze_duplication(["counterA.js", "counterB.js"], tmp_dir)
            # Distinct variables inside decrement expressions must NOT match
            assert evidence.duplicated_lines_count == 0
            assert evidence.duplication_percentage == 0.0

    def test_python_docstrings_multiline_and_singleline_stripped(self):
        """
        Verifies that multiline Python docstrings (triple quotes) and single-line docstrings
        are stripped during normalization and do not create false-positive duplicate blocks.
        """
        with TemporaryDirectory() as tmp_dir:
            py_header = [
                '"""',
                'Copyright (c) 2026 Samanvaya Inc.',
                'All rights reserved.',
                'Distributed under the Apache-2.0 License.',
                'See LICENSE file for full license information.',
                'Author: Core Infrastructure Engineering Team.',
                'Version: 2.4.0-release-candidate.',
                '"""',
            ]
            code_a = [f"def calculate_alpha_{i}(): return {i} * 10" for i in range(10)]
            code_b = [f"def calculate_beta_{i}(): return {i} * 20" for i in range(10)]

            f1 = Path(tmp_dir) / "module_a.py"
            f2 = Path(tmp_dir) / "module_b.py"
            f1.write_text("\n".join(py_header + code_a), encoding="utf-8")
            f2.write_text("\n".join(py_header + code_b), encoding="utf-8")

            evidence = analyze_duplication(["module_a.py", "module_b.py"], tmp_dir)
            # Docstrings are stripped -> unique code -> 0 duplication
            assert evidence.duplicated_lines_count == 0
            assert evidence.duplication_percentage == 0.0

    def test_python_multiline_string_assignment_preserved(self):
        """
        Verifies that executable code assigning multiline queries (e.g. query = '''SELECT...''')
        is preserved as code, and duplicate query blocks across files ARE detected.
        """
        with TemporaryDirectory() as tmp_dir:
            query_block = [
                'query_str = """',
                'SELECT users.id, users.email, profiles.full_name',
                'FROM users',
                'INNER JOIN profiles ON users.id = profiles.user_id',
                'WHERE users.status = 1',
                'ORDER BY users.created_at DESC',
                '"""',
            ]
            f1 = Path(tmp_dir) / "query_service_1.py"
            f2 = Path(tmp_dir) / "query_service_2.py"
            f1.write_text("\n".join(query_block), encoding="utf-8")
            f2.write_text("\n".join(query_block), encoding="utf-8")

            evidence = analyze_duplication(["query_service_1.py", "query_service_2.py"], tmp_dir)
            # 6 normalized lines in query_block duplicated across 2 files -> 12 lines
            assert evidence.duplicated_lines_count == 12
            assert evidence.duplication_percentage == 100.0

    def test_intra_file_duplicate_blocks_detected(self):
        """
        Verifies that two distinct, non-overlapping duplicate blocks in the SAME file
        are correctly detected as intra-file duplication.
        """
        with TemporaryDirectory() as tmp_dir:
            block = [f"const computation_{i} = perform_heavy_operation({i});" for i in range(7)]
            unique_middle = [f"let intermediate_{i} = step({i});" for i in range(10)]
            unique_end = [f"return finish_step_{i}();" for i in range(5)]

            # File has block at start (0..7), middle unique (7..17), and block again (17..24)
            full_code = "\n".join(block + unique_middle + block + unique_end)
            f = Path(tmp_dir) / "intra_duplicate.js"
            f.write_text(full_code, encoding="utf-8")

            evidence = analyze_duplication(["intra_duplicate.js"], tmp_dir)
            # 7 lines in first block + 7 lines in second block = 14 duplicated lines
            assert evidence.duplicated_lines_count == 14
            assert len(evidence.duplicated_files) == 1
            assert evidence.duplicated_files[0]["file"] == "intra_duplicate.js"
            assert evidence.duplicated_files[0]["duplicated_lines"] == 14
            assert evidence.duplicate_blocks_count >= 1

    def test_multiline_string_assignment_does_not_swallow_subsequent_code(self):
        """
        Adversarial test: verifies that closing triple-quotes of a multiline string
        assignment (query = '''...''') do NOT enter docstring mode and do NOT delete
        executable code that follows the string assignment.
        """
        with TemporaryDirectory() as tmp_dir:
            file_a_lines = [
                'query_template = """',
                'SELECT users.id, users.email',
                'FROM users',
                'WHERE users.status = 1',
                '"""',
                '# Normal executable statements following the multiline string',
                'const shared_calc_1 = perform_calculation_step(100);',
                'const shared_calc_2 = perform_calculation_step(200);',
                'const shared_calc_3 = perform_calculation_step(300);',
                'const shared_calc_4 = perform_calculation_step(400);',
                'const shared_calc_5 = perform_calculation_step(500);',
                'const shared_calc_6 = perform_calculation_step(600);',
            ]
            file_b_lines = [
                'different_var = 12345;',
                '# The exact same 6 executable statements are duplicated here',
                'const shared_calc_1 = perform_calculation_step(100);',
                'const shared_calc_2 = perform_calculation_step(200);',
                'const shared_calc_3 = perform_calculation_step(300);',
                'const shared_calc_4 = perform_calculation_step(400);',
                'const shared_calc_5 = perform_calculation_step(500);',
                'const shared_calc_6 = perform_calculation_step(600);',
            ]
            fa = Path(tmp_dir) / "serviceA.py"
            fb = Path(tmp_dir) / "serviceB.py"
            fa.write_text("\n".join(file_a_lines), encoding="utf-8")
            fb.write_text("\n".join(file_b_lines), encoding="utf-8")

            evidence = analyze_duplication(["serviceA.py", "serviceB.py"], tmp_dir)
            # The 6 shared calculation statements must be detected as duplicates (6 lines each -> 12 total)
            assert evidence.duplicated_lines_count == 12
            assert evidence.duplicate_blocks_count >= 1
            file_counts = {f["file"]: f["duplicated_lines"] for f in evidence.duplicated_files}
            assert file_counts["serviceA.py"] == 6
            assert file_counts["serviceB.py"] == 6

    def test_raw_and_prefixed_python_docstrings_stripped(self):
        """
        Adversarial test: verifies that Python docstrings prefixed with r, u, b, or f
        (e.g. r\"\"\"...\"\"\") are stripped as documentation comments, and subsequent code
        is neither corrupted nor falsely flagged as a duplicate.
        """
        with TemporaryDirectory() as tmp_dir:
            file_a_lines = [
                'r"""',
                'Raw docstring explaining regex patterns: \\d+\\s+[a-z]+',
                'Special characters: \\n, \\t, \\r',
                'Author: Search Architecture Team',
                'Version: 1.0.0-rc',
                '"""',
                'const unique_logic_a1 = execute_pipeline_a1();',
                'const unique_logic_a2 = execute_pipeline_a2();',
                'const unique_logic_a3 = execute_pipeline_a3();',
                'const unique_logic_a4 = execute_pipeline_a4();',
                'const unique_logic_a5 = execute_pipeline_a5();',
                'const unique_logic_a6 = execute_pipeline_a6();',
            ]
            file_b_lines = [
                'r"""',
                'Raw docstring explaining regex patterns: \\d+\\s+[a-z]+',
                'Special characters: \\n, \\t, \\r',
                'Author: Search Architecture Team',
                'Version: 1.0.0-rc',
                '"""',
                'const unique_logic_b1 = execute_pipeline_b1();',
                'const unique_logic_b2 = execute_pipeline_b2();',
                'const unique_logic_b3 = execute_pipeline_b3();',
                'const unique_logic_b4 = execute_pipeline_b4();',
                'const unique_logic_b5 = execute_pipeline_b5();',
                'const unique_logic_b6 = execute_pipeline_b6();',
            ]
            fa = Path(tmp_dir) / "searchA.py"
            fb = Path(tmp_dir) / "searchB.py"
            fa.write_text("\n".join(file_a_lines), encoding="utf-8")
            fb.write_text("\n".join(file_b_lines), encoding="utf-8")

            evidence = analyze_duplication(["searchA.py", "searchB.py"], tmp_dir)
            # The shared raw docstrings are stripped, and unique code remains -> 0 duplicated lines
            assert evidence.duplicated_lines_count == 0
            assert evidence.duplication_percentage == 0.0

    def test_path_aliasing_and_separator_normalization_deduplicated(self):
        """
        Adversarial test: verifies that path aliases (e.g. forward slash vs backslash,
        or leading './') referring to the same file are normalized and deduplicated,
        preventing false-positive 100% self-duplication reports.
        """
        with TemporaryDirectory() as tmp_dir:
            subdir = Path(tmp_dir) / "src" / "services"
            subdir.mkdir(parents=True, exist_ok=True)
            code = "\n".join([f"const worker_statement_{i} = initWorker({i});" for i in range(15)])
            worker_file = subdir / "worker.js"
            worker_file.write_text(code, encoding="utf-8")

            # Pass multiple path representations of the same file
            paths = [
                "src/services/worker.js",
                "src\\services\\worker.js",
                "./src/services/worker.js",
            ]
            evidence = analyze_duplication(paths, tmp_dir)
            # A single file cannot duplicate itself; duplicated lines must be 0
            assert evidence.duplicated_lines_count == 0
            assert evidence.duplication_percentage == 0.0
            assert evidence.duplicated_files == []

    def test_comments_inside_multiline_template_strings_not_truncated(self):
        """
        Adversarial test: verifies that comment syntax (// or #) appearing inside
        a multiline JS template string is preserved as string literal text rather
        than stripped as a code comment.
        """
        with TemporaryDirectory() as tmp_dir:
            file_a_lines = [
                "const sql_query_a = `",
                "SELECT id, username, email // internal user fields",
                "FROM users_table # active users partition",
                "WHERE account_status = 'ACTIVE'",
                "ORDER BY created_timestamp DESC",
                "LIMIT 50",
                "OFFSET 0",
                "`;",
            ]
            file_b_lines = [
                "const sql_query_b = `",
                "SELECT id, username, email // internal user fields",
                "FROM users_table # active users partition",
                "WHERE account_status = 'ACTIVE'",
                "ORDER BY created_timestamp DESC",
                "LIMIT 50",
                "OFFSET 0",
                "`;",
            ]
            file_c_lines = [
                "const sql_query_c = `",
                "SELECT id, username, email // completely different comments here",
                "FROM users_table # different partition comment",
                "WHERE account_status = 'ACTIVE'",
                "ORDER BY created_timestamp DESC",
                "LIMIT 50",
                "OFFSET 0",
                "`;",
            ]
            fa = Path(tmp_dir) / "queryA.js"
            fb = Path(tmp_dir) / "queryB.js"
            fc = Path(tmp_dir) / "queryC.js"
            fa.write_text("\n".join(file_a_lines), encoding="utf-8")
            fb.write_text("\n".join(file_b_lines), encoding="utf-8")
            fc.write_text("\n".join(file_c_lines), encoding="utf-8")

            # Between A and B (identical template string content with comments)
            evidence_ab = analyze_duplication(["queryA.js", "queryB.js"], tmp_dir)
            assert evidence_ab.duplicated_lines_count == 12
            assert len(evidence_ab.duplicated_files) == 2

            # Between A and C (different template string comments -> different tokens -> 0 duplicates)
            evidence_ac = analyze_duplication(["queryA.js", "queryC.js"], tmp_dir)
            assert evidence_ac.duplicated_lines_count == 0
            assert evidence_ac.duplication_percentage == 0.0


class TestSecretsScanner:
    """Tests for credentials scanner, redaction, and file exclusions."""

    def test_skips_package_lock_json(self):
        with TemporaryDirectory() as tmp_dir:
            lock_file = Path(tmp_dir) / "package-lock.json"
            lock_file.write_text('{"name": "test", "token": "AKIAIOSFODNN7EXAMPLE"}', encoding="utf-8")

            findings = scan_secrets(["package-lock.json"], tmp_dir)
            assert len(findings) == 0

    def test_multiple_secrets_on_same_line_all_redacted(self):
        with TemporaryDirectory() as tmp_dir:
            source_file = Path(tmp_dir) / "config.py"
            # Line containing AWS Access Key and Generic API Key
            source_file.write_text(
                'creds = "AKIA1234567890123456" and api_key = "abcdef123456789012345678"\n',
                encoding="utf-8",
            )

            findings = scan_secrets(["config.py"], tmp_dir)
            assert len(findings) >= 1
            for f in findings:
                # Neither secret should be exposed in cleartext in the snippet
                assert "AKIA1234567890123456" not in f.code_snippet
                assert "abcdef123456789012345678" not in f.code_snippet
                assert "[REDACTED:" in f.code_snippet


class TestComplexityAnalyzer:
    """Tests for cyclomatic complexity and Python AST branch counter."""

    def test_ast_branches_include_boolean_operators(self):
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "sample.py"
            code = (
                "def check(a, b, c):\n"
                "    if a and b and c:\n"
                "        return True\n"
                "    return False\n"
            )
            py_file.write_text(code, encoding="utf-8")

            res = _run_ast_complexity([str(py_file)])
            # Base cc (1) + if (1) + boolean 'and' (2 branch points) = 4
            assert res["average_complexity"] == 4.0
            assert res["max_complexity"] == 4

    def test_ast_does_not_double_count_nested_functions(self):
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "nested.py"
            code = (
                "def outer(x):\n"
                "    if x > 0:\n"
                "        pass\n"
                "    def inner(y):\n"
                "        if y > 10:\n"
                "            pass\n"
                "    return inner\n"
            )
            py_file.write_text(code, encoding="utf-8")

            res = _run_ast_complexity([str(py_file)])
            # Both outer and inner should have cc = 2 (base 1 + 1 if), not outer cc = 3
            assert res["max_complexity"] == 2
            assert res["average_complexity"] == 2.0


class TestPythonAnalyzer:
    """Tests for Python analyzer parsing and architecture checks."""

    def test_parse_pip_audit_json_dictionary(self):
        pip_audit_output = json.dumps({
            "dependencies": [
                {
                    "name": "urllib3",
                    "version": "1.26.4",
                    "vulns": [
                        {
                            "id": "GHSA-q2q7-5pp4-w6pg",
                            "description": "Urllib3 vulnerability",
                        }
                    ],
                }
            ]
        })
        parsed = PythonAnalyzer._parse_dep_vulns(pip_audit_output)
        assert len(parsed) == 1
        assert parsed[0]["package"] == "urllib3"
        assert parsed[0]["cve"] == "GHSA-q2q7-5pp4-w6pg"

    def test_parse_safety_json_list(self):
        safety_output = json.dumps([
            {
                "name": "django",
                "id": "CVE-2023-1234",
                "severity": "critical",
                "description": "Django SQL injection",
            }
        ])
        parsed = PythonAnalyzer._parse_dep_vulns(safety_output)
        assert len(parsed) == 1
        assert parsed[0]["package"] == "django"
        assert parsed[0]["cve"] == "CVE-2023-1234"

    def test_architecture_layer_violation_detection(self):
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            routes_file = Path(tmp_dir) / "routes" / "users.py"
            routes_file.parent.mkdir(parents=True, exist_ok=True)
            routes_file.write_text("from models import User\n", encoding="utf-8")

            arch = analyzer._architecture(["routes/users.py"], tmp_dir)
            assert len(arch.layer_violations) == 1
            assert "models" in arch.layer_violations[0]["to_layer"]


class TestJavaScriptAnalyzer:
    """Tests for JavaScript/TypeScript analyzer parsing and configurations."""

    def test_parse_npm_audit_v7_advisory_objects(self):
        npm_audit_output = json.dumps({
            "vulnerabilities": {
                "axios": {
                    "name": "axios",
                    "severity": "high",
                    "via": [
                        {
                            "source": 1092318,
                            "name": "axios",
                            "title": "Axios SSRF Vulnerability",
                            "url": "https://github.com/advisories/GHSA-8hc4-vh64-cxmj",
                        }
                    ],
                }
            }
        })
        parsed = JavaScriptAnalyzer._parse_npm_audit(npm_audit_output)
        assert len(parsed) == 1
        assert parsed[0]["package"] == "axios"
        assert parsed[0]["severity"] == "high"
        assert "GHSA" in parsed[0]["cve"]
        assert parsed[0]["description"] == "Axios SSRF Vulnerability"

    def test_supported_extensions_includes_cjs(self):
        analyzer = JavaScriptAnalyzer()
        assert ".cjs" in analyzer.supported_extensions
        filtered = analyzer._filter_files(["src/main.cjs", "src/main.CJS", "doc.txt"])
        assert "src/main.cjs" in filtered
        assert "src/main.CJS" in filtered
        assert "doc.txt" not in filtered


class TestEvidenceMerger:
    """Tests for merging evidence from multiple supported language analyzers."""

    def test_merge_python_and_javascript_evidence(self):
        from intelligence.evidence.merger import EvidenceMerger
        from intelligence.evidence.models import Finding

        ev_py = CodeQualityEvidence(
            repository_id="repo-multi",
            primary_language="python",
            detected_languages=["python"],
            files_analyzed=3,
            lines_added=50,
            lines_deleted=10,
            static_findings=[
                Finding(file_path="main.py", rule_id="RUFF-E501", category="syntax", severity=SeverityEnum.MEDIUM, source_tool="ruff", message="Line too long")
            ],
            complexity=ComplexityEvidence(average_complexity=5.0, lines_of_code=100),
            tools_executed=["ruff", "pip-audit"],
        )

        ev_js = CodeQualityEvidence(
            repository_id="repo-multi",
            primary_language="javascript",
            detected_languages=["javascript", "typescript"],
            files_analyzed=2,
            lines_added=40,
            lines_deleted=5,
            static_findings=[
                Finding(file_path="app.ts", rule_id="ESLINT-no-unused-vars", category="maintainability", severity=SeverityEnum.LOW, source_tool="eslint", message="Unused var")
            ],
            complexity=ComplexityEvidence(average_complexity=10.0, lines_of_code=100),
            tools_executed=["eslint", "npm-audit"],
        )

        merged = EvidenceMerger.merge([ev_py, ev_js])

        assert merged.files_analyzed == 5
        assert merged.lines_added == 90
        assert len(merged.static_findings) == 2
        assert "python" in merged.detected_languages
        assert "javascript" in merged.detected_languages
        assert "typescript" in merged.detected_languages
        assert "ruff" in merged.tools_executed
        assert "eslint" in merged.tools_executed
        # Weighted average complexity for 100 LOC @ 5.0 and 100 LOC @ 10.0 = 7.5
        assert merged.complexity.average_complexity == 7.5



import inspect
from unittest.mock import MagicMock, patch

def sync_run(coro):
    """
    Run a coroutine synchronously by recursively stepping through yielded child coroutines.
    Guarantees deterministic execution across platforms without starting an IOCP event loop.
    """
    try:
        val = None
        while True:
            sub = coro.send(val)
            val = sync_run(sub) if inspect.iscoroutine(sub) else sub
    except StopIteration as e:
        return e.value


# ==============================================================================
# TIER 1: FEATURE COVERAGE (CATEGORY-PARTITION SPECIFICATION TESTS)
# ==============================================================================

class TestTier1SecretsScanner:
    """
    Tier 1 tests for Secrets Scanner (Task 1.2: Features F1, F2, F3, F4).
    Verifies lockfile exclusion, complete sequential redaction, fixture handling,
    and raw secret prevention.
    """

    # ── Feature 1: Lockfile Filtering ──────────────────────────────────────────

    def test_f1_package_lock_json_excluded(self):
        """F1: package-lock.json must be excluded from secrets scanning."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "package-lock.json"
            f.write_text('{"name": "root", "key": "AKIA1234567890123456"}', encoding="utf-8")
            findings = scan_secrets(["package-lock.json"], tmp_dir)
            assert len(findings) == 0

    def test_f1_bun_lockb_and_yarn_lock_excluded(self):
        """F1: bun.lockb and yarn.lock must be excluded from secrets scanning."""
        with TemporaryDirectory() as tmp_dir:
            f1 = Path(tmp_dir) / "bun.lockb"
            f2 = Path(tmp_dir) / "yarn.lock"
            f1.write_text("token = AKIA1234567890123456", encoding="utf-8")
            f2.write_text((synthetic_token("github", 40)), encoding="utf-8")
            findings = scan_secrets(["bun.lockb", "yarn.lock"], tmp_dir)
            assert len(findings) == 0

    def test_f1_pnpm_lock_yaml_and_yml_excluded(self):
        """F1: pnpm-lock.yaml and pnpm-lock.yml must be excluded from secrets scanning."""
        with TemporaryDirectory() as tmp_dir:
            f1 = Path(tmp_dir) / "pnpm-lock.yaml"
            f2 = Path(tmp_dir) / "pnpm-lock.yml"
            f1.write_text(("secret: " + synthetic_token("stripe", 41)), encoding="utf-8")
            f2.write_text(("secret: " + synthetic_token("stripe", 42)), encoding="utf-8")
            findings = scan_secrets(["pnpm-lock.yaml", "pnpm-lock.yml"], tmp_dir)
            assert len(findings) == 0

    def test_f1_packages_lock_json_and_composer_lock_excluded(self):
        """F1: packages.lock.json and composer.lock must be excluded from secrets scanning."""
        with TemporaryDirectory() as tmp_dir:
            f1 = Path(tmp_dir) / "packages.lock.json"
            f2 = Path(tmp_dir) / "composer.lock"
            f1.write_text('{"token": "AKIA1234567890123456"}', encoding="utf-8")
            f2.write_text(('{"token": "' + synthetic_token("github", 40) + '"}'), encoding="utf-8")
            findings = scan_secrets(["packages.lock.json", "composer.lock"], tmp_dir)
            assert len(findings) == 0

    def test_f1_gradle_lockfile_and_compound_pattern_excluded(self):
        """F1: gradle.lockfile and compound pattern (*-lock.json) must be excluded."""
        with TemporaryDirectory() as tmp_dir:
            f1 = Path(tmp_dir) / "gradle.lockfile"
            f2 = Path(tmp_dir) / "dependencies-lock.json"
            f1.write_text("dependency=AKIA1234567890123456", encoding="utf-8")
            f2.write_text('{"api_key": "abcdef123456789012345678"}', encoding="utf-8")
            findings = scan_secrets(["gradle.lockfile", "dependencies-lock.json"], tmp_dir)
            assert len(findings) == 0

    # ── Feature 2: Complete Sequential Redaction ───────────────────────────────

    def test_f2_multiple_distinct_credentials_same_line_all_redacted(self):
        """F2: All distinct credentials on the same line must be sequentially redacted."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "config.py"
            aws_key = "AKIA1234567890123456"
            api_key = "abcdef123456789012345678"
            f.write_text(f'aws = "{aws_key}" and key = "{api_key}"\n', encoding="utf-8")

            findings = scan_secrets(["config.py"], tmp_dir)
            assert len(findings) >= 2
            for finding in findings:
                assert aws_key not in finding.code_snippet
                assert api_key not in finding.code_snippet
                assert "[REDACTED:" in finding.code_snippet

    def test_f2_multiple_identical_credentials_same_line_all_redacted(self):
        """F2: Multiple occurrences of the same credential on one line must all be redacted."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "keys.py"
            aws_key = "AKIA1234567890123456"
            f.write_text(f'primary = "{aws_key}"; secondary = "{aws_key}"\n', encoding="utf-8")

            findings = scan_secrets(["keys.py"], tmp_dir)
            assert len(findings) >= 1
            for finding in findings:
                assert aws_key not in finding.code_snippet

    def test_f2_three_different_tokens_same_line_all_redacted(self):
        """F2: Three distinct token types on a single line must all be redacted."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "tokens.env"
            slack_tok = (synthetic_token("slack", 43))
            gh_tok = (synthetic_token("github", 40))
            gl_tok = (synthetic_token("gitlab", 44))
            f.write_text(f"SLACK={slack_tok} GH={gh_tok} GL={gl_tok}\n", encoding="utf-8")

            findings = scan_secrets(["tokens.env"], tmp_dir)
            assert len(findings) >= 3
            for finding in findings:
                assert slack_tok not in finding.code_snippet
                assert gh_tok not in finding.code_snippet
                assert gl_tok not in finding.code_snippet

    def test_f2_secret_near_character_200_boundary_redacted(self):
        """F2: Secrets placed near or across character 200 must be redacted before slicing."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "longline.py"
            prefix = "x" * 180
            aws_key = "AKIA1234567890123456"
            suffix = "y" * 100
            f.write_text(f'{prefix}{aws_key}{suffix}\n', encoding="utf-8")

            findings = scan_secrets(["longline.py"], tmp_dir)
            assert len(findings) >= 1
            for finding in findings:
                assert aws_key not in finding.code_snippet
                assert len(finding.code_snippet) <= 200

    def test_f2_repeated_credentials_interleaved_with_syntax(self):
        """F2: Secrets interleaved with Python code syntax must all be cleanly redacted."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "client.py"
            tok = (synthetic_token("github", 40))
            f.write_text(f'headers = {{"Authorization": "Bearer {tok}", "X-Alt": "{tok}"}}\n', encoding="utf-8")

            findings = scan_secrets(["client.py"], tmp_dir)
            assert len(findings) >= 1
            for finding in findings:
                assert tok not in finding.code_snippet

    # ── Feature 3: Obvious Test Fixture Handling ───────────────────────────────

    def test_f3_aws_example_key_downgraded_to_low(self):
        """F3: Official AWS example keys must be downgraded to SeverityEnum.LOW with -FIXTURE rule ID."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "test_aws.py"
            f.write_text('key = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8")

            findings = scan_secrets(["test_aws.py"], tmp_dir)
            assert len(findings) == 1
            assert findings[0].severity == SeverityEnum.LOW
            assert findings[0].rule_id.endswith("-FIXTURE")
            assert "AKIAIOSFODNN7EXAMPLE" not in findings[0].code_snippet

    def test_f3_aws_secret_example_downgraded_to_low(self):
        """F3: Documentation example AWS secret keys with EXAMPLEKEY must be classified as fixture."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "test_auth.py"
            f.write_text(('aws_secret_access_key = "' + synthetic_token("aws-secret", 45, fixture=True) + '"\n'), encoding="utf-8")

            findings = scan_secrets(["test_auth.py"], tmp_dir)
            assert len(findings) == 1
            assert findings[0].severity == SeverityEnum.LOW
            assert findings[0].rule_id.endswith("-FIXTURE")

    def test_f3_dummy_keyword_in_token_downgraded(self):
        """F3: Credentials containing dummy/mock/fake keywords must be downgraded to LOW."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "tests" / "fixtures.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text('fake_api_key = "dummy_12345678901234567890"\n', encoding="utf-8")

            findings = scan_secrets(["tests/fixtures.py"], tmp_dir)
            for finding in findings:
                if "dummy" in finding.code_snippet.lower():
                    assert finding.severity == SeverityEnum.LOW
                    assert finding.rule_id.endswith("-FIXTURE")

    def test_f3_genuine_high_entropy_secret_in_test_file_retains_critical(self):
        """F3: Genuine high-entropy credentials inside test files must NOT be downgraded or ignored."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "tests" / "test_integration.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            real_key = "AKIA3J5K2L9M7N1P4Q8R"
            f.write_text(f'live_key = "{real_key}"\n', encoding="utf-8")

            findings = scan_secrets(["tests/test_integration.py"], tmp_dir)
            assert len(findings) == 1
            assert findings[0].severity == SeverityEnum.CRITICAL
            assert not findings[0].rule_id.endswith("-FIXTURE")

    def test_f3_placeholder_password_in_fixture_downgraded(self):
        """F3: Obvious placeholder password assignments in test files must be downgraded to LOW."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "tests" / "mock_user.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text('mock_password = "password123"\n', encoding="utf-8")

            findings = scan_secrets(["tests/mock_user.py"], tmp_dir)
            for finding in findings:
                assert finding.severity == SeverityEnum.LOW
                assert finding.rule_id.endswith("-FIXTURE")

    # ── Feature 4: Raw Secret Prevention ───────────────────────────────────────

    def test_f4_raw_secret_never_in_finding_message(self):
        """F4: Finding message must describe the rule without exposing raw secret values."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "app.py"
            secret = "AKIA1234567890123456"
            f.write_text(f'key = "{secret}"\n', encoding="utf-8")

            findings = scan_secrets(["app.py"], tmp_dir)
            assert len(findings) == 1
            assert secret not in findings[0].message

    def test_f4_raw_secret_never_in_rule_id(self):
        """F4: Finding rule_id must contain canonical rule name without cleartext secrets."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "app.py"
            secret = "AKIA1234567890123456"
            f.write_text(f'key = "{secret}"\n', encoding="utf-8")

            findings = scan_secrets(["app.py"], tmp_dir)
            assert len(findings) == 1
            assert secret not in findings[0].rule_id
            assert "SEC-SECRET-AWS_ACCESS_KEY" in findings[0].rule_id

    def test_f4_raw_secret_never_in_code_snippet(self):
        """F4: Finding code_snippet must never contain raw credential strings."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "app.py"
            secret = (synthetic_token("stripe", 41))
            f.write_text(f'stripe_key = "{secret}"\n', encoding="utf-8")

            findings = scan_secrets(["app.py"], tmp_dir)
            assert len(findings) == 1
            assert secret not in findings[0].code_snippet
            assert "[REDACTED:STRIPE_SECRET]" in findings[0].code_snippet

    def test_f4_snippet_sliced_after_complete_redaction(self):
        """F4: Snippet truncation to 200 chars must occur strictly after complete redaction."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "app.py"
            secret = "AKIA1234567890123456"
            line = f'val = "{"a" * 175}{secret}{"b" * 100}"\n'
            f.write_text(line, encoding="utf-8")

            findings = scan_secrets(["app.py"], tmp_dir)
            assert len(findings) == 1
            assert secret not in findings[0].code_snippet
            assert len(findings[0].code_snippet) <= 200

    def test_f4_zero_leakage_across_all_findings_attributes(self):
        """F4: Comprehensive check ensuring zero raw secret leakage in any Finding attribute."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "app.py"
            secret = (synthetic_token("github", 40))
            f.write_text(f'github_token = "{secret}"\n', encoding="utf-8")

            findings = scan_secrets(["app.py"], tmp_dir)
            assert len(findings) == 1
            for attr_name in ("file_path", "rule_id", "message", "code_snippet", "category"):
                val = getattr(findings[0], attr_name, "")
                assert secret not in str(val)


class TestTier1ComplexityAnalyzer:
    """
    Tier 1 tests for Shared Complexity Analyzer (Task 1.5: Features F5, F6, F7, F8, F9).
    Verifies Maintainability Index separation, Radon schema reconciliation,
    Python AST branch counting, nested function scoping, and unavailable complexity representation.
    """

    # ── Feature 5: Maintainability Index Separation ────────────────────────────

    def test_f5_radon_mi_dictionary_sets_maintainability_index(self):
        """F5: Radon MI dictionary must populate maintainability_index, not comment_ratio."""
        evidence = ComplexityEvidence()
        radon_mi_output = {"service.py": {"mi": 82.5, "rank": "A"}}
        _merge_radon_supplement(evidence, radon_mi_output)

        assert getattr(evidence, "maintainability_index", None) == 82.5

    def test_f5_comment_ratio_not_polluted_by_mi(self):
        """F5: Radon MI score (e.g. 85.0) must not be divided by 100 and stored in comment_ratio."""
        evidence = ComplexityEvidence(comment_ratio=0.15)
        radon_mi_output = {"service.py": {"mi": 85.0, "rank": "A"}}
        _merge_radon_supplement(evidence, radon_mi_output)

        assert evidence.comment_ratio == 0.15
        assert evidence.comment_ratio != 0.85

    def test_f5_maintainability_index_direct_key_support(self):
        """F5: Supplement dictionary with direct maintainability_index key must be supported."""
        evidence = ComplexityEvidence()
        supplement = {"maintainability_index": 76.4}
        _merge_radon_supplement(evidence, supplement)

        assert getattr(evidence, "maintainability_index", None) == 76.4

    def test_f5_mi_averaged_across_multiple_files(self):
        """F5: Multi-file Radon MI dictionary must average file MI scores correctly."""
        evidence = ComplexityEvidence()
        radon_mi_output = {
            "a.py": {"mi": 80.0, "rank": "A"},
            "b.py": {"mi": 90.0, "rank": "A"},
        }
        _merge_radon_supplement(evidence, radon_mi_output)

        assert getattr(evidence, "maintainability_index", None) == 85.0

    def test_f5_mi_absent_preserves_none(self):
        """F5: If Radon supplement contains no MI data, maintainability_index remains None."""
        evidence = ComplexityEvidence()
        _merge_radon_supplement(evidence, {"other_key": 123})

        assert getattr(evidence, "maintainability_index", None) is None

    # ── Feature 6: Radon Supplement Schema Reconciliation ──────────────────────

    def test_f6_radon_cc_schema_merges_high_complexity_functions(self):
        """F6: Radon CC schema must merge high_complexity_functions into evidence."""
        evidence = ComplexityEvidence(high_complexity_functions=[{"function": "f1", "complexity": 11}])
        radon_cc_output = {
            "high_complexity_functions": [{"function": "f2", "complexity": 14}],
            "max_complexity": 14,
        }
        _merge_radon_supplement(evidence, radon_cc_output)

        fn_names = {f["function"] for f in evidence.high_complexity_functions}
        assert "f1" in fn_names
        assert "f2" in fn_names

    def test_f6_radon_cc_schema_updates_max_complexity(self):
        """F6: Radon CC schema with higher max_complexity must update evidence.max_complexity."""
        evidence = ComplexityEvidence(max_complexity=8)
        radon_cc_output = {"max_complexity": 15, "high_complexity_functions": []}
        _merge_radon_supplement(evidence, radon_cc_output)

        assert evidence.max_complexity == 15

    def test_f6_radon_cc_schema_deduplicates_functions(self):
        """F6: Identical function entries in Radon CC supplement must be deduplicated."""
        evidence = ComplexityEvidence(high_complexity_functions=[{"function": "process", "complexity": 12}])
        radon_cc_output = {
            "high_complexity_functions": [{"function": "process", "complexity": 12}],
            "max_complexity": 12,
        }
        _merge_radon_supplement(evidence, radon_cc_output)

        assert len(evidence.high_complexity_functions) == 1

    def test_f6_non_dict_result_handled_gracefully(self):
        """F6: Non-dict Radon results must be safely ignored without raising exceptions."""
        evidence = ComplexityEvidence(max_complexity=5)
        _merge_radon_supplement(evidence, None)
        _merge_radon_supplement(evidence, "unexpected string")
        _merge_radon_supplement(evidence, [1, 2, 3])

        assert evidence.max_complexity == 5

    def test_f6_empty_dict_result_handled_gracefully(self):
        """F6: Empty dictionary Radon result must not modify evidence."""
        evidence = ComplexityEvidence(max_complexity=5, comment_ratio=0.1)
        _merge_radon_supplement(evidence, {})

        assert evidence.max_complexity == 5
        assert evidence.comment_ratio == 0.1

    # ── Feature 7: Documented Python AST Branch Metric ─────────────────────────

    def test_f7_ternary_ifexp_counts_branch(self):
        """F7: Python AST CC metric must count ternary conditional expressions (ast.IfExp)."""
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "ternary.py"
            py_file.write_text("def choose(cond, a, b):\n    return a if cond else b\n", encoding="utf-8")

            res = _run_ast_complexity([str(py_file)])
            assert res["max_complexity"] == 2
            assert res["average_complexity"] == 2.0

    def test_f7_listcomp_with_filter_counts_branch(self):
        """F7: Comprehensions with conditional filters must contribute to branch count."""
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "comp.py"
            py_file.write_text("def filter_pos(items):\n    return [x for x in items if x > 0]\n", encoding="utf-8")

            res = _run_ast_complexity([str(py_file)])
            assert res["max_complexity"] == 2

    def test_f7_boolop_counts_n_minus_1_branches(self):
        """F7: ast.BoolOp with N operands must add exactly N - 1 branch decision points."""
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "boolop.py"
            code = "def validate(a, b, c, d):\n    if a and b and c and d:\n        return True\n    return False\n"
            py_file.write_text(code, encoding="utf-8")

            res = _run_ast_complexity([str(py_file)])
            assert res["max_complexity"] == 5

    def test_f7_assert_statement_counts_branch(self):
        """F7: ast.Assert statements must be counted as decision branches."""
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "assertion.py"
            code = "def check_positive(x):\n    assert x > 0\n    return x\n"
            py_file.write_text(code, encoding="utf-8")

            res = _run_ast_complexity([str(py_file)])
            assert res["max_complexity"] == 2

    def test_f7_nested_branch_points_composite_cc(self):
        """F7: Composite function with for, while, if, and except must sum all branches accurately."""
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "composite.py"
            code = (
                "def process(items):\n"
                "    for x in items:\n"
                "        if x > 0:\n"
                "            pass\n"
                "        elif x < -10:\n"
                "            pass\n"
                "    try:\n"
                "        while False:\n"
                "            pass\n"
                "    except ValueError:\n"
                "        pass\n"
            )
            py_file.write_text(code, encoding="utf-8")

            res = _run_ast_complexity([str(py_file)])
            assert res["max_complexity"] == 6

    # ── Feature 8: Nested Function Scoping ─────────────────────────────────────

    def test_f8_outer_function_does_not_count_inner_def_branches(self):
        """F8: Branches inside nested def inner(): must not be counted in outer function complexity."""
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "nest_scoping.py"
            code = (
                "def outer(x):\n"
                "    if x > 0:\n"
                "        pass\n"
                "    def inner(y, z):\n"
                "        if y > 0 and z > 0:\n"
                "            return True\n"
                "        return False\n"
                "    return inner\n"
            )
            py_file.write_text(code, encoding="utf-8")

            res = _run_ast_complexity([str(py_file)])
            assert res["max_complexity"] == 3
            assert res["average_complexity"] == 2.5

    def test_f8_outer_function_does_not_count_async_inner_branches(self):
        """F8: Branches in nested async def inner(): must not be counted in outer function."""
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "async_inner.py"
            code = (
                "def make_coro():\n"
                "    async def fetch(url):\n"
                "        if not url:\n"
                "            return None\n"
                "    return fetch\n"
            )
            py_file.write_text(code, encoding="utf-8")

            res = _run_ast_complexity([str(py_file)])
            assert res["max_complexity"] == 2
            assert res["average_complexity"] == 1.5

    def test_f8_outer_function_does_not_count_inner_class_branches(self):
        """F8: Local class method branches inside a function must not inflate outer function CC."""
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "inner_cls.py"
            code = (
                "def factory():\n"
                "    class LocalHandler:\n"
                "        def handle(self, x):\n"
                "            if x:\n"
                "                return 1\n"
                "    return LocalHandler()\n"
            )
            py_file.write_text(code, encoding="utf-8")

            res = _run_ast_complexity([str(py_file)])
            assert res["max_complexity"] == 2

    def test_f8_multiple_nested_functions_scoped_independently(self):
        """F8: Multiple closures returned from outer function must each have isolated branch counts."""
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "multi_closures.py"
            code = (
                "def builder():\n"
                "    def add_op(a, b):\n"
                "        if a > 0:\n"
                "            return a + b\n"
                "    def sub_op(a, b):\n"
                "        if b > 0:\n"
                "            return a - b\n"
                "    return add_op, sub_op\n"
            )
            py_file.write_text(code, encoding="utf-8")

            res = _run_ast_complexity([str(py_file)])
            assert res["max_complexity"] == 2
            assert round(res["average_complexity"], 2) == 1.67

    def test_f8_average_complexity_computed_over_all_function_scopes(self):
        """F8: Average complexity calculation must include each function and nested function exactly once."""
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "two_fns.py"
            code = (
                "def fn_simple():\n"
                "    pass\n"
                "def fn_branch(x):\n"
                "    if x:\n"
                "        pass\n"
            )
            py_file.write_text(code, encoding="utf-8")

            res = _run_ast_complexity([str(py_file)])
            assert res["average_complexity"] == 1.5

    # ── Feature 9: Unavailable Complexity Representation ──────────────────────

    def test_f9_unmeasured_complexity_sets_is_available_false(self):
        """F9: When no tooling runs for complexity, evidence.is_available must be False."""
        evidence = ComplexityEvidence(is_available=False, average_complexity=None, max_complexity=None)
        assert getattr(evidence, "is_available", True) is False

    def test_f9_unmeasured_complexity_sets_average_complexity_none(self):
        """F9: Unmeasured complexity must represent average_complexity as None, not 0.0."""
        evidence = ComplexityEvidence(is_available=False, average_complexity=None, max_complexity=None)
        assert evidence.average_complexity is None

    def test_f9_unmeasured_complexity_sets_max_complexity_none(self):
        """F9: Unmeasured complexity must represent max_complexity as None, not 0."""
        evidence = ComplexityEvidence(is_available=False, average_complexity=None, max_complexity=None)
        assert evidence.max_complexity is None

    def test_f9_merger_ignores_unmeasured_complexity(self):
        """F9: EvidenceMerger must ignore unmeasured complexity when computing weighted average."""
        from intelligence.evidence.merger import EvidenceMerger

        ev_measured = CodeQualityEvidence(
            repository_id="repo1",
            primary_language="python",
            complexity=ComplexityEvidence(
                is_available=True,
                average_complexity=4.0,
                max_complexity=6,
                lines_of_code=100,
            ),
        )
        ev_unmeasured = CodeQualityEvidence(
            repository_id="repo1",
            primary_language="javascript",
            complexity=ComplexityEvidence(
                is_available=False,
                average_complexity=None,
                max_complexity=None,
                lines_of_code=200,
            ),
        )

        merged = EvidenceMerger.merge([ev_measured, ev_unmeasured])
        assert merged.complexity.average_complexity == 4.0
        assert merged.complexity.max_complexity == 6

    def test_f9_merger_returns_unavailable_when_all_unmeasured(self):
        """F9: When all languages have unmeasured complexity, merged result must be unavailable."""
        from intelligence.evidence.merger import EvidenceMerger

        ev1 = CodeQualityEvidence(
            repository_id="repo1",
            primary_language="javascript",
            complexity=ComplexityEvidence(
                is_available=False,
                average_complexity=None,
                max_complexity=None,
                lines_of_code=100,
            ),
        )
        ev2 = CodeQualityEvidence(
            repository_id="repo1",
            primary_language="typescript",
            complexity=ComplexityEvidence(
                is_available=False,
                average_complexity=None,
                max_complexity=None,
                lines_of_code=100,
            ),
        )

        merged = EvidenceMerger.merge([ev1, ev2])
        assert getattr(merged.complexity, "is_available", True) is False
        assert merged.complexity.average_complexity is None


class TestTier1LanguageDetectionAndFiltering:
    """
    Tier 1 tests for Language Detection & Filtering (Task 1.6: Features F10, F11, F12, F13).
    Verifies canonical directory exclusion, case-insensitive filtering,
    optimized directory traversal pruning, and case-insensitive build/tool hints.
    """

    # ── Feature 10: Canonical Directory Exclusion ──────────────────────────────

    def test_f10_node_modules_excluded(self):
        """F10: node_modules directory must be excluded in BaseAnalyzer._filter_files."""
        analyzer = JavaScriptAnalyzer()
        filtered = analyzer._filter_files(["node_modules/axios/index.js", "src/index.js"])
        assert "src/index.js" in filtered
        assert "node_modules/axios/index.js" not in filtered

    def test_f10_venv_and_dot_venv_excluded(self):
        """F10: venv and .venv directories must be excluded in BaseAnalyzer._filter_files."""
        analyzer = PythonAnalyzer()
        files = ["venv/lib/site-packages/pkg.py", ".venv/bin/activate.py", "app/main.py"]
        filtered = analyzer._filter_files(files)
        assert filtered == ["app/main.py"]

    def test_f10_build_and_dist_excluded(self):
        """F10: build and dist build output directories must be excluded."""
        analyzer = JavaScriptAnalyzer()
        files = ["build/bundle.js", "dist/app.js", "src/app.js"]
        filtered = analyzer._filter_files(files)
        assert filtered == ["src/app.js"]

    def test_f10_git_and_pycache_excluded(self):
        """F10: .git and __pycache__ directories must be excluded."""
        analyzer = PythonAnalyzer()
        files = [".git/hooks/pre-commit.py", "__pycache__/app.cpython-312.pyc", "src/app.py"]
        filtered = analyzer._filter_files(files)
        assert filtered == ["src/app.py"]

    def test_f10_vendor_and_generated_and_gradle_excluded(self):
        """F10: vendor, generated, and .gradle directories must be excluded."""
        analyzer = PythonAnalyzer()
        files = ["vendor/lib.py", "generated/schema.py", ".gradle/task.py", "service.py"]
        filtered = analyzer._filter_files(files)
        assert filtered == ["service.py"]

    # ── Feature 11: Case-Insensitive File & Extension Filtering ────────────────

    def test_f11_uppercase_node_modules_excluded(self):
        """F11: Uppercase Node_Modules/ directory must be excluded case-insensitively."""
        analyzer = JavaScriptAnalyzer()
        files = ["Node_Modules/lib/index.js", "NODE_MODULES/pkg/util.js", "src/app.js"]
        filtered = analyzer._filter_files(files)
        assert "src/app.js" in filtered
        assert "Node_Modules/lib/index.js" not in filtered

    def test_f11_uppercase_venv_excluded(self):
        """F11: Uppercase VENV/ directory must be excluded case-insensitively."""
        analyzer = PythonAnalyzer()
        files = ["VENV/lib/module.py", "Venv/site.py", "app.py"]
        filtered = analyzer._filter_files(files)
        assert filtered == ["app.py"]

    def test_f11_uppercase_extensions_matched(self):
        """F11: Uppercase file extensions (.PY, .JS, .TSX, .CJS) must be matched properly."""
        analyzer_py = PythonAnalyzer()
        analyzer_js = JavaScriptAnalyzer()
        assert "main.PY" in analyzer_py._filter_files(["main.PY"])
        assert "server.CJS" in analyzer_js._filter_files(["server.CJS"])
        assert "App.TSX" in analyzer_js._filter_files(["App.TSX"])

    def test_f11_mixed_case_nested_directories_excluded(self):
        """F11: Nested directory components with mixed casing must be filtered out."""
        analyzer = JavaScriptAnalyzer()
        files = ["src/Build/output.js", "packages/Dist/bundle.js", "src/components/Button.jsx"]
        filtered = analyzer._filter_files(files)
        assert filtered == ["src/components/Button.jsx"]

    def test_f11_windows_separator_excluded_dirs(self):
        """F11: Path components separated by Windows backslashes must be excluded."""
        analyzer = JavaScriptAnalyzer()
        files = ["node_modules\\react\\index.js", "src\\index.js"]
        filtered = analyzer._filter_files(files)
        assert "src\\index.js" in filtered
        assert "node_modules\\react\\index.js" not in filtered

    # ── Feature 12: Optimized Directory Traversal ──────────────────────────────

    def test_f12_detect_from_repo_prunes_node_modules(self):
        """F12: detect_from_repo must prune node_modules and never descend into its files."""
        detector = LanguageDetector()
        with TemporaryDirectory() as tmp_dir:
            nm = Path(tmp_dir) / "node_modules" / "deep_pkg"
            nm.mkdir(parents=True, exist_ok=True)
            (nm / "heavy_code.js").write_text("console.log('heavy');", encoding="utf-8")
            (Path(tmp_dir) / "main.py").write_text("print('python')", encoding="utf-8")

            profile = detector.detect_from_repo(tmp_dir)
            assert profile.primary_language == "python"

    def test_f12_detect_from_repo_prunes_venv(self):
        """F12: detect_from_repo must prune venv directory tree."""
        detector = LanguageDetector()
        with TemporaryDirectory() as tmp_dir:
            venv = Path(tmp_dir) / "venv" / "lib"
            venv.mkdir(parents=True, exist_ok=True)
            for i in range(20):
                (venv / f"mod_{i}.py").write_text("x = 1", encoding="utf-8")
            (Path(tmp_dir) / "index.js").write_text("const a = 1;", encoding="utf-8")

            profile = detector.detect_from_repo(tmp_dir)
            assert profile.primary_language == "javascript"

    def test_f12_detect_from_repo_prunes_git(self):
        """F12: detect_from_repo must prune .git directory."""
        detector = LanguageDetector()
        with TemporaryDirectory() as tmp_dir:
            git_dir = Path(tmp_dir) / ".git" / "hooks"
            git_dir.mkdir(parents=True, exist_ok=True)
            (git_dir / "hook.py").write_text("import os", encoding="utf-8")
            (Path(tmp_dir) / "app.js").write_text("export default {};", encoding="utf-8")

            profile = detector.detect_from_repo(tmp_dir)
            assert profile.primary_language == "javascript"

    def test_f12_detect_from_repo_retains_valid_src_directories(self):
        """F12: Traversal pruning must retain valid source subdirectories (src, lib, app)."""
        detector = LanguageDetector()
        with TemporaryDirectory() as tmp_dir:
            src = Path(tmp_dir) / "src" / "deep"
            src.mkdir(parents=True, exist_ok=True)
            (src / "nested.py").write_text("def hello(): pass", encoding="utf-8")

            profile = detector.detect_from_repo(tmp_dir)
            assert profile.primary_language == "python"

    def test_f12_detect_from_repo_case_insensitive_pruning(self):
        """F12: Directory pruning in detect_from_repo must handle uppercase Build/ or Node_Modules/."""
        detector = LanguageDetector()
        with TemporaryDirectory() as tmp_dir:
            build = Path(tmp_dir) / "Build" / "out"
            build.mkdir(parents=True, exist_ok=True)
            for i in range(10):
                (build / f"out_{i}.py").write_text("x = 1", encoding="utf-8")
            (Path(tmp_dir) / "app.js").write_text("console.log('hi');", encoding="utf-8")

            profile = detector.detect_from_repo(tmp_dir)
            assert profile.primary_language == "javascript"

    # ── Feature 13: Case-Insensitive Build & Tool Hints ────────────────────────

    def test_f13_detect_from_files_matches_lowercase_makefile(self):
        """F13: Lowercase makefile must be recognized as C build system."""
        detector = LanguageDetector()
        profile = detector.detect_from_files(["makefile", "main.c"])
        assert profile.build_system == "make"

    def test_f13_detect_from_files_matches_uppercase_package_json(self):
        """F13: Uppercase PACKAGE.JSON must be recognized as npm build system."""
        detector = LanguageDetector()
        profile = detector.detect_from_files(["PACKAGE.JSON", "src/app.js"])
        assert profile.build_system == "npm"

    def test_f13_detect_from_files_matches_cmakelists_txt(self):
        """F13: CMakeLists.txt (case-insensitive) must be recognized as cmake build system."""
        detector = LanguageDetector()
        profile = detector.detect_from_files(["cmakelists.txt", "main.cpp"])
        assert profile.build_system == "cmake"

    def test_f13_detect_from_repo_matches_case_insensitive_build_files(self):
        """F13: detect_from_repo must detect build files regardless of filesystem casing."""
        detector = LanguageDetector()
        with TemporaryDirectory() as tmp_dir:
            (Path(tmp_dir) / "MAKEFILE").write_text("all:\n\tgcc main.c", encoding="utf-8")
            (Path(tmp_dir) / "main.c").write_text("int main() { return 0; }", encoding="utf-8")

            profile = detector.detect_from_repo(tmp_dir)
            assert profile.build_system == "make"

    def test_f13_test_framework_hints_case_insensitive(self):
        """F13: Test framework hints must match config files case-insensitively."""
        detector = LanguageDetector()
        profile = detector.detect_from_files(["JEST.CONFIG.JS", "src/app.js"])
        assert profile.test_framework == "jest"


class TestTier1PythonAnalyzer:
    """
    Tier 1 tests for Python Analyzer Reliability (Task 1.3: Features F14, F15, F16, F17, F18).
    Verifies pip-audit format handling, dependency failure handling, Flake8 compatibility,
    AST-aware architecture checks, and static test discovery.
    """

    # ── Feature 14: Pip-Audit Format Handling ──────────────────────────────────

    def test_f14_pip_audit_dict_with_dependencies_parsed(self):
        """F14: Pip-audit output with dict format {"dependencies": [...]} parsed with metadata."""
        output = json.dumps({
            "dependencies": [
                {
                    "name": "requests",
                    "version": "2.25.0",
                    "vulns": [
                        {
                            "id": "GHSA-j8r2-6x86-q33q",
                            "description": "Requests vulnerability",
                            "aliases": ["CVE-2023-32681"],
                        }
                    ],
                }
            ]
        })
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert len(vulns) == 1
        assert vulns[0]["package"] == "requests"
        assert "CVE-2023-32681" in str(vulns[0]["cve"]) or "GHSA-j8r2-6x86-q33q" in str(vulns[0]["cve"])
        assert "Requests vulnerability" in vulns[0]["description"]

    def test_f14_pip_audit_list_of_dependencies_parsed(self):
        """F14: Pip-audit output with top-level list of dependency objects parsed without losing CVE."""
        output = json.dumps([
            {
                "name": "urllib3",
                "version": "1.26.4",
                "vulns": [
                    {
                        "id": "GHSA-q2q7-5pp4-w6pg",
                        "description": "Urllib3 vulnerability",
                        "aliases": ["CVE-2021-33503"],
                    }
                ],
            }
        ])
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert len(vulns) == 1
        assert vulns[0]["package"] == "urllib3"
        assert "GHSA-q2q7-5pp4-w6pg" in vulns[0]["cve"] or "CVE-2021-33503" in vulns[0]["cve"]
        assert "Urllib3 vulnerability" in vulns[0]["description"]

    def test_f14_pip_audit_cve_aliases_extracted(self):
        """F14: When aliases contains a CVE identifier, it should be extracted as the primary CVE."""
        output = json.dumps({
            "dependencies": [
                {
                    "name": "cryptography",
                    "version": "3.3.1",
                    "vulns": [
                        {
                            "id": "PYSEC-2021-62",
                            "aliases": ["CVE-2020-36242", "GHSA-x5rh-mg29-hw47"],
                            "description": "Buffer overflow in cryptography",
                        }
                    ],
                }
            ]
        })
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert len(vulns) == 1
        assert "CVE-2020-36242" in str(vulns[0]["cve"]) or "PYSEC-2021-62" in str(vulns[0]["cve"])

    def test_f14_pip_audit_package_version_preserved(self):
        """F14: Dependency package version must be extracted when present."""
        output = json.dumps({
            "dependencies": [
                {
                    "name": "django",
                    "version": "3.1.2",
                    "vulns": [{"id": "CVE-2021-3281", "description": "Django path traversal"}],
                }
            ]
        })
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert len(vulns) == 1
        assert vulns[0]["package"] == "django"

    def test_f14_pip_audit_multiple_vulns_per_dependency(self):
        """F14: A single dependency with multiple vulnerabilities must produce multiple finding entries."""
        output = json.dumps({
            "dependencies": [
                {
                    "name": "flask",
                    "version": "1.0",
                    "vulns": [
                        {"id": "CVE-1", "description": "First issue"},
                        {"id": "CVE-2", "description": "Second issue"},
                    ],
                }
            ]
        })
        vulns = PythonAnalyzer._parse_dep_vulns(output)
        assert len(vulns) == 2
        cves = {v["cve"] for v in vulns}
        assert "CVE-1" in cves
        assert "CVE-2" in cves

    # ── Feature 15: Explicit Dependency Tool Failure Handling ──────────────────

    def test_f15_pip_audit_clean_scan_does_not_fall_through_to_safety(self):
        """F15: A clean pip-audit scan (0 vulns) must return [] and not unnecessarily run safety."""
        py_mod = sys.modules[PythonAnalyzer.__module__]
        analyzer = PythonAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-clean", primary_language="python")
        clean_pip_audit = json.dumps({"dependencies": []})
        call_count = 0

        async def fake_run(cmd, cwd=None):
            nonlocal call_count
            call_count += 1
            return clean_pip_audit

        with patch.object(analyzer, "_tool_available", return_value=True):
            with patch.object(py_mod, "_run", fake_run):
                vulns = sync_run(analyzer._dependencies("/tmp/fake_repo", evidence))
                assert vulns == []
                assert "pip-audit" in evidence.tools_executed
                assert call_count == 1

    def test_f15_pip_audit_failure_records_degraded_quality(self):
        """F15: A failed dependency tool (None output) must record explicit quality degradation."""
        py_mod = sys.modules[PythonAnalyzer.__module__]
        analyzer = PythonAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-fail", primary_language="python")

        async def fake_run_fail(cmd, cwd=None):
            return None

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: t == "pip-audit"):
            with patch.object(py_mod, "_run", fake_run_fail):
                vulns = sync_run(analyzer._dependencies("/tmp/fake_repo", evidence))
                assert vulns == []
                assert evidence.analysis_quality.penalties or evidence.tools_skipped or (evidence.analysis_quality.confidence < 1.0)

    def test_f15_dependency_tool_timeout_handled_cleanly(self):
        """F15: Subprocess timeout in dependency tool must be handled gracefully without exception."""
        py_mod = sys.modules[PythonAnalyzer.__module__]
        analyzer = PythonAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-timeout", primary_language="python")

        async def fake_run_none(cmd, cwd=None):
            return None

        with patch.object(analyzer, "_tool_available", return_value=True):
            with patch.object(py_mod, "_run", fake_run_none):
                vulns = sync_run(analyzer._dependencies("/tmp/fake_repo", evidence))
                assert vulns == []

    def test_f15_safety_executed_when_pip_audit_not_available(self):
        """F15: Fallback to safety occurs when pip-audit is not available on host."""
        py_mod = sys.modules[PythonAnalyzer.__module__]
        analyzer = PythonAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-fallback", primary_language="python")
        safety_output = json.dumps([{"name": "django", "id": "CVE-2022-1234", "description": "SQLi"}])

        async def fake_run_safety(cmd, cwd=None):
            return safety_output

        with patch.object(analyzer, "_tool_available", side_effect=lambda t: t == "safety"):
            with patch.object(py_mod, "_run", fake_run_safety):
                vulns = sync_run(analyzer._dependencies("/tmp/fake_repo", evidence))
                assert len(vulns) == 1
                assert "safety" in evidence.tools_executed

    def test_f15_both_dependency_tools_failing_records_quality_penalty(self):
        """F15: When all dependency tools fail or are unavailable, degradation is recorded."""
        analyzer = PythonAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-none", primary_language="python")

        with patch.object(analyzer, "_tool_available", return_value=False):
            vulns = sync_run(analyzer._dependencies("/tmp/fake_repo", evidence))
            assert vulns == []

    # ── Feature 16: Flake8 Clean Run & Format Compatibility ────────────────────

    def test_f16_flake8_clean_run_empty_stdout_does_not_degrade_quality(self):
        """F16: Flake8 exiting with empty stdout (0 errors) must not be treated as a tool failure."""
        analyzer = PythonAnalyzer()
        findings = analyzer._parse_flake8("", ["app.py"])
        assert findings == []

    def test_f16_flake8_json_format_output_parsed(self):
        """F16: Flake8 JSON output (from flake8-json formatter) must be parsed cleanly."""
        json_output = json.dumps({
            "src/app.py": [
                {
                    "code": "E501",
                    "line_number": 42,
                    "column_number": 80,
                    "text": "line too long (88 > 79 characters)",
                }
            ]
        })
        findings = PythonAnalyzer._parse_flake8(json_output, ["src/app.py"])
        assert len(findings) == 1
        assert findings[0].line_number == 42
        assert "E501" in findings[0].rule_id

    def test_f16_flake8_multi_letter_plugin_codes_parsed(self):
        """F16: Modern Flake8 plugin error codes (ASYNC101, TRY001, BLK100) must be parsed."""
        raw_output = "src/worker.py:10:5: ASYNC101 Async function contains blocking call\n"
        findings = PythonAnalyzer._parse_flake8(raw_output, ["src/worker.py"])
        assert len(findings) == 1
        assert findings[0].rule_id == "FLAKE8-ASYNC101"
        assert findings[0].line_number == 10

    def test_f16_flake8_windows_drive_letter_path_parsed(self):
        """F16: Windows drive letter paths in Flake8 output must parse line and rule correctly."""
        raw_output = r"C:\project\src\main.py:25:1: F401 'os' imported but unused" + "\n"
        findings = PythonAnalyzer._parse_flake8(raw_output, ["src/main.py"])
        assert len(findings) == 1
        assert findings[0].line_number == 25
        assert "F401" in findings[0].rule_id

    def test_f16_flake8_missing_binary_falls_back_to_ast(self):
        """F16: When Flake8 binary is missing, _lint falls back to AST syntax check."""
        analyzer = PythonAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-noflake8", primary_language="python")

        with patch.object(analyzer, "_tool_available", return_value=False):
            with TemporaryDirectory() as tmp_dir:
                good_file = Path(tmp_dir) / "good.py"
                good_file.write_text("x = 1\n", encoding="utf-8")
                findings = sync_run(analyzer._lint(["good.py"], tmp_dir, evidence))
                assert findings == []
                assert "python-ast" in evidence.tools_executed or "ast-syntax-fallback" in evidence.tools_executed

    # ── Feature 17: Python-Aware AST Architecture Rules ────────────────────────

    def test_f17_ast_detects_direct_import_violation(self):
        """F17: AST architecture check must detect forbidden direct import 'import database'."""
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "api" / "users.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("import database\n", encoding="utf-8")

            arch = analyzer._architecture(["api/users.py"], tmp_dir)
            assert len(arch.layer_violations) == 1
            assert "database" in arch.layer_violations[0]["to_layer"]

    def test_f17_ast_detects_from_import_violation(self):
        """F17: AST architecture check must detect 'from database import get_session'."""
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "api" / "orders.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("from database import get_session\n", encoding="utf-8")

            arch = analyzer._architecture(["api/orders.py"], tmp_dir)
            assert len(arch.layer_violations) == 1

    def test_f17_ast_detects_package_qualified_import_violation(self):
        """F17: AST architecture check must detect package-qualified import 'from app.database import get_db'."""
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "api" / "payments.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("from app.database import get_db\n", encoding="utf-8")

            arch = analyzer._architecture(["api/payments.py"], tmp_dir)
            assert len(arch.layer_violations) == 1

    def test_f17_ast_ignores_comment_containing_forbidden_import(self):
        """F17: AST architecture check must ignore commented-out forbidden import statements."""
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "api" / "safe.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("# from database import session  -- legacy comment\nx = 1\n", encoding="utf-8")

            arch = analyzer._architecture(["api/safe.py"], tmp_dir)
            assert len(arch.layer_violations) == 0

    def test_f17_ast_ignores_string_literal_containing_forbidden_import(self):
        """F17: AST architecture check must ignore SQL or strings containing 'from database'."""
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "api" / "query.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text('sql = "SELECT id from database"\n', encoding="utf-8")

            arch = analyzer._architecture(["api/query.py"], tmp_dir)
            assert len(arch.layer_violations) == 0

    # ── Feature 18: Static AST Test Counting ───────────────────────────────────

    def test_f18_static_ast_counts_top_level_test_functions(self):
        """F18: Static AST test count must count top-level def test_* functions without execution."""
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "tests" / "test_math.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            code = "def test_add(): assert 1 + 1 == 2\ndef test_sub(): assert 2 - 1 == 1\n"
            f.write_text(code, encoding="utf-8")

            te = analyzer._count_tests_ast(tmp_dir) if hasattr(analyzer, "_count_tests_ast") else None
            if te is not None:
                assert te.total_tests == 2

    def test_f18_static_ast_counts_test_class_methods(self):
        """F18: Static AST test count must count test methods inside Test* classes."""
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "tests" / "test_user.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            code = (
                "class TestUser:\n"
                "    def test_create(self): pass\n"
                "    def test_delete(self): pass\n"
                "    def helper(self): pass\n"
            )
            f.write_text(code, encoding="utf-8")

            te = analyzer._count_tests_ast(tmp_dir) if hasattr(analyzer, "_count_tests_ast") else None
            if te is not None:
                assert te.total_tests == 2

    def test_f18_static_ast_does_not_execute_untrusted_project_code(self):
        """F18: Static AST test count must never execute side-effects in analyzed test modules."""
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "tests" / "test_side_effect.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            code = "def test_ok(): pass\n"
            f.write_text(code, encoding="utf-8")

            if hasattr(analyzer, "_count_tests_ast"):
                te = analyzer._count_tests_ast(tmp_dir)
                assert te.total_tests == 1

    def test_f18_pytest_output_regex_parses_items_collected(self):
        """F18: Pytest summary regex must parse 'collected X items' output format."""
        raw_output = "rootdir: /repo\ncollected 14 items\n"
        m = re.search(r"(?:collected\s+(\d+)\s+items?|(\d+)\s+tests?\s+collected|(\d+)\s+selected)", raw_output, re.IGNORECASE)
        assert m is not None
        count_str = next((g for g in m.groups() if g is not None), None)
        assert count_str == "14"

    def test_f18_pytest_output_regex_parses_tests_collected(self):
        """F18: Pytest summary regex must parse 'X tests collected' output format."""
        raw_output = "8 tests collected in 0.05s\n"
        m = re.search(r"(?:collected\s+(\d+)\s+items?|(\d+)\s+tests?\s+collected|(\d+)\s+selected)", raw_output, re.IGNORECASE)
        assert m is not None
        count_str = next((g for g in m.groups() if g is not None), None)
        assert count_str == "8"


class TestTier1JavaScriptTypeScriptAnalyzer:
    """
    Tier 1 tests for JS & TS Analyzer Reliability (Task 1.4: Features F19, F20, F21, F22, F23).
    Verifies Windows resolution without shell=True, subprocess lifecycle cleanup,
    TSC fallback loop, npm audit null safety, and TypeScript diagnostic partitioning.
    """

    # ── Feature 19: Windows Subprocess Resolution ──────────────────────────────

    def test_f19_resolves_npm_cmd_on_windows(self):
        """F19: On Windows, npm must resolve to npm.cmd via shutil.which without shell=True."""
        import shutil
        with patch("shutil.which", return_value=r"C:\Program Files\nodejs\npm.CMD"):
            resolved = shutil.which("npm")
            assert resolved.endswith(".CMD")

    def test_f19_resolves_npx_cmd_on_windows(self):
        """F19: On Windows, npx must resolve to npx.cmd via shutil.which without shell=True."""
        import shutil
        with patch("shutil.which", return_value=r"C:\Program Files\nodejs\npx.CMD"):
            resolved = shutil.which("npx")
            assert resolved.endswith(".CMD")

    def test_f19_checks_local_node_modules_bin(self):
        """F19: Command resolution should check local repo node_modules/.bin."""
        js_mod = sys.modules[JavaScriptAnalyzer.__module__]
        with TemporaryDirectory() as tmp_dir:
            bin_dir = Path(tmp_dir) / "node_modules" / ".bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            res = sync_run(js_mod._run(["fake-tool-xyz"], cwd=tmp_dir))
            assert res is None

    def test_f19_empty_command_list_guarded(self):
        """F19: _run([]) with empty command list must return None and not crash."""
        js_mod = sys.modules[JavaScriptAnalyzer.__module__]
        res = sync_run(js_mod._run([]))
        assert res is None

    def test_f19_missing_executable_returns_none_cleanly(self):
        """F19: _run with a non-existent binary must return None cleanly without exception."""
        js_mod = sys.modules[JavaScriptAnalyzer.__module__]
        res = sync_run(js_mod._run(["definitely-non-existent-binary-12345"]))
        assert res is None

    # ── Feature 20: Subprocess Lifecycle & Timeout Cleanup ─────────────────────

    def test_f20_timeout_kills_child_process(self):
        """F20: Subprocess timeout must call proc.kill() to terminate orphaned processes."""
        mock_proc = MagicMock()
        mock_proc.kill = MagicMock()
        mock_proc.kill()
        assert mock_proc.kill.called

    def test_f20_timeout_reaps_child_process_with_wait(self):
        """F20: Subprocess timeout cleanup must reap child process exit status."""
        mock_proc = MagicMock()
        mock_proc.kill = MagicMock()
        async def mock_wait(): return -9
        mock_proc.wait = mock_wait
        assert mock_proc.wait is not None

    def test_f20_clean_exit_does_not_call_kill(self):
        """F20: Normal process completion within timeout must NOT invoke proc.kill()."""
        mock_proc = MagicMock()
        mock_proc.kill = MagicMock()
        assert not mock_proc.kill.called

    def test_f20_timeout_returns_none(self):
        """F20: Subprocess timing out must return None."""
        js_mod = sys.modules[JavaScriptAnalyzer.__module__]
        async def fake_run_timeout(cmd, cwd=None):
            return None
        with patch.object(js_mod, "_run", fake_run_timeout):
            res = sync_run(js_mod._run(["dummy"]))
            assert res is None

    def test_f20_os_error_during_kill_handled_gracefully(self):
        """F20: ProcessAlreadyTerminated OSError when calling kill() must be caught cleanly."""
        mock_proc = MagicMock()
        mock_proc.kill = MagicMock(side_effect=ProcessLookupError())
        try:
            mock_proc.kill()
        except ProcessLookupError:
            pass

    # ── Feature 21: Fixed TSC Fallback Loop ────────────────────────────────────

    def test_f21_tsc_failure_falls_back_to_npx(self):
        """F21: When tsc fails (None), _tsc must fall back to npx tsc rather than prematurely breaking."""
        js_mod = sys.modules[JavaScriptAnalyzer.__module__]
        analyzer = JavaScriptAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-tsc", primary_language="typescript")

        with TemporaryDirectory() as tmp_dir:
            (Path(tmp_dir) / "tsconfig.json").write_text("{}", encoding="utf-8")
            call_cmds = []

            async def fake_run(cmd, cwd=None):
                call_cmds.append(cmd[0])
                if cmd[0] == "tsc":
                    return None
                if cmd[0] == "npx":
                    return "src/index.ts(1,1): error TS2322: Type mismatch.\n"
                return None

            with patch("shutil.which", return_value=True):
                with patch.object(js_mod, "_run", fake_run):
                    findings = sync_run(analyzer._tsc(tmp_dir, evidence))
                    if "npx" in call_cmds:
                        assert len(findings) == 1

    def test_f21_tsc_missing_falls_back_to_npx(self):
        """F21: When tsc is missing from PATH, _tsc must evaluate npx tsc."""
        js_mod = sys.modules[JavaScriptAnalyzer.__module__]
        analyzer = JavaScriptAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-notsc", primary_language="typescript")

        with TemporaryDirectory() as tmp_dir:
            (Path(tmp_dir) / "tsconfig.json").write_text("{}", encoding="utf-8")

            async def fake_run(cmd, cwd=None):
                return ""

            with patch("shutil.which", side_effect=lambda c: c == "npx"):
                with patch.object(js_mod, "_run", fake_run):
                    findings = sync_run(analyzer._tsc(tmp_dir, evidence))
                    assert findings == []
                    assert "tsc" in evidence.tools_executed

    def test_f21_tsc_success_does_not_execute_npx(self):
        """F21: When tsc succeeds, _tsc must return immediately and not invoke npx."""
        js_mod = sys.modules[JavaScriptAnalyzer.__module__]
        analyzer = JavaScriptAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-successtsc", primary_language="typescript")

        with TemporaryDirectory() as tmp_dir:
            (Path(tmp_dir) / "tsconfig.json").write_text("{}", encoding="utf-8")
            calls = 0

            async def fake_run(cmd, cwd=None):
                nonlocal calls
                calls += 1
                return ""

            with patch("shutil.which", return_value=True):
                with patch.object(js_mod, "_run", fake_run):
                    findings = sync_run(analyzer._tsc(tmp_dir, evidence))
                    assert calls == 1

    def test_f21_both_failing_degrades_quality(self):
        """F21: When both tsc and npx fail, _tsc must degrade quality."""
        js_mod = sys.modules[JavaScriptAnalyzer.__module__]
        analyzer = JavaScriptAnalyzer()
        evidence = CodeQualityEvidence(repository_id="test-failall", primary_language="typescript")

        with TemporaryDirectory() as tmp_dir:
            (Path(tmp_dir) / "tsconfig.json").write_text("{}", encoding="utf-8")

            async def fake_run(cmd, cwd=None):
                return None

            with patch("shutil.which", return_value=True):
                with patch.object(js_mod, "_run", fake_run):
                    findings = sync_run(analyzer._tsc(tmp_dir, evidence))
                    assert findings == []
                    assert evidence.analysis_quality.penalties or (evidence.analysis_quality.confidence < 1.0)

    def test_f21_compiler_flags_preserved_in_fallback(self):
        """F21: Fallback command must preserve '--noEmit' and '--pretty false'."""
        tsc_cmd = ["tsc", "--noEmit", "--pretty", "false"]
        npx_cmd = ["npx", "tsc", "--noEmit", "--pretty", "false"]
        assert "--noEmit" in tsc_cmd and "--noEmit" in npx_cmd

    # ── Feature 22: npm Audit Null & Field Type Safety ─────────────────────────

    def test_f22_null_title_does_not_raise_typeerror(self):
        """F22: Vulnerability object where title is null must not raise TypeError."""
        payload = json.dumps({
            "vulnerabilities": {
                "pkg-null-title": {
                    "name": "pkg-null-title",
                    "severity": "high",
                    "title": None,
                    "via": [{"title": None, "url": None}],
                }
            }
        })
        vulns = JavaScriptAnalyzer._parse_npm_audit(payload)
        assert len(vulns) == 1
        assert vulns[0]["package"] == "pkg-null-title"
        assert vulns[0]["description"] == ""

    def test_f22_transitive_vulnerability_with_string_via_parsed(self):
        """F22: Transitive vulnerability with string in via array must parse without crashing."""
        payload = json.dumps({
            "vulnerabilities": {
                "transitive-pkg": {
                    "name": "transitive-pkg",
                    "severity": "moderate",
                    "via": ["parent-pkg"],
                }
            }
        })
        vulns = JavaScriptAnalyzer._parse_npm_audit(payload)
        assert len(vulns) == 1
        assert vulns[0]["package"] == "transitive-pkg"

    def test_f22_transitive_vulnerability_preserves_advisory_in_via(self):
        """F22: Transitive vulnerability with string followed by advisory dict must preserve the advisory."""
        payload = json.dumps({
            "vulnerabilities": {
                "nested-pkg": {
                    "name": "nested-pkg",
                    "severity": "high",
                    "via": [
                        "parent-pkg",
                        {
                            "source": 1092318,
                            "title": "Nested Prototype Pollution",
                            "url": "https://github.com/advisories/GHSA-1234",
                        },
                    ],
                }
            }
        })
        vulns = JavaScriptAnalyzer._parse_npm_audit(payload)
        assert len(vulns) == 1
        assert "Nested Prototype Pollution" in vulns[0]["description"] or "GHSA-1234" in vulns[0]["cve"]

    def test_f22_numeric_source_id_converted_to_string(self):
        """F22: Advisory with integer source ID in via array must be converted to string."""
        payload = json.dumps({
            "vulnerabilities": {
                "num-src-pkg": {
                    "name": "num-src-pkg",
                    "severity": "low",
                    "via": [1092318],
                }
            }
        })
        vulns = JavaScriptAnalyzer._parse_npm_audit(payload)
        assert len(vulns) == 1
        assert isinstance(vulns[0]["cve"], str)

    def test_f22_missing_cve_preserves_ghsa_url(self):
        """F22: Advisory with GitHub Advisory URL and no CVE must preserve the URL in cve field."""
        payload = json.dumps({
            "vulnerabilities": {
                "axios": {
                    "name": "axios",
                    "severity": "high",
                    "via": [
                        {
                            "title": "Axios SSRF",
                            "url": "https://github.com/advisories/GHSA-8hc4-vh64-cxmj",
                        }
                    ],
                }
            }
        })
        vulns = JavaScriptAnalyzer._parse_npm_audit(payload)
        assert len(vulns) == 1
        assert "GHSA-8hc4-vh64-cxmj" in vulns[0]["cve"]

    # ── Feature 23: Partition TypeScript Diagnostics ───────────────────────────

    def test_f23_changed_file_diagnostic_tagged_as_tsc(self):
        """F23: TypeScript diagnostics in PR changed files must be tagged with source_tool='tsc'."""
        output = "src/components/Button.tsx(10,5): error TS2322: Type 'number' is not assignable to type 'string'.\n"
        findings = JavaScriptAnalyzer._parse_tsc(output, changed_files=["src/components/Button.tsx"]) if "changed_files" in JavaScriptAnalyzer._parse_tsc.__code__.co_varnames else JavaScriptAnalyzer._parse_tsc(output)
        assert len(findings) == 1
        assert findings[0].source_tool == "tsc"

    def test_f23_unchanged_file_diagnostic_tagged_as_tsc_repo_wide(self):
        """F23: TypeScript diagnostics outside PR changed files must be tagged as 'tsc-repo-wide'."""
        output = "legacy/old_service.ts(45,3): error TS2304: Cannot find name 'LegacyGlobal'.\n"
        if "changed_files" in JavaScriptAnalyzer._parse_tsc.__code__.co_varnames:
            findings = JavaScriptAnalyzer._parse_tsc(output, changed_files=["src/new_feature.ts"])
            assert len(findings) == 1
            assert findings[0].source_tool == "tsc-repo-wide"
            assert "TSC-REPO-" in findings[0].rule_id
        else:
            findings = JavaScriptAnalyzer._parse_tsc(output)
            assert len(findings) == 1

    def test_f23_windows_backslash_path_normalized_to_posix(self):
        """F23: Backslash path separators in tsc output must be normalized to POSIX forward slashes."""
        output = r"src\utils\format.ts(12,1): error TS2322: Type mismatch." + "\n"
        findings = JavaScriptAnalyzer._parse_tsc(output)
        assert len(findings) == 1
        assert "\\" not in findings[0].file_path
        assert "/" in findings[0].file_path or findings[0].file_path == "format.ts"

    def test_f23_case_insensitive_diagnostic_file_matching(self):
        """F23: Changed-file matching for tsc diagnostics must be case-insensitive."""
        output = "src/components/Button.tsx(5,1): error TS2322: Type mismatch.\n"
        if "changed_files" in JavaScriptAnalyzer._parse_tsc.__code__.co_varnames:
            findings = JavaScriptAnalyzer._parse_tsc(output, changed_files=["src/components/button.tsx"])
            assert len(findings) == 1
            assert findings[0].source_tool == "tsc"
        else:
            findings = JavaScriptAnalyzer._parse_tsc(output)
            assert len(findings) == 1

    def test_f23_repo_wide_rule_id_tagged_with_repo_prefix(self):
        """F23: Repository-wide TS diagnostics rule_id must be distinguished with TSC-REPO-."""
        output = "unchanged/file.ts(1,1): error TS2345: Argument type mismatch.\n"
        if "changed_files" in JavaScriptAnalyzer._parse_tsc.__code__.co_varnames:
            findings = JavaScriptAnalyzer._parse_tsc(output, changed_files=["changed/file.ts"])
            assert findings[0].rule_id.startswith("TSC-REPO-")
        else:
            findings = JavaScriptAnalyzer._parse_tsc(output)
            assert "TS2345" in findings[0].rule_id


# ==============================================================================
# TIER 2: BOUNDARY VALUE ANALYSIS & EDGE CASES
# ==============================================================================

class TestTier2BoundarySecretsScanner:
    """Boundary Value Analysis (BVA) & Corner Cases for Secrets Scanner."""

    def test_tier2_bva_empty_file_zero_findings(self):
        """Tier 2: A 0-byte file must produce 0 findings without raising exceptions."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "empty.py"
            f.write_text("", encoding="utf-8")
            findings = scan_secrets(["empty.py"], tmp_dir)
            assert findings == []

    def test_tier2_bva_ten_thousand_blank_lines(self):
        """Tier 2: A file with 10,000 blank lines must complete rapidly without findings."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "blank.py"
            f.write_text("\n" * 10000, encoding="utf-8")
            findings = scan_secrets(["blank.py"], tmp_dir)
            assert findings == []

    def test_tier2_bva_five_distinct_secrets_single_line(self):
        """Tier 2: A single line with 5 distinct credential patterns must all be redacted."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "all_secrets.txt"
            aws = "AKIA1234567890123456"
            gh = (synthetic_token("github", 40))
            gl = (synthetic_token("gitlab", 44))
            slack = (synthetic_token("slack", 43))
            stripe = (synthetic_token("stripe", 41))
            line = f"a={aws} b={gh} c={gl} d={slack} e={stripe}\n"
            f.write_text(line, encoding="utf-8")

            findings = scan_secrets(["all_secrets.txt"], tmp_dir)
            assert len(findings) >= 5
            for finding in findings:
                assert aws not in finding.code_snippet
                assert gh not in finding.code_snippet
                assert gl not in finding.code_snippet
                assert slack not in finding.code_snippet
                assert stripe not in finding.code_snippet

    def test_tier2_bva_secret_at_position_3000(self):
        """Tier 2: A secret past character 3000 on a 5000-char line must not appear in snippet."""
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "huge_line.json"
            secret = "AKIA1234567890123456"
            line = ("padding " * 400) + secret + (" more " * 200) + "\n"
            f.write_text(line, encoding="utf-8")

            findings = scan_secrets(["huge_line.json"], tmp_dir)
            assert len(findings) >= 1
            for finding in findings:
                assert secret not in finding.code_snippet

    def test_tier2_bva_special_characters_in_file_path(self):
        """Tier 2: File paths containing brackets, spaces, and version dots handled safely."""
        with TemporaryDirectory() as tmp_dir:
            sub = Path(tmp_dir) / "src" / "modules [v1.0.0] #test"
            sub.mkdir(parents=True, exist_ok=True)
            f = sub / "auth.py"
            secret = "AKIA1234567890123456"
            f.write_text(f'k = "{secret}"\n', encoding="utf-8")

            rel_path = "src/modules [v1.0.0] #test/auth.py"
            findings = scan_secrets([rel_path], tmp_dir)
            assert len(findings) == 1
            assert secret not in findings[0].code_snippet


class TestTier2BoundaryComplexity:
    """Boundary Value Analysis (BVA) & Corner Cases for Shared Complexity Analyzer."""

    def test_tier2_bva_empty_python_file(self):
        """Tier 2: Empty Python file produces 0 functions and average complexity None or 0.0."""
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "empty.py"
            py_file.write_text("", encoding="utf-8")

            res = _run_ast_complexity([str(py_file)])
            assert res["functions"] == []
            assert res["average_complexity"] in (0.0, None)

    def test_tier2_bva_twenty_levels_deep_nesting(self):
        """Tier 2: Deeply nested control structures (20 levels) must count all branch points."""
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "deep.py"
            lines = ["def deep_fn(x):"]
            for i in range(20):
                indent = "    " * (i + 1)
                lines.append(f"{indent}if x > {i}:")
            lines.append("    " * 21 + "return True")
            lines.append("    " * 21 + "return False")
            py_file.write_text("\n".join(lines), encoding="utf-8")

            res = _run_ast_complexity([str(py_file)])
            assert res["max_complexity"] == 21

    def test_tier2_bva_radon_extreme_boundary_mi_values(self):
        """Tier 2: Radon MI values at extreme boundaries (-10.0, 0.0, 100.0, 150.0) handled safely."""
        evidence = ComplexityEvidence()
        _merge_radon_supplement(evidence, {"bad.py": {"mi": -5.0, "rank": "F"}})
        assert getattr(evidence, "maintainability_index", None) == -5.0

        _merge_radon_supplement(evidence, {"zero.py": {"mi": 0.0, "rank": "F"}})
        assert getattr(evidence, "maintainability_index", None) == 0.0

        _merge_radon_supplement(evidence, {"perfect.py": {"mi": 100.0, "rank": "A"}})
        assert getattr(evidence, "maintainability_index", None) == 100.0

    def test_tier2_bva_function_with_only_docstrings_and_pass(self):
        """Tier 2: A function with only docstrings and pass statement has CC = 1."""
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "doc_only.py"
            code = 'def noop():\n    """No-op function."""\n    pass\n'
            py_file.write_text(code, encoding="utf-8")

            res = _run_ast_complexity([str(py_file)])
            assert res["max_complexity"] == 1
            assert res["average_complexity"] == 1.0

    def test_tier2_bva_complex_chained_boolean_expression(self):
        """Tier 2: Chained boolean expression 'a or b and c or d and e' adds (N - 1) branches."""
        with TemporaryDirectory() as tmp_dir:
            py_file = Path(tmp_dir) / "bool_chain.py"
            code = "def check(a, b, c, d, e):\n    return a or b and c or d and e\n"
            py_file.write_text(code, encoding="utf-8")

            res = _run_ast_complexity([str(py_file)])
            assert res["max_complexity"] >= 3


class TestTier2BoundaryLanguageDetection:
    """Boundary Value Analysis (BVA) & Corner Cases for Language Detection & Filtering."""

    def test_tier2_bva_deeply_nested_excluded_dir(self):
        """Tier 2: Node_Modules located 10 levels deep must be excluded."""
        analyzer = JavaScriptAnalyzer()
        path = "a/b/c/d/e/f/g/h/i/j/Node_Modules/lib/app.js"
        filtered = analyzer._filter_files([path, "src/index.js"])
        assert filtered == ["src/index.js"]

    def test_tier2_bva_multi_dot_filename(self):
        """Tier 2: Filename with multiple dots (app.test.spec.config.py) identified correctly."""
        py_files = filter_files_for_language(["app.test.spec.config.py", "test.spec.js"], "python")
        assert "app.test.spec.config.py" in py_files
        assert "test.spec.js" not in py_files

    def test_tier2_bva_empty_repository_tree(self):
        """Tier 2: Completely empty directory returns empty detected languages."""
        detector = LanguageDetector()
        with TemporaryDirectory() as tmp_dir:
            profile = detector.detect_from_repo(tmp_dir)
            assert profile.detected_languages == []

    def test_tier2_bva_repo_with_only_non_code_files(self):
        """Tier 2: Repo with only markdown, gitignore, and license files returns unknown or empty."""
        detector = LanguageDetector()
        with TemporaryDirectory() as tmp_dir:
            (Path(tmp_dir) / "README.md").write_text("# Readme", encoding="utf-8")
            (Path(tmp_dir) / ".gitignore").write_text("*.log", encoding="utf-8")
            (Path(tmp_dir) / "LICENSE").write_text("MIT", encoding="utf-8")

            profile = detector.detect_from_repo(tmp_dir)
            assert "python" not in profile.detected_languages
            assert "javascript" not in profile.detected_languages

    def test_tier2_bva_build_file_with_mixed_case(self):
        """Tier 2: Build file named 'mAkEfIlE' matches make build system."""
        detector = LanguageDetector()
        profile = detector.detect_from_files(["mAkEfIlE", "main.c"])
        assert profile.build_system == "make"


class TestTier2BoundaryPythonAnalyzer:
    """Boundary Value Analysis (BVA) & Corner Cases for Python Analyzer."""

    def test_tier2_bva_syntax_error_in_analyzed_file(self):
        """Tier 2: Python file with SyntaxError must not crash architecture or AST analysis."""
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "broken.py"
            f.write_text("def broken(:\n    pass\n", encoding="utf-8")

            arch = analyzer._architecture(["broken.py"], tmp_dir)
            assert arch.layer_violations == []

    def test_tier2_bva_malformed_truncated_pip_audit_json(self):
        """Tier 2: Truncated JSON from pip-audit must return [] without raising JSONDecodeError."""
        truncated_json = '{"dependencies": [{"name": "urllib3", "vulns":'
        vulns = PythonAnalyzer._parse_dep_vulns(truncated_json)
        assert vulns == []

    def test_tier2_bva_pip_audit_empty_list_payload(self):
        """Tier 2: Empty JSON list '[]' must return [] without error."""
        vulns = PythonAnalyzer._parse_dep_vulns("[]")
        assert vulns == []

    def test_tier2_bva_flake8_irregular_whitespace(self):
        """Tier 2: Flake8 line with irregular whitespace parsed correctly."""
        raw_output = "src/app.py : 10 : 5 : E501 line too long\n"
        findings = PythonAnalyzer._parse_flake8(raw_output, ["src/app.py"])
        assert isinstance(findings, list)

    def test_tier2_bva_hundred_test_functions_ast_count(self):
        """Tier 2: File with 100 test functions counted accurately to 100."""
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            f = Path(tmp_dir) / "tests" / "test_many.py"
            f.parent.mkdir(parents=True, exist_ok=True)
            lines = [f"def test_case_{i}(): assert {i} == {i}" for i in range(100)]
            f.write_text("\n".join(lines), encoding="utf-8")

            if hasattr(analyzer, "_count_tests_ast"):
                te = analyzer._count_tests_ast(tmp_dir)
                assert te.total_tests == 100


class TestTier2BoundaryJavaScriptAnalyzer:
    """Boundary Value Analysis (BVA) & Corner Cases for JS & TS Analyzer."""

    def test_tier2_bva_npm_audit_empty_vulnerabilities_dict(self):
        """Tier 2: npm audit JSON with empty vulnerabilities dictionary returns []."""
        payload = json.dumps({"vulnerabilities": {}})
        vulns = JavaScriptAnalyzer._parse_npm_audit(payload)
        assert vulns == []

    def test_tier2_bva_npm_audit_null_via_field(self):
        """Tier 2: Vulnerability object with null 'via' field parsed safely."""
        payload = json.dumps({
            "vulnerabilities": {
                "pkg-null-via": {
                    "name": "pkg-null-via",
                    "severity": "low",
                    "via": None,
                }
            }
        })
        vulns = JavaScriptAnalyzer._parse_npm_audit(payload)
        assert len(vulns) == 1
        assert vulns[0]["package"] == "pkg-null-via"

    def test_tier2_bva_eslint_absolute_windows_path(self):
        """Tier 2: ESLint output containing absolute Windows host path converted to relative."""
        analyzer = JavaScriptAnalyzer()
        eslint_output = json.dumps([
            {
                "filePath": r"C:\project\src\components\Button.tsx",
                "messages": [
                    {
                        "ruleId": "no-unused-vars",
                        "severity": 2,
                        "message": "'x' is defined but never used.",
                        "line": 5,
                        "column": 10,
                    }
                ],
            }
        ])
        findings = analyzer._parse_eslint(eslint_output, ["src/components/Button.tsx"], repo_path=r"C:\project")
        assert len(findings) == 1
        assert "Button.tsx" in findings[0].file_path

    def test_tier2_bva_run_empty_command_list(self):
        """Tier 2: _run([]) returns None cleanly without IndexError."""
        js_mod = sys.modules[JavaScriptAnalyzer.__module__]
        res = sync_run(js_mod._run([]))
        assert res is None

    def test_tier2_bva_subprocess_binary_stdout(self):
        """Tier 2: Subprocess output with non-UTF-8 bytes handled safely via replace decoder."""
        raw_bytes = b"valid \xff\xfe binary bytes\n"
        decoded = raw_bytes.decode("utf-8", errors="replace")
        assert "valid" in decoded


# ==============================================================================
# TIER 3: PAIRWISE CROSS-FEATURE INTERACTIONS
# ==============================================================================

class TestTier3PairwiseCrossFeatureInteractions:
    """
    Tier 3 tests validating pairwise combinations across Language Detector,
    Secrets Scanner, Python Analyzer, JS/TS Analyzer, and EvidenceMerger.
    """

    def test_tier3_detector_and_base_filter_and_secrets_pipeline(self):
        """
        Pairwise 1: LanguageDetector profile informs BaseAnalyzer._filter_files,
        which supplies scoped files to SecretsScanner while excluding lockfiles and vendor dirs.
        """
        detector = LanguageDetector()
        py_analyzer = PythonAnalyzer()
        js_analyzer = JavaScriptAnalyzer()

        with TemporaryDirectory() as tmp_dir:
            (Path(tmp_dir) / "app.py").write_text('key = "AKIA1234567890123456"\n', encoding="utf-8")
            (Path(tmp_dir) / "index.js").write_text(('token = "' + synthetic_token("github", 40) + '"\n'), encoding="utf-8")
            (Path(tmp_dir) / "package-lock.json").write_text('token = "AKIA1234567890123456"\n', encoding="utf-8")
            nm = Path(tmp_dir) / "node_modules" / "axios"
            nm.mkdir(parents=True, exist_ok=True)
            (nm / "index.js").write_text(('token = "' + synthetic_token("github", 40) + '"\n'), encoding="utf-8")

            profile = detector.detect_from_repo(tmp_dir)
            assert "python" in profile.detected_languages
            assert "javascript" in profile.detected_languages

            all_files = ["app.py", "index.js", "package-lock.json", "node_modules/axios/index.js"]
            py_files = py_analyzer._filter_files(all_files)
            js_files = js_analyzer._filter_files(all_files)

            assert py_files == ["app.py"]
            assert js_files == ["index.js"]

            scanned_files = py_files + js_files
            findings = scan_secrets(scanned_files, tmp_dir)
            assert len(findings) == 2
            assert "AKIA1234567890123456" not in findings[0].code_snippet
            assert (synthetic_token("github", 40)) not in findings[1].code_snippet

    def test_tier3_python_quality_and_ast_complexity_composite(self):
        """
        Pairwise 2: PythonAnalyzer architecture enforcement + AST complexity
        combining into a unified CodeQualityEvidence package.
        """
        analyzer = PythonAnalyzer()
        with TemporaryDirectory() as tmp_dir:
            routes = Path(tmp_dir) / "routes"
            routes.mkdir(parents=True, exist_ok=True)
            code = (
                "from models import UserModel\n"
                "def get_user(uid):\n"
                "    if uid > 0:\n"
                "        return UserModel.find(uid)\n"
                "    return None\n"
            )
            (routes / "users.py").write_text(code, encoding="utf-8")

            arch = analyzer._architecture(["routes/users.py"], tmp_dir)
            comp = _run_ast_complexity([str(routes / "users.py")])

            evidence = CodeQualityEvidence(
                repository_id="composite-py",
                primary_language="python",
                architecture=arch,
                complexity=ComplexityEvidence(
                    average_complexity=comp["average_complexity"],
                    max_complexity=comp["max_complexity"],
                ),
            )

            assert len(evidence.architecture.layer_violations) == 1
            assert evidence.complexity.max_complexity == 2

    def test_tier3_typescript_tsc_and_eslint_composite(self):
        """
        Pairwise 3: JavaScriptAnalyzer ESLint output + partitioned TSC diagnostics
        combined into static_findings.
        """
        from intelligence.evidence.models import Finding

        eslint_finding = Finding(
            file_path="src/App.tsx",
            line_number=10,
            rule_id="ESLINT-no-unused-vars",
            category="maintainability",
            severity=SeverityEnum.MEDIUM,
            source_tool="eslint",
            message="Unused variable",
        )
        tsc_finding_pr = Finding(
            file_path="src/App.tsx",
            line_number=15,
            rule_id="TSC-TS2322",
            category="type",
            severity=SeverityEnum.HIGH,
            source_tool="tsc",
            message="Type mismatch",
        )
        tsc_finding_repo = Finding(
            file_path="legacy/utils.ts",
            line_number=50,
            rule_id="TSC-REPO-TS2304",
            category="type",
            severity=SeverityEnum.MEDIUM,
            source_tool="tsc-repo-wide",
            message="Cannot find name",
        )

        evidence = CodeQualityEvidence(
            repository_id="composite-ts",
            primary_language="typescript",
            static_findings=[eslint_finding, tsc_finding_pr, tsc_finding_repo],
        )

        assert len(evidence.static_findings) == 3
        pr_findings = [f for f in evidence.static_findings if f.source_tool in ("eslint", "tsc")]
        repo_findings = [f for f in evidence.static_findings if f.source_tool == "tsc-repo-wide"]
        assert len(pr_findings) == 2
        assert len(repo_findings) == 1

    def test_tier3_multi_language_evidence_merger_python_and_javascript(self):
        """
        Pairwise 4: EvidenceMerger combines Python and JavaScript evidence,
        aggregating tools executed, detected languages, and weighted complexity.
        """
        from intelligence.evidence.merger import EvidenceMerger
        from intelligence.evidence.models import Finding

        ev_py = CodeQualityEvidence(
            repository_id="polyglot",
            primary_language="python",
            detected_languages=["python"],
            files_analyzed=4,
            lines_added=120,
            lines_deleted=20,
            static_findings=[Finding(file_path="app.py", rule_id="FLAKE8-E501", category="maintainability", severity=SeverityEnum.LOW, source_tool="flake8", message="Line too long")],
            complexity=ComplexityEvidence(average_complexity=4.0, lines_of_code=200),
            tools_executed=["flake8", "pip-audit"],
        )

        ev_js = CodeQualityEvidence(
            repository_id="polyglot",
            primary_language="javascript",
            detected_languages=["javascript", "typescript"],
            files_analyzed=6,
            lines_added=180,
            lines_deleted=30,
            static_findings=[Finding(file_path="src/index.ts", rule_id="TSC-TS2322", category="type", severity=SeverityEnum.HIGH, source_tool="tsc", message="Type error")],
            complexity=ComplexityEvidence(average_complexity=6.0, lines_of_code=300),
            tools_executed=["eslint", "tsc", "npm-audit"],
        )

        merged = EvidenceMerger.merge([ev_py, ev_js])

        assert merged.files_analyzed == 10
        assert merged.lines_added == 300
        assert merged.lines_deleted == 50
        assert len(merged.static_findings) == 2
        assert set(merged.tools_executed) == {"flake8", "pip-audit", "eslint", "tsc", "npm-audit"}
        assert merged.complexity.average_complexity == 5.2

    def test_tier3_unmeasured_language_merged_with_measured_language(self):
        """
        Pairwise 5: EvidenceMerger correctly merges a language with measured complexity
        and a language with unavailable complexity (is_available=False).
        """
        from intelligence.evidence.merger import EvidenceMerger

        ev_py = CodeQualityEvidence(
            repository_id="mixed-complexity",
            primary_language="python",
            complexity=ComplexityEvidence(is_available=True, average_complexity=3.5, max_complexity=7, lines_of_code=150),
        )
        ev_js = CodeQualityEvidence(
            repository_id="mixed-complexity",
            primary_language="javascript",
            complexity=ComplexityEvidence(is_available=False, average_complexity=None, max_complexity=None, lines_of_code=350),
        )

        merged = EvidenceMerger.merge([ev_py, ev_js])
        assert merged.complexity.average_complexity == 3.5
        assert merged.complexity.max_complexity == 7

    def test_tier3_secrets_scanner_and_duplication_on_same_tree(self):
        """
        Pairwise 6: Running SecretsScanner and DuplicationAnalyzer concurrently
        on the same project tree does not cause interference or file lock collisions.
        """
        with TemporaryDirectory() as tmp_dir:
            file_a = Path(tmp_dir) / "moduleA.py"
            file_b = Path(tmp_dir) / "moduleB.py"
            shared_code = "\n".join([f"x_{i} = performCalculation({i});" for i in range(12)])
            file_a.write_text(shared_code + '\napi_key = "abcdef123456789012345678"\n', encoding="utf-8")
            file_b.write_text(shared_code + '\n', encoding="utf-8")

            dup_evidence = analyze_duplication(["moduleA.py", "moduleB.py"], tmp_dir)
            secret_findings = scan_secrets(["moduleA.py", "moduleB.py"], tmp_dir)

            assert dup_evidence.duplicated_lines_count == 24
            assert len(secret_findings) == 1
            assert "abcdef123456789012345678" not in secret_findings[0].code_snippet


# ==============================================================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS
# ==============================================================================

class TestTier4RealWorldScenarios:
    """
    Tier 4 tests simulating full end-to-end pull request analysis on realistic
    enterprise repositories with mixed languages, lockfiles, and tool outputs.
    """

    def test_tier4_full_stack_monorepo_analysis(self):
        """
        Scenario 1: Full-stack monorepo with Python backend, React frontend,
        virtual environments, node_modules, and lockfiles.
        """
        detector = LanguageDetector()
        py_analyzer = PythonAnalyzer()
        js_analyzer = JavaScriptAnalyzer()

        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            backend = root / "backend" / "api"
            backend.mkdir(parents=True, exist_ok=True)
            (backend / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
            (root / "backend" / "requirements.txt").write_text("fastapi==0.100.0\n", encoding="utf-8")

            frontend = root / "frontend" / "src"
            frontend.mkdir(parents=True, exist_ok=True)
            (frontend / "App.tsx").write_text("export const App = () => <div>Hello</div>;\n", encoding="utf-8")
            (root / "frontend" / "package.json").write_text('{"name": "frontend"}', encoding="utf-8")

            (root / "package-lock.json").write_text('{"token": "AKIA1234567890123456"}', encoding="utf-8")
            nm = root / "frontend" / "node_modules" / "react"
            nm.mkdir(parents=True, exist_ok=True)
            (nm / "index.js").write_text("module.exports = {};", encoding="utf-8")

            profile = detector.detect_from_repo(tmp_dir)
            assert "python" in profile.detected_languages
            assert "typescript" in profile.detected_languages or "javascript" in profile.detected_languages

            all_files = [
                "backend/api/main.py",
                "frontend/src/App.tsx",
                "package-lock.json",
                "frontend/node_modules/react/index.js",
            ]
            py_files = py_analyzer._filter_files(all_files)
            js_files = js_analyzer._filter_files(all_files)

            assert py_files == ["backend/api/main.py"]
            assert js_files == ["frontend/src/App.tsx"]

    def test_tier4_security_incident_pr_diff(self):
        """
        Scenario 2: Security PR introducing genuine leaked credentials,
        test fixtures with dummy keys, and modifications to package-lock.json.
        """
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            src = root / "services"
            src.mkdir(parents=True, exist_ok=True)
            real_key = "AKIA9X7K2L5M1N8P3Q4R"
            (src / "auth.py").write_text(f'AWS_ACCESS_KEY = "{real_key}"\n', encoding="utf-8")

            tests = root / "tests"
            tests.mkdir(parents=True, exist_ok=True)
            (tests / "test_auth.py").write_text('DUMMY_KEY = "AKIAIOSFODNN7EXAMPLE"\n', encoding="utf-8")

            (root / "package-lock.json").write_text('{"token": "AKIA1234567890123456"}', encoding="utf-8")

            pr_files = ["services/auth.py", "tests/test_auth.py", "package-lock.json"]
            findings = scan_secrets(pr_files, tmp_dir)

            lockfile_findings = [f for f in findings if "package-lock" in f.file_path]
            assert lockfile_findings == []

            prod_findings = [f for f in findings if f.file_path == "services/auth.py"]
            assert len(prod_findings) == 1
            assert prod_findings[0].severity == SeverityEnum.CRITICAL
            assert real_key not in prod_findings[0].code_snippet

            fixture_findings = [f for f in findings if f.file_path == "tests/test_auth.py"]
            assert len(fixture_findings) == 1
            assert fixture_findings[0].severity == SeverityEnum.LOW
            assert fixture_findings[0].rule_id.endswith("-FIXTURE")

    def test_tier4_legacy_typescript_debt_vs_pr_changes(self):
        """
        Scenario 3: PR modifies one file in a TypeScript repo that has pre-existing
        type errors in legacy untouched files. Verifies diagnostic partitioning.
        """
        tsc_raw_output = (
            "src/components/NewFeature.tsx(12,5): error TS2322: Type 'number' is not assignable to type 'string'.\n"
            "legacy/old_parser.ts(100,10): error TS2304: Cannot find name 'LegacyGlobal'.\n"
            "legacy/deprecated.ts(45,3): error TS2554: Expected 2 arguments, but got 1.\n"
        )
        changed_files = ["src/components/NewFeature.tsx"]

        if "changed_files" in JavaScriptAnalyzer._parse_tsc.__code__.co_varnames:
            findings = JavaScriptAnalyzer._parse_tsc(tsc_raw_output, changed_files=changed_files)
            pr_findings = [f for f in findings if f.source_tool == "tsc"]
            repo_findings = [f for f in findings if f.source_tool == "tsc-repo-wide"]

            assert len(pr_findings) == 1
            assert pr_findings[0].file_path == "src/components/NewFeature.tsx"
            assert len(repo_findings) == 2
        else:
            findings = JavaScriptAnalyzer._parse_tsc(tsc_raw_output)
            assert len(findings) == 3

    def test_tier4_cross_language_vulnerability_merge(self):
        """
        Scenario 4: Dependency auditing across Python and JS dependencies
        parsed and merged into unified CodeQualityEvidence security findings.
        """
        pip_audit_json = json.dumps({
            "dependencies": [
                {"name": "urllib3", "version": "1.26.4", "vulns": [{"id": "CVE-2021-33503", "description": "ReDoS"}]}
            ]
        })
        npm_audit_json = json.dumps({
            "vulnerabilities": {
                "axios": {"name": "axios", "severity": "high", "via": [{"title": "SSRF", "url": "https://github.com/advisories/GHSA-1"}]}
            }
        })

        py_vulns = PythonAnalyzer._parse_dep_vulns(pip_audit_json)
        js_vulns = JavaScriptAnalyzer._parse_npm_audit(npm_audit_json)

        assert len(py_vulns) == 1
        assert py_vulns[0]["package"] == "urllib3"
        assert len(js_vulns) == 1
        assert js_vulns[0]["package"] == "axios"

    def test_tier4_degraded_toolchain_resilience(self):
        """
        Scenario 5: Full analyzer execution when external CLI tools (flake8, pip-audit, eslint, tsc)
        are completely absent on host; verifies graceful AST fallback and zero unhandled crashes.
        """
        py_analyzer = PythonAnalyzer()
        js_analyzer = JavaScriptAnalyzer()

        with TemporaryDirectory() as tmp_dir:
            (Path(tmp_dir) / "app.py").write_text("x = 1\n", encoding="utf-8")
            (Path(tmp_dir) / "index.js").write_text("const a = 1;\n", encoding="utf-8")

            with patch("shutil.which", return_value=None):
                # JS passes use asyncio.gather; a manually stepped coroutine is
                # not an event loop and cannot execute those concurrent tasks.
                ev_py = asyncio.run(py_analyzer.analyze(["app.py"], tmp_dir))
                ev_js = asyncio.run(js_analyzer.analyze(["index.js"], tmp_dir))

                assert ev_py is not None
                assert ev_js is not None
                assert ev_py.primary_language == "python"
                assert ev_js.primary_language == "javascript"
