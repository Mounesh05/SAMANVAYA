"""
Universal Complexity Analyzer.
Language-agnostic via Lizard (multi-language) + radon (Python deep dive) + AST fallback.

Produces ComplexityEvidence consumed by the RiskEngine and QualityEngine.
Never raises on missing tools — degrades gracefully.
"""

import asyncio
import json
import subprocess
import ast
from pathlib import Path
from typing import Any, Dict, List, Optional
import shutil

from intelligence.evidence.models import ComplexityEvidence


# Cyclomatic complexity threshold above which a function is "high complexity"
HIGH_COMPLEXITY_THRESHOLD = 10
# Absolute max considered critical
CRITICAL_COMPLEXITY_THRESHOLD = 20


async def _run(cmd: List[str], cwd: Optional[str] = None) -> Optional[str]:
    """Run a subprocess and return stdout, or None on failure."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        return stdout.decode("utf-8", errors="replace")
    except (asyncio.TimeoutError, FileNotFoundError, OSError):
        return None


async def analyze_complexity(
    files: List[str],
    repo_path: str,
    tools_executed: List[str],
    tools_skipped: List[str],
) -> ComplexityEvidence:
    """
    Calculate cyclomatic complexity metrics for a list of files.

    Priority:
      1. Lizard (multi-language — handles Python, JS, Java, C, C++)
      2. Radon   (Python-specific deeper analysis)
      3. Pure Python AST walk (final fallback)

    Args:
        files: File paths relative to repo_path
        repo_path: Absolute repo root
        tools_executed: Mutated — append tools that ran
        tools_skipped:  Mutated — append tools that were unavailable

    Returns:
        ComplexityEvidence with normalized metrics
    """
    evidence = ComplexityEvidence()

    if not files:
        return evidence

    abs_files = [str(Path(repo_path) / f) for f in files]

    # ── Attempt 1: Lizard ─────────────────────────────────────────────────────
    if shutil.which("lizard"):
        result = await _run_lizard(abs_files)
        if result:
            tools_executed.append("lizard")
            _merge(evidence, result)
            # Supplement with radon for Python files if available
            py_files = [f for f in abs_files if f.endswith(".py")]
            if py_files and shutil.which("radon"):
                radon_result = await _run_radon(py_files)
                if radon_result:
                    tools_executed.append("radon")
                    _merge_radon_supplement(evidence, radon_result)
            return evidence
        tools_skipped.append("lizard-failed")
    else:
        tools_skipped.append("lizard")

    # ── Attempt 2: Radon (Python only) ────────────────────────────────────────
    py_files = [f for f in abs_files if f.endswith(".py")]
    if py_files and shutil.which("radon"):
        result = await _run_radon(py_files)
        if result:
            tools_executed.append("radon")
            _merge(evidence, result)
            return evidence
        tools_skipped.append("radon-failed")
    elif not py_files:
        tools_skipped.append("radon")  # not applicable

    # ── Attempt 3: Python AST fallback ────────────────────────────────────────
    if py_files:
        tools_executed.append("python-ast-fallback")
        ast_result = _run_ast_complexity(py_files)
        _merge(evidence, ast_result)

    return evidence


# ── Lizard integration ────────────────────────────────────────────────────────

async def _run_lizard(files: List[str]) -> Optional[Dict]:
    """Run lizard with JSON output and parse results."""
    cmd = ["lizard", "--csv", "-l", "python", "-l", "javascript",
           "-l", "java", "-l", "cpp", "-l", "c"] + files
    output = await _run(cmd)
    if not output:
        return None

    # lizard --csv format: filename,nloc,ccn,token_count,param,length,location,func
    functions = []
    total_complexity = 0
    max_complexity = 0
    total_loc = 0

    for line in output.strip().splitlines():
        parts = line.strip().split(",")
        if len(parts) < 8:
            continue
        try:
            ccn = int(parts[2])
            loc = int(parts[1])
            func_name = parts[6]
            filename = parts[0]
            total_complexity += ccn
            total_loc += loc
            if ccn > max_complexity:
                max_complexity = ccn
            if ccn >= HIGH_COMPLEXITY_THRESHOLD:
                functions.append({
                    "function": func_name,
                    "file": filename,
                    "complexity": ccn,
                    "severity": "critical" if ccn >= CRITICAL_COMPLEXITY_THRESHOLD else "high",
                })
        except (ValueError, IndexError):
            continue

    count = len([l for l in output.strip().splitlines() if l.strip()])
    return {
        "average_complexity": round(total_complexity / count, 2) if count else 0.0,
        "max_complexity": max_complexity,
        "high_complexity_functions": functions,
        "lines_of_code": total_loc,
    }


# ── Radon integration ─────────────────────────────────────────────────────────

async def _run_radon(files: List[str]) -> Optional[Dict]:
    """Run radon cc (cyclomatic complexity) with JSON output."""
    cmd = ["radon", "cc", "--json", "--min", "A"] + files
    output = await _run(cmd)
    if not output:
        return None

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return None

    functions = []
    total_cc = 0
    max_cc = 0
    count = 0

    for filepath, items in data.items():
        for item in items:
            cc = item.get("complexity", 0)
            total_cc += cc
            count += 1
            if cc > max_cc:
                max_cc = cc
            if cc >= HIGH_COMPLEXITY_THRESHOLD:
                functions.append({
                    "function": item.get("name", "unknown"),
                    "file": filepath,
                    "complexity": cc,
                    "rank": item.get("rank", ""),
                    "severity": "critical" if cc >= CRITICAL_COMPLEXITY_THRESHOLD else "high",
                })

    return {
        "average_complexity": round(total_cc / count, 2) if count else 0.0,
        "max_complexity": max_cc,
        "high_complexity_functions": functions,
        "lines_of_code": 0,  # supplemented by other tools
    }


def _run_radon_supplement(radon_result: Dict) -> None:
    """Used when radon supplements lizard — extract MI and comment ratio."""
    pass  # Extended in a future iteration with `radon mi` for maintainability index


async def _run_radon_supplement_async(files: List[str]) -> Optional[Dict]:
    """Run radon mi for maintainability index (supplement)."""
    cmd = ["radon", "mi", "--json"] + files
    output = await _run(cmd)
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None


# ── Pure Python AST fallback ──────────────────────────────────────────────────

def _run_ast_complexity(files: List[str]) -> Dict:
    """
    Pure Python AST-based complexity estimation.
    Counts branching nodes (if, for, while, except, with, assert, comprehension)
    as a proxy for cyclomatic complexity.
    """
    BRANCH_NODES = (
        ast.If, ast.For, ast.While, ast.ExceptHandler,
        ast.With, ast.AsyncWith, ast.AsyncFor,
        ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp,
    )

    functions = []
    total_cc = 0
    max_cc = 0
    count = 0
    total_loc = 0

    for filepath in files:
        try:
            source = Path(filepath).read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
            total_loc += source.count("\n")

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    cc = 1 + sum(
                        1 for child in ast.walk(node)
                        if isinstance(child, BRANCH_NODES)
                    )
                    total_cc += cc
                    count += 1
                    if cc > max_cc:
                        max_cc = cc
                    if cc >= HIGH_COMPLEXITY_THRESHOLD:
                        functions.append({
                            "function": node.name,
                            "file": filepath,
                            "complexity": cc,
                            "severity": "critical" if cc >= CRITICAL_COMPLEXITY_THRESHOLD else "high",
                            "source": "ast-fallback",
                        })
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue

    return {
        "average_complexity": round(total_cc / count, 2) if count else 0.0,
        "max_complexity": max_cc,
        "high_complexity_functions": functions,
        "lines_of_code": total_loc,
    }


# ── Merge helpers ─────────────────────────────────────────────────────────────

def _merge(evidence: ComplexityEvidence, result: Dict) -> None:
    """Merge a result dict into the ComplexityEvidence object."""
    if result.get("average_complexity"):
        evidence.average_complexity = result["average_complexity"]
    if result.get("max_complexity", 0) > evidence.max_complexity:
        evidence.max_complexity = result["max_complexity"]
    if result.get("high_complexity_functions"):
        evidence.high_complexity_functions.extend(result["high_complexity_functions"])
    if result.get("lines_of_code", 0) > 0:
        evidence.lines_of_code = result["lines_of_code"]


def _merge_radon_supplement(evidence: ComplexityEvidence, result: Dict) -> None:
    """Supplement existing evidence with radon's MI data (comment ratio, etc.)."""
    ratios = [v.get("mi", 0) for v in result.values() if isinstance(v, dict)]
    if ratios:
        # MI 0-100: convert to approximate comment ratio
        evidence.comment_ratio = round(sum(ratios) / len(ratios) / 100, 2)
