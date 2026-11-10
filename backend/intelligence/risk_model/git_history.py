"""
Read a repository's history with git as CHANGES that landed on the main
branch, oldest first: a direct commit, or a merged pull request (its whole
diff against the main line). This matches how SAMANVAYA predicts risk: per PR.

For each change: the lines added and deleted per file, the commits it brought
in (so SZZ can map a blamed commit back to the change that introduced it),
the author who wrote most of those commits, and the time it landed.

Renames ("old => new", "dir/{a => b}/f.py") are reported under the new path.
Binary files ("-" counts) are skipped.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import List, Optional, Sequence, Tuple

RECORD, UNIT = "\x1e", "\x1f"
_BRACE_RENAME = re.compile(r"\{([^{}]*) => ([^{}]*)\}")

# Files that are not product code: excluded from labels and features.
_NON_SOURCE_DIRS = {"tests", "test", "testing", "docs", "doc", "examples", "example", "benchmarks", "scripts", ".github",
                    # vendored third-party code: not written by the team (e.g. requests/packages/urllib3)
                    "vendor", "vendored", "_vendor", "third_party", "thirdparty", "extern", "site-packages"}
# "packages" below the top level is the classic vendoring folder (pkg/packages/...);
# at the top level it is usually a monorepo root, so it is kept there.
_NESTED_VENDOR_DIRS = {"packages"}


class GitError(RuntimeError):
    pass


def run_git(repo: str, args: Sequence[str], timeout: int = 300) -> str:
    """Run git in `repo` with an argument list (no shell); return stdout."""
    result = subprocess.run(
        ["git", "-C", str(repo), "-c", "core.quotepath=false", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
    )
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args[:3])} failed: {result.stderr.strip()[:300]}")
    return result.stdout


@dataclass(frozen=True)
class FileChange:
    path: str
    added: int
    deleted: int


@dataclass
class Commit:
    """One change on the main branch (a direct commit or a merge of a PR)."""

    sha: str
    parents: Tuple[str, ...]
    author: str            # e-mail, lower case (identity for experience features)
    timestamp: int         # time it landed on the main branch (committer time), Unix seconds
    subject: str
    files: List[FileChange] = field(default_factory=list)
    commits: Tuple[str, ...] = ()       # commits this change brought in (itself included)
    messages: Tuple[str, ...] = ()      # their subjects (merges: the PR's commit messages)

    @property
    def parent(self) -> Optional[str]:
        return self.parents[0] if self.parents else None

    @property
    def is_merge(self) -> bool:
        return len(self.parents) > 1


def rename_target(path: str) -> str:
    """'a/{old => new}/f.py' -> 'a/new/f.py';  'old.py => new.py' -> 'new.py'."""
    if "=>" not in path:
        return path
    if "{" in path:
        new = _BRACE_RENAME.sub(lambda m: m.group(2), path)
        return re.sub(r"/+", "/", new).strip("/")
    return path.split("=>")[-1].strip()


def is_source_file(path: str, suffixes: Sequence[str] = (".py",)) -> bool:
    """Product code only: matching suffix, not in test / doc / example / vendored folders, not a test file."""
    p = PurePosixPath(path)
    if p.suffix not in suffixes:
        return False
    dirs = [part.lower() for part in p.parts[:-1]]
    if any(d in _NON_SOURCE_DIRS for d in dirs) or any(d in _NESTED_VENDOR_DIRS for d in dirs[1:]):
        return False
    name = p.name.lower()
    return not (name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py")


def parse_log(text: str) -> List[Commit]:
    """Parse `git log --numstat` output produced by read_commits()."""
    commits: List[Commit] = []
    for record in text.split(RECORD):
        record = record.strip("\n")
        if not record.strip():
            continue
        header, _, body = record.partition("\n")
        parts = header.split(UNIT)
        if len(parts) < 5:
            continue
        sha, parents, author, timestamp, subject = parts[0], parts[1], parts[2], parts[3], UNIT.join(parts[4:])
        commit = Commit(sha, tuple(p for p in parents.split() if p), author.strip().lower(), int(timestamp), subject)
        for line in body.splitlines():
            cols = line.split("\t")
            if len(cols) != 3 or cols[0] == "-" or cols[1] == "-":
                continue
            try:
                commit.files.append(FileChange(rename_target(cols[2]), int(cols[0]), int(cols[1])))
            except ValueError:
                continue
        commits.append(commit)
    return commits


def _commit_info(repo: str, ref: str) -> dict:
    """sha -> (author e-mail, subject) for every commit reachable from ref."""
    out = run_git(repo, ["log", f"--format=%H{UNIT}%ae{UNIT}%s", ref], timeout=600)
    info = {}
    for line in out.splitlines():
        parts = line.split(UNIT)
        if len(parts) >= 3:
            info[parts[0]] = (parts[1].strip().lower(), UNIT.join(parts[2:]))
    return info


def read_commits(repo: str, ref: str = "HEAD", max_commits: Optional[int] = None) -> List[Commit]:
    """Changes on the main branch (first-parent line of `ref`), oldest first.

    A merge's files are its diff against the first parent (the PR as a
    whole); its author is the author of most of the commits it brought in.
    """
    args = ["log", "--first-parent", "--diff-merges=first-parent", "--reverse", "--numstat", "--no-renames",
            f"--format={RECORD}%H{UNIT}%P{UNIT}%ae{UNIT}%ct{UNIT}%s", ref]
    changes = parse_log(run_git(repo, args, timeout=600))
    if max_commits:
        changes = changes[-max_commits:]
    info = _commit_info(repo, ref)
    for change in changes:
        if change.is_merge:
            brought = run_git(repo, ["rev-list", f"{change.parents[0]}..{change.sha}"]).split()
        else:
            brought = [change.sha]
        change.commits = tuple(brought)
        messages = [info[s][1] for s in brought if s in info and s != change.sha]
        change.messages = tuple(messages) or (change.subject,)
        authors = [info[s][0] for s in brought if s in info and s != change.sha]
        if authors:  # a merge's own author is whoever pressed "merge"
            change.author = max(set(authors), key=authors.count)
    return changes
