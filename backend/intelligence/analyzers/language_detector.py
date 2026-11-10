"""
LanguageDetector — inspects a repository's files and build configs
to determine the primary language and ecosystem details.

Detects via two signals (both must agree for high confidence):
  1. File extensions in the changed file list
  2. Build system / package manager files (package.json, pom.xml, etc.)
"""

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from intelligence.analyzers.base import EXCLUDED_DIRS


# ── Extension → Language mapping ─────────────────────────────────────────────

EXTENSION_MAP: Dict[str, str] = {
    # Python
    ".py":  "python",  ".pyi": "python",
    # JavaScript / TypeScript
    ".js":  "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts":  "typescript", ".tsx": "typescript",
    # Java
    ".java": "java",
    # C
    ".c": "c", ".h": "c",
    # C++
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
    ".hpp": "cpp", ".hxx": "cpp",
    # Go
    ".go": "go",
    # Rust
    ".rs": "rust",
    # C#
    ".cs": "csharp",
    # Kotlin
    ".kt": "kotlin", ".kts": "kotlin",
    # PHP
    ".php": "php",
    # Ruby
    ".rb": "ruby",
}


# ── Reverse map: Language → Extensions ───────────────────────────────────────

def get_extensions_for_language(language: str) -> List[str]:
    """Get list of file extensions for a given language (case-insensitive)."""
    if not language:
        return []
    target_lang = language.strip().lower()
    return [ext for ext, lang in EXTENSION_MAP.items() if lang == target_lang]


def filter_files_for_language(files: List[str], language: str) -> List[str]:
    """
    Filter file list to only include files relevant to the given language.
    
    Args:
        files: List of file paths
        language: Language identifier (e.g., 'python', 'javascript', 'typescript')
        
    Returns:
        Filtered list containing only files matching the language's extensions
        
    Example:
        files = ['app.py', 'util.js', 'test.ts', 'README.md']
        filter_files_for_language(files, 'python')  → ['app.py']
        filter_files_for_language(files, 'typescript')  → ['test.ts']
    """
    valid_extensions = tuple(get_extensions_for_language(language))
    if not valid_extensions:
        return []  # Unknown language, no files
    
    filtered = []
    for file_path in files:
        if not file_path:
            continue
        f_norm = file_path.replace("\\", "/")
        parts = f_norm.split("/")[:-1]
        if any(p.lower() in EXCLUDED_DIRS for p in parts if p):
            continue
        if f_norm.lower().endswith(valid_extensions):
            filtered.append(file_path)
    
    return filtered


# ── Build-system file → (language, build_system, package_manager) ─────────────

BUILD_FILE_MAP: Dict[str, Dict[str, Optional[str]]] = {
    "package.json":       {"language": "javascript", "build": "npm",    "pkg": "npm"},
    "yarn.lock":          {"language": "javascript", "build": "yarn",   "pkg": "yarn"},
    "requirements.txt":   {"language": "python",     "build": "pip",    "pkg": "pip"},
    "pyproject.toml":     {"language": "python",     "build": "poetry", "pkg": "poetry"},
    "setup.py":           {"language": "python",     "build": "setuptools", "pkg": "pip"},
    "Pipfile":            {"language": "python",     "build": "pipenv", "pkg": "pipenv"},
    "pom.xml":            {"language": "java",       "build": "maven",  "pkg": "maven"},
    "build.gradle":       {"language": "java",       "build": "gradle", "pkg": "gradle"},
    "build.gradle.kts":   {"language": "kotlin",     "build": "gradle", "pkg": "gradle"},
    "CMakeLists.txt":     {"language": "cpp",        "build": "cmake",  "pkg": None},
    "Makefile":           {"language": "c",          "build": "make",   "pkg": None},
    "Cargo.toml":         {"language": "rust",       "build": "cargo",  "pkg": "cargo"},
    "go.mod":             {"language": "go",         "build": "go",     "pkg": "go"},
    "composer.json":      {"language": "php",        "build": "composer","pkg": "composer"},
    "Gemfile":            {"language": "ruby",       "build": "bundler","pkg": "bundler"},
    "*.csproj":           {"language": "csharp",     "build": "dotnet", "pkg": "nuget"},
}

# ── Test framework hints ──────────────────────────────────────────────────────

TEST_FRAMEWORK_HINTS: Dict[str, str] = {
    "pytest.ini": "pytest", "conftest.py": "pytest",
    "jest.config.js": "jest", "jest.config.ts": "jest",
    "jasmine.json": "jasmine",
    "TestNG.xml": "testng",
    "CMakeTests.txt": "ctest",
}


def _lookup_build_file(filename: str) -> Optional[Dict[str, Optional[str]]]:
    """
    Case-insensitive lookup for build system files in BUILD_FILE_MAP.
    Supports exact names (e.g. 'makefile', 'Makefile', 'PACKAGE.JSON')
    and glob patterns (e.g. '*.csproj').
    """
    if not filename:
        return None
    if filename in BUILD_FILE_MAP:
        return BUILD_FILE_MAP[filename]
    fn_lower = filename.lower()
    for pattern, info in BUILD_FILE_MAP.items():
        pat_lower = pattern.lower()
        if pat_lower.startswith("*"):
            if fnmatch.fnmatch(fn_lower, pat_lower):
                return info
        elif pat_lower == fn_lower:
            return info
    return None


def _lookup_test_framework(filename: str) -> Optional[str]:
    """
    Case-insensitive lookup for test framework hints in TEST_FRAMEWORK_HINTS.
    Supports names like 'jest.config.js', 'JEST.CONFIG.JS', 'pytest.ini', etc.
    """
    if not filename:
        return None
    if filename in TEST_FRAMEWORK_HINTS:
        return TEST_FRAMEWORK_HINTS[filename]
    fn_lower = filename.lower()
    for name, framework in TEST_FRAMEWORK_HINTS.items():
        if name.lower() == fn_lower:
            return framework
    return None


@dataclass
class LanguageProfile:
    """Result of language detection — passed to AnalyzerRegistry."""

    primary_language: str
    detected_languages: List[str] = field(default_factory=list)
    build_system: Optional[str] = None
    package_manager: Optional[str] = None
    test_framework: Optional[str] = None
    is_polyglot: bool = False

    # Confidence: 1.0 = both extension + build file agree; 0.5 = extension only
    confidence: float = 1.0


class LanguageDetector:
    """
    Detects what languages and build ecosystem a repository uses.

    Two-signal detection:
      1. File extensions in changed_files (fast, always available)
      2. Build/config files in repo root (authoritative, when available)
    """

    def detect_from_files(self, changed_files: List[str]) -> LanguageProfile:
        """
        Detect language profile purely from the list of changed file paths.
        Used when only a file list is available (e.g., GitHub PR diff).
        """
        lang_counts: Dict[str, int] = {}
        build_info: Dict[str, Optional[str]] = {}
        test_framework: Optional[str] = None

        for path in changed_files:
            if not path:
                continue
            normalized = path.replace("\\", "/")
            parts = normalized.split("/")
            # Check parent directories against EXCLUDED_DIRS
            dir_parts = parts[:-1]
            if any(p.lower() in EXCLUDED_DIRS for p in dir_parts if p):
                continue

            filename = parts[-1]
            if not filename:
                continue

            # Check extension (case-insensitive)
            suffix = Path(filename).suffix.lower()
            if suffix in EXTENSION_MAP:
                lang = EXTENSION_MAP[suffix]
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

            # Check build files (case-insensitive)
            info = _lookup_build_file(filename)
            if info:
                build_info = info
                # Build files are authoritative — bump that language count significantly
                bld_lang = info.get("language", "")
                if bld_lang:
                    lang_counts[bld_lang] = lang_counts.get(bld_lang, 0) + 10

            # Test framework hints (case-insensitive)
            hint = _lookup_test_framework(filename)
            if hint:
                test_framework = hint

        return self._build_profile(lang_counts, build_info, test_framework)

    def detect_from_repo(self, repo_path: str) -> LanguageProfile:
        """
        Detect language profile by walking the repository root directory.
        More authoritative than extension-only detection.

        Uses in-place directory pruning with os.walk to prevent deep recursion
        into massive excluded directories (node_modules, venv, build, etc.).
        """
        root = Path(repo_path)
        if not root.exists() or not root.is_dir():
            return LanguageProfile(
                primary_language="unknown",
                confidence=0.0,
            )

        lang_counts: Dict[str, int] = {}
        build_info: Dict[str, Optional[str]] = {}
        test_framework: Optional[str] = None

        root_abs = os.path.abspath(str(root))

        try:
            for dirpath, dirnames, filenames in os.walk(str(root)):
                # In-place directory pruning to avoid traversing excluded directories
                dirnames[:] = [d for d in dirnames if d.lower() not in EXCLUDED_DIRS and not d.startswith(".")]

                is_root = (os.path.abspath(dirpath) == root_abs)

                for name in filenames:
                    # Check build system files (case-insensitive)
                    info = _lookup_build_file(name)
                    if info:
                        if is_root or not build_info:
                            build_info = info
                        bld_lang = info.get("language", "")
                        if bld_lang:
                            weight = 20 if is_root else 10
                            lang_counts[bld_lang] = lang_counts.get(bld_lang, 0) + weight

                    # Check test framework hints (case-insensitive)
                    hint = _lookup_test_framework(name)
                    if hint:
                        if is_root or not test_framework:
                            test_framework = hint

                    # Check source file extension (case-insensitive)
                    suffix = Path(name).suffix.lower()
                    if suffix in EXTENSION_MAP:
                        lang = EXTENSION_MAP[suffix]
                        lang_counts[lang] = lang_counts.get(lang, 0) + 1
        except (PermissionError, OSError):
            pass

        return self._build_profile(lang_counts, build_info, test_framework)

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_profile(
        lang_counts: Dict[str, int],
        build_info: Dict[str, Optional[str]],
        test_framework: Optional[str],
    ) -> LanguageProfile:
        if not lang_counts:
            return LanguageProfile(
                primary_language="unknown",
                confidence=0.0,
            )

        sorted_langs = sorted(lang_counts, key=lang_counts.get, reverse=True)
        primary = sorted_langs[0]

        # If build file overrides extension count, trust it
        build_lang = build_info.get("language", "") if build_info else ""
        if build_lang and build_lang != primary:
            # Build file is authoritative — override
            primary = build_lang
            confidence = 0.9
        elif build_lang == primary:
            confidence = 1.0
        else:
            confidence = 0.6  # extension-only

        # Ensure primary language is at the head of detected_languages
        detected = [primary] + [lang for lang in sorted_langs if lang != primary]

        return LanguageProfile(
            primary_language=primary,
            detected_languages=detected[:5],  # top 5
            build_system=build_info.get("build") if build_info else None,
            package_manager=build_info.get("pkg") if build_info else None,
            test_framework=test_framework,
            is_polyglot=len(sorted_langs) > 1,
            confidence=confidence,
        )
