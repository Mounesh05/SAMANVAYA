"""
Cognitive complexity (SonarSource, G. Ann Campbell, 2017) for Python source code.

Measures how hard a function is for a human to READ, not how many paths it
has. Unlike cyclomatic complexity it charges extra for nesting, so a deeply
nested function scores higher than a flat one with the same branches.

The three rules:
    1. +1 for each break in linear flow
         if, elif, else, for, while, except, match, ternary,
         loop `else`, recursion
    2. + nesting level, on top of rule 1, for structures that nest:
         if, for, while, except, match, ternary
       (elif / else get +1 but no nesting penalty)
       Nesting grows inside: if/elif/else, loops, except, match cases,
       ternaries, nested functions, lambdas.
    3. +1 for each SEQUENCE of the same boolean operator
         `a and b and c` = +1      `a and b or c` = +2

Not counted: try, finally, with, return, break, continue, `not`.

Choices for Python constructs the SonarSource spec does not define:
    - comprehensions: +1 per `for` clause and +1 per `if` filter, without a
      nesting penalty (they are a compact one-line idiom); their contents are
      one nesting level deeper.
    - try/else: not counted (like finally).
    - for/while `else`: +1 (a separate branch, like if/else).

Nested functions and lambdas are folded into the enclosing function with one
extra nesting level (SonarSource rule), so only top-level functions and
methods are reported.

Every increment is recorded with its line and reason so a score can be
explained ("line 12: if (nesting 2) = +3").
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

LOW_MAX = 7        # 0-7   easy to read
MODERATE_MAX = 15  # 8-15  getting hard; above 15 = too complex (SonarQube's default limit)


def classify(score: int) -> str:
    """Map a cognitive complexity value to a readability band."""
    if score <= LOW_MAX:
        return "low"
    if score <= MODERATE_MAX:
        return "moderate"
    return "high"


@dataclass(frozen=True)
class Increment:
    """One contribution to a function's score, for explaining it."""

    line: int
    amount: int
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {"line": self.line, "amount": self.amount, "reason": self.reason}


@dataclass(frozen=True)
class FunctionCognitive:
    """Cognitive complexity of one function or method."""

    name: str
    lineno: int
    end_lineno: int
    cognitive: int
    increments: Tuple[Increment, ...] = ()

    @property
    def risk(self) -> str:
        return classify(self.cognitive)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "lineno": self.lineno,
            "end_lineno": self.end_lineno,
            "cognitive": self.cognitive,
            "risk": self.risk,
            "increments": [i.to_dict() for i in self.increments],
        }


@dataclass
class FileCognitive:
    """Cognitive complexity of every function in one file, plus aggregates."""

    path: str
    functions: List[FunctionCognitive] = field(default_factory=list)
    parse_error: Optional[str] = None

    @property
    def function_count(self) -> int:
        return len(self.functions)

    @property
    def total(self) -> int:
        return sum(f.cognitive for f in self.functions)

    @property
    def average(self) -> float:
        return round(self.total / self.function_count, 2) if self.functions else 0.0

    @property
    def maximum(self) -> int:
        return max((f.cognitive for f in self.functions), default=0)

    @property
    def high_complexity_functions(self) -> List[FunctionCognitive]:
        """Functions above SonarQube's limit of 15, most complex first."""
        return sorted(
            (f for f in self.functions if f.cognitive > MODERATE_MAX),
            key=lambda f: f.cognitive,
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


def _is_elif(parent: ast.If, child: ast.If) -> bool:
    """`elif` sits in the same column as its `if`; `else:` + `if` is indented."""
    return child.col_offset == parent.col_offset and child.lineno > parent.lineno


class _CognitiveWalker:
    """Walks one function body, tracking the nesting level."""

    def __init__(self, func: ast.AST) -> None:
        self.func_name: str = getattr(func, "name", "")
        self.increments: List[Increment] = []
        self.recursive = False

    def run(self, func: ast.AST) -> int:
        self.visit_all(getattr(func, "body", []), 0)
        if self.recursive:
            self._add(func, 1, "recursion")
        return sum(i.amount for i in self.increments)

    # ── helpers ──
    def _add(self, node: ast.AST, amount: int, reason: str) -> None:
        self.increments.append(Increment(getattr(node, "lineno", 0), amount, reason))

    def _structural(self, node: ast.AST, nesting: int, label: str) -> None:
        reason = label if nesting == 0 else f"{label} (nesting {nesting})"
        self._add(node, 1 + nesting, reason)

    def visit_all(self, nodes: Sequence[ast.AST], nesting: int) -> None:
        for node in nodes:
            self.visit(node, nesting)

    def visit(self, node: ast.AST, nesting: int) -> None:
        handler = getattr(self, f"_visit_{type(node).__name__}", None)
        if handler is not None:
            handler(node, nesting)
        else:
            self.visit_all(list(ast.iter_child_nodes(node)), nesting)

    # ── if / elif / else ──
    def _visit_If(self, node: ast.If, nesting: int) -> None:
        self._if_chain(node, nesting, is_elif=False)

    def _if_chain(self, node: ast.If, nesting: int, is_elif: bool) -> None:
        if is_elif:
            self._add(node, 1, "elif")
        else:
            self._structural(node, nesting, "if")
        self.visit(node.test, nesting)
        self.visit_all(node.body, nesting + 1)

        orelse = node.orelse
        if not orelse:
            return
        if len(orelse) == 1 and isinstance(orelse[0], ast.If) and _is_elif(node, orelse[0]):
            self._if_chain(orelse[0], nesting, is_elif=True)
        else:
            self._add(orelse[0], 1, "else")
            self.visit_all(orelse, nesting + 1)

    # ── loops ──
    def _loop(self, node: ast.AST, nesting: int, label: str) -> None:
        self._structural(node, nesting, label)
        for attr in ("target", "iter", "test"):
            child = getattr(node, attr, None)
            if child is not None:
                self.visit(child, nesting)
        self.visit_all(node.body, nesting + 1)
        if node.orelse:
            self._add(node.orelse[0], 1, f"{label} else")
            self.visit_all(node.orelse, nesting + 1)

    def _visit_For(self, node: ast.For, nesting: int) -> None:
        self._loop(node, nesting, "for")

    def _visit_AsyncFor(self, node: ast.AsyncFor, nesting: int) -> None:
        self._loop(node, nesting, "async for")

    def _visit_While(self, node: ast.While, nesting: int) -> None:
        self._loop(node, nesting, "while")

    # ── try / except ──
    def _visit_Try(self, node: ast.Try, nesting: int) -> None:
        self.visit_all(node.body, nesting)  # try itself adds no nesting
        for handler in node.handlers:
            self._structural(handler, nesting, "except")
            if handler.type is not None:
                self.visit(handler.type, nesting)
            self.visit_all(handler.body, nesting + 1)
        self.visit_all(node.orelse, nesting)
        self.visit_all(node.finalbody, nesting)

    _visit_TryStar = _visit_Try  # Python 3.11+ `except*`

    # ── match ──
    def _visit_Match(self, node: ast.AST, nesting: int) -> None:
        self._structural(node, nesting, "match")  # one increment for the whole match
        self.visit(node.subject, nesting)
        for case in node.cases:
            if case.guard is not None:
                self.visit(case.guard, nesting + 1)
            self.visit_all(case.body, nesting + 1)

    # ── expressions ──
    def _visit_IfExp(self, node: ast.IfExp, nesting: int) -> None:
        self._structural(node, nesting, "ternary")
        self.visit_all([node.test, node.body, node.orelse], nesting + 1)

    def _visit_BoolOp(self, node: ast.BoolOp, nesting: int) -> None:
        op = "and" if isinstance(node.op, ast.And) else "or"
        self._add(node, 1, f"'{op}' sequence")
        self._boolop_operands(node, nesting)

    def _boolop_operands(self, node: ast.BoolOp, nesting: int) -> None:
        for value in node.values:
            if isinstance(value, ast.BoolOp) and type(value.op) is type(node.op):
                self._boolop_operands(value, nesting)  # same operator: same sequence
            else:
                self.visit(value, nesting)

    def _comprehension(self, node: ast.AST, nesting: int) -> None:
        for gen in node.generators:
            self._add(node, 1, "comprehension for")
            self.visit(gen.iter, nesting)
            for cond in gen.ifs:
                self._add(cond, 1, "comprehension if")
                self.visit(cond, nesting + 1)
        elements = [getattr(node, a) for a in ("elt", "key", "value") if hasattr(node, a)]
        self.visit_all(elements, nesting + 1)

    _visit_ListComp = _comprehension
    _visit_SetComp = _comprehension
    _visit_DictComp = _comprehension
    _visit_GeneratorExp = _comprehension

    def _visit_Lambda(self, node: ast.Lambda, nesting: int) -> None:
        self.visit(node.body, nesting + 1)

    def _visit_Call(self, node: ast.Call, nesting: int) -> None:
        func = node.func
        if isinstance(func, ast.Name) and func.id == self.func_name:
            self.recursive = True
        elif (
            isinstance(func, ast.Attribute)
            and func.attr == self.func_name
            and isinstance(func.value, ast.Name)
            and func.value.id in ("self", "cls")
        ):
            self.recursive = True
        self.visit_all(list(ast.iter_child_nodes(node)), nesting)

    # ── nested definitions: folded in, one level deeper ──
    def _nested_def(self, node: ast.AST, nesting: int) -> None:
        self.visit_all(getattr(node, "decorator_list", []), nesting)
        self.visit_all(node.body, nesting + 1)

    _visit_FunctionDef = _nested_def
    _visit_AsyncFunctionDef = _nested_def
    _visit_ClassDef = _nested_def


def cognitive_complexity(func: ast.AST) -> Tuple[int, Tuple[Increment, ...]]:
    """Cognitive complexity of one FunctionDef / AsyncFunctionDef node.

    Returns (score, increments sorted by line).
    """
    walker = _CognitiveWalker(func)
    score = walker.run(func)
    increments = tuple(sorted(walker.increments, key=lambda i: i.line))
    return score, increments


def _collect(node: ast.AST, prefix: str, out: List[FunctionCognitive]) -> None:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            score, increments = cognitive_complexity(child)
            out.append(
                FunctionCognitive(
                    name=f"{prefix}{child.name}",
                    lineno=child.lineno,
                    end_lineno=getattr(child, "end_lineno", child.lineno) or child.lineno,
                    cognitive=score,
                    increments=increments,
                )
            )
            # functions nested inside are folded into this score, not listed
        elif isinstance(child, ast.ClassDef):
            _collect(child, f"{prefix}{child.name}.", out)
        elif isinstance(child, ast.stmt):
            _collect(child, prefix, out)  # e.g. defs under a module-level `if`


def analyze_source(source: str, path: str = "<string>") -> FileCognitive:
    """Measure every top-level function and method in Python source code."""
    source = source.lstrip("﻿")  # UTF-8 byte-order mark
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError) as exc:
        return FileCognitive(path=path, parse_error=f"{type(exc).__name__}: {exc}")

    functions: List[FunctionCognitive] = []
    _collect(tree, "", functions)
    functions.sort(key=lambda f: f.lineno)
    return FileCognitive(path=path, functions=functions)


def analyze_file(path: str | Path) -> FileCognitive:
    """Measure every top-level function and method in a Python file."""
    p = Path(path)
    try:
        source = p.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        return FileCognitive(path=str(p), parse_error=f"{type(exc).__name__}: {exc}")
    return analyze_source(source, path=str(p))
