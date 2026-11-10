"""Data-only contract tests: no Docker, candidate imports, or candidate execution."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest
from benchmark_worker import contracts
from benchmark_worker.contracts import (
    is_generic,
    validate_function_payload,
    validate_schema,
)
from pydantic import ValidationError

from domain.schemas.algorithm_benchmark import (
    BenchmarkRequest,
    FunctionCandidate,
    SortCandidate,
)


def _case_id(value):
    """Keep payload representations out of Windows' PYTEST_CURRENT_TEST value."""
    if type(value) is str and len(value) <= 24 and value.isascii() and value.isprintable() and value.strip():
        return value
    return type(value).__name__


@pytest.fixture
def payload():
    return {
        "contract": {
            "kind": "function", "name": "example.sum", "version": "1",
            "input_schema": {"type": "array", "items": {"type": "integer"}, "minItems": 1},
            "output_schema": {"type": "integer"}, "correctness": "expected",
        },
        "datasets": [{"id": "small", "args": [1, 2], "expected": 3, "dimensions": {"n": 2}}],
    }


def api_payload(payload):
    return {
        **payload, "project_id": "P1", "language": "python",
        "candidates": [{"name": "baseline", "entrypoint": "sum_values",
                        "source": "raise RuntimeError('must never execute')"}],
    }


def test_host_and_standalone_worker_import(payload):
    spec = importlib.util.spec_from_file_location("contracts", Path(contracts.__file__))
    assert spec is not None and spec.loader is not None
    standalone = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(standalone)
    standalone.validate_function_payload(payload)
    standalone.validate_schema([1], {"type": "array", "items": {"type": "integer"}})


def test_valid_contract_is_pure_and_defaults_are_not_inserted(payload):
    before = copy.deepcopy(payload)
    assert validate_function_payload(payload) is None
    assert payload == before
    assert "output" not in payload["contract"] and "resources" not in payload
    assert is_generic(payload)


@pytest.mark.parametrize("payload,expected", [({}, False), ({"contract": None}, False),
    ({"contract": {}}, True), ({"contract": False}, True), (None, False), ([], False)], ids=_case_id)
def test_generic_detection(payload, expected):
    assert is_generic(payload) is expected


@pytest.mark.parametrize("payload", [{}, {"contract": None}, {"contract": None, "sizes": [1]}], ids=_case_id)
def test_legacy_payload_is_not_function_validated(payload):
    validate_function_payload(payload)


@pytest.mark.parametrize("value,schema", [
    (None, {"type": "null"}), (True, {"type": "boolean"}),
    (1.25, {"type": "number", "minimum": 1, "maximum": 2}),
    (1.0, {"type": "integer"}), (-(2**53 - 1), {"type": "integer"}),
    ("é🙂", {"type": "string", "minLength": 2, "maxLength": 2}),
    ([1, 2], {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2}),
    ({"x": 1}, {"type": "object", "properties": {"x": {"type": "integer"}},
                "required": ["x"], "additionalProperties": False}),
    ({"other": None}, {"type": "object"}),
    (None, {}), ({"x": [1]}, {"enum": [{"x": [1.0]}]}),
    (True, {"enum": [True, 1]}), (None, {"enum": [None]}),
], ids=_case_id)
def test_schema_valid_values(value, schema):
    validate_schema(value, schema)


@pytest.mark.parametrize("value,schema", [
    (False, {"type": "integer"}), (True, {"type": "number"}), (0, {"type": "boolean"}),
    (1.5, {"type": "integer"}), (None, {"type": "string"}),
    (True, {"enum": [1]}), (1, {"enum": [True]}), ([True], {"enum": [[1]]}),
    ({"x": True}, {"enum": [{"x": 1}]}), (0, {"type": "number", "minimum": 1}),
    (3, {"type": "number", "maximum": 2}),
    ("a", {"type": "string", "minLength": 2}), ("abc", {"type": "string", "maxLength": 2}),
    ([], {"type": "array", "minItems": 1}), ([1], {"type": "array", "maxItems": 0}),
    (["a"], {"type": "array", "items": {"type": "number"}}),
    ({}, {"type": "object", "required": ["x"]}),
    ({"x": 1}, {"type": "object", "additionalProperties": False}),
    ({"x": "a"}, {"type": "object", "properties": {"x": {"type": "integer"}}}),
], ids=_case_id)
def test_schema_mismatches(value, schema):
    with pytest.raises(ValueError):
        validate_schema(value, schema)


@pytest.mark.parametrize("schema", [
    None, True, [], {"type": "date"}, {"type": ["null", "string"]}, {"type": {}},
    {"$ref": "file:///etc/passwd"}, {"$schema": "https://example.com/schema"},
    {"oneOf": []}, {"pattern": ".*"}, {"format": "email"}, {"default": 0},
    {"enum": []}, {"enum": "x"}, {"enum": [1, 1.0]}, {"enum": [{"x": 1}, {"x": 1.0}]},
    {"type": "integer", "enum": [True]},
    {"items": {}}, {"type": "string", "items": {}}, {"type": "array", "items": []},
    {"type": "array", "items": {"$ref": "evil"}},
    {"type": "object", "properties": []}, {"type": "object", "properties": {"x": False}},
    {"type": "object", "required": [1]}, {"type": "object", "required": ["x", "x"]},
    {"type": "object", "required": "x"}, {"type": "object", "additionalProperties": {}},
    {"type": "object", "additionalProperties": False, "required": ["x"]},
    {"type": "string", "minLength": -1}, {"type": "string", "minLength": True},
    {"type": "string", "maxLength": 1.0}, {"type": "number", "minimum": True},
    {"type": "string", "minimum": 0}, {"type": "integer", "minimum": 3, "maximum": 2},
    {"type": "array", "minItems": 2, "maxItems": 1},
    {"type": "string", "minLength": 2, "maxLength": 1},
], ids=_case_id)
def test_invalid_schemas_even_with_no_matching_data(schema):
    with pytest.raises(ValueError):
        validate_schema(None, schema)


@pytest.mark.parametrize("value", [
    float("nan"), float("inf"), -float("inf"), 2**53, -(2**53), float(2**53),
    {1: "bad"}, {"nested": (1, 2)}, {"nested": {1, 2}}, b"bytes", object(), "\ud800",
], ids=_case_id)
def test_nonportable_json_rejected_everywhere(payload, value):
    with pytest.raises(ValueError):
        validate_schema(value, {})
    with pytest.raises(ValueError):
        validate_schema(None, {"enum": [value]})
    payload["datasets"][0]["args"] = [value]
    with pytest.raises(ValueError):
        validate_function_payload(payload)


def nested(depth):
    value = None
    for _ in range(depth):
        value = [value]
    return value


def test_depth_and_node_boundaries():
    validate_schema(nested(32), {})
    with pytest.raises(ValueError, match="depth"):
        validate_schema(nested(33), {})
    validate_schema([None] * 49_999, {})
    with pytest.raises(ValueError, match="nodes"):
        validate_schema([None] * 50_000, {})
    cyclic = []
    cyclic.append(cyclic)
    with pytest.raises(ValueError, match="depth"):
        validate_schema(cyclic, {})


def test_excessively_nested_schema():
    schema = {}
    for _ in range(33):
        schema = {"type": "array", "items": schema}
    with pytest.raises(ValueError, match="depth"):
        validate_schema([], schema)


@pytest.mark.parametrize("field", ["kind", "name", "version", "input_schema", "output_schema", "correctness"])
def test_required_contract_fields(payload, field):
    del payload["contract"][field]
    with pytest.raises(ValueError):
        validate_function_payload(payload)


@pytest.mark.parametrize("field,value", [
    ("kind", "sorting"), ("name", " "), ("name", "x" * 129), ("name", 1),
    ("version", "\n"), ("version", "x" * 65), ("version", None),
    ("correctness", "validator"), ("correctness", None), ("mutation", "sometimes"),
    ("mutation", True), ("input_schema", {}), ("input_schema", {"type": "object"}),
    ("output_schema", {"format": "python"}), ("validator", "exec"),
    ("output", {}), ("output", None), ("output", {"source": "stdout"}),
    ("output", {"source": "return", "extra": True}),
    ("output", {"source": "argument", "index": True}),
    ("output", {"source": "argument", "index": -1}),
    ("output", {"source": "argument", "index": 0.0}),
    ("output", {"source": "argument", "index": 2}),
], ids=_case_id)
def test_invalid_contract_fields(payload, field, value):
    payload["contract"][field] = value
    with pytest.raises(ValueError):
        validate_function_payload(payload)


@pytest.mark.parametrize("contract", [False, [], "function", 42], ids=_case_id)
def test_invalid_contract_container(payload, contract):
    payload["contract"] = contract
    with pytest.raises(ValueError):
        validate_function_payload(payload)


@pytest.mark.parametrize("datasets", [[], None, {}, [None], [{}], [{"id": "x"}],
    [{"id": "x", "args": [], "expected": 0}] * 33], ids=_case_id)
def test_invalid_dataset_containers(payload, datasets):
    payload["datasets"] = datasets
    with pytest.raises(ValueError):
        validate_function_payload(payload)


@pytest.mark.parametrize("field,value", [
    ("id", ""), ("id", "  "), ("id", "x" * 129), ("id", False),
    ("args", {}), ("args", []), ("args", [True]), ("args", ["1"]),
    ("expected", None), ("expected", True), ("expected", "3"),
    ("dimensions", []), ("dimensions", {"n": -1}), ("dimensions", {"n": True}),
    ("dimensions", {"n": 1.0}), ("dimensions", {"n": 2**53}), ("other", 1),
], ids=_case_id)
def test_invalid_dataset_fields(payload, field, value):
    payload["datasets"][0][field] = value
    with pytest.raises(ValueError):
        validate_function_payload(payload)


def test_dataset_uniqueness_and_limit(payload):
    payload["datasets"] *= 2
    with pytest.raises(ValueError, match="unique"):
        validate_function_payload(payload)
    payload["datasets"] = [{"id": str(i), "args": [1], "expected": 1} for i in range(32)]
    validate_function_payload(payload)


def test_expected_presence_null_and_none_policy(payload):
    dataset = payload["datasets"][0]
    del dataset["expected"]
    with pytest.raises(ValueError, match="explicit expected"):
        validate_function_payload(payload)
    dataset["expected"] = None
    payload["contract"]["output_schema"] = {"type": "null"}
    validate_function_payload(payload)
    payload["contract"]["correctness"] = "none"
    with pytest.raises(ValueError, match="disallows expected"):
        validate_function_payload(payload)
    del dataset["expected"]
    validate_function_payload(payload)


@pytest.mark.parametrize("mutation", ["allowed", "forbidden"])
def test_argument_output_index_checked_in_every_dataset(payload, mutation):
    payload["contract"].update(mutation=mutation, output={"source": "argument", "index": 1})
    validate_function_payload(payload)
    payload["datasets"].append({"id": "short", "args": [1], "expected": 1})
    with pytest.raises(ValueError, match="index"):
        validate_function_payload(payload)
    payload["contract"]["output"] = {"source": "argument"}
    validate_function_payload(payload)


def test_input_schema_covers_entire_positional_array(payload):
    payload["contract"]["input_schema"] = {
        "type": "array", "minItems": 1, "maxItems": 1,
        "items": {"type": "array", "items": {"type": "integer"}},
    }
    payload["datasets"][0]["args"] = [[1, 2]]
    validate_function_payload(payload)
    payload["datasets"][0]["args"] = [1, 2]
    with pytest.raises(ValueError):
        validate_function_payload(payload)


def test_identity_and_dimension_boundaries(payload):
    payload["contract"].update(name="n" * 128, version="v" * 64)
    payload["datasets"][0].update(id="d" * 128, dimensions={"zero": 0, "safe": 2**53 - 1})
    validate_function_payload(payload)


def test_total_json_byte_boundary(payload):
    payload["contract"]["input_schema"] = {"type": "array"}
    payload["datasets"][0]["args"] = [""]
    base = len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    payload["datasets"][0]["args"] = ["x" * (500_000 - base)]
    validate_function_payload(payload)
    payload["datasets"][0]["args"][0] += "x"
    with pytest.raises(ValueError, match="500000"):
        validate_function_payload(payload)
    payload["datasets"][0]["args"] = ["é" * 250_000]
    with pytest.raises(ValueError, match="500000"):
        validate_function_payload(payload)


def test_combined_json_node_budget(payload):
    payload["contract"]["input_schema"] = {"type": "array"}
    payload["datasets"][0]["args"] = [None] * 25_000
    payload["datasets"].append({"id": "second", "args": [None] * 25_000, "expected": 0})
    with pytest.raises(ValueError, match="nodes"):
        validate_function_payload(payload)


@pytest.mark.parametrize("resources", [
    {}, {"timeout_seconds": 1, "memory_bytes": 64 * 1024**2, "cpus": 0.1, "pids": 16},
    {"timeout_seconds": 120, "memory_bytes": 512 * 1024**2, "cpus": 1, "pids": 64},
], ids=_case_id)
def test_resource_boundaries(payload, resources):
    validate_function_payload({**payload, "resources": resources})
    validate_function_payload({"resources": resources})


@pytest.mark.parametrize("resources", [
    None, [], {"extra": 1}, {"timeout_seconds": 0}, {"timeout_seconds": 121},
    {"timeout_seconds": True}, {"timeout_seconds": 1.0}, {"timeout_seconds": "1"},
    {"memory_bytes": 64 * 1024**2 - 1}, {"memory_bytes": 512 * 1024**2 + 1},
    {"memory_bytes": True}, {"pids": 15}, {"pids": 65}, {"pids": 16.0}, {"pids": True},
    {"cpus": 0.099}, {"cpus": 1.001}, {"cpus": True}, {"cpus": "1"},
    {"cpus": float("nan")}, {"cpus": float("inf")}, {"cpus": 10**1000},
], ids=_case_id)
def test_invalid_resources_for_generic_and_legacy(payload, resources):
    for request in (payload, {}):
        with pytest.raises(ValueError):
            validate_function_payload({**request, "resources": resources})


@pytest.mark.parametrize("value", [None, [], 1])
def test_invalid_payload(value):
    with pytest.raises(ValueError):
        validate_function_payload(value)


def test_generic_validation_does_not_depend_on_sorting_fields(payload):
    validate_function_payload({**payload, "sizes": None, "distributions": None})


def test_api_generic_single_baseline_and_legacy_alias(payload):
    request = BenchmarkRequest.model_validate(api_payload(payload))
    assert len(request.candidates) == 1
    assert isinstance(request.candidates[0], FunctionCandidate)
    assert SortCandidate is FunctionCandidate
    assert request.resources == {}
    assert request.sizes == [100, 1000]
    assert request.contract == payload["contract"]


def test_api_legacy_count_and_defaults(payload):
    body = api_payload({})
    with pytest.raises(ValidationError, match="Legacy sorting"):
        BenchmarkRequest.model_validate(body)
    body["candidates"].append({**body["candidates"][0], "name": "challenger"})
    request = BenchmarkRequest.model_validate(body)
    assert request.contract is None and request.datasets == [] and request.resources == {}
    other = BenchmarkRequest.model_validate(body)
    request.resources["cpus"] = 0.5
    request.datasets.append({})
    assert other.resources == {} and other.datasets == []


@pytest.mark.parametrize("count", [1, 5])
def test_api_generic_candidate_bounds(payload, count):
    body = api_payload(payload)
    body["candidates"] = [{**body["candidates"][0], "name": str(i)} for i in range(count)]
    BenchmarkRequest.model_validate(body)


@pytest.mark.parametrize("count", [0, 6])
def test_api_generic_invalid_candidate_bounds(payload, count):
    body = api_payload(payload)
    body["candidates"] = [{**body["candidates"][0], "name": str(i)} for i in range(count)]
    with pytest.raises(ValidationError):
        BenchmarkRequest.model_validate(body)


def test_api_calls_pure_validation_before_runner_update(payload, monkeypatch):
    calls = []
    monkeypatch.setattr("domain.schemas.algorithm_benchmark.DockerBenchmarkRunner._validate",
                        lambda body: calls.append(body))
    BenchmarkRequest.model_validate(api_payload(payload))
    assert len(calls) == 1
    del payload["datasets"][0]["expected"]
    with pytest.raises(ValidationError, match="explicit expected"):
        BenchmarkRequest.model_validate(api_payload(payload))
    assert len(calls) == 1


@pytest.mark.parametrize("field,value", [
    ("contract", []), ("datasets", ()), ("datasets", None), ("resources", []),
    ("resources", None), ("resources", {"cpus": True}),
], ids=_case_id)
def test_api_rejects_non_json_containers_and_invalid_resources(payload, field, value):
    body = api_payload(payload)
    body[field] = value
    with pytest.raises(ValidationError):
        BenchmarkRequest.model_validate(body)


@pytest.mark.parametrize("change", ["unknown-schema-key", "nonfinite", "unsafe-integer", "bad-expected"])
def test_api_enforces_pure_nested_validation(payload, change):
    if change == "unknown-schema-key":
        payload["contract"]["output_schema"]["$ref"] = "evil"
    elif change == "nonfinite":
        payload["datasets"][0]["args"] = [float("nan")]
    elif change == "unsafe-integer":
        payload["datasets"][0]["args"] = [2**53]
    else:
        payload["datasets"][0]["expected"] = True
    with pytest.raises(ValidationError):
        BenchmarkRequest.model_validate(api_payload(payload))


def test_api_retains_common_candidate_validation(payload):
    body = api_payload(payload)
    body["candidates"].append(dict(body["candidates"][0]))
    with pytest.raises(ValidationError, match="unique"):
        BenchmarkRequest.model_validate(body)


@pytest.mark.parametrize("legacy", [{}, {"contract": None}], ids=["missing-contract", "null-contract"])
@pytest.mark.parametrize("datasets", [[], [{"id": "case", "args": []}], [None]],
                         ids=["empty", "nonempty", "malformed-entry"])
def test_legacy_datasets_require_contract(legacy, datasets):
    request = {**legacy, "datasets": datasets}
    before = copy.deepcopy(request)
    if datasets:
        with pytest.raises(ValueError, match="Nonempty datasets require a function contract"):
            validate_function_payload(request)
    else:
        validate_function_payload(request)
    assert request == before


@pytest.mark.parametrize("legacy", [{}, {"contract": None}], ids=["missing-contract", "null-contract"])
@pytest.mark.parametrize("datasets", [None, {}, (), "", False, 0],
                         ids=["null", "object", "tuple", "string", "bool", "number"])
def test_legacy_datasets_must_be_an_array(legacy, datasets):
    with pytest.raises(ValueError, match="datasets must be an array"):
        validate_function_payload({**legacy, "datasets": datasets})


@pytest.mark.parametrize("case,index", [("zero", 0), ("positive", 1), ("null", None),
                                       ("bool", False), ("negative", -1), ("float", 0.0)],
                         ids=_case_id)
def test_return_output_rejects_any_explicit_index(payload, case, index):
    payload["contract"]["output"] = {"source": "return", "index": index}
    with pytest.raises(ValueError, match="Return output must not specify an index"):
        validate_function_payload(payload)


@pytest.mark.parametrize("output", [{"source": "return"}, {"source": "argument"},
                                    {"source": "argument", "index": 0}],
                         ids=["return", "argument-default", "argument-zero"])
def test_supported_output_selectors_stay_valid(payload, output):
    payload["contract"]["output"] = output
    before = copy.deepcopy(payload)
    validate_function_payload(payload)
    assert payload == before


@pytest.mark.parametrize("key", [chr(0xD800), chr(0xDFFF), 0],
                         ids=["high-surrogate", "low-surrogate", "integer"])
@pytest.mark.parametrize("location", ["args", "expected", "input-enum", "output-property", "dimensions"])
def test_nonportable_object_keys_rejected_in_every_location(payload, key, location):
    bad_object = {key: None}
    with pytest.raises(ValueError):
        validate_schema(bad_object, {})
    if location == "args":
        payload["datasets"][0]["args"] = [bad_object]
    elif location == "expected":
        payload["datasets"][0]["expected"] = bad_object
    elif location == "input-enum":
        payload["contract"]["input_schema"] = {"type": "array", "enum": [[bad_object]]}
    elif location == "output-property":
        payload["contract"]["output_schema"] = {"type": "object", "properties": {key: {}}}
    else:
        payload["datasets"][0]["dimensions"] = {key: 0}
    with pytest.raises(ValueError):
        validate_function_payload(payload)


@pytest.mark.parametrize("cycle_kind", ["array", "object"])
def test_cyclic_schema_and_dataset_values_are_bounded(payload, cycle_kind):
    if cycle_kind == "array":
        cycle = []
        cycle.append(cycle)
    else:
        cycle = {}
        cycle["self"] = cycle
    with pytest.raises(ValueError, match="depth"):
        validate_schema(None, {"enum": [cycle]})
    payload["datasets"][0]["expected"] = cycle
    with pytest.raises(ValueError, match="depth"):
        validate_function_payload(payload)


def test_object_keys_count_toward_node_budget():
    validate_schema(dict.fromkeys(map(str, range(24_999))), {})
    with pytest.raises(ValueError, match="nodes"):
        validate_schema(dict.fromkeys(map(str, range(25_000))), {})


def test_json_byte_budget_includes_schema_not_just_dataset_args(payload):
    payload["contract"]["output_schema"] = {"enum": ["x" * 500_000]}
    with pytest.raises(ValueError, match="500000 JSON bytes"):
        validate_function_payload(payload)


def test_enum_json_identity_ignores_object_key_order_and_numeric_representation():
    schema = {"enum": [{"a": 1, "b": [2]}, {"b": [2.0], "a": 1.0}]}
    with pytest.raises(ValueError, match="enum values must be unique"):
        validate_schema(None, schema)
    validate_schema({"a": True}, {"enum": [{"a": 1}, {"a": True}]})
    validate_schema(-0.0, {"enum": [0]})
    with pytest.raises(ValueError, match="enum values must be unique"):
        validate_schema(0, {"enum": [0, -0.0]})
