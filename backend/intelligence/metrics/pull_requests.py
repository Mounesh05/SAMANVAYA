"""
Pull request metrics: size, review status, time to first review, time to
merge, review rounds, and median / percentile summaries.

Size         lines added + deleted, excluding generated and lock files
             (package-lock.json, *.min.js, dist/, *_pb2.py, ...).
             Buckets: XS < 10, S < 100, M < 400, L < 1000, XL >= 1000 lines.
             Reviews of more than ~400 lines find defects less effectively
             (SmartBear / Cisco code-review study).
Review state from the reviews themselves: each human reviewer's latest
             decision counts (APPROVED / CHANGES_REQUESTED; DISMISSED cancels
             it). Any outstanding "changes requested" wins over approvals.
             Bots and the PR author are ignored.
Timings      first human review - opened; merged - opened; closed - opened
             (closed without merging). Optionally weekends are not counted.
Rounds       number of "changes requested" reviews before the PR ended.
Summaries    median and 85th / 90th percentile (linear interpolation, like
             numpy's default): a few very slow PRs distort the mean.
             Unreviewed merge rate: merged PRs that no human reviewed.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

SIZE_BUCKETS = ((10, "XS"), (100, "S"), (400, "M"), (1000, "L"))

_GENERATED = re.compile(
    r"(^|/)(package-lock\.json|npm-shrinkwrap\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|Pipfile\.lock"
    r"|Cargo\.lock|go\.sum|composer\.lock|Gemfile\.lock|uv\.lock)$"
    r"|\.min\.(js|css)$|\.map$|(^|/)(dist|build|vendor|node_modules|__snapshots__)/"
    r"|_pb2(_grpc)?\.py$|\.pb\.go$|\.generated\.\w+$",
    re.IGNORECASE,
)
_KNOWN_BOTS = {"dependabot", "renovate", "github-actions", "codecov", "sonarcloud", "snyk-bot", "mergify", "coderabbitai"}


def parse_time(value: Any) -> Optional[datetime]:
    """ISO-8601 string or datetime -> timezone-aware UTC datetime (None if missing)."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def hours_between(start: Any, end: Any, exclude_weekends: bool = False) -> Optional[float]:
    """Elapsed hours from start to end; with exclude_weekends, Saturday and
    Sunday (UTC) are not counted. None when either time is missing or end < start."""
    s, e = parse_time(start), parse_time(end)
    if s is None or e is None or e < s:
        return None
    total = (e - s).total_seconds()
    if exclude_weekends:
        day = datetime(s.year, s.month, s.day, tzinfo=timezone.utc)
        while day < e:
            nxt = day + timedelta(days=1)
            if day.weekday() >= 5:  # Saturday, Sunday
                overlap = (min(nxt, e) - max(day, s)).total_seconds()
                total -= max(0.0, overlap)
            day = nxt
    return round(total / 3600, 2)


def is_generated(path: str) -> bool:
    return bool(_GENERATED.search(path.replace("\\", "/")))


def is_bot(login: Optional[str], user_type: Optional[str] = None) -> bool:
    name = (login or "").lower()
    return user_type == "Bot" or name.endswith("[bot]") or name.split("[")[0] in _KNOWN_BOTS


def size_bucket(lines: int) -> str:
    for limit, label in SIZE_BUCKETS:
        if lines < limit:
            return label
    return "XL"


# ── size ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PRSize:
    lines_added: int
    lines_deleted: int
    files: int
    generated_lines_excluded: int = 0

    @property
    def lines_changed(self) -> int:
        return self.lines_added + self.lines_deleted

    @property
    def bucket(self) -> str:
        return size_bucket(self.lines_changed)

    def to_dict(self) -> Dict[str, Any]:
        return {"lines_added": self.lines_added, "lines_deleted": self.lines_deleted,
                "lines_changed": self.lines_changed, "files": self.files,
                "generated_lines_excluded": self.generated_lines_excluded, "bucket": self.bucket}


def pr_size(files: Iterable[Mapping[str, Any]]) -> PRSize:
    """From GitHub's PR files list ({filename, additions, deletions})."""
    added = deleted = count = excluded = 0
    for f in files:
        a, d = int(f.get("additions") or 0), int(f.get("deletions") or 0)
        if is_generated(str(f.get("filename", ""))):
            excluded += a + d
            continue
        added, deleted, count = added + a, deleted + d, count + 1
    return PRSize(added, deleted, count, excluded)


# ── reviews ───────────────────────────────────────────────────────

def _human_reviews(reviews: Iterable[Mapping[str, Any]], author: Optional[str]) -> List[Mapping[str, Any]]:
    out = []
    for r in reviews:
        user = r.get("user") or {}
        login = user.get("login") if isinstance(user, Mapping) else r.get("reviewer")
        login = login or r.get("reviewer")
        user_type = user.get("type") if isinstance(user, Mapping) else None
        state = str(r.get("state", "")).upper()
        bot = bool(r.get("is_bot")) or is_bot(login, user_type)   # stored reviews carry is_bot
        if not login or bot or (author and login.lower() == author.lower()) or state == "PENDING":
            continue
        out.append({"login": login, "state": state, "submitted_at": r.get("submitted_at")})
    out.sort(key=lambda r: parse_time(r["submitted_at"]) or datetime.max.replace(tzinfo=timezone.utc))
    return out


def review_status(reviews: Iterable[Mapping[str, Any]], author: Optional[str] = None) -> str:
    """SAMANVAYA review_status: pending | in_review | approved | changes_requested."""
    human = _human_reviews(reviews, author)
    if not human:
        return "pending"
    latest: Dict[str, str] = {}
    for r in human:
        if r["state"] in ("APPROVED", "CHANGES_REQUESTED"):
            latest[r["login"]] = r["state"]
        elif r["state"] == "DISMISSED":
            latest.pop(r["login"], None)
    if "CHANGES_REQUESTED" in latest.values():
        return "changes_requested"
    if "APPROVED" in latest.values():
        return "approved"
    return "in_review"


def first_review_at(reviews: Iterable[Mapping[str, Any]], author: Optional[str] = None) -> Optional[str]:
    human = [r for r in _human_reviews(reviews, author) if parse_time(r["submitted_at"])]
    return human[0]["submitted_at"] if human else None


def review_rounds(reviews: Iterable[Mapping[str, Any]], author: Optional[str] = None) -> int:
    return sum(1 for r in _human_reviews(reviews, author) if r["state"] == "CHANGES_REQUESTED")


def compact_reviews(reviews: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """What SAMANVAYA stores per review: reviewer, bot flag, state, time."""
    out = []
    for r in reviews:
        user = r.get("user") or {}
        out.append({
            "reviewer": user.get("login"),
            "is_bot": is_bot(user.get("login"), user.get("type")),
            "state": str(r.get("state", "")).upper(),
            "submitted_at": r.get("submitted_at"),
        })
    return out


# ── one PR ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PRMetrics:
    pr_number: Optional[int]
    status: str                       # open | merged | closed
    size: Optional[PRSize]
    review_status: str
    review_rounds: int
    reviewed: bool
    hours_to_first_review: Optional[float]
    hours_to_merge: Optional[float]
    hours_to_close: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pr_number": self.pr_number, "status": self.status,
            "size": self.size.to_dict() if self.size else None,
            "review_status": self.review_status, "review_rounds": self.review_rounds, "reviewed": self.reviewed,
            "hours_to_first_review": self.hours_to_first_review, "hours_to_merge": self.hours_to_merge,
            "hours_to_close": self.hours_to_close,
        }


def pr_metrics(pr: Mapping[str, Any], exclude_weekends: bool = False) -> PRMetrics:
    """Metrics for one stored PR document (SAMANVAYA fields, GitHub field names accepted too)."""
    author = pr.get("author_login") or (pr.get("user") or {}).get("login")
    reviews = pr.get("reviews") or []
    opened = pr.get("created_at")
    merged = pr.get("merged_at")
    closed = pr.get("closed_at")
    status = pr.get("status") or ("merged" if merged else "closed" if closed else "open")
    if pr.get("lines_added") is not None or pr.get("lines_deleted") is not None:
        size = PRSize(int(pr.get("lines_added") or 0), int(pr.get("lines_deleted") or 0),
                      int(pr.get("files_changed_count") or 0), int(pr.get("generated_lines_excluded") or 0))
    elif pr.get("files"):
        size = pr_size(pr["files"])
    else:
        size = None
    first = pr.get("first_review_at") or first_review_at(reviews, author)
    return PRMetrics(
        pr_number=pr.get("pr_number") or pr.get("number"),
        status=status,
        size=size,
        review_status=review_status(reviews, author) if reviews else str(pr.get("review_status") or "pending"),
        review_rounds=review_rounds(reviews, author),
        reviewed=first is not None,
        hours_to_first_review=hours_between(opened, first, exclude_weekends),
        hours_to_merge=hours_between(opened, merged, exclude_weekends),
        hours_to_close=hours_between(opened, closed, exclude_weekends) if status == "closed" else None,
    )


# ── summaries ─────────────────────────────────────────────────────

def percentile(values: Sequence[float], p: float) -> Optional[float]:
    """Linear interpolation between closest ranks (numpy's default method)."""
    data = sorted(v for v in values if v is not None)
    if not data:
        return None
    rank = (p / 100) * (len(data) - 1)
    low, high = math.floor(rank), math.ceil(rank)
    value = data[low] + (data[high] - data[low]) * (rank - low)
    return round(value, 2)


@dataclass(frozen=True)
class Distribution:
    n: int
    median: Optional[float]
    p85: Optional[float]
    p90: Optional[float]
    mean: Optional[float]

    @classmethod
    def of(cls, values: Iterable[Optional[float]]) -> "Distribution":
        data = [v for v in values if v is not None]
        mean = round(sum(data) / len(data), 2) if data else None
        return cls(len(data), percentile(data, 50), percentile(data, 85), percentile(data, 90), mean)

    def to_dict(self) -> Dict[str, Any]:
        return {"n": self.n, "median": self.median, "p85": self.p85, "p90": self.p90, "mean": self.mean}


@dataclass
class PRSummary:
    prs: List[PRMetrics] = field(default_factory=list)

    def _merged(self) -> List[PRMetrics]:
        return [p for p in self.prs if p.status == "merged"]

    @property
    def unreviewed_merge_rate(self) -> Optional[float]:
        """% of merged PRs that no human reviewed."""
        merged = self._merged()
        if not merged:
            return None
        return round(100 * sum(1 for p in merged if not p.reviewed) / len(merged), 2)

    def to_dict(self) -> Dict[str, Any]:
        sized = [p.size for p in self.prs if p.size]
        buckets = {label: 0 for _, label in SIZE_BUCKETS}
        buckets["XL"] = 0
        for s in sized:
            buckets[s.bucket] += 1
        return {
            "prs": len(self.prs),
            "merged": len(self._merged()),
            "open": sum(1 for p in self.prs if p.status == "open"),
            "size_lines": Distribution.of(s.lines_changed for s in sized).to_dict(),
            "size_buckets": buckets,
            "hours_to_first_review": Distribution.of(p.hours_to_first_review for p in self.prs).to_dict(),
            "hours_to_merge": Distribution.of(p.hours_to_merge for p in self.prs).to_dict(),
            "review_rounds_mean": round(sum(p.review_rounds for p in self.prs) / len(self.prs), 2) if self.prs else None,
            "unreviewed_merge_rate": self.unreviewed_merge_rate,
        }


def summarize_prs(prs: Iterable[Mapping[str, Any]], exclude_weekends: bool = False) -> PRSummary:
    return PRSummary([pr_metrics(pr, exclude_weekends) for pr in prs])
