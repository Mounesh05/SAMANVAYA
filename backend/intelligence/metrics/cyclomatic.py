"""
Cyclomatic complexity (McCabe, 1976) for Python source code.

    CC = 1 + number of decision points in a function

CC is the number of independent paths through a function, which is also the
minimum number of test cases needed to exercise every path.

Counting rules (each adds +1):
    if / elif                      a branch
    x if cond else y               a branch (ternary)
    for / async for / while        a loop condition
    except <handler>               an alternative path per handler
    and / or                       +1 per extra operand: `a and b and c` = +2
    comprehension `for`            a loop
    comprehension `if` filter      a branch
    match `case` (not `case _`)    a branch

Not counted: else, finally, try, with, return, break, continue, assert.

Nested functions and methods are measured separately and are NOT added to
the enclosing function. Lambdas are counted inline in their enclosing function.

Pure computation with the standard-library `ast` module: no external tools,
same input always gives the same output.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Risk bands (McCabe's guidance, also used by radon/SonarQube-style reports)
LOW_MAX = 10        # 1-10   simple, low risk
MODERATE_MAX = 20   # 11-20  moderately complex
HIGH_MAX = 50       # 21-50  complex, high risk; above 50 = untestable


def classify(cc: int) -> str:
    """Map a cyclomatic complexity value to a risk band."""
    if cc <= LOW_MAX:
        return "low"
    if cc <= MODERATE_MAX:
        return "moderate"
    if cc <= HIGH_MAX:
        return "high"
    return "very_high"


@dataclass(frozen=True)
class FunctionComplexity:
    """Cyclomatic complexity of one function or method."""

    name: str        # qualified name, e.g. "AuthService.login" or "outer.inner"
    lineno: int
    end_lineno: int
    cyclomatic: int

    @property
    def risk(self) -> str:
        return classify(self.cyclomatic)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "lineno": self.lineno,
            "end_lineno": self.end_lineno,
            "cyclomatic": self.cyclomatic,
            "risk": self.risk,
        }


@dataclass
class FileComplexity:
    """Cyclomatic complexity of every function in one file, plus aggregates."""

    path: str
    functions: List[FunctionComplexity] = field(default_factory=list)
    parse_error: Optional[str] = None

    @property
    def function_count(self) -> int:
        return len(self.functions)

    @property
    def total(self) -> int:
        return sum(f.cyclomatic for f in self.functions)

    @property
    def average(self) -> float:
        return round(self.total / self.function_count, 2) if self.functions else 0.0

    @property
    def maximum(self) -> int:
        return max((f.cyclomatic for f in self.functions), default=0)

    @property
    def high_complexity_functions(self) -> List[FunctionComplexity]:
        """Functions above the low-risk band (CC > 10), most complex first."""
        return sorted(
            (f for f in self.functions if f.cyclomatic > LOW_MAX),
            key=lambda f: f.cyclomatic,
            reverse=True,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "parse_error": self.parse_error,
            "function_count": self.function_count,
            "total": self.total,
            "average": self.average,
            "maximum": self.maximum,
            "high_complexity_count": len(self.high_complexity_functions),
            "functions": [f.to_dict() for f in self.functions],
        }


class _DecisionCounter(ast.NodeVisitor):
    """Counts decision points inside one function body.

    Does not descend into nested functions or classes: those are measured
    as separate blocks.
    """

    def __init__(self) -> None:
        self.count = 0

    # ── boundaries: measured separately ──
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    # ── decision points ──
    def _branch(self, node: ast.AST) -> None:
        self.count += 1
        self.generic_visit(node)

    visit_If = _branch          # `elif` is an If nested in orelse, so it counts too
    visit_IfExp = _branch
    visit_For = _branch
    visit_AsyncFor = _branch
    visit_While = _branch
    visit_ExceptHandler = _branch

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.count += len(node.values) - 1
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.count += 1 + len(node.ifs)
        self.generic_visit(node)

    def visit_match_case(self, node: ast.AST) -> None:
        pattern = getattr(node, "pattern", None)
        is_wildcard = (
            isinstance(pattern, ast.MatchAs)
            and pattern.pattern is None
            and pattern.name is None
        )
        if not is_wildcard:
            self.count += 1
        self.generic_visit(node)


def cyclomatic_complexity(func: ast.AST) -> int:
    """Cyclomatic complexity of a single FunctionDef / AsyncFunctionDef node."""
    counter = _DecisionCounter()
    for stmt in getattr(func, "body", []):
        counter.visit(stmt)
    return 1 + counter.count


def _collect(node: ast.AST, prefix: str, out: List[FunctionComplexity]) -> None:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = f"{prefix}{child.name}"
            out.append(
                FunctionComplexity(
                    name=name,
                    lineno=child.lineno,
                    end_lineno=getattr(child, "end_lineno", child.lineno) or child.lineno,
                    cyclomatic=cyclomatic_complexity(child),
                )
            )
            _collect(child, f"{name}.", out)
        elif isinstance(child, ast.ClassDef):
            _collect(child, f"{prefix}{child.name}.", out)
        else:
            _collect(child, prefix, out)


def analyze_source(source: str, path: str = "<string>") -> FileComplexity:
    """Measure every function in a piece of Python source code."""
    source = source.lstrip("﻿")  # UTF-8 byte-order mark, which Python itself accepts
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError) as exc:
        return FileComplexity(path=path, parse_error=f"{type(exc).__name__}: {exc}")

    functions: List[FunctionComplexity] = []
    _collect(tree, "", functions)
    functions.sort(key=lambda f: f.lineno)
    return FileComplexity(path=path, functions=functions)


def analyze_file(path: str | Path) -> FileComplexity:
    """Measure every function in a Python file on disk."""
    p = Path(path)
    try:
        source = p.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        return FileComplexity(path=str(p), parse_error=f"{type(exc).__name__}: {exc}")
    return analyze_source(source, path=str(p))
