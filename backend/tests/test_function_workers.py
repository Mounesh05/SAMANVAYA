"""Pure data/AST checks on the host; all candidate execution is Docker opt-in only."""

import copy
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from benchmark_worker import contracts, python_worker


WORKER = Path(__file__).resolve().parents[1] / "benchmark_worker" / "node_worker.cjs"
DOCKER = pytest.mark.skipif(
    os.environ.get("SAMANVAYA_DOCKER_BENCHMARK_TESTS") != "1",
    reason="opt-in: requires Docker and rebuilt pinned worker images",
)


def function_payload(language="python", source="", *, expected: object = 3):
    return {
        "language": language,
        "candidates": [{"name": "fixture", "entrypoint": "solve", "source": source}],
        "repetitions": 2,
        "contract": {
            "kind": "function", "name": "fixture.sum", "version": "1",
            "input_schema": {"type": "array"}, "output_schema": {},
            "correctness": "expected",
        },
        "datasets": [{"id": "small", "args": [1, 2], "expected": expected,
                      "dimensions": {"n": 2}}],
    }


def node_data(script, data=None):
    """Run only fixed validator/AST test code, never submitted candidate functions."""
    if not shutil.which("node"):
        pytest.skip("Node is not installed")
    completed = subprocess.run(
        ["node", "-e", "const w = require(process.argv[1]);\n" + script, str(WORKER)],
        input=json.dumps(data, ensure_ascii=True), text=True, capture_output=True,
        timeout=15, check=True,
    )
    return json.loads(completed.stdout)


def node_checks(actions):
    return node_data("""
const fs = require('node:fs');
const actions = JSON.parse(fs.readFileSync(0, 'utf8'));
console.log(JSON.stringify(actions.map(action => {
  try {
    if (action.kind === 'schema') w.validateSchema(action.value, action.schema);
    else if (action.kind === 'payload') w.validateFunctionPayload(action.payload);
    else w.checkFunctionResult(action.output, action.args, action.dataset, action.contract);
    return true;
  } catch (error) { return false; }
})));
""", actions)


@pytest.mark.parametrize("payload,expected", [({}, False), ({"contract": None}, False),
    ({"contract": {}}, True), ({"contract": False}, True)])
def test_worker_generic_selection(payload, expected):
    assert python_worker.is_generic(payload) is expected
    assert node_data("console.log(JSON.stringify(w.isGeneric(JSON.parse(require('node:fs').readFileSync(0, 'utf8')))));", payload) is expected


SCHEMA_CASES = [
    (None, {"type": "null"}, True),
    (True, {"type": "boolean"}, True),
    (True, {"type": "integer"}, False),
    (1, {"type": "boolean"}, False),
    (True, {"enum": [1]}, False),
    ({"a": [True]}, {"enum": [{"a": [1]}]}, False),
    ({"b": 2, "a": [1]}, {"enum": [{"a": [1.0], "b": 2}]}, True),
    (1, {"enum": [True, 1]}, True),
    (1, {"enum": [1, 1.0]}, False),
    ("é🙂", {"type": "string", "minLength": 2, "maxLength": 2}, True),
    ("🙂", {"type": "string", "minLength": 2}, False),
    ("\ud800", {}, False),
    ([1, 2], {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2}, True),
    ([1, False], {"type": "array", "items": {"type": "number"}}, False),
    ([], {"type": "array", "minItems": 1}, False),
    ([1], {"type": "array", "maxItems": 0}, False),
    (1.25, {"type": "number", "minimum": 1, "maximum": 2}, True),
    (0, {"type": "number", "minimum": 1}, False),
    (3, {"type": "integer", "maximum": 2}, False),
    (1.25, {"type": "integer"}, False),
    (2**53 - 1, {"type": "integer"}, True),
    (2**53, {}, False),
    ({"x": None}, {"type": "object", "required": ["x"], "properties": {"x": {"type": "null"}}, "additionalProperties": False}, True),
    ({}, {"type": "object", "required": ["x"]}, False),
    ({"x": 1}, {"type": "object", "additionalProperties": False}, False),
    ({"constructor": 1}, {"type": "object", "additionalProperties": False}, False),
    ({"__proto__": 1}, {"type": "object", "properties": {"__proto__": {"type": "integer"}}, "additionalProperties": False}, True),
    (None, {"$ref": "https://example.invalid"}, False),
    (None, {"type": ["null"]}, False),
    (None, {"enum": []}, False),
    (None, {"type": "array", "items": []}, False),
    (None, {"type": "object", "required": ["x", "x"]}, False),
    (None, {"type": "object", "required": ["x"], "additionalProperties": False}, False),
    (None, {"type": "object", "additionalProperties": 1}, False),
    (None, {"type": "string", "minLength": True}, False),
    (None, {"type": "array", "minItems": 2, "maxItems": 1}, False),
    (None, {"type": "number", "minimum": True}, False),
    (None, {"type": "number", "minimum": 2, "maximum": 1}, False),
    (None, {"items": {}}, False),
]


def test_pure_schema_parity():
    actions = []
    for value, schema, expected in SCHEMA_CASES:
        try:
            contracts.validate_schema(value, schema)
            passed = True
        except ValueError:
            passed = False
        assert passed is expected, (value, schema)
        actions.append({"kind": "schema", "value": value, "schema": schema})
    assert node_checks(actions) == [expected for _, _, expected in SCHEMA_CASES]


def nested(depth):
    value = None
    for _ in range(depth):
        value = [value]
    return value


def test_json_traversal_boundaries_match():
    cases = [(nested(32), True), (nested(33), False), ([None] * 49999, True),
             ([None] * 50000, False), ({"x": [None] * 49997}, True),
             ({"x": [None] * 49998}, False)]
    for value, valid in cases:
        if valid:
            contracts.validate_schema(value, {})
        else:
            with pytest.raises(ValueError):
                contracts.validate_schema(value, {})
    assert node_checks([{"kind": "schema", "value": value, "schema": {}} for value, _ in cases]) == [valid for _, valid in cases]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"),
                                   (1, 2), {1: "bad"}, b"bytes", {1, 2}, object()])
def test_python_non_json_output_rejected(value):
    with pytest.raises(ValueError):
        python_worker.check_function_result(value, [], {"args": []},
                                            {"correctness": "none", "output_schema": {}})


@pytest.mark.parametrize("policy", ["expected", "none"])
@pytest.mark.parametrize("output", [None, False, True, 0, 1.25, "é🙂", [1, None],
                                     {"then": "ordinary JSON property", "x": [True]}])
def test_python_basic_generic_outputs(output, policy):
    contract = {"correctness": policy, "output_schema": {}}
    dataset = {"args": []}
    if policy == "expected":
        dataset["expected"] = copy.deepcopy(output)
    python_worker.check_function_result(output, [], dataset, contract)


def test_python_async_results_rejected_before_output_selection():
    class Awaitable:
        def __await__(self):
            raise AssertionError("result must never be awaited")

    class Thenable:
        def then(self):
            raise AssertionError("then must never be invoked")

    async def coroutine_fixture():
        raise AssertionError("coroutine body must never execute")

    async def async_generator_fixture():
        raise AssertionError("async generator body must never execute")
        yield None

    coroutine = coroutine_fixture()
    generator = (value for value in [1])
    async_generator = async_generator_fixture()
    try:
        for output in [Awaitable(), Thenable(), coroutine, generator, async_generator]:
            for selector in [{"source": "return"}, {"source": "argument"}]:
                with pytest.raises(ValueError, match="unsupported"):
                    python_worker.check_function_result(
                        output, [[1]], {"args": [[1]]},
                        {"correctness": "none", "output_schema": {}, "output": selector},
                    )
    finally:
        coroutine.close()
        generator.close()


def test_non_json_js_values_and_cross_realm_plain_objects():
    assert node_data("""
const vm = require('node:vm');
const sparse = Array(2);
const getter = Object.defineProperty({}, 'x', {enumerable: true, get() { throw new Error('must not run getter'); }});
const extras = [1]; extras.extra = 2;
const hidden = Object.defineProperty({}, 'x', {value: 1});
const cycle = {}; cycle.x = cycle;
const values = [undefined, NaN, Infinity, 2 ** 53, 1n, () => 1, new Date(), new Map(),
  new Set(), new Number(1), sparse, getter, extras, hidden, cycle, {[Symbol('x')]: 1},
  vm.runInNewContext('({a: [1, null, true]})'), Object.assign(Object.create(null), {a: 1})];
console.log(JSON.stringify(values.map(value => {
  try { w.validateSchema(value, {}); return true; } catch (error) { return false; }
})));
""") == [False] * 16 + [True, True]


def test_payload_validation_is_pure_and_matches_python():
    valid = function_payload()
    actions = [{"kind": "payload", "payload": valid}]
    variants = []
    for key, value in [("contract", False), ("contract", {}), ("datasets", []),
                       ("resources", {"cpus": True})]:
        request = copy.deepcopy(valid)
        request[key] = value
        variants.append(request)
    for key, value in [("correctness", "maybe"), ("mutation", "sometimes"),
                       ("output", {"source": "argument", "index": 2}),
                       ("output", {"source": "return", "index": True}),
                       ("input_schema", {"type": "object"}), ("extra", True)]:
        request = copy.deepcopy(valid)
        request["contract"][key] = value
        variants.append(request)
    for key, value in [("id", " "), ("args", {}), ("dimensions", {"n": True}),
                       ("expected", {"x": 2**53}), ("extra", 1)]:
        request = copy.deepcopy(valid)
        request["datasets"][0][key] = value
        variants.append(request)
    duplicate = copy.deepcopy(valid)
    duplicate["datasets"].append(copy.deepcopy(duplicate["datasets"][0]))
    variants.append(duplicate)
    missing = copy.deepcopy(valid)
    del missing["datasets"][0]["expected"]
    variants.append(missing)
    none_with_expected = copy.deepcopy(valid)
    none_with_expected["contract"]["correctness"] = "none"
    variants.append(none_with_expected)
    for request in variants:
        with pytest.raises(ValueError):
            contracts.validate_function_payload(request)
        actions.append({"kind": "payload", "payload": request})
    for request in [valid, {"contract": None}, {}, {
        **copy.deepcopy(valid), "contract": {**valid["contract"], "correctness": "none"},
        "datasets": [{"id": "null", "args": [None]}],
    }]:
        before = copy.deepcopy(request)
        contracts.validate_function_payload(request)
        assert before == request
    assert node_checks(actions) == [True] + [False] * len(variants)


@pytest.mark.parametrize("output,args_,expected,mutation,selector,valid", [
    ({"b": 2, "a": [1]}, [], {"a": [1.0], "b": 2}, "allowed", {"source": "return"}, True),
    (True, [], 1, "allowed", {"source": "return"}, False),
    (None, [], None, "allowed", {"source": "return"}, True),
    (None, [[1, 2]], [1, 2], "allowed", {"source": "argument"}, True),
    (None, [0, {"value": 3}], {"value": 3}, "allowed", {"source": "argument", "index": 1}, True),
    (3, [True], 3, "forbidden", {"source": "return"}, False),
    (3, [1], 3, "forbidden", {"source": "return"}, True),
])
def test_data_only_invocation_checks(output, args_, expected, mutation, selector, valid):
    contract = {"correctness": "expected", "output_schema": {}, "mutation": mutation, "output": selector}
    dataset = {"args": [1] if mutation == "forbidden" else copy.deepcopy(args_), "expected": expected}
    if valid:
        python_worker.check_function_result(output, args_, dataset, contract)
    else:
        with pytest.raises(ValueError):
            python_worker.check_function_result(output, args_, dataset, contract)
    assert node_checks([{"kind": "result", "output": output, "args": args_,
                         "dataset": dataset, "contract": contract}]) == [valid]


def test_none_policy_still_checks_schema_and_selected_argument():
    contract = {"correctness": "none", "output_schema": {"type": "integer"}}
    dataset = {"args": []}
    python_worker.check_function_result(7, [], dataset, contract)
    with pytest.raises(ValueError):
        python_worker.check_function_result(True, [], dataset, contract)
    assert node_checks([{"kind": "result", "output": output, "args": [], "dataset": dataset,
                         "contract": contract} for output in [7, True]]) == [True, False]
    assert node_data("""
const dataset = {args: [[1]], expected: [1]};
const contract = {correctness: 'expected', output_schema: {}, output: {source: 'argument'}};
const outputs = [undefined, {then() {}}, (function* () {})()];
const answers = outputs.map(output => {
  try { w.checkFunctionResult(output, [[1]], dataset, contract); return true; } catch (error) { return false; }
});
try { w.checkFunctionResult(undefined, [], {args: []}, {correctness: 'none', output_schema: {}}); answers.push(true); }
catch (error) { answers.push(false); }
console.log(JSON.stringify(answers));
""") == [True, False, False, False]


def test_typescript_ast_only_original_source_and_diagnostics():
    available = node_data("try { require(require.resolve('typescript', {paths: [require('node:path').dirname(process.argv[1])]})); console.log(true); } catch (error) { console.log(false); }")
    if not available:
        pytest.skip("TypeScript compiler not installed locally; AST fixtures also run in Docker")
    source = """throw new Error('must never execute on host');
function solve(xs: number[]): number[] {
  const out = [];
  for (const x of xs) { while (false) { if (x) out.push(x); } }
  function nested() { for (;;) { break; } }
  if (xs.length) solve([]);
  return out;
}
"""
    parsed = node_data("console.log(JSON.stringify(w.analyzeStructure(JSON.parse(require('node:fs').readFileSync(0, 'utf8')), 'typescript')));",
                       {"source": source, "entrypoint": "solve"})
    assert parsed["status"] == "available" and parsed["parser"] == "typescript"
    solve, inner = parsed["functions"]
    assert (solve["name"], solve["line"], solve["end_line"]) == ("solve", 2, 8)
    assert (solve["loops"], solve["max_loop_nesting"], solve["branches"], solve["direct_recursive_calls"]) == (2, 2, 2, 1)
    assert solve["calls"] == ["out.push", "solve"]
    assert inner["loops"] == 1
    assert solve["allocations"][0] == {"kind": "array_literal", "line": 3}
    bad = node_data("console.log(JSON.stringify(w.analyzeStructure(JSON.parse(require('node:fs').readFileSync(0, 'utf8')), 'javascript')));",
                    {"source": "function solve( {", "entrypoint": "solve"})
    assert bad["status"] == "unavailable" and bad["diagnostics"] and not bad["functions"]


def docker_report(request):
    """Exercise the worker protocol directly, independent of parent result normalization."""
    from intelligence.algorithms.runner import IMAGES

    name = "function-worker-test-" + uuid.uuid4().hex
    command = ["docker", "run", "--rm", "--pull=never", "--name", name,
               "--network=none", "--cap-drop=ALL", "--security-opt=no-new-privileges:true",
               "--user=65532:65532", "--read-only",
               "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=64m,mode=1777",
               "--memory=512m", "--memory-swap=512m", "--cpus=1", "--pids-limit=64",
               "--init", "--log-driver=none", "-i", IMAGES[request["language"]]]
    try:
        completed = subprocess.run(command, input=json.dumps(request), text=True,
                                   capture_output=True, timeout=40, check=True)
        return json.loads(completed.stdout)["result"]
    finally:
        subprocess.run(["docker", "rm", "--force", name], capture_output=True, timeout=10, check=False)


@DOCKER
@pytest.mark.parametrize("language", ["javascript", "typescript"])
def test_structure_only_operation_does_not_execute_source_inside_docker(language):
    signature = "function solve(a, b)" if language == "javascript" else "function solve(a: number, b: number): number"
    source = "throw new Error('structure-only source must never execute');\n" + signature + " { return a + b; }"
    request = {
        "operation": "structure", "language": language,
        "candidates": [{"name": "structure-only", "entrypoint": "solve", "source": source}],
    }
    report = docker_report(request)
    assert report["candidate"] == "structure-only"
    assert report["error"] is None
    assert report["cases"] == []
    assert report["structure"]["status"] == "available"
    assert report["structure"]["parser"] == "typescript"
    assert report["structure"]["entrypoint"] == "solve"
    assert any(function["name"] == "solve" for function in report["structure"]["functions"])


@DOCKER
@pytest.mark.parametrize("language", ["python", "javascript", "typescript"])
@pytest.mark.parametrize("algorithm", ["sum", "search", "path"])
def test_generic_algorithms_inside_docker(language, algorithm):
    sources = {
        "sum": ("def solve(a, b): return a + b", "function solve(a, b) { return a + b; }"),
        "search": ("def solve(values, target):\n return values.index(target) if target in values else -1",
                   "function solve(values, target) { return values.indexOf(target); }"),
        "path": ("def solve(obj, keys):\n for key in keys: obj = obj[key]\n return obj",
                 "function solve(obj, keys) { for (const key of keys) obj = obj[key]; return obj; }"),
    }
    source = sources[algorithm][language != "python"]
    if language == "typescript" and algorithm == "sum":
        source = "function solve(a: number, b: number): number { return a + b; }"
    request = function_payload(language, source)
    request["contract"]["mutation"] = "forbidden"
    if algorithm == "search":
        request["datasets"] = [{"id": "found", "args": [[4, 7, 2], 7], "expected": 1},
                               {"id": "missing", "args": [[], 0], "expected": -1}]
    elif algorithm == "path":
        request["datasets"] = [{"id": "object", "args": [{"root": {"b": 2, "a": [1, None]}}, ["root"]],
                                "expected": {"a": [1, None], "b": 2}, "dimensions": {"depth": 1}}]
    report = docker_report(request)
    assert report["error"] is None
    for case, dataset in zip(report["cases"], request["datasets"]):
        assert case["case_id"] == dataset["id"] and case["dimensions"] == dataset.get("dimensions", {})
        assert case["correct"] is True and case["validation_status"] == "verified"
        assert len(case["timings_seconds"]) == 2 and all(n >= 0 for n in case["timings_seconds"])
        assert isinstance(case["memory_bytes"], int) and case["memory_metric"] and case["error"] is None
    if language != "python":
        assert report["structure"]["status"] == "available"
        assert any(fn["name"] == "solve" for fn in report["structure"]["functions"])


@DOCKER
@pytest.mark.parametrize("language", ["python", "javascript", "typescript"])
@pytest.mark.parametrize("policy", ["expected", "none"])
def test_deep_copies_output_argument_and_unverified_measurements(language, policy):
    source = ("def solve(obj):\n obj['nested']['values'].append(2)" if language == "python" else
              "function solve(obj) { obj.nested.values.push(2); }")
    request = function_payload(language, source)
    request["contract"].update(correctness=policy, output={"source": "argument"}, output_schema={"type": "object"})
    request["datasets"] = [{"id": "nested", "args": [{"nested": {"values": [1]}}]}]
    if policy == "expected":
        request["datasets"][0]["expected"] = {"nested": {"values": [1, 2]}}
    case = docker_report(request)["cases"][0]
    assert case["correct"] is (True if policy == "expected" else None)
    assert case["validation_status"] == ("verified" if policy == "expected" else "unverified")
    assert len(case["timings_seconds"]) == 2 and case["memory_bytes"] is not None and case["error"] is None


@DOCKER
@pytest.mark.parametrize("language", ["python", "javascript", "typescript"])
@pytest.mark.parametrize("failure", ["bool", "mutation", "schema", "sample", "memory", "async", "generator", "returned_async", "returned_generator", "non_json", "syntax", "load"])
def test_generic_failures_inside_docker(language, failure):
    py = {
        "bool": "def solve(a, b): return True",
        "mutation": "def solve(obj):\n obj['x'] = True\n return 3",
        "schema": "def solve(a, b): return 'bad'",
        "sample": "calls = 0\ndef solve(a, b):\n global calls\n calls += 1\n return 3 if calls <= 2 else False",
        "memory": "calls = 0\ndef solve(a, b):\n global calls\n calls += 1\n return 3 if calls <= 4 else False",
        "async": "async def solve(a, b): return 3",
        "generator": "def solve(a, b): yield 3",
        "returned_async": "async def later(): return 3\ndef solve(a, b): return later()",
        "returned_generator": "def solve(a, b): return (x for x in [3])",
        "non_json": "def solve(a, b): return float('nan')",
        "syntax": "def solve(:",
        "load": "raise RuntimeError('load failed')\ndef solve(a, b): return 3",
    }
    js = {
        "bool": "function solve(a, b) { return true; }",
        "mutation": "function solve(obj) { obj.x = true; return 3; }",
        "schema": "function solve(a, b) { return 'bad'; }",
        "sample": "let calls=0; function solve(a,b) { return ++calls <= 2 ? 3 : false; }",
        "memory": "let calls=0; function solve(a,b) { return ++calls <= 4 ? 3 : false; }",
        "async": "async function solve(a,b) { return 3; }",
        "generator": "function* solve(a,b) { yield 3; }",
        "returned_async": "function solve(a,b) { return Promise.resolve(3); }",
        "returned_generator": "function solve(a,b) { return (function* () { yield 3; })(); }",
        "non_json": "function solve(a,b) { return undefined; }",
        "syntax": "function solve( {",
        "load": "throw new Error('load failed'); function solve(a,b) { return 3; }",
    }
    request = function_payload(language, (py if language == "python" else js)[failure], expected=1 if failure == "bool" else 3)
    if failure == "mutation":
        request["contract"]["mutation"] = "forbidden"
        request["datasets"][0]["args"] = [{"x": 1}]
    if failure == "schema":
        request["contract"]["correctness"] = "none"
        request["contract"]["output_schema"] = {"type": "integer"}
        del request["datasets"][0]["expected"]
    report = docker_report(request)
    if failure in ("async", "generator", "syntax", "load"):
        assert report["error"] and report["cases"] == []
        if language != "python":
            if failure == "syntax":
                assert report["structure"]["status"] == "unavailable" and report["structure"]["diagnostics"]
            else:
                assert report["structure"]["status"] == "available" and report["structure"]["functions"]
    else:
        case = report["cases"][0]
        assert case["correct"] is False and case["validation_status"] == "failed" and case["error"]
        assert len(case["timings_seconds"]) == (2 if failure == "memory" else 0)


@DOCKER
@pytest.mark.parametrize("language", ["python", "javascript", "typescript"])
def test_null_output_and_explicit_null_contract_legacy(language):
    source = "def solve(): return None" if language == "python" else "function solve() { return null; }"
    request = function_payload(language, source, expected=None)
    request["contract"]["output_schema"] = {"type": "null"}
    request["datasets"][0]["args"] = []
    assert docker_report(request)["cases"][0]["correct"] is True
    request["contract"] = None
    request.update(sizes=[3], distributions=["random"], seed=42)
    request["candidates"][0]["source"] = ("def solve(values): return sorted(values)" if language == "python" else
                                            "function solve(values) { values.sort((a,b)=>a-b); }")
    case = docker_report(request)["cases"][0]
    assert case["correct"] is True and case["size"] == 3 and "case_id" not in case
