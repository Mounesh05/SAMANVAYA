"""Portable, dependency-free function contracts shared by host and workers.

Only data is inspected here: schemas are an allowlisted subset, never executable
validators. Contract names and versions are caller-owned semantic identities.
"""

import json
import math

MAX_SAFE_INTEGER = 2**53 - 1
MAX_DEPTH = 32
MAX_NODES = 50_000
MAX_BYTES = 500_000
_TYPES = {"null", "boolean", "number", "integer", "string", "array", "object"}
_KEYWORDS = {
    "type", "enum", "items", "properties", "required", "additionalProperties",
    "minItems", "maxItems", "minLength", "maxLength", "minimum", "maximum",
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _json(value):
    """Bound traversal before serialization; this also rejects cycles and surrogates."""
    nodes = 0
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        nodes += 1
        _require(nodes <= MAX_NODES, "JSON exceeds 50000 nodes")
        _require(depth <= MAX_DEPTH, "JSON exceeds depth 32")
        kind = type(item)
        if item is None or kind is bool:
            continue
        if kind is str:
            try:
                item.encode("utf-8")
            except UnicodeError as exc:
                raise ValueError("JSON strings must be valid UTF-8") from exc
        elif kind is int:
            _require(abs(item) <= MAX_SAFE_INTEGER, "JSON integer exceeds safe integer range")
        elif kind is float:
            _require(math.isfinite(item), "JSON numbers must be finite")
            _require(not item.is_integer() or abs(item) <= MAX_SAFE_INTEGER,
                     "JSON integer exceeds safe integer range")
        elif kind is list:
            _require(nodes + len(stack) + len(item) <= MAX_NODES, "JSON exceeds 50000 nodes")
            stack.extend((child, depth + 1) for child in item)
        elif kind is dict:
            _require(all(type(key) is str for key in item), "JSON object keys must be strings")
            _require(nodes + len(stack) + 2 * len(item) <= MAX_NODES, "JSON exceeds 50000 nodes")
            for key, child in item.items():
                stack.append((key, depth + 1))
                stack.append((child, depth + 1))
        else:
            raise ValueError("Value is not portable JSON")


def _integer(value, lower, upper):
    return type(value) is int and lower <= value <= upper


def _number(value):
    return type(value) is int or type(value) is float and math.isfinite(value)


def _same(left, right):
    # Python considers True == 1; JSON Schema does not.
    if type(left) in (int, float) and type(right) in (int, float):
        return left == right
    if type(left) is not type(right):
        return False
    if type(left) is list:
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    if type(left) is dict:
        return left.keys() == right.keys() and all(_same(left[k], right[k]) for k in left)
    return left == right


def _schema(schema, depth=0):
    _require(depth <= MAX_DEPTH, "Schema exceeds depth 32")
    _require(type(schema) is dict, "Schema must be an object")
    _require(not schema.keys() - _KEYWORDS, "Unsupported schema keyword")
    kind = schema.get("type")
    _require("type" not in schema or type(kind) is str and kind in _TYPES, "Invalid schema type")
    if "enum" in schema:
        values = schema["enum"]
        _require(type(values) is list and bool(values), "enum must be a nonempty array")
        # Hash JSON identities to avoid quadratic duplicate detection.
        seen = set()
        for value in values:
            key = _enum_key(value)
            _require(key not in seen, "enum values must be unique")
            seen.add(key)
            if kind is not None:
                _require(_matches_type(value, kind), "enum value does not match schema type")
    groups = {
        "array": ("items", "minItems", "maxItems"),
        "object": ("properties", "required", "additionalProperties"),
        "string": ("minLength", "maxLength"),
        "number": ("minimum", "maximum"),
    }
    for expected, keys in groups.items():
        if any(key in schema for key in keys):
            _require(kind == expected or expected == "number" and kind == "integer",
                     "Schema keyword is incompatible with type")
    for low, high in (("minItems", "maxItems"), ("minLength", "maxLength")):
        for key in (low, high):
            if key in schema:
                _require(_integer(schema[key], 0, MAX_SAFE_INTEGER), "Schema length must be a nonnegative integer")
        if low in schema and high in schema:
            _require(schema[low] <= schema[high], "Schema minimum exceeds maximum")
    for key in ("minimum", "maximum"):
        if key in schema:
            _require(_number(schema[key]), "Schema numeric bound must be finite")
    if "minimum" in schema and "maximum" in schema:
        _require(schema["minimum"] <= schema["maximum"], "Schema minimum exceeds maximum")
    if "items" in schema:
        _schema(schema["items"], depth + 1)
    if "properties" in schema:
        _require(type(schema["properties"]) is dict, "properties must be an object")
        for child in schema["properties"].values():
            _schema(child, depth + 1)
    if "required" in schema:
        required = schema["required"]
        _require(type(required) is list and all(type(key) is str for key in required),
                 "required must be an array of strings")
        _require(len(set(required)) == len(required), "required must be unique")
        if schema.get("additionalProperties") is False:
            _require(set(required) <= schema.get("properties", {}).keys(),
                     "Required property is forbidden by additionalProperties")
    if "additionalProperties" in schema:
        _require(type(schema["additionalProperties"]) is bool, "additionalProperties must be boolean")


def _enum_key(value):
    """Hashable JSON identity with numeric equality but distinct booleans."""
    if type(value) in (int, float):
        return ("number", value)
    if type(value) is list:
        return ("array", tuple(_enum_key(child) for child in value))
    if type(value) is dict:
        return ("object", frozenset((key, _enum_key(child)) for key, child in value.items()))
    return (type(value).__name__, value)


def _matches_type(value, kind):
    return {
        "null": value is None,
        "boolean": type(value) is bool,
        "number": type(value) in (int, float),
        "integer": type(value) is int or type(value) is float and value.is_integer(),
        "string": type(value) is str,
        "array": type(value) is list,
        "object": type(value) is dict,
    }[kind]


def _validate(value, schema):
    if "type" in schema:
        _require(_matches_type(value, schema["type"]), "Value does not match schema type")
    if "enum" in schema:
        _require(any(_same(value, choice) for choice in schema["enum"]), "Value is not in enum")
    if type(value) in (list, str):
        low, high = ("minItems", "maxItems") if type(value) is list else ("minLength", "maxLength")
        _require(len(value) >= schema.get(low, 0), "Value is shorter than schema minimum")
        if high in schema:
            _require(len(value) <= schema[high], "Value exceeds schema maximum length")
        if type(value) is list and "items" in schema:
            for item in value:
                _validate(item, schema["items"])
    elif type(value) is dict:
        _require(all(key in value for key in schema.get("required", [])), "Missing required property")
        properties = schema.get("properties", {})
        for key, item in value.items():
            if key in properties:
                _validate(item, properties[key])
            else:
                _require(schema.get("additionalProperties", True), "Additional property is forbidden")
    elif type(value) in (int, float):
        if "minimum" in schema:
            _require(value >= schema["minimum"], "Value is below schema minimum")
        if "maximum" in schema:
            _require(value <= schema["maximum"], "Value exceeds schema maximum")


def validate_schema(value, schema):
    """Validate portable JSON against the bounded schema subset, or raise ValueError."""
    _json(schema)
    _json(value)
    _schema(schema)
    _validate(value, schema)


def is_generic(payload):
    """A non-null contract selects generic validation, even when malformed."""
    return isinstance(payload, dict) and payload.get("contract") is not None


def _identity(value, limit, label):
    _require(type(value) is str and bool(value.strip()) and len(value) <= limit,
             f"{label} must be nonblank and at most {limit} characters")


def _resources(resources):
    _require(type(resources) is dict, "resources must be an object")
    _require(not resources.keys() - {"timeout_seconds", "memory_bytes", "cpus", "pids"},
             "Unsupported resource limit")
    for key, lower, upper in (("timeout_seconds", 1, 120),
                              ("memory_bytes", 64 * 1024**2, 512 * 1024**2), ("pids", 16, 64)):
        if key in resources:
            _require(_integer(resources[key], lower, upper), f"Invalid resource {key}")
    if "cpus" in resources:
        _require(_number(resources["cpus"]) and 0.1 <= resources["cpus"] <= 1,
                 "cpus must be a finite number in 0.1..1")


def validate_function_payload(payload):
    """Validate function-specific fields; common runner checks remain with the caller.

    Null/missing contracts retain legacy sorting only without datasets. Defaults
    are interpreted without mutating the payload, keeping this usable with either
    host or worker imports.
    """
    _require(type(payload) is dict, "Payload must be an object")
    _resources(payload.get("resources", {}))
    datasets = payload.get("datasets", [])
    if not is_generic(payload):
        _require(type(datasets) is list, "datasets must be an array")
        _require(not datasets, "Nonempty datasets require a function contract")
        return
    contract = payload["contract"]
    bounded = {"contract": contract, "datasets": datasets}
    _json(bounded)
    _require(len(json.dumps(bounded, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8"))
             <= MAX_BYTES, "Contract and datasets exceed 500000 JSON bytes")
    _require(type(contract) is dict, "contract must be an object")
    required = {"kind", "name", "version", "input_schema", "output_schema", "correctness"}
    _require(required <= contract.keys(), "Missing required contract field")
    _require(not contract.keys() - required - {"mutation", "output"}, "Unsupported contract field")
    _require(contract["kind"] == "function", "contract kind must be function")
    _identity(contract["name"], 128, "Contract name")
    _identity(contract["version"], 64, "Contract version")
    _require(contract["correctness"] in ("expected", "none"), "Invalid correctness policy")
    _require(contract.get("mutation", "allowed") in ("allowed", "forbidden"), "Invalid mutation policy")
    for key in ("input_schema", "output_schema"):
        _schema(contract[key])
    _require(contract["input_schema"].get("type") == "array", "input_schema must have type array")
    output = contract.get("output", {"source": "return"})
    _require(type(output) is dict and not output.keys() - {"source", "index"}, "Invalid output selector")
    _require(output.get("source") in ("return", "argument"), "Invalid output source")
    _require(output["source"] != "return" or "index" not in output,
             "Return output must not specify an index")
    index = output.get("index", 0)
    _require(_integer(index, 0, MAX_SAFE_INTEGER), "Output index must be a nonnegative safe integer")
    _require(type(datasets) is list and 1 <= len(datasets) <= 32, "Provide 1..32 datasets")
    ids = set()
    for dataset in datasets:
        if type(dataset) is not dict:
            raise ValueError("Dataset must be an object")
        _require({"id", "args"} <= dataset.keys(), "Dataset requires id and args")
        _require(not dataset.keys() - {"id", "args", "expected", "dimensions"}, "Unsupported dataset field")
        _identity(dataset["id"], 128, "Dataset id")
        _require(dataset["id"] not in ids, "Dataset ids must be unique")
        ids.add(dataset["id"])
        _require(type(dataset["args"]) is list, "Dataset args must be an array")
        _validate(dataset["args"], contract["input_schema"])
        if output["source"] == "argument":
            _require(index < len(dataset["args"]), "Output argument index does not exist in every dataset")
        if contract["correctness"] == "expected":
            _require("expected" in dataset, "Expected correctness requires explicit expected on every dataset")
            _validate(dataset["expected"], contract["output_schema"])
        else:
            _require("expected" not in dataset, "Correctness none disallows expected")
        if "dimensions" in dataset:
            dimensions = dataset["dimensions"]
            _require(type(dimensions) is dict and all(_integer(n, 0, MAX_SAFE_INTEGER) for n in dimensions.values()),
                     "Dimensions must map strings to nonnegative safe integers")
