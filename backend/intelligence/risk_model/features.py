"""
Kamei et al. (2013) change metrics, "A Large-Scale Empirical Study of
Just-in-Time Quality Assurance" (IEEE TSE). Computed in one chronological
pass, so every change only sees its own past (no look-ahead).

Only product-code files (git_history.is_source_file) are counted.

    size        LA  lines added        LD  lines deleted
                LT  lines in the touched files before the change
    diffusion   NS  subsystems (top-level directories)   ND  directories
                NF  files    ENTROPY  spread of the change across files
                    (Shannon entropy normalised by log2(NF); 0 = one file)
    purpose     FIX 1 if the change is a bug fix
    history     NDEV developers who changed these files before
                AGE  mean days since these files last changed
                NUC  unique earlier changes to these files
    experience  EXP  author's earlier changes   REXP  the same, weighted
                     1 / (1 + years ago)        SEXP  author's earlier
                     changes in the same subsystems

The running state (per file and per author) is exported by HistoryState so a
trained model can score a NEW pull request without re-reading history.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .git_history import Commit, is_source_file
from .szz import is_fix

FEATURES = ("LA", "LD", "LT", "NS", "ND", "NF", "ENTROPY", "FIX", "NDEV", "AGE", "NUC", "EXP", "REXP", "SEXP")
SECONDS_PER_DAY = 86400
SECONDS_PER_YEAR = 365.25 * SECONDS_PER_DAY


def subsystem(path: str) -> str:
    parts = PurePosixPath(path).parts
    return parts[0] if len(parts) > 1 else "(root)"


def directory(path: str) -> str:
    parent = str(PurePosixPath(path).parent)
    return "" if parent == "." else parent


def entropy(churn: Sequence[int]) -> float:
    total = sum(churn)
    if total <= 0 or len(churn) <= 1:
        return 0.0
    h = -sum(c / total * math.log2(c / total) for c in churn if c > 0)
    return round(h / math.log2(len(churn)), 4)


@dataclass
class HistoryState:
    """What the history knows before the next change."""

    file_size: Dict[str, int] = field(default_factory=dict)
    file_last_change: Dict[str, int] = field(default_factory=dict)
    file_developers: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    file_changes: Dict[str, Set[str]] = field(default_factory=lambda: defaultdict(set))
    author_changes: Dict[str, List[int]] = field(default_factory=lambda: defaultdict(list))   # timestamps
    author_subsystem: Dict[Tuple[str, str], int] = field(default_factory=lambda: defaultdict(int))

    def features(self, files: Sequence[Tuple[str, int, int]], author: str, timestamp: int,
                 fix: bool) -> Dict[str, float]:
        """Metrics for a change touching `files` [(path, added, deleted)] by `author` at `timestamp`."""
        files = [(p, a, d) for p, a, d in files if a or d]
        paths = [p for p, _, _ in files]
        subsystems = {subsystem(p) for p in paths}
        ages = [(timestamp - self.file_last_change[p]) / SECONDS_PER_DAY for p in paths if p in self.file_last_change]
        developers: Set[str] = set()
        prior_changes: Set[str] = set()
        for p in paths:
            developers |= self.file_developers.get(p, set())
            prior_changes |= self.file_changes.get(p, set())
        history = [t for t in self.author_changes.get(author, []) if t <= timestamp]
        return {
            "LA": float(sum(a for _, a, _ in files)),
            "LD": float(sum(d for _, _, d in files)),
            "LT": float(sum(self.file_size.get(p, 0) for p in paths)),
            "NS": float(len(subsystems)),
            "ND": float(len({directory(p) for p in paths})),
            "NF": float(len(paths)),
            "ENTROPY": entropy([a + d for _, a, d in files]),
            "FIX": 1.0 if fix else 0.0,
            "NDEV": float(len(developers)),
            "AGE": round(sum(ages) / len(ages), 3) if ages else 0.0,
            "NUC": float(len(prior_changes)),
            "EXP": float(len(history)),
            "REXP": round(sum(1 / (1 + max(0.0, (timestamp - t) / SECONDS_PER_YEAR)) for t in history), 4),
            "SEXP": float(sum(self.author_subsystem.get((author, s), 0) for s in subsystems)),
        }

    def apply(self, change_id: str, files: Sequence[Tuple[str, int, int]], author: str, timestamp: int) -> None:
        """Record a change so later changes see it."""
        touched = [(p, a, d) for p, a, d in files if a or d]
        for path, added, deleted in touched:
            self.file_size[path] = max(0, self.file_size.get(path, 0) + added - deleted)
            self.file_last_change[path] = timestamp
            self.file_developers[path].add(author)
            self.file_changes[path].add(change_id)
        self.author_changes[author].append(timestamp)
        for s in {subsystem(p) for p, _, _ in touched}:
            self.author_subsystem[(author, s)] += 1

    # ── export for scoring new pull requests ──────────────────────
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_size": self.file_size,
            "file_last_change": self.file_last_change,
            "file_developers": {p: sorted(v) for p, v in self.file_developers.items()},
            "file_change_count": {p: len(v) for p, v in self.file_changes.items()},
            "author_changes": {a: v[-500:] for a, v in self.author_changes.items()},
            "author_subsystem": [[a, s, n] for (a, s), n in self.author_subsystem.items()],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "HistoryState":
        state = cls()
        state.file_size = dict(data.get("file_size", {}))
        state.file_last_change = {k: int(v) for k, v in data.get("file_last_change", {}).items()}
        for p, devs in data.get("file_developers", {}).items():
            state.file_developers[p] = set(devs)
        # exact prior-change ids are not exported; placeholders keep the counts (NUC)
        for p, n in data.get("file_change_count", {}).items():
            state.file_changes[p] = {f"{p}#{i}" for i in range(int(n))}
        for a, times in data.get("author_changes", {}).items():
            state.author_changes[a] = [int(t) for t in times]
        for a, s, n in data.get("author_subsystem", []):
            state.author_subsystem[(a, s)] = int(n)
        return state


@dataclass(frozen=True)
class ChangeRow:
    sha: str
    timestamp: int
    features: Dict[str, float]
    buggy: bool


def build_dataset(changes: Iterable[Commit], buggy: Set[str], suffixes: Sequence[str] = (".py",)
                  ) -> Tuple[List[ChangeRow], HistoryState]:
    """One row per change that touches product code, plus the final history state."""
    state = HistoryState()
    rows: List[ChangeRow] = []
    for change in changes:
        files = [(f.path, f.added, f.deleted) for f in change.files if is_source_file(f.path, suffixes)]
        if any(a or d for _, a, d in files):
            rows.append(ChangeRow(change.sha, change.timestamp,
                                  state.features(files, change.author, change.timestamp, is_fix(change)),
                                  change.sha in buggy))
        state.apply(change.sha, files, change.author, change.timestamp)
    return rows, state
