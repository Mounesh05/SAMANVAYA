"""
AnalyzerRegistry — dynamic language-to-analyzer dispatch.

Replaces monolithic if-elif chains with a simple dictionary lookup.
Adding a new language requires only:
  1. Implement a new BaseAnalyzer subclass
  2. Add one entry to ANALYZER_REGISTRY below
  — Frontend, RiskEngine, and AI Agent require zero changes.

Gap Fix #2: RISK_WEIGHTS are defined here as concrete, tunable constants.
"""

from __future__ import annotations

import importlib
import logging
from typing import Dict, Optional, Type

from intelligence.analyzers.base import BaseAnalyzer
from intelligence.analyzers.language_detector import LanguageProfile

logger = logging.getLogger(__name__)


# ── Gap Fix #2: Concrete Risk Weight Table ────────────────────────────────────
# These feed into the RiskEngine.analyze_evidence() formula:
#
#   R = BASE_RISK
#       + alpha  * Z_size          (PR size deviation from repo historical norm)
#       + beta   * hotspot_weight  (historically buggy files changed)
#       + gamma  * dependency_risk (new/updated third-party packages)
#       + delta  * missing_tests   (changed lines with no test coverage)
#       + epsilon* security_score  (CVSS-weighted vulnerability score)
#       + zeta   * complexity_spike(cyclomatic deviation above repo baseline)
#
# All weights sum to 100 so risk score stays in [0, 100].

RISK_WEIGHTS: Dict[str, float] = {
    "alpha_size_zscore":   12.0,   # PR size risk (lines + files changed) - TODO: rename to alpha_size
    "beta_hotspot":        20.0,   # historically incident-prone files
    "gamma_dependency":    15.0,   # new / updated third-party packages
    "delta_missing_tests": 18.0,   # changed lines without test coverage
    "epsilon_security":    25.0,   # CVSS-weighted vulnerability score
    "zeta_complexity":     10.0,   # cyclomatic spike above threshold
}
BASE_RISK: float = 10.0           # Every PR starts with 10 base risk points

# ── Quality Dimension Weights ─────────────────────────────────────────────────
# Used by QualityEngine to compute the independent Quality Index Q ∈ [0, 100]:
#
#   Q = 100 - (w_s*S_pen + w_c*C_pen + w_t*T_pen + w_d*D_pen + w_a*A_pen)
#
# Weights must sum to 1.0.

QUALITY_WEIGHTS: Dict[str, float] = {
    "static_security": 0.25,   # lint + security finding penalty
    "testing":         0.25,   # coverage + test failure penalty
    "complexity":      0.20,   # cyclomatic complexity penalty
    "architecture":    0.20,   # layer violations + circular deps penalty
    "duplication":     0.10,   # copy-paste block penalty
}


# ── Analyzer Registry — one line per language ─────────────────────────────────
# Format: "language_key": "module.path:ClassName"
# Lazy-loaded on first use to avoid import overhead for unused languages.

ANALYZER_REGISTRY: Dict[str, str] = {
    "python":     "intelligence.analyzers.python.analyzer:PythonAnalyzer",
    "javascript": "intelligence.analyzers.javascript.analyzer:JavaScriptAnalyzer",
    "typescript": "intelligence.analyzers.javascript.analyzer:JavaScriptAnalyzer",
    "java":       "intelligence.analyzers.java.analyzer:JavaAnalyzer",
    "c":          "intelligence.analyzers.c.analyzer:CAnalyzer",
    "cpp":        "intelligence.analyzers.cpp.analyzer:CppAnalyzer",
    # ── Future languages (uncomment when adapter is implemented) ──────────────
    # "go":      "intelligence.analyzers.go.analyzer:GoAnalyzer",
    # "rust":    "intelligence.analyzers.rust.analyzer:RustAnalyzer",
    # "csharp":  "intelligence.analyzers.csharp.analyzer:CSharpAnalyzer",
    # "kotlin":  "intelligence.analyzers.kotlin.analyzer:KotlinAnalyzer",
    # "php":     "intelligence.analyzers.php.analyzer:PHPAnalyzer",
    # "ruby":    "intelligence.analyzers.ruby.analyzer:RubyAnalyzer",
}

# Internal cache — avoids re-importing the same class on every request
_analyzer_cache: Dict[str, BaseAnalyzer] = {}


def get_analyzer(language: str) -> Optional[BaseAnalyzer]:
    """
    Resolve a language string to its registered analyzer instance.

    Args:
        language: Lowercase language name e.g. "python", "java", "cpp"

    Returns:
        Instantiated BaseAnalyzer subclass, or None if not yet registered.
    """
    lang = language.lower().strip()

    if lang in _analyzer_cache:
        return _analyzer_cache[lang]

    module_path = ANALYZER_REGISTRY.get(lang)
    if not module_path:
        logger.warning(
            "No analyzer registered for language '%s'. "
            "Add an entry to ANALYZER_REGISTRY in registry.py.", lang
        )
        return None

    try:
        module_str, class_name = module_path.rsplit(":", 1)
        module = importlib.import_module(module_str)
        cls: Type[BaseAnalyzer] = getattr(module, class_name)
        instance = cls()
        _analyzer_cache[lang] = instance
        logger.info("Loaded analyzer '%s' for language '%s'", class_name, lang)
        return instance
    except (ImportError, AttributeError) as e:
        logger.error(
            "Failed to load analyzer for language '%s': %s", lang, str(e)
        )
        return None


def get_analyzers_for_profile(profile: LanguageProfile) -> Dict[str, BaseAnalyzer]:
    """
    Return all analyzers needed for a polyglot LanguageProfile.

    For monolingual repos: returns {"python": PythonAnalyzer()}
    For polyglot repos: returns {"python": ..., "typescript": ...}

    Args:
        profile: LanguageProfile from LanguageDetector

    Returns:
        Dict mapping language → analyzer instance (only resolved ones included)
    """
    analyzers: Dict[str, BaseAnalyzer] = {}
    languages = profile.detected_languages or [profile.primary_language]

    for lang in languages:
        analyzer = get_analyzer(lang)
        if analyzer is not None:
            analyzers[lang] = analyzer

    return analyzers


def list_supported_languages() -> list[str]:
    """Return the list of all currently registered language keys."""
    return sorted(ANALYZER_REGISTRY.keys())
