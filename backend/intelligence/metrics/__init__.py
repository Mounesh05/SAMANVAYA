"""
Code-quality metrics (Intelligence Engine, Layer 5).

Deterministic, dependency-free implementations of the core code-quality
metrics. Every function here is pure computation: the same source code
always produces the same numbers, so results can be verified against
reference tools (radon, SonarQube) and reproduced in evaluations.

Implemented:
- cyclomatic: Cyclomatic complexity (McCabe, 1976)
- cognitive:  Cognitive complexity (SonarSource, 2017)
- duplication: Token windows + Rabin-Karp rolling hash (type 1 and 2 clones)
- maintainability: Maintainability index (Oman & Hagemeister, 1992) + Halstead
- issues:     Issues per 1,000 lines of code (NCLOC), severity-weighted
- debt:       Technical debt + A-E rating (SQALE, Letouzey 2012)

Supporting modules:
- size:       Line counts (LOC, NCLOC, comments, docstrings)
- project:    Runs all six metrics over a set of files

Scores built on top of these live in QualityEngine
(backend/intelligence/quality_engine.py).
"""

from .cognitive import (
    FileCognitive,
    FunctionCognitive,
    Increment,
    analyze_file as cognitive_analyze_file,
    analyze_source as cognitive_analyze_source,
    classify as classify_cognitive,
    cognitive_complexity,
)
from .duplication import (
    Clone,
    CloneBlock,
    DuplicationReport,
    FileDuplication,
    analyze_files as duplication_analyze_files,
    detect_duplicates,
)
from .debt import TechnicalDebt, rating_for, technical_debt
from .issues import (
    Issue,
    IssueDensityReport,
    complexity_issues,
    duplication_issues,
    issue_density,
    issues_from_findings,
)
from .maintainability import (
    FileMaintainability,
    FunctionMaintainability,
    Halstead,
    analyze_file as maintainability_analyze_file,
    analyze_source as maintainability_analyze_source,
    maintainability_index,
)
from .project import CodeQualitySummary, FileQuality, FunctionQuality, analyze_paths, analyze_sources
from .size import FileSize, measure_file, measure_source
from .cyclomatic import (
    FileComplexity,
    FunctionComplexity,
    analyze_file as cyclomatic_analyze_file,
    analyze_source as cyclomatic_analyze_source,
    classify as classify_cyclomatic,
    cyclomatic_complexity,
)

__all__ = [
    "TechnicalDebt",
    "rating_for",
    "technical_debt",
    "Issue",
    "IssueDensityReport",
    "complexity_issues",
    "duplication_issues",
    "issue_density",
    "issues_from_findings",
    "FileMaintainability",
    "FunctionMaintainability",
    "Halstead",
    "maintainability_analyze_file",
    "maintainability_analyze_source",
    "maintainability_index",
    "CodeQualitySummary",
    "FileQuality",
    "FunctionQuality",
    "analyze_paths",
    "analyze_sources",
    "FileSize",
    "measure_file",
    "measure_source",
    "Clone",
    "CloneBlock",
    "DuplicationReport",
    "FileDuplication",
    "duplication_analyze_files",
    "detect_duplicates",
    "FileCognitive",
    "FunctionCognitive",
    "Increment",
    "cognitive_analyze_file",
    "cognitive_analyze_source",
    "classify_cognitive",
    "cognitive_complexity",
    "FileComplexity",
    "FunctionComplexity",
    "cyclomatic_analyze_file",
    "cyclomatic_analyze_source",
    "classify_cyclomatic",
    "cyclomatic_complexity",
]
