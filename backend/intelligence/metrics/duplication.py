"""
Code duplication detection: token windows + Rabin-Karp rolling hash.

How it works:
    1. Tokenize each file with Python's own tokenizer and drop what does not
       change behaviour: comments, blank lines, indentation tokens and
       import statements (shared imports are not copy-paste).
    2. Normalize tokens so renamed copies still match:
       identifiers -> ID, numbers -> NUM, strings -> STR.
       Keywords and operators keep their text.
    3. Slide a window of `min_tokens` tokens over every file and compute a
       Rabin-Karp rolling hash for each window, O(1) per step.
    4. Windows with the same hash in two places are candidate copies; the
       tokens are compared to rule out hash collisions.
    5. Each match is extended backwards and forwards to its maximal length.
    6. Clones spanning at least `min_lines` lines are kept.
       Duplication density = duplicated code lines / code lines x 100.

Clone types detected:
    type 1  exact copy (layout and comments ignored)
    type 2  copy with renamed identifiers / changed literals (normalize=True)
Not detected: type 3 (statements added or removed inside the copy) and
type 4 (same behaviour written differently).

Defaults follow SonarQube's rule of thumb: at least 100 duplicated tokens
spread over at least 10 lines. "Code lines" are NCLOC as defined in
size.py (comments, blank lines and docstrings excluded), the same
denominator every other metric uses.
"""

from __future__ import annotations

import ast
import io
import keyword
import tokenize
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, Optional, Set, Tuple

from .size import code_rows as _ncloc_rows, docstring_rows as _docstring_rows

DEFAULT_MIN_TOKENS = 100
DEFAULT_MIN_LINES = 10

_HASH_BASE = 1_000_003
_HASH_MOD = (1 << 61) - 1  # Mersenne prime

_SKIP_TYPES = {
    tokenize.COMMENT,
    tokenize.NL,
    tokenize.INDENT,
    tokenize.DEDENT,
    tokenize.ENCODING,
}


# ── tokens ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Token:
    value: str
    start_line: int
    end_line: int


def _normalize(tok: tokenize.TokenInfo, normalize: bool) -> str:
    if tok.type == tokenize.NAME:
        if not normalize or keyword.iskeyword(tok.string):
            return tok.string
        return "ID"
    if tok.type == tokenize.NUMBER:
        return "NUM" if normalize else tok.string
    if tok.type == tokenize.STRING:
        return "STR" if normalize else tok.string
    name = tokenize.tok_name.get(tok.type, "")
    if name.endswith("_MIDDLE"):  # f-string / t-string text (Python 3.12+)
        return "STR" if normalize else tok.string
    if name.endswith("_START") or name.endswith("_END"):
        return name
    return tok.string  # operators and punctuation


def _is_import(line_tokens: List[tokenize.TokenInfo]) -> bool:
    return bool(line_tokens) and line_tokens[0].type == tokenize.NAME and (
        line_tokens[0].string in ("import", "from")
    )


def tokenize_source(source: str, normalize: bool = True) -> List[Token]:
    """Comparable tokens of Python source code.

    Raises tokenize.TokenError / SyntaxError for code that cannot be tokenized.
    """
    source = source.lstrip("﻿")
    tokens: List[Token] = []
    logical_line: List[tokenize.TokenInfo] = []

    def flush() -> None:
        if not _is_import(logical_line):
            tokens.extend(
                Token(_normalize(t, normalize), t.start[0], t.end[0]) for t in logical_line
            )
        logical_line.clear()

    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type in (tokenize.NEWLINE, tokenize.ENDMARKER):
            flush()
        elif tok.type not in _SKIP_TYPES:
            logical_line.append(tok)
    flush()
    return tokens


def _rolling_hashes(seq: List[int], window: int) -> Iterator[Tuple[int, int]]:
    """Yield (position, hash) for every window of `window` tokens (Rabin-Karp)."""
    if len(seq) < window:
        return
    high = pow(_HASH_BASE, window - 1, _HASH_MOD)
    h = 0
    for value in seq[:window]:
        h = (h * _HASH_BASE + value) % _HASH_MOD
    yield 0, h
    for pos in range(1, len(seq) - window + 1):
        h = ((h - seq[pos - 1] * high) * _HASH_BASE + seq[pos + window - 1]) % _HASH_MOD
        yield pos, h


def _direct_hash(seq: List[int]) -> int:
    h = 0
    for value in seq:
        h = (h * _HASH_BASE + value) % _HASH_MOD
    return h


# ── results ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class CloneBlock:
    path: str
    start_line: int
    end_line: int

    @property
    def lines(self) -> int:
        return self.end_line - self.start_line + 1

    def to_dict(self) -> Dict[str, object]:
        return {"path": self.path, "start_line": self.start_line, "end_line": self.end_line}


@dataclass(frozen=True)
class Clone:
    """Two copies of the same code. `original` is the one found first."""

    original: CloneBlock
    copy: CloneBlock
    tokens: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "original": self.original.to_dict(),
            "copy": self.copy.to_dict(),
            "tokens": self.tokens,
            "lines": self.copy.lines,
        }


@dataclass
class FileDuplication:
    path: str
    code_lines: int
    duplicated_lines: int

    @property
    def density(self) -> float:
        return round(100 * self.duplicated_lines / self.code_lines, 2) if self.code_lines else 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "path": self.path,
            "code_lines": self.code_lines,
            "duplicated_lines": self.duplicated_lines,
            "density": self.density,
        }


@dataclass
class DuplicationReport:
    files: List[FileDuplication] = field(default_factory=list)
    clones: List[Clone] = field(default_factory=list)
    parse_errors: Dict[str, str] = field(default_factory=dict)
    min_tokens: int = DEFAULT_MIN_TOKENS
    min_lines: int = DEFAULT_MIN_LINES

    @property
    def code_lines(self) -> int:
        return sum(f.code_lines for f in self.files)

    @property
    def duplicated_lines(self) -> int:
        return sum(f.duplicated_lines for f in self.files)

    @property
    def density(self) -> float:
        return round(100 * self.duplicated_lines / self.code_lines, 2) if self.code_lines else 0.0

    def to_dict(self) -> Dict[str, object]:
        return {
            "min_tokens": self.min_tokens,
            "min_lines": self.min_lines,
            "code_lines": self.code_lines,
            "duplicated_lines": self.duplicated_lines,
            "density": self.density,
            "clone_count": len(self.clones),
            "clones": [c.to_dict() for c in self.clones],
            "files": [f.to_dict() for f in self.files],
            "parse_errors": dict(self.parse_errors),
        }


# ── detection ─────────────────────────────────────────────────────

def detect_duplicates(
    sources: Mapping[str, str],
    min_tokens: int = DEFAULT_MIN_TOKENS,
    min_lines: int = DEFAULT_MIN_LINES,
    normalize: bool = True,
) -> DuplicationReport:
    """Find duplicated code across (and within) the given files.

    Args:
        sources: path -> Python source code
        min_tokens: shortest clone, in tokens
        min_lines: shortest clone, in lines (each copy must span this many)
        normalize: also match copies with renamed identifiers / literals
    """
    if min_tokens < 2:
        raise ValueError("min_tokens must be at least 2")
    if min_lines < 1:
        raise ValueError("min_lines must be at least 1")

    report = DuplicationReport(min_tokens=min_tokens, min_lines=min_lines)
    paths: List[str] = []
    token_lists: List[List[Token]] = []
    for path in sorted(sources):
        try:
            tokens = tokenize_source(sources[path], normalize=normalize)
        except (tokenize.TokenError, SyntaxError, ValueError) as exc:
            report.parse_errors[path] = f"{type(exc).__name__}: {exc}"
            continue
        paths.append(path)
        token_lists.append(tokens)

    # Intern token values as integers for hashing and fast comparison
    vocab: Dict[str, int] = {}
    seqs = [[vocab.setdefault(t.value, len(vocab) + 1) for t in toks] for toks in token_lists]

    buckets: Dict[int, List[Tuple[int, int]]] = {}
    for fi, seq in enumerate(seqs):
        for pos, h in _rolling_hashes(seq, min_tokens):
            buckets.setdefault(h, []).append((fi, pos))

    found: List[Tuple[int, int, int, int, int]] = []
    covered: Dict[Tuple[int, int, int], List[Tuple[int, int]]] = {}

    for occurrences in buckets.values():
        if len(occurrences) < 2:
            continue
        groups: Dict[Tuple[int, ...], List[Tuple[int, int]]] = {}
        for fi, pos in occurrences:  # verify tokens: rules out hash collisions
            groups.setdefault(tuple(seqs[fi][pos:pos + min_tokens]), []).append((fi, pos))
        for members in groups.values():
            first = members[0]
            for other in members[1:]:
                clone = _maximal_clone(first, other, seqs, min_tokens, covered)
                if clone is not None:
                    found.append(clone)

    code_line_sets: List[Set[int]] = []
    for path, toks in zip(paths, token_lists):
        rows = _ncloc(sources[path])
        code_line_sets.append(rows if rows is not None else _code_lines(toks))  # empty set is valid
    duplicated: List[Set[int]] = [set() for _ in paths]
    # Token ranges already reported as a copy, per file. Repetitive code
    # (e.g. 20 lines of the same shape) matches itself at many offsets;
    # those overlapping copies are reported once but still counted in density.
    reported_copies: Dict[int, List[Tuple[int, int]]] = {}

    for fa, pa, fb, pb, length in sorted(found):
        block_a = _block(paths[fa], token_lists[fa], pa, length)
        block_b = _block(paths[fb], token_lists[fb], pb, length)
        if min(block_a.lines, block_b.lines) < min_lines:
            continue
        copy_range = (pb, pb + length)
        if not any(s < copy_range[1] and copy_range[0] < e for s, e in reported_copies.get(fb, [])):
            reported_copies.setdefault(fb, []).append(copy_range)
            report.clones.append(Clone(original=block_a, copy=block_b, tokens=length))
        for fi, block in ((fa, block_a), (fb, block_b)):
            duplicated[fi].update(
                line for line in range(block.start_line, block.end_line + 1)
                if line in code_line_sets[fi]
            )

    report.files = [
        FileDuplication(path=paths[i], code_lines=len(code_line_sets[i]), duplicated_lines=len(duplicated[i]))
        for i in range(len(paths))
    ]
    return report


def _maximal_clone(
    a: Tuple[int, int],
    b: Tuple[int, int],
    seqs: List[List[int]],
    min_tokens: int,
    covered: Dict[Tuple[int, int, int], List[Tuple[int, int]]],
) -> Optional[Tuple[int, int, int, int, int]]:
    """Extend a matching window pair to the longest clone; None if already found or overlapping."""
    (fa, pa), (fb, pb) = a, b
    delta = pb - pa
    if fa == fb and abs(delta) < min_tokens:
        return None  # the two windows overlap: repetition, not a copy

    diagonal = (fa, fb, delta)
    for start, end in covered.get(diagonal, []):
        if start <= pa < end:
            return None  # part of a clone already reported

    sa, sb = seqs[fa], seqs[fb]
    length = min_tokens
    while pa > 0 and pb > 0 and sa[pa - 1] == sb[pb - 1]:
        if fa == fb and length >= abs(delta):
            break
        pa, pb, length = pa - 1, pb - 1, length + 1
    while pa + length < len(sa) and pb + length < len(sb) and sa[pa + length] == sb[pb + length]:
        if fa == fb and length >= abs(delta):
            break
        length += 1

    covered.setdefault(diagonal, []).append((pa, pa + length))
    return fa, pa, fb, pb, length


def _block(path: str, tokens: List[Token], start: int, length: int) -> CloneBlock:
    return CloneBlock(path, tokens[start].start_line, tokens[start + length - 1].end_line)


def _ncloc(source: str) -> Optional[Set[int]]:
    """NCLOC line numbers (shared definition from size.py); None if unparseable."""
    source = source.lstrip("﻿")
    try:
        return _ncloc_rows(source, _docstring_rows(ast.parse(source)))
    except (SyntaxError, ValueError, tokenize.TokenError):
        return None


def _code_lines(tokens: Iterable[Token]) -> Set[int]:
    lines: Set[int] = set()
    for t in tokens:
        lines.update(range(t.start_line, t.end_line + 1))
    return lines


def analyze_files(
    paths: Iterable[str | Path],
    root: str | Path | None = None,
    min_tokens: int = DEFAULT_MIN_TOKENS,
    min_lines: int = DEFAULT_MIN_LINES,
    normalize: bool = True,
) -> DuplicationReport:
    """Read Python files from disk and detect duplicates across them.

    Paths in the report are relative to `root` when it is given.
    """
    sources: Dict[str, str] = {}
    unreadable: Dict[str, str] = {}
    root_path = Path(root) if root is not None else None
    for path in paths:
        p = Path(path)
        key = (p.relative_to(root_path) if root_path is not None else p).as_posix()
        try:
            sources[key] = p.read_text(encoding="utf-8-sig", errors="replace")
        except OSError as exc:
            unreadable[key] = f"{type(exc).__name__}: {exc}"
    report = detect_duplicates(sources, min_tokens=min_tokens, min_lines=min_lines, normalize=normalize)
    report.parse_errors.update(unreadable)
    return report
