"""
Size metrics for Python source: the line counts other metrics divide by.

    loc               physical lines
    blank_lines       whitespace-only lines
    comment_lines     lines containing a `#` comment (trailing comments included)
    docstring_lines   lines of module / class / function docstrings
    code_lines        lines with at least one code token, docstrings excluded
                      (NCLOC: "non-comment lines of code")

    comment_density = comment-or-docstring lines /
                      (code lines + comment-or-docstring lines) x 100
    (same definition as SonarQube's "Comments (%)")
"""

from __future__ import annotations

import ast
import io
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Set

_NON_CODE = {
    tokenize.COMMENT,
    tokenize.NL,
    tokenize.NEWLINE,
    tokenize.INDENT,
    tokenize.DEDENT,
    tokenize.ENCODING,
    tokenize.ENDMARKER,
}


@dataclass
class FileSize:
    path: str
    loc: int = 0
    blank_lines: int = 0
    comment_lines: int = 0
    docstring_lines: int = 0
    code_lines: int = 0
    commented_lines: int = 0  # lines with a comment OR docstring (no double counting)
    parse_error: Optional[str] = None

    @property
    def comment_density(self) -> float:
        denominator = self.code_lines + self.commented_lines
        return round(100 * self.commented_lines / denominator, 2) if denominator else 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "path": self.path,
            "loc": self.loc,
            "blank_lines": self.blank_lines,
            "comment_lines": self.comment_lines,
            "docstring_lines": self.docstring_lines,
            "code_lines": self.code_lines,
            "comment_density": self.comment_density,
            "parse_error": self.parse_error,
        }


def docstring_rows(tree: ast.AST) -> Set[int]:
    """Line numbers covered by module, class and function docstrings."""
    rows: Set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                expr = body[0]
                rows.update(range(expr.lineno, (expr.end_lineno or expr.lineno) + 1))
    return rows


def code_rows(source: str, docstrings: Set[int]) -> Set[int]:
    """Line numbers holding code tokens, docstring lines excluded."""
    rows: Set[int] = set()
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type not in _NON_CODE:
            rows.update(range(tok.start[0], tok.end[0] + 1))
    return rows - docstrings


def measure_source(source: str, path: str = "<string>") -> FileSize:
    source = source.lstrip("﻿")
    lines = source.splitlines()
    size = FileSize(path=path, loc=len(lines), blank_lines=sum(1 for l in lines if not l.strip()))
    try:
        tree = ast.parse(source, filename=path)
        docstrings = docstring_rows(tree)
        comments: Set[int] = set()
        code: Set[int] = set()
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                comments.add(tok.start[0])
            elif tok.type not in _NON_CODE:
                code.update(range(tok.start[0], tok.end[0] + 1))
    except (SyntaxError, ValueError, tokenize.TokenError) as exc:
        size.parse_error = f"{type(exc).__name__}: {exc}"
        return size

    code -= docstrings
    size.comment_lines = len(comments)
    size.docstring_lines = len(docstrings)
    size.code_lines = len(code)
    size.commented_lines = len(comments | docstrings)
    return size


def measure_file(path: str | Path) -> FileSize:
    p = Path(path)
    try:
        source = p.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        return FileSize(path=str(p), parse_error=f"{type(exc).__name__}: {exc}")
    return measure_source(source, path=str(p))
