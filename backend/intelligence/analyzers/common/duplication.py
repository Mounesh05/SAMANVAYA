"""
Universal Duplication Detector.
Language-agnostic token-based copy-paste block detection using
a rolling-hash (Rabin-Karp style) n-gram comparison.

Works on any text-based language. No external tools required.
Produces DuplicationEvidence consumed by QualityEngine.

Matching Strategy & SIMILARITY_THRESHOLD:
-----------------------------------------
Matching is EXACT at the block level: each N-line window is normalized
(whitespace collapsed, comments and noise lines stripped) and hashed using
SHA-256. Windows match if and only if their SHA-256 hashes are identical
(100% exact match of normalized token lines).

`SIMILARITY_THRESHOLD` (0.85) is defined as a configuration constant reserved
for future approximate/fuzzy token similarity algorithms (e.g. MinHash, Jaccard
distance, or Levenshtein ratio). In the current exact rolling-hash implementation,
all identified duplicates have an exact similarity of 1.0 (>= SIMILARITY_THRESHOLD).
"""

import hashlib
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from intelligence.evidence.models import DuplicationEvidence


# ── Configuration ─────────────────────────────────────────────────────────────
MIN_BLOCK_LINES = 6          # Minimum consecutive lines to consider a duplicate

# SIMILARITY_THRESHOLD: Reserved for future approximate/fuzzy matching.
# Current block matching uses exact SHA-256 rolling hashes over normalized lines,
# which corresponds to an exact similarity of 1.0 (>= SIMILARITY_THRESHOLD).
SIMILARITY_THRESHOLD = 0.85  # Min token similarity ratio for a block match

# Lines to ignore in duplicate detection (noise lines that appear everywhere)
IGNORE_PATTERNS = {
    "", "{", "}", "(", ")", "//", "#", "/*", "*/", "<!--", "-->", '"""', "'''",
    '""";', "''';", '"""\');', "'''\');", '`);',
    "pass", "return", "break", "continue", "else:", "try:", "finally:",
}

DOCSTRING_START_RE = re.compile(r'^[rRuUbBfF]{0,2}("""|\'\'\')')


def analyze_duplication(
    files: List[str],
    repo_path: str,
) -> DuplicationEvidence:
    """
    Detect duplicated code blocks across all provided files.

    Matching is EXACT on normalized lines: sliding windows of MIN_BLOCK_LINES
    are hashed using SHA-256, so matching blocks have identical normalized tokens.
    `SIMILARITY_THRESHOLD` is reserved for future approximate matching.

    To eliminate inflation from overlapping sliding-window fingerprints,
    duplicated line ranges are merged per-file using interval union ([start, end)).
    This guarantees:
      - Each source line in a file is counted as duplicated at most once.
      - Global duplicated line count equals the sum of per-file duplicated lines.
      - Duplication percentage remains strictly between 0.0 and 100.0.

    Algorithm:
      1. Normalize each file into token lines (strip whitespace, comments, noise).
      2. Build a rolling hash fingerprint for every N-line window.
      3. Group matching fingerprints (fingerprints with 2+ independent occurrences).
      4. For each file, union overlapping window intervals into disjoint intervals.
      5. Calculate exact duplicated line counts and percentages.

    Args:
        files: File paths relative to repo_path
        repo_path: Absolute repo root

    Returns:
        DuplicationEvidence with counts, percentage, and file list
    """
    evidence = DuplicationEvidence()

    if not files:
        return evidence

    # Deduplicate and normalize input file paths while preserving order
    unique_files: List[str] = []
    seen_paths = set()
    for f in files:
        if not f or not f.strip():
            continue
        norm_f = os.path.normpath(f.strip()).replace("\\", "/")
        if norm_f not in seen_paths:
            seen_paths.add(norm_f)
            unique_files.append(norm_f)

    # Read and normalize file contents
    file_lines: Dict[str, List[str]] = {}
    total_lines = 0

    for rel_path in unique_files:
        abs_path = Path(repo_path) / rel_path
        try:
            raw = abs_path.read_text(encoding="utf-8", errors="replace")
            normalized = _normalize_lines(raw.splitlines())
            file_lines[rel_path] = normalized
            total_lines += len(normalized)
        except (OSError, UnicodeDecodeError):
            continue

    if total_lines < MIN_BLOCK_LINES * 2:
        return evidence  # Not enough content to find duplicates

    # Build fingerprint table: hash → [(file, start_line)]
    hash_table: Dict[str, List[Tuple[str, int]]] = defaultdict(list)

    for filepath, lines in file_lines.items():
        for i in range(len(lines) - MIN_BLOCK_LINES + 1):
            block = lines[i: i + MIN_BLOCK_LINES]
            if _is_trivial_block(block):
                continue
            fingerprint = _hash_block(block)
            hash_table[fingerprint].append((filepath, i))

    # Find duplicates — fingerprints with 2+ independent occurrences
    file_intervals: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
    duplicate_blocks = 0

    for fingerprint, locations in hash_table.items():
        if not _has_independent_occurrences(locations):
            continue
        duplicate_blocks += 1
        for filepath, start_line in locations:
            file_intervals[filepath].append((start_line, start_line + MIN_BLOCK_LINES))

    # Per-file interval union: merge overlapping sliding-window intervals
    # so each duplicated source line is counted at most once per file
    file_duplicate_counts: Dict[str, int] = {}
    for filepath, intervals in file_intervals.items():
        merged = _union_intervals(intervals)
        count = sum(end - start for start, end in merged)
        if count > 0:
            file_duplicate_counts[filepath] = count

    # Overall duplicated line count is the sum of per-file duplicated lines,
    # ensuring mathematical consistency between global and per-file metrics
    total_duplicated_lines = sum(file_duplicate_counts.values())

    # Build output
    evidence.duplicate_blocks_count = duplicate_blocks
    evidence.duplicated_lines_count = total_duplicated_lines
    raw_pct = (total_duplicated_lines / total_lines * 100.0) if total_lines > 0 else 0.0
    evidence.duplication_percentage = round(min(100.0, max(0.0, raw_pct)), 2)
    evidence.duplicated_files = [
        {"file": fp, "duplicated_lines": count}
        for fp, count in sorted(file_duplicate_counts.items(), key=lambda x: (-x[1], x[0]))
    ]

    return evidence


# ── Internal helpers ──────────────────────────────────────────────────────────

def _has_independent_occurrences(locations: List[Tuple[str, int]]) -> bool:
    """
    Check if a fingerprint appears in at least two independent (non-overlapping)
    occurrences across files.
    """
    if len(locations) < 2:
        return False
    # If locations span 2 or more distinct files, they are independent occurrences
    distinct_files = {loc[0] for loc in locations}
    if len(distinct_files) >= 2:
        return True
    # All locations are in the same file: greedily check for at least 2 non-overlapping windows
    sorted_starts = sorted(loc[1] for loc in locations)
    count = 0
    last_end = -1
    for start in sorted_starts:
        if start >= last_end:
            count += 1
            last_end = start + MIN_BLOCK_LINES
            if count >= 2:
                return True
    return False


def _union_intervals(intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """
    Merge overlapping or adjacent half-open intervals [start, end).

    Args:
        intervals: List of (start_line, end_line) tuples.

    Returns:
        Sorted list of merged disjoint intervals.
    """
    if not intervals:
        return []

    # Sort intervals primarily by start ascending, then by end ascending
    sorted_intervals = sorted(intervals, key=lambda iv: (iv[0], iv[1]))
    merged: List[Tuple[int, int]] = [sorted_intervals[0]]

    for start, end in sorted_intervals[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            # Overlapping or contiguous interval -> extend
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged


def _normalize_lines(lines: List[str]) -> List[str]:
    """
    Strip comments, whitespace, and noise from lines.
    Produces canonical tokens for hash comparison.
    Handles multiline block comments (/* ... */ and <!-- ... -->),
    Python multiline docstrings (\"\"\" ... \"\"\" and ''' ... '''),
    prefixed docstrings (r\"\"\", f\"\"\", u\"\"\", b\"\"\"),
    Python multiline string assignments, JS multiline template strings,
    whole-line comments, and quote-aware trailing inline comments.
    Distinguishes SQL/Lua -- comments from C/JS/Java decrement operators (--var, var--).
    """
    normalized: List[str] = []
    in_block_comment: Optional[str] = None
    in_multiline_string: Optional[str] = None

    for line in lines:
        stripped_line = line.strip()

        # Handle multiline Python docstrings when in docstring state
        if in_block_comment in ('"""', "'''"):
            if in_block_comment in stripped_line:
                in_block_comment = None
            continue

        # Handle lines inside an active multiline string literal
        if in_multiline_string:
            delim = in_multiline_string
            if delim in stripped_line:
                in_multiline_string = None
                cleaned = " ".join(stripped_line.split())
                if cleaned not in IGNORE_PATTERNS and cleaned != delim + ";":
                    normalized.append(cleaned)
            else:
                cleaned = " ".join(stripped_line.split())
                if cleaned and cleaned not in IGNORE_PATTERNS:
                    normalized.append(cleaned)
            continue

        # Handle Python standalone or opening docstrings (including r""" / f""" prefixes)
        if in_block_comment is None:
            m = DOCSTRING_START_RE.match(stripped_line)
            if m:
                delim = m.group(1)
                prefix_len = len(m.group(0))
                remainder = stripped_line[prefix_len:]
                if delim in remainder:
                    continue  # Single-line docstring """...""" or r"""..."""
                else:
                    in_block_comment = delim
                    continue

        out: List[str] = []
        i = 0
        n = len(line)
        in_quote: Optional[str] = None

        while i < n:
            if in_block_comment == "/*":
                if line[i:i + 2] == "*/":
                    in_block_comment = None
                    i += 2
                else:
                    i += 1
                continue

            if in_block_comment == "<!--":
                if line[i:i + 3] == "-->":
                    in_block_comment = None
                    i += 3
                else:
                    i += 1
                continue

            ch = line[i]

            if in_quote:
                out.append(ch)
                if ch == "\\" and i + 1 < n:
                    i += 1
                    out.append(line[i])
                elif ch == in_quote:
                    in_quote = None
                i += 1
                continue

            # Check Python triple quotes in code statements (e.g. query = """...""")
            if line[i:i + 3] in ('"""', "'''"):
                t_delim = line[i:i + 3]
                closing = line.find(t_delim, i + 3)
                if closing != -1:
                    out.append(line[i:closing + 3])
                    i = closing + 3
                else:
                    out.append(line[i:])
                    in_multiline_string = t_delim
                    break
                continue

            # Check JS template literal backtick (e.g. const query = `...`)
            if ch == "`":
                closing = line.find("`", i + 1)
                if closing != -1:
                    out.append(line[i:closing + 1])
                    i = closing + 1
                else:
                    out.append(line[i:])
                    in_multiline_string = "`"
                    break
                continue

            if ch in ('"', "'"):
                in_quote = ch
                out.append(ch)
                i += 1
                continue

            if line[i:i + 2] == "/*":
                in_block_comment = "/*"
                i += 2
                continue

            if line[i:i + 4] == "<!--":
                in_block_comment = "<!--"
                i += 4
                continue

            # Decrement operator check: in C/C++/Java/JS, -- can be x-- or --x or items[--i]
            if line[i:i + 2] == "--":
                is_decrement = False
                if i > 0 and (line[i - 1].isalnum() or line[i - 1] in "_)$]"):
                    is_decrement = True
                elif i + 2 < n and (line[i + 2].isalnum() or line[i + 2] in "_($"):
                    is_decrement = True

                if not is_decrement:
                    break

            if line[i:i + 2] == "//" or ch == "#":
                break

            out.append(ch)
            i += 1

        cleaned = " ".join("".join(out).split())
        if cleaned and cleaned not in IGNORE_PATTERNS:
            normalized.append(cleaned)

    return normalized


def _is_trivial_block(block: List[str]) -> bool:
    """Return True if a block is too trivial to be a meaningful duplicate."""
    meaningful = [line for line in block if len(line) > 8]
    return len(meaningful) < MIN_BLOCK_LINES // 2


def _hash_block(block: List[str]) -> str:
    """Compute a stable SHA-256 fingerprint for a normalized block of lines."""
    content = "\n".join(block).encode("utf-8")
    return hashlib.sha256(content).hexdigest()[:16]
