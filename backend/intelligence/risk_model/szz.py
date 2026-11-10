"""
SZZ: label the changes that introduced bugs (Sliwerski, Zimmermann & Zeller,
"When do changes induce fixes?", MSR 2005).

    1. find bug-FIXING changes: a message with fix / bug / defect / patch
       (Mockus & Votta's keywords), unless the message is about docs, typos,
       lint, formatting, CI or tests (non-functional "fixes")
    2. for each fix, take the product-code lines it deleted or modified
       (git diff -U0 against its parent); blank and comment-only lines are
       skipped
    3. git blame -w those lines in the parent: the commit that last changed
       each line is a bug-INTRODUCING candidate (whitespace changes ignored)
    4. map that commit to the main-branch change that brought it in

Known limits (stated, not hidden): fixes that only ADD lines cannot be traced;
keyword matching misses some fixes and includes some non-fixes; the newest
changes have had little time to be found buggy, so they are under-labelled
(the evaluation drops them from the test set).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set

from .git_history import Commit, GitError, is_source_file, run_git

FIX_RE = re.compile(r"(?i)\b(fix(e[sd]|ing)?|bug(s|fix)?|defects?|patch(e[sd])?)\b")
NOISE_RE = re.compile(
    r"(?i)\b(typos?|docs?|documentation|docstrings?|readme|changelog|lint(ing)?|flake8|pylint|black|isort|mypy"
    r"|format(ting)?|whitespace|spelling|ci|tox|tests?|testing|coverage|github actions|workflows?)\b"
)
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")
_SHA = re.compile(r"^([0-9a-f]{40}) \d+ \d+")


def is_fix_message(message: str) -> bool:
    return bool(FIX_RE.search(message)) and not NOISE_RE.search(message)


def is_fix(change: Commit) -> bool:
    return any(is_fix_message(m) for m in (change.subject, *change.messages))


def _meaningful(line: str) -> bool:
    text = line.strip()
    return bool(text) and not text.startswith("#")


def deleted_lines(diff_text: str) -> Dict[str, List[int]]:
    """Old-file line numbers deleted or modified per path, from `git diff -U0` output."""
    out: Dict[str, List[int]] = {}
    path: Optional[str] = None
    old_line = 0
    for raw in diff_text.splitlines():
        if raw.startswith("--- "):
            target = raw[4:].strip()
            path = None if target == "/dev/null" else (target[2:] if target.startswith("a/") else target)
        elif raw.startswith("+++ "):
            continue
        elif raw.startswith("@@"):
            m = _HUNK.match(raw)
            if m:
                old_line = int(m.group(1))
        elif path and raw.startswith("-"):
            if _meaningful(raw[1:]):
                out.setdefault(path, []).append(old_line)
            old_line += 1
        elif raw.startswith(" "):
            old_line += 1
    return out


def to_ranges(lines: Iterable[int]) -> List[tuple]:
    ranges: List[list] = []
    for n in sorted(set(lines)):
        if ranges and n == ranges[-1][1] + 1:
            ranges[-1][1] = n
        else:
            ranges.append([n, n])
    return [tuple(r) for r in ranges]


def blamed_commits(porcelain: str) -> Set[str]:
    return {m.group(1) for line in porcelain.splitlines() for m in [_SHA.match(line)] if m}


@dataclass
class SZZResult:
    buggy: Set[str] = field(default_factory=set)              # main-line change shas that introduced bugs
    fixes: List[str] = field(default_factory=list)            # fix change shas analysed
    links: Dict[str, Set[str]] = field(default_factory=dict)  # fix -> introducing changes
    errors: int = 0

    def to_dict(self) -> Dict[str, object]:
        return {"buggy_changes": len(self.buggy), "fixes": len(self.fixes),
                "fixes_traced": sum(1 for f in self.fixes if self.links.get(f)), "errors": self.errors}


def run_szz(repo: str, changes: Sequence[Commit], suffixes: Sequence[str] = (".py",),
            max_fixes: Optional[int] = None) -> SZZResult:
    """Label the bug-introducing changes among `changes` (oldest first)."""
    owner = {sha: change.sha for change in changes for sha in (change.commits or (change.sha,))}
    position = {change.sha: i for i, change in enumerate(changes)}
    result = SZZResult()
    fixes = [c for c in changes if c.parent and is_fix(c) and any(is_source_file(f.path, suffixes) for f in c.files)]
    if max_fixes:
        fixes = fixes[-max_fixes:]
    for fix in fixes:
        result.fixes.append(fix.sha)
        paths = [f.path for f in fix.files if is_source_file(f.path, suffixes) and f.deleted > 0]
        if not paths:
            continue
        try:
            diff = run_git(repo, ["diff", "-U0", "--no-renames", "--no-color", fix.parent, fix.sha, "--", *paths])
        except GitError:
            result.errors += 1
            continue
        introducing: Set[str] = set()
        for path, lines in deleted_lines(diff).items():
            ranges = to_ranges(lines)
            if not ranges:
                continue
            args = ["blame", "-w", "--porcelain"]
            for start, end in ranges:
                args += ["-L", f"{start},{end}"]
            try:
                blame = run_git(repo, [*args, fix.parent, "--", path])
            except GitError:
                result.errors += 1
                continue
            for sha in blamed_commits(blame):
                change = owner.get(sha)
                if change and change != fix.sha and position.get(change, 1 << 30) < position[fix.sha]:
                    introducing.add(change)
        result.links[fix.sha] = introducing
        result.buggy |= introducing
    return result
