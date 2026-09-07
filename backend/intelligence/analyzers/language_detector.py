"""
LanguageDetector — inspects a repository's files and build configs
to determine the primary language and ecosystem details.

Detects via two signals (both must agree for high confidence):
  1. File extensions in the changed file list
  2. Build system / package manager files (package.json, pom.xml, etc.)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# ── Extension → Language mapping ─────────────────────────────────────────────

EXTENSION_MAP: Dict[str, str] = {
    # Python
    ".py":  "python",  ".pyi": "python",
    # JavaScript / TypeScript
    ".js":  "javascript", ".jsx": "javascript", ".mjs": "javascript",
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
    """Get list of file extensions for a given language."""
    return [ext for ext, lang in EXTENSION_MAP.items() if lang == language]


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
    valid_extensions = get_extensions_for_language(language)
    if not valid_extensions:
        return []  # Unknown language, no files
    
    filtered = []
    for file_path in files:
        path = Path(file_path)
        if path.suffix.lower() in valid_extensions:
            filtered.append(file_path)
    
    return filtered


# ── Build-system file → (language, build_system, package_manager) ─────────────

BUILD_FILE_MAP: Dict[str, Dict[str, str]] = {
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
        build_info: Dict[str, str] = {}
        test_framework: Optional[str] = None

        for path in changed_files:
            normalized = path.replace("\\", "/")
            filename = normalized.split("/")[-1]

            # Check extension
            for ext, lang in EXTENSION_MAP.items():
                if filename.endswith(ext):
                    lang_counts[lang] = lang_counts.get(lang, 0) + 1

            # Check build files (exact name match)
            if filename in BUILD_FILE_MAP:
                info = BUILD_FILE_MAP[filename]
                build_info = info
                # Build files are authoritative — bump that language count significantly
                bld_lang = info.get("language", "")
                lang_counts[bld_lang] = lang_counts.get(bld_lang, 0) + 10

            # Test framework hints
            if filename in TEST_FRAMEWORK_HINTS:
                test_framework = TEST_FRAMEWORK_HINTS[filename]

        return self._build_profile(lang_counts, build_info, test_framework)

    def detect_from_repo(self, repo_path: str) -> LanguageProfile:
        """
        Detect language profile by walking the repository root directory.
        More authoritative than extension-only detection.
        """
        root = Path(repo_path)
        lang_counts: Dict[str, int] = {}
        build_info: Dict[str, str] = {}
        test_framework: Optional[str] = None

        # Scan root-level files first (build configs are usually there)
        for item in root.iterdir():
            if item.is_file():
                name = item.name
                if name in BUILD_FILE_MAP:
                    build_info = BUILD_FILE_MAP[name]
                    bld_lang = build_info.get("language", "")
                    lang_counts[bld_lang] = lang_counts.get(bld_lang, 0) + 20
                if name in TEST_FRAMEWORK_HINTS:
                    test_framework = TEST_FRAMEWORK_HINTS[name]

        # Walk source files (skip excluded dirs)
        SKIP = {"node_modules", "venv", ".venv", "build", "dist",
                 "target", ".git", "vendor", "__pycache__"}
        try:
            for path in root.rglob("*"):
                if any(part in SKIP for part in path.parts):
                    continue
                for ext, lang in EXTENSION_MAP.items():
                    if path.suffix == ext:
                        lang_counts[lang] = lang_counts.get(lang, 0) + 1
                        break
        except PermissionError:
            pass

        profile = self._build_profile(lang_counts, build_info, test_framework)
        return profile

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_profile(
        lang_counts: Dict[str, int],
        build_info: Dict[str, str],
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
        build_lang = build_info.get("language", "")
        if build_lang and build_lang != primary:
            # Build file is authoritative — override
            primary = build_lang
            confidence = 0.9
        elif build_lang == primary:
            confidence = 1.0
        else:
            confidence = 0.6  # extension-only

        return LanguageProfile(
            primary_language=primary,
            detected_languages=sorted_langs[:5],  # top 5
            build_system=build_info.get("build"),
            package_manager=build_info.get("pkg"),
            test_framework=test_framework,
            is_polyglot=len(sorted_langs) > 1,
            confidence=confidence,
        )
