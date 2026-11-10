"""
Comprehensive Regression Test Suite for Milestone 5 (Task 1.6):
Language Detection and Filtering.

Features Covered:
- Feature 10: Canonical EXCLUDED_DIRS (14 canonical directory names)
- Feature 11: Case-Insensitive Path Normalization & Extension Filtering
- Feature 12: In-Place Directory Traversal Pruning via os.walk
- Feature 13: Case-Insensitive Build Configs, Wildcards & Test Framework Hints
- Multi-Language Polyglot Profiling & Tie-Breaking
- Analyzer Registry Preservation & Contracts
"""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import pytest

from intelligence.analyzers.base import EXCLUDED_DIRS, BaseAnalyzer
from intelligence.analyzers.c.analyzer import CAnalyzer
from intelligence.analyzers.cpp.analyzer import CppAnalyzer
from intelligence.analyzers.java.analyzer import JavaAnalyzer
from intelligence.analyzers.javascript.analyzer import JavaScriptAnalyzer
from intelligence.analyzers.language_detector import (
    BUILD_FILE_MAP,
    EXTENSION_MAP,
    TEST_FRAMEWORK_HINTS,
    LanguageDetector,
    LanguageProfile,
    filter_files_for_language,
    get_extensions_for_language,
)
from intelligence.analyzers.python.analyzer import PythonAnalyzer
from intelligence.analyzers.registry import (
    ANALYZER_REGISTRY,
    get_analyzer,
    get_analyzers_for_profile,
    list_supported_languages,
)


# ── Feature 10: Canonical EXCLUDED_DIRS ───────────────────────────────────────

class TestFeature10CanonicalDirectoryExclusion:
    """Verifies that all 14 canonical excluded directories are excluded."""

    CANONICAL_14 = {
        "node_modules", "venv", ".venv", "build", "dist",
        "target", "bin", "obj", "__pycache__", "vendor",
        ".git", "generated", ".gradle", ".mvn",
    }

    def test_canonical_excluded_dirs_set_contains_all_14_entries(self):
        """EXCLUDED_DIRS frozenset in base.py must contain all 14 canonical entries."""
        assert self.CANONICAL_14.issubset(EXCLUDED_DIRS)

    @pytest.mark.parametrize("excluded_dir", list(CANONICAL_14))
    def test_each_canonical_dir_excluded_in_python_analyzer(self, excluded_dir):
        """PythonAnalyzer._filter_files must exclude every canonical excluded directory."""
        analyzer = PythonAnalyzer()
        files = [
            f"{excluded_dir}/lib/app.py",
            f"nested/{excluded_dir}/util.py",
            "src/main.py",
        ]
        filtered = analyzer._filter_files(files)
        assert filtered == ["src/main.py"]

    @pytest.mark.parametrize("excluded_dir", list(CANONICAL_14))
    def test_each_canonical_dir_excluded_in_javascript_analyzer(self, excluded_dir):
        """JavaScriptAnalyzer._filter_files must exclude every canonical excluded directory."""
        analyzer = JavaScriptAnalyzer()
        files = [
            f"{excluded_dir}/index.js",
            f"packages/{excluded_dir}/bundle.ts",
            "src/index.js",
        ]
        filtered = analyzer._filter_files(files)
        assert filtered == ["src/index.js"]


# ── Feature 11: Case-Insensitive Filtering & Path Normalization ──────────────

class TestFeature11CaseInsensitiveFileAndExtensionFiltering:
    """Verifies case-insensitive filtering for path segments and file extensions."""

    @pytest.mark.parametrize(
        "cased_dir",
        [
            "Node_Modules", "NODE_MODULES", "node_modules",
            "Venv", "VENV", ".Venv", ".VENV",
            "Build", "BUILD", "Dist", "DIST",
            "Target", "TARGET", "Bin", "BIN", "Obj", "OBJ",
            "__Pycache__", "__PYCACHE__",
            "Vendor", "VENDOR", "Generated", "GENERATED",
            ".Gradle", ".GRADLE", ".Mvn", ".MVN", ".Git", ".GIT",
        ],
    )
    def test_cased_excluded_directories_filtered_out(self, cased_dir):
        """Excluded directories must be filtered out regardless of casing."""
        analyzer = JavaScriptAnalyzer()
        files = [f"{cased_dir}/pkg/app.js", "src/index.js"]
        assert analyzer._filter_files(files) == ["src/index.js"]

    def test_windows_backslashes_with_mixed_case_excluded(self):
        """Windows backslash paths with mixed-case directories must be filtered out."""
        analyzer = PythonAnalyzer()
        files = [
            r"Node_Modules\deep\sub\pkg.py",
            r"Venv\Scripts\site.py",
            r"Build\output\main.py",
            r"src\service\main.py",
        ]
        filtered = analyzer._filter_files(files)
        assert filtered == [r"src\service\main.py"]

    def test_deeply_nested_excluded_directories(self):
        """Deeply nested excluded directories must be filtered out."""
        analyzer = JavaScriptAnalyzer()
        path = "a/b/c/d/e/f/g/h/i/j/Node_Modules/lib/app.js"
        filtered = analyzer._filter_files([path, "src/index.js"])
        assert filtered == ["src/index.js"]

    def test_valid_files_named_after_excluded_dirs_preserved(self):
        """Files whose name matches an excluded dir (e.g. build.py, vendor.js) must be preserved."""
        analyzer = PythonAnalyzer()
        files = [
            "build.py",
            "src/build.py",
            "src/vendor.py",
            "src/target.py",
            "src/generated.py",
            "src/bin.py",
        ]
        filtered = analyzer._filter_files(files)
        assert filtered == files

    def test_prefix_substring_directories_preserved(self):
        """Directories that share a prefix with an excluded dir must not be falsely excluded."""
        analyzer = PythonAnalyzer()
        files = [
            "src/build_scripts/run.py",
            "vendor_api/client.py",
            "my_node_modules_test/check.py",
            "distribution/package.py",
            "binary_trees/tree.py",
        ]
        filtered = analyzer._filter_files(files)
        assert filtered == files

    @pytest.mark.parametrize(
        "file_path,analyzer_cls",
        [
            ("main.PY", PythonAnalyzer),
            ("types.PYI", PythonAnalyzer),
            ("util.Py", PythonAnalyzer),
            ("script.PyI", PythonAnalyzer),
            ("app.JS", JavaScriptAnalyzer),
            ("component.JSX", JavaScriptAnalyzer),
            ("server.MJS", JavaScriptAnalyzer),
            ("config.CJS", JavaScriptAnalyzer),
            ("index.TS", JavaScriptAnalyzer),
            ("view.TSX", JavaScriptAnalyzer),
            ("App.JAVA", JavaAnalyzer),
            ("driver.C", CAnalyzer),
            ("engine.CPP", CppAnalyzer),
        ],
    )
    def test_uppercase_extensions_matched_by_analyzers(self, file_path, analyzer_cls):
        """Analyzer _filter_files must match uppercase and mixed-case extensions."""
        analyzer = analyzer_cls()
        files = [file_path, "README.TXT", "notes.doc"]
        filtered = analyzer._filter_files(files)
        assert filtered == [file_path]

    def test_filter_files_for_language_case_insensitivity(self):
        """filter_files_for_language must match extensions case-insensitively and exclude EXCLUDED_DIRS."""
        files = [
            "app.PY",
            "UTIL.JS",
            "server.CJS",
            "view.TSX",
            "main.JAVA",
            "lib.CPP",
            "doc.TXT",
            "Node_Modules/lib/bad.py",
            "VENV/bad.py",
            "src/build.py",
        ]
        py_files = filter_files_for_language(files, "python")
        assert "app.PY" in py_files
        assert "src/build.py" in py_files
        assert "Node_Modules/lib/bad.py" not in py_files
        assert "VENV/bad.py" not in py_files

        js_files = filter_files_for_language(files, "javascript")
        assert "UTIL.JS" in js_files
        assert "server.CJS" in js_files

        ts_files = filter_files_for_language(files, "typescript")
        assert "view.TSX" in ts_files

    def test_get_extensions_for_language_case_insensitivity(self):
        """get_extensions_for_language must strip and lowercase language name."""
        assert set(get_extensions_for_language("python")) == {".py", ".pyi"}
        assert set(get_extensions_for_language("  PYTHON  ")) == {".py", ".pyi"}
        assert set(get_extensions_for_language("Python")) == {".py", ".pyi"}
        assert set(get_extensions_for_language("javascript")) == {".js", ".jsx", ".mjs", ".cjs"}
        assert set(get_extensions_for_language("JAVASCRIPT")) == {".js", ".jsx", ".mjs", ".cjs"}
        assert set(get_extensions_for_language("typescript")) == {".ts", ".tsx"}
        assert get_extensions_for_language("unknown_lang") == []
        assert get_extensions_for_language("") == []


# ── Feature 12: In-Place Directory Traversal Pruning via os.walk ──────────────

class TestFeature12OptimizedDirectoryTraversalPruning:
    """Verifies that os.walk prunes excluded directories in-place."""

    def test_prunes_massive_node_modules_without_visiting(self):
        """detect_from_repo must prune massive node_modules without visiting inner files."""
        detector = LanguageDetector()
        with TemporaryDirectory() as tmp_dir:
            nm = Path(tmp_dir) / "node_modules" / "huge_dep" / "nested"
            nm.mkdir(parents=True, exist_ok=True)
            for i in range(150):
                (nm / f"file_{i}.js").write_text("console.log(1);", encoding="utf-8")
            (Path(tmp_dir) / "main.py").write_text("print('hello')", encoding="utf-8")

            profile = detector.detect_from_repo(tmp_dir)
            assert profile.primary_language == "python"
            assert "javascript" not in profile.detected_languages

    def test_prunes_uppercase_build_and_dist(self):
        """detect_from_repo must prune uppercase Build and Dist directories."""
        detector = LanguageDetector()
        with TemporaryDirectory() as tmp_dir:
            build = Path(tmp_dir) / "Build" / "intermediate"
            build.mkdir(parents=True, exist_ok=True)
            for i in range(20):
                (build / f"generated_{i}.py").write_text("x = 1", encoding="utf-8")
            dist = Path(tmp_dir) / "DIST" / "bin"
            dist.mkdir(parents=True, exist_ok=True)
            (dist / "bundle.py").write_text("x = 1", encoding="utf-8")

            (Path(tmp_dir) / "index.ts").write_text("const x: number = 1;", encoding="utf-8")

            profile = detector.detect_from_repo(tmp_dir)
            assert profile.primary_language == "typescript"
            assert "python" not in profile.detected_languages

    def test_os_walk_pruning_verified_via_walk_inspection(self):
        """Verify that os.walk in detect_from_repo mutates dirnames in-place to avoid subtrees."""
        detector = LanguageDetector()
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "node_modules" / "pkg").mkdir(parents=True)
            (root / "node_modules" / "pkg" / "bad.js").write_text("x = 1")
            (root / "src" / "deep").mkdir(parents=True)
            (root / "src" / "deep" / "good.py").write_text("y = 2")

            visited_dirs = []
            orig_walk = os.walk

            def tracking_walk(top, *args, **kwargs):
                for dirpath, dirnames, filenames in orig_walk(top, *args, **kwargs):
                    visited_dirs.append(os.path.relpath(dirpath, top))
                    yield dirpath, dirnames, filenames

            with patch("intelligence.analyzers.language_detector.os.walk", side_effect=tracking_walk):
                profile = detector.detect_from_repo(tmp_dir)

            assert profile.primary_language == "python"
            # node_modules/pkg must NOT have been visited because node_modules was pruned at root
            assert not any("node_modules" in d and d != "." for d in visited_dirs)

    def test_retains_nested_source_trees(self):
        """detect_from_repo must retain and traverse valid nested source directories."""
        detector = LanguageDetector()
        with TemporaryDirectory() as tmp_dir:
            src = Path(tmp_dir) / "src" / "services" / "api"
            src.mkdir(parents=True, exist_ok=True)
            (src / "client.py").write_text("class Client: pass", encoding="utf-8")

            profile = detector.detect_from_repo(tmp_dir)
            assert profile.primary_language == "python"

    def test_empty_and_non_code_repositories(self):
        """detect_from_repo on empty or non-code repos returns unknown with 0.0 confidence."""
        detector = LanguageDetector()
        with TemporaryDirectory() as tmp_dir:
            profile_empty = detector.detect_from_repo(tmp_dir)
            assert profile_empty.primary_language == "unknown"
            assert profile_empty.detected_languages == []
            assert profile_empty.confidence == 0.0

            (Path(tmp_dir) / "README.md").write_text("# Project", encoding="utf-8")
            (Path(tmp_dir) / ".gitignore").write_text("*.pyc", encoding="utf-8")
            (Path(tmp_dir) / "LICENSE").write_text("MIT", encoding="utf-8")

            profile_non_code = detector.detect_from_repo(tmp_dir)
            assert profile_non_code.primary_language == "unknown"
            assert profile_non_code.detected_languages == []

    def test_non_existent_directory_handled_gracefully(self):
        """detect_from_repo handles non-existent or invalid directory path without raising."""
        detector = LanguageDetector()
        profile = detector.detect_from_repo("/non_existent_path_xyz_12345")
        assert profile.primary_language == "unknown"
        assert profile.confidence == 0.0


# ── Feature 13: Case-Insensitive Build & Tool Hints ───────────────────────────

class TestFeature13CaseInsensitiveBuildAndToolHints:
    """Verifies case-insensitive matching for build files and test framework hints."""

    @pytest.mark.parametrize(
        "filename,expected_build,expected_lang",
        [
            ("makefile", "make", "c"),
            ("Makefile", "make", "c"),
            ("MAKEFILE", "make", "c"),
            ("mAkEfIlE", "make", "c"),
            ("package.json", "npm", "javascript"),
            ("PACKAGE.JSON", "npm", "javascript"),
            ("Package.Json", "npm", "javascript"),
            ("requirements.txt", "pip", "python"),
            ("REQUIREMENTS.TXT", "pip", "python"),
            ("Requirements.Txt", "pip", "python"),
            ("pyproject.toml", "poetry", "python"),
            ("PYPROJECT.TOML", "poetry", "python"),
            ("setup.py", "setuptools", "python"),
            ("SETUP.PY", "setuptools", "python"),
            ("Pipfile", "pipenv", "python"),
            ("pipfile", "pipenv", "python"),
            ("PIPFILE", "pipenv", "python"),
            ("pom.xml", "maven", "java"),
            ("POM.XML", "maven", "java"),
            ("build.gradle", "gradle", "java"),
            ("BUILD.GRADLE", "gradle", "java"),
            ("build.gradle.kts", "gradle", "kotlin"),
            ("BUILD.GRADLE.KTS", "gradle", "kotlin"),
            ("CMakeLists.txt", "cmake", "cpp"),
            ("cmakelists.txt", "cmake", "cpp"),
            ("CMAKELISTS.TXT", "cmake", "cpp"),
            ("Cargo.toml", "cargo", "rust"),
            ("cargo.toml", "cargo", "rust"),
            ("CARGO.TOML", "cargo", "rust"),
            ("go.mod", "go", "go"),
            ("GO.MOD", "go", "go"),
            ("composer.json", "composer", "php"),
            ("COMPOSER.JSON", "composer", "php"),
            ("Gemfile", "bundler", "ruby"),
            ("gemfile", "bundler", "ruby"),
            ("GEMFILE", "bundler", "ruby"),
            ("MyProject.csproj", "dotnet", "csharp"),
            ("app.csproj", "dotnet", "csharp"),
            ("SERVER.CSPROJ", "dotnet", "csharp"),
        ],
    )
    def test_build_files_detect_from_files_case_insensitive(
        self, filename, expected_build, expected_lang
    ):
        """detect_from_files must recognize build files case-insensitively."""
        detector = LanguageDetector()
        profile = detector.detect_from_files([filename])
        assert profile.build_system == expected_build
        assert profile.primary_language == expected_lang

    def test_build_file_in_detect_from_repo_case_insensitive(self):
        """detect_from_repo must detect build files regardless of casing."""
        detector = LanguageDetector()
        with TemporaryDirectory() as tmp_dir:
            (Path(tmp_dir) / "MAKEFILE").write_text("all:\n\tgcc main.c", encoding="utf-8")
            (Path(tmp_dir) / "main.c").write_text("int main() { return 0; }", encoding="utf-8")

            profile = detector.detect_from_repo(tmp_dir)
            assert profile.build_system == "make"
            assert profile.primary_language == "c"

    @pytest.mark.parametrize(
        "hint_file,expected_framework",
        [
            ("pytest.ini", "pytest"),
            ("PYTEST.INI", "pytest"),
            ("Pytest.Ini", "pytest"),
            ("conftest.py", "pytest"),
            ("CONFTEST.PY", "pytest"),
            ("jest.config.js", "jest"),
            ("JEST.CONFIG.JS", "jest"),
            ("Jest.Config.Js", "jest"),
            ("jest.config.ts", "jest"),
            ("JEST.CONFIG.TS", "jest"),
            ("jasmine.json", "jasmine"),
            ("JASMINE.JSON", "jasmine"),
            ("TestNG.xml", "testng"),
            ("testng.xml", "testng"),
            ("TESTNG.XML", "testng"),
            ("CMakeTests.txt", "ctest"),
            ("cmaketests.txt", "ctest"),
            ("CMAKETESTS.TXT", "ctest"),
        ],
    )
    def test_test_framework_hints_case_insensitive(
        self, hint_file, expected_framework
    ):
        """Test framework hints must match case-insensitively."""
        detector = LanguageDetector()
        profile = detector.detect_from_files([hint_file, "src/code.py"])
        assert profile.test_framework == expected_framework


# ── Polyglot Profiling & Pre-Filtering ────────────────────────────────────────

class TestPolyglotProfilingAndPreFiltering:
    """Verifies polyglot profiling, build file authority, and PR diff pre-filtering."""

    def test_detect_from_files_pre_filters_excluded_directories(self):
        """Files in node_modules or venv must not inflate language counts in detect_from_files."""
        detector = LanguageDetector()
        changed_files = [
            "node_modules/axios/index.js",
            "node_modules/react/index.js",
            "node_modules/lodash/index.js",
            "src/service.py",
        ]
        profile = detector.detect_from_files(changed_files)
        assert profile.primary_language == "python"
        assert "javascript" not in profile.detected_languages

    def test_build_file_overrides_extension_count(self):
        """Authoritative build file overrides pure extension count."""
        detector = LanguageDetector()
        files = [f"src/file_{i}.py" for i in range(10)] + ["package.json"]
        profile = detector.detect_from_files(files)
        assert profile.primary_language == "javascript"
        assert profile.confidence == 0.9

    def test_polyglot_monorepo_python_and_typescript(self):
        """Mixed Python and TypeScript monorepo detected as polyglot."""
        detector = LanguageDetector()
        files = [
            "backend/app.py",
            "backend/requirements.txt",
            "frontend/src/App.tsx",
            "frontend/package.json",
        ]
        profile = detector.detect_from_files(files)
        assert profile.is_polyglot is True
        assert "python" in profile.detected_languages
        assert "typescript" in profile.detected_languages or "javascript" in profile.detected_languages


# ── Analyzer Registry Contracts ───────────────────────────────────────────────

class TestAnalyzerRegistryContracts:
    """Verifies AnalyzerRegistry dynamic contracts and preservation."""

    def test_list_supported_languages_returns_sorted_active_keys(self):
        """list_supported_languages returns the 6 registered languages in sorted order."""
        langs = list_supported_languages()
        assert langs == ["c", "cpp", "java", "javascript", "python", "typescript"]

    @pytest.mark.parametrize(
        "lang_input,expected_class",
        [
            ("python", PythonAnalyzer),
            ("PYTHON", PythonAnalyzer),
            ("  Python  ", PythonAnalyzer),
            ("javascript", JavaScriptAnalyzer),
            ("JAVASCRIPT", JavaScriptAnalyzer),
            ("typescript", JavaScriptAnalyzer),
            ("java", JavaAnalyzer),
            ("c", CAnalyzer),
            ("cpp", CppAnalyzer),
        ],
    )
    def test_get_analyzer_case_and_whitespace_insensitive(self, lang_input, expected_class):
        """get_analyzer resolves language keys case-insensitively and strips whitespace."""
        analyzer = get_analyzer(lang_input)
        assert analyzer is not None
        assert isinstance(analyzer, expected_class)

    def test_get_analyzer_unknown_language_returns_none(self):
        """get_analyzer returns None for unsupported language."""
        assert get_analyzer("unknown_lang") is None
        assert get_analyzer("fortran") is None

    def test_get_analyzers_for_profile_resolves_all_languages(self):
        """get_analyzers_for_profile returns instantiated analyzers for detected languages."""
        profile = LanguageProfile(
            primary_language="python",
            detected_languages=["python", "typescript", "unsupported_lang"],
        )
        analyzers = get_analyzers_for_profile(profile)
        assert "python" in analyzers
        assert isinstance(analyzers["python"], PythonAnalyzer)
        assert "typescript" in analyzers
        assert isinstance(analyzers["typescript"], JavaScriptAnalyzer)
        assert "unsupported_lang" not in analyzers
