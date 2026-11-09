"""
Maintainability Index (Oman & Hagemeister, 1992) with Halstead metrics (1977).

    MI = max(0, (171 - 5.2 ln(V) - 0.23 G - 16.2 ln(L)) x 100 / 171)

        V = Halstead volume     how much "information" the code holds
        G = cyclomatic complexity (total over the file's functions)
        L = lines of code (code_lines / NCLOC)

The x 100 / 171 scaling to 0-100 is the Visual Studio variant, the most
widely used form. The original formula also has a comment bonus:

    + 50 sin(sqrt(2.4 C))      C = comment percentage, in radians

It is optional here (include_comments=True) because comments do not make
code itself easier to change, and the term is often criticised.

Bands (Visual Studio / radon):
    20-100  high      easy to maintain
    10-19   moderate
    0-9     low       hard to maintain

Halstead counting (token based, Python's own tokenizer):
    operators   keywords (except True/False/None), operators, punctuation;
                closing brackets ) ] } are not counted separately
    operands    identifiers, numbers, strings, True/False/None

    n1, n2  distinct operators / operands     N1, N2  total
    vocabulary n = n1 + n2                    length N = N1 + N2
    volume     V = N log2(n)                  difficulty D = (n1 / 2)(N2 / n2)
    effort     E = D V                        time T = E / 18 seconds
    bugs       B = V / 3000
"""

from __future__ import annotations

import ast
import io
import keyword
import math
import tokenize
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from .cyclomatic import analyze_source as _cyclomatic_source
from .size import code_rows, docstring_rows, measure_source

HIGH_MIN = 20
MODERATE_MIN = 10

_SKIP = {
    tokenize.COMMENT,
    tokenize.NL,
    tokenize.NEWLINE,
    tokenize.INDENT,
    tokenize.DEDENT,
    tokenize.ENCODING,
    tokenize.ENDMARKER,
}
_CLOSING = {")", "]", "}"}
_OPERAND_KEYWORDS = {"True", "False", "None"}


def classify(mi: float) -> str:
    if mi >= HIGH_MIN:
        return "high"
    if mi >= MODERATE_MIN:
        return "moderate"
    return "low"


# ── Halstead ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class HalsteadToken:
    kind: str   # "operator" | "operand"
    value: str
    line: int


@dataclass(frozen=True)
class Halstead:
    distinct_operators: int = 0   # n1
    distinct_operands: int = 0    # n2
    total_operators: int = 0      # N1
    total_operands: int = 0       # N2

    @property
    def vocabulary(self) -> int:
        return self.distinct_operators + self.distinct_operands

    @property
    def length(self) -> int:
        return self.total_operators + self.total_operands

    @property
    def volume(self) -> float:
        return self.length * math.log2(self.vocabulary) if self.vocabulary > 1 else 0.0

    @property
    def difficulty(self) -> float:
        if not self.distinct_operands:
            return 0.0
        return (self.distinct_operators / 2) * (self.total_operands / self.distinct_operands)

    @property
    def effort(self) -> float:
        return self.difficulty * self.volume

    @property
    def time_seconds(self) -> float:
        return self.effort / 18

    @property
    def bugs(self) -> float:
        return self.volume / 3000

    def to_dict(self) -> Dict[str, float]:
        return {
            "n1": self.distinct_operators,
            "n2": self.distinct_operands,
            "N1": self.total_operators,
            "N2": self.total_operands,
            "vocabulary": self.vocabulary,
            "length": self.length,
            "volume": round(self.volume, 2),
            "difficulty": round(self.difficulty, 2),
            "effort": round(self.effort, 2),
            "time_seconds": round(self.time_seconds, 2),
            "bugs": round(self.bugs, 4),
        }


def halstead_tokens(source: str) -> List[HalsteadToken]:
    """Classify every token of Python source as operator or operand."""
    out: List[HalsteadToken] = []
    for tok in tokenize.generate_tokens(io.StringIO(source.lstrip("﻿")).readline):
        if tok.type in _SKIP:
            continue
        line = tok.start[0]
        if tok.type == tokenize.NAME:
            if keyword.iskeyword(tok.string) and tok.string not in _OPERAND_KEYWORDS:
                out.append(HalsteadToken("operator", tok.string, line))
            else:
                out.append(HalsteadToken("operand", tok.string, line))
        elif tok.type in (tokenize.NUMBER, tokenize.STRING):
            out.append(HalsteadToken("operand", tok.string, line))
        elif tok.type == tokenize.OP:
            if tok.string not in _CLOSING:
                out.append(HalsteadToken("operator", tok.string, line))
        else:
            name = tokenize.tok_name.get(tok.type, "")
            if name.endswith("_MIDDLE"):        # f-string / t-string text
                out.append(HalsteadToken("operand", tok.string, line))
            elif name.endswith("_START"):       # f-string / t-string opener
                out.append(HalsteadToken("operator", name, line))
    return out


def halstead(tokens: Iterable[HalsteadToken]) -> Halstead:
    operators: Dict[str, int] = {}
    operands: Dict[str, int] = {}
    for t in tokens:
        bucket = operators if t.kind == "operator" else operands
        bucket[t.value] = bucket.get(t.value, 0) + 1
    return Halstead(
        distinct_operators=len(operators),
        distinct_operands=len(operands),
        total_operators=sum(operators.values()),
        total_operands=sum(operands.values()),
    )


# ── Maintainability index ─────────────────────────────────────────

def maintainability_index(
    volume: float,
    cyclomatic: int,
    code_lines: int,
    comment_percent: Optional[float] = None,
) -> float:
    """MI on a 0-100 scale. Empty code (no volume or lines) is fully maintainable."""
    if volume <= 0 or code_lines <= 0:
        return 100.0
    raw = 171 - 5.2 * math.log(volume) - 0.23 * cyclomatic - 16.2 * math.log(code_lines)
    if comment_percent is not None and comment_percent > 0:
        raw += 50 * math.sin(math.sqrt(2.4 * math.radians(comment_percent)))
    return round(min(100.0, max(0.0, raw * 100 / 171)), 2)


@dataclass(frozen=True)
class FunctionMaintainability:
    name: str
    lineno: int
    end_lineno: int
    mi: float
    halstead_volume: float
    cyclomatic: int
    code_lines: int

    @property
    def rank(self) -> str:
        return classify(self.mi)

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "lineno": self.lineno,
            "end_lineno": self.end_lineno,
            "mi": self.mi,
            "rank": self.rank,
            "halstead_volume": round(self.halstead_volume, 2),
            "cyclomatic": self.cyclomatic,
            "code_lines": self.code_lines,
        }


@dataclass
class FileMaintainability:
    path: str
    mi: float = 100.0
    halstead: Halstead = field(default_factory=Halstead)
    cyclomatic_total: int = 0
    code_lines: int = 0
    comment_density: float = 0.0
    functions: List[FunctionMaintainability] = field(default_factory=list)
    parse_error: Optional[str] = None

    @property
    def rank(self) -> str:
        return classify(self.mi)

    @property
    def average_function_mi(self) -> float:
        """Mean MI of the file's functions.

        File-level MI falls as a file grows (ln V and ln L both rise), so any
        large file scores low. The per-function average does not depend on
        file size; report both.
        """
        if not self.functions:
            return self.mi
        return round(sum(f.mi for f in self.functions) / len(self.functions), 2)

    @property
    def low_maintainability_functions(self) -> List[FunctionMaintainability]:
        """Functions below the moderate band (MI < 10), worst first."""
        return sorted((f for f in self.functions if f.mi < MODERATE_MIN), key=lambda f: f.mi)

    def to_dict(self) -> Dict[str, object]:
        return {
            "path": self.path,
            "mi": self.mi,
            "rank": self.rank,
            "average_function_mi": self.average_function_mi,
            "halstead": self.halstead.to_dict(),
            "cyclomatic_total": self.cyclomatic_total,
            "code_lines": self.code_lines,
            "comment_density": self.comment_density,
            "functions": [f.to_dict() for f in self.functions],
            "parse_error": self.parse_error,
        }


def analyze_source(source: str, path: str = "<string>", include_comments: bool = False) -> FileMaintainability:
    """Maintainability index of a file and of each of its functions."""
    source = source.lstrip("﻿")
    size = measure_source(source, path)
    if size.parse_error:
        return FileMaintainability(path=path, parse_error=size.parse_error)

    tokens = halstead_tokens(source)
    file_halstead = halstead(tokens)
    cyclo = _cyclomatic_source(source, path)
    comment_percent = size.comment_density if include_comments else None

    rows = code_rows(source, docstring_rows(ast.parse(source)))
    functions: List[FunctionMaintainability] = []
    for func in cyclo.functions:
        span = range(func.lineno, func.end_lineno + 1)
        func_tokens = [t for t in tokens if t.line in span]
        volume = halstead(func_tokens).volume
        lines = sum(1 for r in rows if r in span)
        functions.append(
            FunctionMaintainability(
                name=func.name,
                lineno=func.lineno,
                end_lineno=func.end_lineno,
                mi=maintainability_index(volume, func.cyclomatic, lines),
                halstead_volume=volume,
                cyclomatic=func.cyclomatic,
                code_lines=lines,
            )
        )

    return FileMaintainability(
        path=path,
        mi=maintainability_index(file_halstead.volume, cyclo.total, size.code_lines, comment_percent),
        halstead=file_halstead,
        cyclomatic_total=cyclo.total,
        code_lines=size.code_lines,
        comment_density=size.comment_density,
        functions=functions,
    )


def analyze_file(path: str | Path, include_comments: bool = False) -> FileMaintainability:
    p = Path(path)
    try:
        source = p.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        return FileMaintainability(path=str(p), parse_error=f"{type(exc).__name__}: {exc}")
    return analyze_source(source, path=str(p), include_comments=include_comments)
