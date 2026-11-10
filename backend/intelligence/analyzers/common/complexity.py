"""
Universal Complexity Analyzer.
Language-agnostic via Lizard (multi-language) + radon (Python deep dive) + AST fallback.

Produces ComplexityEvidence consumed by the RiskEngine and QualityEngine.
Never raises on missing tools — degrades gracefully.
"""

import asyncio
import json
import ast
from pathlib import Path
from typing import Dict, List, Optional
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
        evidence.is_available = False
        evidence.average_complexity = None
        evidence.max_complexity = None
        return evidence

    abs_files = [str(Path(repo_path) / f) for f in files]
    complexity_tools: List[str] = []

    # ── Attempt 1: Lizard ─────────────────────────────────────────────────────
    if shutil.which("lizard"):
        result = await _run_lizard(abs_files)
        if result:
            tools_executed.append("lizard")
            complexity_tools.append("lizard")
            _merge(evidence, result)
            # Supplement with radon for Python files if available
            py_files = [f for f in abs_files if f.endswith(".py")]
            if py_files and shutil.which("radon"):
                radon_result = await _run_radon(py_files)
                if radon_result:
                    tools_executed.append("radon")
                    complexity_tools.append("radon")
                    _merge_radon_supplement(evidence, radon_result)
                radon_mi = await _run_radon_supplement_async(py_files)
                if radon_mi:
                    _merge_radon_supplement(evidence, radon_mi)
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
            complexity_tools.append("radon")
            _merge(evidence, result)
            radon_mi = await _run_radon_supplement_async(py_files)
            if radon_mi:
                _merge_radon_supplement(evidence, radon_mi)
            return evidence
        tools_skipped.append("radon-failed")
    elif not py_files:
        tools_skipped.append("radon")  # not applicable

    # ── Attempt 3: Python AST fallback ────────────────────────────────────────
    if py_files:
        tools_executed.append("python-ast-fallback")
        complexity_tools.append("python-ast-fallback")
        ast_result = _run_ast_complexity(py_files)
        _merge(evidence, ast_result)
        return evidence

    # No complexity tool executed (e.g. JS/TS files with no Lizard installed)
    if not complexity_tools:
        evidence.is_available = False
        evidence.average_complexity = None
        evidence.max_complexity = None

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
    Pure Python AST-based cyclomatic complexity estimation.

    Metric Definition:
      McCabe Cyclomatic Complexity CC = 1 + B, where:
      - Base complexity = 1 per function definition (representing the initial path).
      - Branch points (B) include:
        1. Conditionals: if, elif, ternary expressions (ast.IfExp)
        2. Loops: for, async for, while
        3. Exception handlers: except (ast.ExceptHandler)
        4. Context managers: with, async with (ast.With, ast.AsyncWith)
        5. Assertions: assert (ast.Assert)
        6. Comprehensions: list, dict, set comprehensions, generator expressions
           (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)
        7. Pattern matching: case blocks (ast.match_case)
        8. Boolean operators: ast.BoolOp (and, or) contribute (N - 1) branch points
           for N operands, reflecting short-circuit evaluation paths.
      - Scoping:
        Nested function definitions (ast.FunctionDef, ast.AsyncFunctionDef) and
        class definitions (ast.ClassDef) are excluded from the outer function's
        branch count to prevent double-counting.
    """
    BRANCH_NODES = (
        ast.If, ast.IfExp, ast.For, ast.While, ast.ExceptHandler,
        ast.With, ast.AsyncWith, ast.AsyncFor,
        ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp,
        ast.Assert,
    )
    if hasattr(ast, "match_case"):
        BRANCH_NODES = BRANCH_NODES + (ast.match_case,)

    def _count_fn_branches(fn_node: ast.AST) -> int:
        branches = 0
        for child in ast.iter_child_nodes(fn_node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            if isinstance(child, BRANCH_NODES):
                branches += 1
            elif isinstance(child, ast.BoolOp):
                branches += max(1, len(child.values) - 1)
            branches += _count_fn_branches(child)
        return branches

    functions = []
    all_functions = []
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
                    cc = 1 + _count_fn_branches(node)
                    total_cc += cc
                    count += 1
                    if cc > max_cc:
                        max_cc = cc

                    fn_data = {
                        "name": node.name,
                        "function": node.name,
                        "file": filepath,
                        "complexity": cc,
                        "severity": "critical" if cc >= CRITICAL_COMPLEXITY_THRESHOLD else "high" if cc >= HIGH_COMPLEXITY_THRESHOLD else "low",
                        "source": "ast-fallback",
                    }
                    all_functions.append(fn_data)

                    if cc >= HIGH_COMPLEXITY_THRESHOLD:
                        functions.append(fn_data)
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue

    return {
        "average_complexity": round(total_cc / count, 2) if count else 0.0,
        "max_complexity": max_cc,
        "functions": all_functions,
        "high_complexity_functions": functions,
        "lines_of_code": total_loc,
    }


# ── Merge helpers ─────────────────────────────────────────────────────────────

def _merge(evidence: ComplexityEvidence, result: Dict) -> None:
    """Merge a result dict into the ComplexityEvidence object."""
    if not isinstance(result, dict) or not result:
        return
    if result.get("average_complexity") is not None:
        evidence.average_complexity = result["average_complexity"]
    if result.get("max_complexity") is not None:
        curr_max = evidence.max_complexity or 0
        if result["max_complexity"] > curr_max:
            evidence.max_complexity = result["max_complexity"]
    if result.get("high_complexity_functions"):
        existing_keys = {
            (f.get("function"), f.get("file"))
            for f in evidence.high_complexity_functions
            if isinstance(f, dict)
        }
        for func in result["high_complexity_functions"]:
            if isinstance(func, dict):
                key = (func.get("function"), func.get("file"))
                if key not in existing_keys:
                    evidence.high_complexity_functions.append(func)
                    existing_keys.add(key)
    if result.get("lines_of_code", 0) > 0:
        evidence.lines_of_code = result["lines_of_code"]
    evidence.is_available = True


def _merge_radon_supplement(evidence: ComplexityEvidence, result: Dict) -> None:
    """
    Safely supplement existing evidence with radon findings.

    Supports both:
    1. Radon Cyclomatic Complexity (CC) schema:
       {"average_complexity": float, "max_complexity": int, "high_complexity_functions": list}
    2. Radon Maintainability Index (MI) schema:
       {"filepath": {"mi": float, "rank": str}} or {"maintainability_index": float}

    Note: Maintainability Index is stored in evidence.maintainability_index
    and is strictly separated from evidence.comment_ratio.
    """
    if not isinstance(result, dict) or not result:
        return

    # ── Schema 1: Cyclomatic Complexity supplement ─────────────────────────
    if result.get("high_complexity_functions"):
        existing = set()
        for f in evidence.high_complexity_functions:
            if isinstance(f, dict):
                fn_name = f.get("function")
                file_name = f.get("file")
                existing.add((fn_name, file_name))
                if file_name is None:
                    existing.add(fn_name)

        for func in result["high_complexity_functions"]:
            if not isinstance(func, dict):
                continue
            fn_name = func.get("function")
            file_name = func.get("file")
            if (fn_name, file_name) in existing or (file_name is None and fn_name in existing) or (fn_name and any(f.get("function") == fn_name for f in evidence.high_complexity_functions if f.get("file") is None)):
                continue
            evidence.high_complexity_functions.append(func)
            existing.add((fn_name, file_name))
            if file_name is None:
                existing.add(fn_name)

    new_max = result.get("max_complexity")
    if isinstance(new_max, (int, float)):
        curr_max = evidence.max_complexity or 0
        if int(new_max) > curr_max:
            evidence.max_complexity = int(new_max)

    # ── Schema 2: Maintainability Index supplement ─────────────────────────
    if "maintainability_index" in result and isinstance(result["maintainability_index"], (int, float)):
        evidence.maintainability_index = round(float(result["maintainability_index"]), 2)
    else:
        # Per-file radon mi output: {filepath: {"mi": float, ...}}
        mi_values = [
            float(v["mi"])
            for v in result.values()
            if isinstance(v, dict) and "mi" in v and isinstance(v["mi"], (int, float))
        ]
        if mi_values:
            evidence.maintainability_index = round(sum(mi_values) / len(mi_values), 2)
