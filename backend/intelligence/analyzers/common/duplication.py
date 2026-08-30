"""
Universal Duplication Detector.
Language-agnostic token-based copy-paste block detection using
a rolling-hash (Rabin-Karp style) n-gram comparison.

Works on any text-based language. No external tools required.
Produces DuplicationEvidence consumed by QualityEngine.
"""

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from intelligence.evidence.models import DuplicationEvidence


# ── Configuration ─────────────────────────────────────────────────────────────
MIN_BLOCK_LINES = 6          # Minimum consecutive lines to consider a duplicate
SIMILARITY_THRESHOLD = 0.85  # Min token similarity ratio for a block match

# Lines to ignore in duplicate detection (noise lines that appear everywhere)
IGNORE_PATTERNS = {
    "", "{", "}", "(", ")", "//", "#", "/*", "*/", "<!--", "-->",
    "pass", "return", "break", "continue", "else:", "try:", "finally:",
}


def analyze_duplication(
    files: List[str],
    repo_path: str,
) -> DuplicationEvidence:
    """
    Detect duplicated code blocks across all provided files.

    Algorithm:
      1. Normalize each file into token lines (strip whitespace, comments)
      2. Build a rolling hash fingerprint for every N-line window
      3. Group matching fingerprints — each group is a duplicate cluster
      4. Deduplicate clusters and calculate total duplicated line count

    Args:
        files: File paths relative to repo_path
        repo_path: Absolute repo root

    Returns:
        DuplicationEvidence with counts, percentage, and file list
    """
    evidence = DuplicationEvidence()

    if not files:
        return evidence

    # Read and normalize file contents
    file_lines: Dict[str, List[str]] = {}
    total_lines = 0

    for rel_path in files:
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

    # Find duplicates — fingerprints with 2+ occurrences
    duplicate_blocks = 0
    duplicated_lines = 0
    affected_files: Dict[str, int] = {}  # file → duplicate line count

    for fingerprint, locations in hash_table.items():
        if len(locations) < 2:
            continue
        duplicate_blocks += 1
        duplicated_lines += MIN_BLOCK_LINES
        for filepath, start_line in locations:
            affected_files[filepath] = affected_files.get(filepath, 0) + MIN_BLOCK_LINES

    # Build output
    evidence.duplicate_blocks_count = duplicate_blocks
    evidence.duplicated_lines_count = duplicated_lines
    evidence.duplication_percentage = (
        round(duplicated_lines / total_lines * 100, 2) if total_lines > 0 else 0.0
    )
    evidence.duplicated_files = [
        {"file": fp, "duplicated_lines": cnt}
        for fp, cnt in sorted(affected_files.items(), key=lambda x: -x[1])
    ]

    return evidence


# ── Internal helpers ──────────────────────────────────────────────────────────

def _normalize_lines(lines: List[str]) -> List[str]:
    """
    Strip comments, whitespace, and noise from lines.
    Produces canonical tokens for hash comparison.
    """
    normalized = []
    for line in lines:
        # Strip inline comments
        stripped = line.strip()
        for prefix in ("//", "#", "/*", "*/", "--"):
            if stripped.startswith(prefix):
                stripped = ""
                break
        # Collapse whitespace
        stripped = " ".join(stripped.split())
        if stripped and stripped not in IGNORE_PATTERNS:
            normalized.append(stripped)
    return normalized


def _is_trivial_block(block: List[str]) -> bool:
    """Return True if a block is too trivial to be a meaningful duplicate."""
    meaningful = [line for line in block if len(line) > 8]
    return len(meaningful) < MIN_BLOCK_LINES // 2


def _hash_block(block: List[str]) -> str:
    """Compute a stable SHA-256 fingerprint for a normalized block of lines."""
    content = "\n".join(block).encode("utf-8")
    return hashlib.sha256(content).hexdigest()[:16]
