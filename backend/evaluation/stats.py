"""
Small statistics helpers for the evaluation scripts (standard library only).

    Agreement     paired values: exact match, close match, mean absolute error,
                  Pearson r, Spearman rho
    LineOverlap   two sets of duplicated lines: precision, recall, F1, Jaccard
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence, Set, Tuple


def _ranks(values: Sequence[float]) -> List[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1  # average rank for ties
        i = j + 1
    return ranks


def pearson(x: Sequence[float], y: Sequence[float]) -> float:
    n = len(x)
    if n < 2:
        return float("nan")
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return sxy / (sx * sy) if sx and sy else float("nan")


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    return pearson(_ranks(x), _ranks(y))


TABLE_HEADER = (
    "| Comparison | n | Exact match | Close match | Mean abs. error | Pearson r | Spearman ρ |\n"
    "|---|---|---|---|---|---|---|"
)


@dataclass
class Agreement:
    """Paired measurements of the same thing by SAMANVAYA (ours) and a reference tool."""

    name: str
    ours: List[float] = field(default_factory=list)
    theirs: List[float] = field(default_factory=list)

    def add(self, ours: float, theirs: float) -> None:
        self.ours.append(ours)
        self.theirs.append(theirs)

    @property
    def n(self) -> int:
        return len(self.ours)

    def exact(self) -> float:
        return 100 * sum(a == b for a, b in zip(self.ours, self.theirs)) / self.n if self.n else 0.0

    def within(self, tolerance: float) -> float:
        return 100 * sum(abs(a - b) <= tolerance for a, b in zip(self.ours, self.theirs)) / self.n if self.n else 0.0

    def mae(self) -> float:
        return sum(abs(a - b) for a, b in zip(self.ours, self.theirs)) / self.n if self.n else 0.0

    def row(self, tolerance: float) -> str:
        return (
            f"| {self.name} | {self.n} | {self.exact():.1f}% | {self.within(tolerance):.1f}% (±{tolerance:g}) "
            f"| {self.mae():.2f} | {pearson(self.ours, self.theirs):.3f} | {spearman(self.ours, self.theirs):.3f} |"
        )


LineSet = Set[Tuple[str, int]]


def lines_from_ranges(ranges: Iterable[Tuple[str, int, int]]) -> LineSet:
    """(path, start, end) ranges -> set of (path, line)."""
    out: LineSet = set()
    for path, start, end in ranges:
        out.update((path, line) for line in range(start, end + 1))
    return out


@dataclass
class LineOverlap:
    """Agreement between two sets of duplicated lines; `theirs` is the reference."""

    name: str
    ours: LineSet
    theirs: LineSet

    @property
    def both(self) -> int:
        return len(self.ours & self.theirs)

    @property
    def precision(self) -> float:
        """Share of the lines we flag that the reference also flags."""
        return 100 * self.both / len(self.ours) if self.ours else 0.0

    @property
    def recall(self) -> float:
        """Share of the reference's lines that we also flag."""
        return 100 * self.both / len(self.theirs) if self.theirs else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    @property
    def jaccard(self) -> float:
        union = self.ours | self.theirs
        return 100 * self.both / len(union) if union else 100.0

    def row(self) -> str:
        return (
            f"| {self.name} | {len(self.ours)} | {len(self.theirs)} | {self.both} "
            f"| {self.precision:.1f}% | {self.recall:.1f}% | {self.f1:.1f}% | {self.jaccard:.1f}% |"
        )


OVERLAP_HEADER = (
    "| Comparison | Our lines | Their lines | Both | Precision | Recall | F1 | Jaccard |\n"
    "|---|---|---|---|---|---|---|---|"
)


def by_file(lines: LineSet) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for path, _ in lines:
        counts[path] = counts.get(path, 0) + 1
    return counts
