"""v4 investigation item 4 / AL-16: Mode C pairs only genuine alternatives.

Mode C used to pair any two changed functions that one assertion line merely
mentioned. Composition (``slugify(normalize(s))``), round trips
(``decode(encode(x))``) and unrelated checks joined with ``and`` were all
offered as "interchangeable alternatives". A pair is now formed only when the
assertion compares the two calls with each other as equals.
"""

import pytest

from domain.services.pr_algorithm_intelligence_service import apply_same_revision_alternatives, changed_functions
from intelligence.algorithms.discovery.service import discover_sources

pytestmark = pytest.mark.anyio

PY_LIB = (
    "def normalize(s):\n    return s.strip().lower()\n\n\n"
    "def slugify(s):\n    return s.replace(' ', '-')\n\n\n"
    "def encode(xs):\n    return ','.join(str(x) for x in xs)\n\n\n"
    "def decode(text):\n    return [int(x) for x in text.split(',')]\n\n\n"
    "def add(a, b):\n    return a + b\n\n\n"
    "def mul(a, b):\n    return a * b\n\n\n"
    "def linear_contains(xs, t):\n    return t in xs\n\n\n"
    "def binary_contains(xs, t):\n    return t in set(xs)\n"
)
PY_TESTS = (
    "from src.lib import normalize, slugify, encode, decode, add, mul, linear_contains, binary_contains\n\n\n"
    "def test_composition():\n    assert slugify(normalize(' A B ')) == 'a-b'\n\n\n"
    "def test_round_trip():\n    assert decode(encode([1, 2])) == [1, 2]\n\n\n"
    "def test_unrelated_in_one_line():\n    assert add(1, 2) == 3 and mul(2, 3) == 6\n\n\n"
    "def test_alternatives_agree():\n    assert linear_contains([1, 3], 3) == binary_contains([1, 3], 3)\n"
)
JS_LIB = (
    "export function norm(s) { return s.trim(); }\n"
    "export function slug(s) { return s.replace(' ', '-'); }\n"
    "export function linear(xs, t) { return xs.includes(t); }\n"
    "export function binary(xs, t) { return new Set(xs).has(t); }\n"
)
JS_TESTS = (
    "import { norm, slug, linear, binary } from '../src/lib';\n"
    "function check() {\n"
    "  expect(slug(norm(' a '))).toBe('a');\n"
    "  expect(linear([1, 3], 3)).toEqual(binary([1, 3], 3));\n"
    "}\n"
)


async def mode_c_pairs(sources):
    base = (await discover_sources({"src/other.py": "def other():\n    return 1\n"}, "P", "b" * 40)).model_dump(mode="json")
    head = (await discover_sources(sources, "P", "a" * 40)).model_dump(mode="json")
    files = [{"filename": path, "status": "added"} for path in sources]
    rows = apply_same_revision_alternatives(changed_functions(base, head, files, {"src/other.py": ""}, sources))
    return {frozenset({row["current"]["name"], row["previous"]["name"]}) for row in rows if row["mode"] == "C"}


async def test_python_only_directly_compared_calls_become_mode_c():
    pairs = await mode_c_pairs({"src/lib.py": PY_LIB, "tests/test_lib.py": PY_TESTS})
    assert pairs == {frozenset({"linear_contains", "binary_contains"})}


async def test_javascript_only_directly_compared_calls_become_mode_c():
    pairs = await mode_c_pairs({"src/lib.js": JS_LIB, "tests/lib.test.js": JS_TESTS})
    assert pairs == {frozenset({"linear", "binary"})}
