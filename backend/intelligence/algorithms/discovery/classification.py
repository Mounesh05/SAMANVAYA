"""Generic static classification of discovered functions.

Classification answers one question only: what *kind* of function is this, so
that test scaffolding, helpers and nested definitions are never presented as
algorithm candidates beside real application code.

Every decision is derived from syntax and path structure. No repository, file,
function, pull request or framework name is ever matched, and nothing here is
used to decide correctness.
"""

from __future__ import annotations

import re

METHOD = "static-function-classification-v1"

# Path components that mark a directory as test-only scaffolding.
_TEST_DIRECTORIES = frozenset({
    "tests", "test", "__tests__", "spec", "specs", "testing", "fixture",
    "fixtures", "mock", "mocks", "__snapshots__", "conftest",
})

# File suffixes used by JavaScript/TypeScript test runners.
_TEST_FILE_SUFFIXES = (
    ".test.js", ".test.jsx", ".test.ts", ".test.tsx",
    ".spec.js", ".spec.jsx", ".spec.ts", ".spec.tsx",
    ".test.mjs", ".test.cjs", ".spec.mjs", ".spec.cjs",
)

# Identifier prefixes/suffixes conventionally reserved for test cases.
_TEST_NAME_PREFIXES = ("test_", "tests_", "it_", "its_", "describe_", "should_", "spec_")
_TEST_NAME_SUFFIXES = ("_test", "_tests", "_spec", "_specs")
_TEST_NAME_INLINE = re.compile(r"(?:^|_)(?:test|tests|spec)(?:_|$)")

TEST = "test"
TEST_HELPER = "test_helper"
APPLICATION = "application"
HELPER = "helper"
NESTED = "nested"

_LIMITATIONS = (
    "Classification is derived from path structure, identifier shape and observed structure only; "
    "it does not describe what the function does or whether it is correct.",
    "A function outside a test path with a conventional test name is still classified as a test, "
    "and a test-support function without a test name is still classified as application code.",
    "Nested definitions and lambdas are attributed to their enclosing definition rather than judged alone.",
)


def _path_parts(path: str) -> list[str]:
    return [part.lower() for part in str(path).replace("\\", "/").split("/") if part]


def _is_test_path(path: str) -> bool:
    lowered = str(path).replace("\\", "/").lower()
    if lowered.endswith(_TEST_FILE_SUFFIXES):
        return True
    parts = _path_parts(path)
    if any(part in _TEST_DIRECTORIES for part in parts[:-1]):
        return True
    # A file directly named like a test module (test_x.py, x_test.py).
    stem = parts[-1].rsplit(".", 1)[0] if parts else ""
    return bool(stem) and _is_test_name(stem)


def _is_test_name(name: str) -> bool:
    lowered = str(name).lower()
    if lowered.startswith(_TEST_NAME_PREFIXES) or lowered.endswith(_TEST_NAME_SUFFIXES):
        return True
    return bool(_TEST_NAME_INLINE.search(lowered))


def _is_lambda(qualified_name: str, name: str) -> bool:
    return "<lambda>" in name or "<lambda>" in qualified_name or ".<lambda>" in qualified_name


def _enclosing_name(qualified_name: str) -> str | None:
    """The enclosing definition of a nested symbol, or None at module level."""
    name = str(qualified_name)
    for marker in (".<lambda>", "<lambda>"):
        if marker in name:
            enclosing = name.split(marker, 1)[0].strip(".")
            return enclosing or None
    if "." not in name:
        return None
    return name.rsplit(".", 1)[0] or None


def classify(path, qualified_name, name, language="python", patterns=(), complexity=None):
    """Classify one discovered function.

    Returns a dict with ``category``, ``attribution`` (the enclosing definition
    for nested symbols), ``reasons`` (traceable evidence for the decision) and
    ``limitations``.
    """
    qualified_name = str(qualified_name or name or "")
    name = str(name or "")
    reasons: list[str] = []

    if _is_lambda(qualified_name, name):
        parent = _enclosing_name(qualified_name)
        reasons.append("The definition is a lambda or an inner symbol, so it is attributed to its enclosing definition.")
        return {
            "category": NESTED, "attribution": parent, "is_test": False,
            "reasons": reasons, "limitations": list(_LIMITATIONS), "method": METHOD,
        }

    if qualified_name != name and "." in qualified_name:
        parent = _enclosing_name(qualified_name)
        reasons.append("The qualified name is nested inside another definition, so it is attributed to that definition.")
        return {
            "category": NESTED, "attribution": parent, "is_test": False,
            "reasons": reasons, "limitations": list(_LIMITATIONS), "method": METHOD,
        }

    in_test_path = _is_test_path(path)
    named_as_test = _is_test_name(name)
    if in_test_path and named_as_test:
        reasons.append("The function lives on a test path and uses a conventional test identifier.")
        return {"category": TEST, "attribution": None, "is_test": True,
                "reasons": reasons, "limitations": list(_LIMITATIONS), "method": METHOD}
    if in_test_path:
        reasons.append("The function lives on a test path, so it supports tests rather than shipping behaviour.")
        return {"category": TEST_HELPER, "attribution": None, "is_test": True,
                "reasons": reasons, "limitations": list(_LIMITATIONS), "method": METHOD}
    if named_as_test:
        reasons.append("The identifier follows a conventional test naming pattern even though the path is not a test path.")
        return {"category": TEST, "attribution": None, "is_test": True,
                "reasons": reasons, "limitations": list(_LIMITATIONS), "method": METHOD}

    observed = [str(pattern) for pattern in (patterns or ())]
    if observed:
        reasons.append("The body matched " + ", ".join(sorted(set(observed))) +
                       ", so it performs observable computational work.")
        return {"category": APPLICATION, "attribution": None, "is_test": False,
                "reasons": reasons, "limitations": list(_LIMITATIONS), "method": METHOD}

    bound = (complexity or {}).get("time_complexity")
    status = (complexity or {}).get("status")
    if status in {"estimated", "partial"} and bound in {"O(1)", "O( n )"}:
        reasons.append("No structural pattern matched and the derived time bound is constant, "
                       "so the function supplies data or glue rather than an algorithm.")
        return {"category": HELPER, "attribution": None, "is_test": False,
                "reasons": reasons, "limitations": list(_LIMITATIONS), "method": METHOD}

    reasons.append("No structural pattern matched and a constant bound was not established, "
                   "so the function is reported as application code without an algorithmic claim.")
    return {"category": APPLICATION, "attribution": None, "is_test": False,
            "reasons": reasons, "limitations": list(_LIMITATIONS), "method": METHOD}
