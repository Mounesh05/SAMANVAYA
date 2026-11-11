'use strict';
// Container-only harness. The child output is discarded; only its result file is forwarded.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const {spawnSync} = require('node:child_process');
const {performance} = require('node:perf_hooks');
// Lazy loading keeps the data-only validators usable without compiler installation.
let compiler;
function typescript() { return compiler || (compiler = require('typescript')); }
const MEMORY_METRIC = 'node_heap_used_delta_bytes';
const VALIDATION_VERSION = 'functional-validation-v1';
class ContractViolation extends Error {}

function comparisonMode(contract) {
  const comparison = Object.prototype.hasOwnProperty.call(contract, 'comparison') ? contract.comparison : {version: '1', mode: 'exact'};
  requireValue(plainObject(comparison) && Object.keys(comparison).length === 2 &&
    comparison.version === '1' && ['exact', 'unordered_set', 'unordered_multiset', 'one_of'].includes(comparison.mode), 'Unsupported comparison validator');
  if (['unordered_set', 'unordered_multiset'].includes(comparison.mode)) requireValue(contract.output_schema.type === 'array', 'Unordered comparison requires an explicit array output schema');
  return comparison.mode;
}

function matchesExpected(output, dataset, contract) {
  const mode = comparisonMode(contract);
  if (mode === 'one_of') return dataset.acceptable_outputs.some(choice => sameJSON(output, choice));
  if (mode === 'exact') return sameJSON(output, dataset.expected);
  if (!Array.isArray(output) || !Array.isArray(dataset.expected)) return false;
  // Numeric equality follows the existing portable JSON contract; boolean remains distinct.
  const key = value => {
    if (Array.isArray(value)) return ['array', value.map(key)];
    if (plainObject(value)) return ['object', Object.keys(value).sort().map(k => [k, key(value[k])])];
    return [value === null ? 'null' : typeof value, value];
  };
  const canonical = values => {
    const keys = values.map(v => JSON.stringify(key(v)));
    return (mode === 'unordered_set' ? [...new Set(keys)] : keys).sort();
  };
  return sameJSON(canonical(output), canonical(dataset.expected));
}

const MAX_SAFE_INTEGER = Number.MAX_SAFE_INTEGER;
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
function requireValue(condition, message) { if (!condition) throw new Error(message); }
function isGeneric(payload) { return payload !== null && typeof payload === 'object' &&
  own(payload, 'contract') && payload.contract !== null; }

function plainObject(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false;
  const proto = Object.getPrototypeOf(value);
  if (proto === null) return true;
  const constructor = Object.getOwnPropertyDescriptor(proto, 'constructor');
  return Object.getPrototypeOf(proto) === null && constructor &&
    typeof constructor.value === 'function' &&
    Function.prototype.toString.call(constructor.value) === Function.prototype.toString.call(Object);
}

// This is a portability check, NOT a hostile-object security boundary. Proxies and
// deliberately spoofed prototypes can run traps; Docker remains the trust boundary.
// Descriptors reject normal getters, hidden/symbol properties, and sparse arrays.
function portableJSON(value) {
  const stack = [[value, 0]];
  let nodes = 0;
  while (stack.length) {
    const [item, depth] = stack.pop();
    requireValue(++nodes <= 50000, 'JSON exceeds 50000 nodes');
    requireValue(depth <= 32, 'JSON exceeds depth 32');
    if (item === null || typeof item === 'boolean') continue;
    if (typeof item === 'string') {
      for (const char of item) {
        const code = char.codePointAt(0);
        requireValue(code < 0xD800 || code > 0xDFFF, 'JSON strings must be valid UTF-8');
      }
    } else if (typeof item === 'number') {
      requireValue(Number.isFinite(item), 'JSON numbers must be finite');
      requireValue(!Number.isInteger(item) || Number.isSafeInteger(item), 'JSON integer exceeds safe integer range');
    } else if (Array.isArray(item)) {
      requireValue(nodes + stack.length + item.length <= 50000, 'JSON exceeds 50000 nodes');
      requireValue(Reflect.ownKeys(item).length === item.length + 1, 'JSON arrays must be dense without extra properties');
      for (let i = 0; i < item.length; i++) {
        const descriptor = Object.getOwnPropertyDescriptor(item, String(i));
        requireValue(descriptor && own(descriptor, 'value') && descriptor.enumerable, 'JSON arrays must be dense data');
        stack.push([descriptor.value, depth + 1]);
      }
    } else if (plainObject(item)) {
      const keys = Reflect.ownKeys(item);
      requireValue(nodes + stack.length + 2 * keys.length <= 50000, 'JSON exceeds 50000 nodes');
      for (const key of keys) {
        const descriptor = Object.getOwnPropertyDescriptor(item, key);
        requireValue(typeof key === 'string' && descriptor.enumerable && own(descriptor, 'value'),
          'JSON objects require enumerable string data properties');
        stack.push([key, depth + 1], [descriptor.value, depth + 1]);
      }
    } else throw new Error('Value is not portable JSON');
  }
}

function sameJSON(left, right) {
  if (left === right) return true;
  if (left === null || right === null || typeof left !== typeof right) return false;
  if (Array.isArray(left)) return Array.isArray(right) && left.length === right.length &&
    left.every((value, index) => sameJSON(value, right[index]));
  if (typeof left === 'object' && !Array.isArray(right)) {
    const keys = Object.keys(left);
    return keys.length === Object.keys(right).length && keys.every(key => own(right, key) && sameJSON(left[key], right[key]));
  }
  return false;
}

function matchesType(value, kind) {
  switch (kind) {
    case 'null': return value === null;
    case 'boolean': return typeof value === 'boolean';
    case 'number': return typeof value === 'number';
    case 'integer': return typeof value === 'number' && Number.isInteger(value);
    case 'string': return typeof value === 'string';
    case 'array': return Array.isArray(value);
    case 'object': return plainObject(value);
    default: return false;
  }
}
function integer(value, low = 0, high = MAX_SAFE_INTEGER) {
  return Number.isSafeInteger(value) && value >= low && value <= high;
}
function enumKey(value) {
  if (Array.isArray(value)) return ['array', value.map(enumKey)];
  if (plainObject(value)) return ['object', Object.keys(value).sort().map(key => [key, enumKey(value[key])])];
  return [value === null ? 'null' : typeof value, value];
}
function checkSchema(schema, depth = 0) {
  requireValue(depth <= 32, 'Schema exceeds depth 32');
  requireValue(plainObject(schema), 'Schema must be an object');
  const keywords = ['type', 'enum', 'items', 'properties', 'required', 'additionalProperties',
    'minItems', 'maxItems', 'minLength', 'maxLength', 'minimum', 'maximum'];
  requireValue(Object.keys(schema).every(key => keywords.includes(key)), 'Unsupported schema keyword');
  const kind = own(schema, 'type') ? schema.type : undefined;
  requireValue(!own(schema, 'type') || ['null', 'boolean', 'number', 'integer', 'string', 'array', 'object'].includes(kind),
    'Invalid schema type');
  if (own(schema, 'enum')) {
    requireValue(Array.isArray(schema.enum) && schema.enum.length > 0, 'enum must be a nonempty array');
    const seen = new Set();
    for (const value of schema.enum) {
      const key = JSON.stringify(enumKey(value));
      requireValue(!seen.has(key), 'enum values must be unique');
      seen.add(key);
      if (kind !== undefined) requireValue(matchesType(value, kind), 'enum value does not match schema type');
    }
  }
  for (const [expected, keys] of Object.entries({array: ['items', 'minItems', 'maxItems'],
    object: ['properties', 'required', 'additionalProperties'], string: ['minLength', 'maxLength'],
    number: ['minimum', 'maximum']})) {
    if (keys.some(key => own(schema, key))) requireValue(kind === expected || expected === 'number' && kind === 'integer',
      'Schema keyword is incompatible with type');
  }
  for (const [low, high] of [['minItems', 'maxItems'], ['minLength', 'maxLength']]) {
    for (const key of [low, high]) if (own(schema, key)) requireValue(integer(schema[key]), 'Schema length must be a nonnegative integer');
    if (own(schema, low) && own(schema, high)) requireValue(schema[low] <= schema[high], 'Schema minimum exceeds maximum');
  }
  for (const key of ['minimum', 'maximum']) if (own(schema, key)) {
    requireValue(typeof schema[key] === 'number' && Number.isFinite(schema[key]), 'Schema numeric bound must be finite');
  }
  if (own(schema, 'minimum') && own(schema, 'maximum')) requireValue(schema.minimum <= schema.maximum, 'Schema minimum exceeds maximum');
  if (own(schema, 'items')) checkSchema(schema.items, depth + 1);
  if (own(schema, 'properties')) {
    requireValue(plainObject(schema.properties), 'properties must be an object');
    for (const child of Object.values(schema.properties)) checkSchema(child, depth + 1);
  }
  if (own(schema, 'required')) {
    requireValue(Array.isArray(schema.required) && schema.required.every(key => typeof key === 'string'), 'required must be an array of strings');
    requireValue(new Set(schema.required).size === schema.required.length, 'required must be unique');
    if (schema.additionalProperties === false) requireValue(schema.required.every(key => own(schema.properties || {}, key)),
      'Required property is forbidden by additionalProperties');
  }
  if (own(schema, 'additionalProperties')) requireValue(typeof schema.additionalProperties === 'boolean', 'additionalProperties must be boolean');
}
function validateValue(value, schema) {
  if (own(schema, 'type')) requireValue(matchesType(value, schema.type), 'Value does not match schema type');
  if (own(schema, 'enum')) requireValue(schema.enum.some(choice => sameJSON(value, choice)), 'Value is not in enum');
  if (Array.isArray(value) || typeof value === 'string') {
    const [low, high] = Array.isArray(value) ? ['minItems', 'maxItems'] : ['minLength', 'maxLength'];
    const length = typeof value === 'string' ? Array.from(value).length : value.length;
    requireValue(length >= (schema[low] || 0), 'Value is shorter than schema minimum');
    if (own(schema, high)) requireValue(length <= schema[high], 'Value exceeds schema maximum length');
    if (Array.isArray(value) && own(schema, 'items')) for (const item of value) validateValue(item, schema.items);
  } else if (plainObject(value)) {
    requireValue((schema.required || []).every(key => own(value, key)), 'Missing required property');
    const properties = schema.properties || {};
    for (const key of Object.keys(value)) {
      if (own(properties, key)) validateValue(value[key], properties[key]);
      else requireValue(schema.additionalProperties !== false, 'Additional property is forbidden');
    }
  } else if (typeof value === 'number') {
    if (own(schema, 'minimum')) requireValue(value >= schema.minimum, 'Value is below schema minimum');
    if (own(schema, 'maximum')) requireValue(value <= schema.maximum, 'Value exceeds schema maximum');
  }
}
function validateSchema(value, schema) {
  portableJSON(schema);
  portableJSON(value);
  checkSchema(schema);
  validateValue(value, schema);
}
function identity(value, limit, label) {
  requireValue(typeof value === 'string' && value.trim().length > 0 && Array.from(value).length <= limit,
    `${label} must be nonblank and at most ${limit} characters`);
}
function validateFunctionPayload(payload) {
  requireValue(plainObject(payload), 'Payload must be an object');
  const resources = own(payload, 'resources') ? payload.resources : {};
  requireValue(plainObject(resources), 'resources must be an object');
  requireValue(Object.keys(resources).every(key => ['timeout_seconds', 'memory_bytes', 'cpus', 'pids'].includes(key)), 'Unsupported resource limit');
  for (const [key, low, high] of [['timeout_seconds', 1, 120], ['memory_bytes', 64 * 1024 ** 2, 512 * 1024 ** 2], ['pids', 16, 64]]) {
    if (own(resources, key)) requireValue(integer(resources[key], low, high), `Invalid resource ${key}`);
  }
  if (own(resources, 'cpus')) requireValue(typeof resources.cpus === 'number' && Number.isFinite(resources.cpus) &&
    resources.cpus >= 0.1 && resources.cpus <= 1, 'cpus must be a finite number in 0.1..1');
  if (!isGeneric(payload)) return;
  const contract = payload.contract;
  const datasets = own(payload, 'datasets') ? payload.datasets : [];
  const bounded = {contract, datasets};
  portableJSON(bounded);
  requireValue(Buffer.byteLength(JSON.stringify(bounded), 'utf8') <= 500000, 'Contract and datasets exceed 500000 JSON bytes');
  requireValue(plainObject(contract), 'contract must be an object');
  const required = ['kind', 'name', 'version', 'input_schema', 'output_schema', 'correctness'];
  requireValue(required.every(key => own(contract, key)), 'Missing required contract field');
  requireValue(Object.keys(contract).every(key => [...required, 'mutation', 'output', 'comparison'].includes(key)), 'Unsupported contract field');
  requireValue(contract.kind === 'function', 'contract kind must be function');
  identity(contract.name, 128, 'Contract name');
  identity(contract.version, 64, 'Contract version');
  requireValue(['expected', 'none'].includes(contract.correctness), 'Invalid correctness policy');
  const mode = comparisonMode(contract);
  requireValue(!own(contract, 'mutation') || ['allowed', 'forbidden'].includes(contract.mutation), 'Invalid mutation policy');
  checkSchema(contract.input_schema);
  checkSchema(contract.output_schema);
  requireValue(contract.input_schema.type === 'array', 'input_schema must have type array');
  const output = own(contract, 'output') ? contract.output : {source: 'return'};
  requireValue(plainObject(output) && Object.keys(output).every(key => ['source', 'index'].includes(key)), 'Invalid output selector');
  requireValue(['return', 'argument'].includes(output.source), 'Invalid output source');
  const index = own(output, 'index') ? output.index : 0;
  requireValue(integer(index), 'Output index must be a nonnegative safe integer');
  requireValue(Array.isArray(datasets) && datasets.length >= 1 && datasets.length <= 32, 'Provide 1..32 datasets');
  const ids = new Set();
  for (const dataset of datasets) {
    requireValue(plainObject(dataset), 'Dataset must be an object');
    requireValue(own(dataset, 'id') && own(dataset, 'args'), 'Dataset requires id and args');
    requireValue(Object.keys(dataset).every(key => ['id', 'args', 'expected', 'dimensions', 'acceptable_outputs'].includes(key)), 'Unsupported dataset field');
    identity(dataset.id, 128, 'Dataset id');
    requireValue(!ids.has(dataset.id), 'Dataset ids must be unique');
    ids.add(dataset.id);
    requireValue(Array.isArray(dataset.args), 'Dataset args must be an array');
    validateValue(dataset.args, contract.input_schema);
    if (output.source === 'argument') requireValue(index < dataset.args.length, 'Output argument index does not exist in every dataset');
    if (contract.correctness === 'expected') {
      requireValue(own(dataset, 'expected'), 'Expected correctness requires explicit expected on every dataset');
      validateValue(dataset.expected, contract.output_schema);
    } else requireValue(!own(dataset, 'expected'), 'Correctness none disallows expected');
    if (mode === 'one_of') {
      requireValue(contract.correctness === 'expected' && Array.isArray(dataset.acceptable_outputs) && dataset.acceptable_outputs.length >= 1 && dataset.acceptable_outputs.length <= 16, 'one_of requires explicit acceptable outputs');
      for (const choice of dataset.acceptable_outputs) validateValue(choice, contract.output_schema);
      requireValue(dataset.acceptable_outputs.some(choice => sameJSON(dataset.expected, choice)), 'Expected output must be an approved choice');
    } else requireValue(!own(dataset, 'acceptable_outputs'), 'Acceptable outputs require one_of comparison');
    if (own(dataset, 'dimensions')) requireValue(plainObject(dataset.dimensions) && Object.values(dataset.dimensions).every(n => integer(n)),
      'Dimensions must map strings to nonnegative safe integers');
  }
}

function makeInput(size, distribution, seed) {
  let state = seed >>> 0;
  const values = [];
  for (let i = 0; i < size; i++) {
    state = (Math.imul(1664525, state) + 1013904223) >>> 0;
    values.push(state % (distribution === 'duplicates' ? 8 : 20001)
      - (distribution === 'duplicates' ? 0 : 10000));
  }
  if (distribution === 'sorted') values.sort((a, b) => a - b);
  if (distribution === 'reversed') values.sort((a, b) => b - a);
  return values;
}

function checkResult(result, argument, expected) {
  // Both null and thenables are rejected: only undefined denotes an in-place JS sort.
  const output = result === undefined ? argument : result;
  if (!Array.isArray(output) || output.length !== expected.length ||
      output.some((value, index) => typeof value !== 'number' || !Number.isFinite(value) || value !== expected[index])) {
    throw new Error('incorrect numeric sorting result (order or multiset mismatch)');
  }
  // Array.prototype.some skips sparse slots.
  for (let i = 0; i < output.length; i++) {
    if (!Object.prototype.hasOwnProperty.call(output, i)) throw new Error('sparse result is not a numeric list');
  }
}

function analyzeStructure(candidate, language) {
  const ts = typescript();
  const result = {status: 'available', parser: 'typescript', entrypoint: candidate.entrypoint,
    functions: [], limitations: [
      'Syntactic observations only; no Big-O inference, type checking, or call resolution.',
      'Counts cover each function body, excluding nested function bodies; lines are 1-based inclusive.',
      'Branches count if, conditional expressions, switch clauses, and catch clauses.',
      'Direct recursion counts identifier calls to the function name or its variable binding only.',
      'Allocations count array literals, object literals, and new expressions, not runtime allocations.',
      'Reports retain at most 128 functions, 512 call labels, and 1024 allocation sites; labels are bounded.',
    ]};
  try {
    const source = ts.createSourceFile(language === 'typescript' ? 'candidate.ts' : 'candidate.js',
      candidate.source, ts.ScriptTarget.ES2022, true,
      language === 'typescript' ? ts.ScriptKind.TS : ts.ScriptKind.JS);
    const line = position => source.getLineAndCharacterOfPosition(position).line + 1;
    if (source.parseDiagnostics.length) {
      result.status = 'unavailable';
      result.diagnostics = source.parseDiagnostics.map(diagnostic => ({
        message: ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n'),
        line: line(diagnostic.start || 0),
        column: source.getLineAndCharacterOfPosition(diagnostic.start || 0).character + 1,
      }));
      return result;
    }
    const isFunction = node => ts.isFunctionDeclaration(node) || ts.isFunctionExpression(node) ||
      ts.isArrowFunction(node) || ts.isMethodDeclaration(node) || ts.isConstructorDeclaration(node) ||
      ts.isGetAccessorDeclaration(node) || ts.isSetAccessorDeclaration(node);
    function bindingName(node) {
      if (ts.isVariableDeclaration(node.parent) || ts.isPropertyAssignment(node.parent) || ts.isPropertyDeclaration(node.parent)) {
        return node.parent.name.getText(source);
      }
      return null;
    }
    const budget = {nodes: 0, calls: 512, allocations: 1024, truncated: false};
    function callName(node) {
      const parts = [];
      while (ts.isPropertyAccessExpression(node) && parts.length < 32) {
        parts.push(node.name.text);
        node = node.expression;
      }
      if (!ts.isIdentifier(node)) return null;
      parts.push(node.text);
      return parts.reverse().join('.').slice(0, 120);
    }
    function collect(node) {
      requireValue(++budget.nodes <= 50000, 'AST exceeds 50000 nodes');
      if (isFunction(node) && node.body && result.functions.length < 128) {
        const name = (node.name ? node.name.getText(source) : bindingName(node) ||
          (ts.isConstructorDeclaration(node) ? 'constructor' : `<anonymous@${line(node.getStart(source))}>`)).slice(0, 120);
        const record = {name, line: line(node.getStart(source)), end_line: line(Math.max(node.getStart(source), node.end - 1)),
          loops: 0, max_loop_nesting: 0, branches: 0, direct_recursive_calls: 0, calls: [], allocations: []};
        const calls = new Set();
        const recursiveNames = new Set([node.name && ts.isIdentifier(node.name) ? node.name.text : null, bindingName(node)]);
        function observe(child, nesting) {
          if (isFunction(child)) return;
          const loop = ts.isForStatement(child) || ts.isForInStatement(child) || ts.isForOfStatement(child) ||
            ts.isWhileStatement(child) || ts.isDoStatement(child);
          if (loop) {
            record.loops++;
            nesting++;
            record.max_loop_nesting = Math.max(record.max_loop_nesting, nesting);
          }
          if (ts.isIfStatement(child) || ts.isConditionalExpression(child) || ts.isCaseClause(child) ||
              ts.isDefaultClause(child) || ts.isCatchClause(child)) record.branches++;
          if (ts.isCallExpression(child)) {
            const label = callName(child.expression);
            if (label && !calls.has(label)) {
              if (budget.calls > 0) { calls.add(label); budget.calls--; }
              else budget.truncated = true;
            }
            if (ts.isIdentifier(child.expression) && recursiveNames.has(child.expression.text)) record.direct_recursive_calls++;
          }
          const kind = ts.isArrayLiteralExpression(child) ? 'array_literal' :
            ts.isObjectLiteralExpression(child) ? 'object_literal' : ts.isNewExpression(child) ? 'new_expression' : null;
          if (kind) {
            if (budget.allocations > 0) { record.allocations.push({kind, line: line(child.getStart(source))}); budget.allocations--; }
            else budget.truncated = true;
          }
          ts.forEachChild(child, nested => observe(nested, nesting));
        }
        observe(node.body, 0);
        record.calls = [...calls];
        result.functions.push(record);
      } else if (isFunction(node) && node.body) budget.truncated = true;
      ts.forEachChild(node, collect);
    }
    collect(source);
    if (budget.truncated) result.limitations.push('Structural output was truncated to its documented bounds.');
  } catch (error) {
    result.status = 'unavailable';
    result.functions = [];
    result.diagnostics = [{message: String(error).slice(0, 1500)}];
  }
  return result;
}

function checkFunctionResult(output, arguments_, dataset, contract) {
  if (output !== null && (typeof output === 'object' || typeof output === 'function')) {
    requireValue(typeof output.then !== 'function', 'async and thenable results are unsupported');
    requireValue(!(typeof output.next === 'function' &&
      (typeof output[Symbol.iterator] === 'function' || typeof output[Symbol.asyncIterator] === 'function')),
    'generator results are unsupported');
  }
  if (contract.mutation === 'forbidden') {
    portableJSON(arguments_);
    if (!sameJSON(arguments_, dataset.args)) throw new ContractViolation('argument mutation is forbidden');
  }
  const selector = contract.output || {source: 'return'};
  if (selector.source === 'argument') output = arguments_[selector.index || 0];
  if (comparisonMode(contract) === 'unordered_set' && !Array.isArray(output)) {
    try { output = Array.from(Set.prototype.values.call(output)); }
    catch { /* No generic iterable conversion: only native Set internal slots. */ }
  }
  try { validateSchema(output, contract.output_schema); }
  catch { throw new ContractViolation('output violates approved JSON schema'); }
  if (contract.correctness === 'expected' && !matchesExpected(output, dataset, contract)) throw new ContractViolation('output does not match expected JSON');
}
function benchmarkFunctionCases(payload, fn, result) {
  const contract = payload.contract;
  for (const dataset of payload.datasets) {
    const entry = {case_id: dataset.id, dimensions: {...(dataset.dimensions || {})}, correct: false,
      validation_status: 'failed', timings_seconds: [], memory_bytes: null, memory_metric: MEMORY_METRIC, error: null};
    result.cases.push(entry);
    const cloneArguments = () => JSON.parse(JSON.stringify(dataset.args));
    try {
      for (let i = 0; i < 2; i++) {
        const arguments_ = cloneArguments();
        checkFunctionResult(fn(...arguments_), arguments_, dataset, contract);
      }
      for (let i = 0; i < payload.repetitions; i++) {
        const arguments_ = cloneArguments();
        const start = performance.now();
        const output = fn(...arguments_);
        const elapsed = (performance.now() - start) / 1000;
        checkFunctionResult(output, arguments_, dataset, contract);
        entry.timings_seconds.push(elapsed);
      }
      const arguments_ = cloneArguments();
      if (global.gc) global.gc();
      const before = process.memoryUsage().heapUsed;
      const output = fn(...arguments_);
      const after = process.memoryUsage().heapUsed;
      checkFunctionResult(output, arguments_, dataset, contract);
      entry.memory_bytes = after - before;
      const verified = contract.correctness === 'expected';
      entry.correct = verified ? true : null;
      entry.validation_status = verified ? 'verified' : 'unverified';
    } catch (error) { entry.error = String(error).slice(0, 1500) || 'candidate invocation failed'; }
  }
}

function benchmarkIndependentCases(payload, fn, result, clock = () => performance.now(), memory = () => process.memoryUsage().heapUsed) {
  const generic = isGeneric(payload);
  const descriptors = generic ? payload.datasets : payload.sizes.flatMap(size => payload.distributions.map(distribution => ({size, distribution})));
  for (const descriptor of descriptors) {
    const entry = {...(generic ? {case_id: descriptor.id, dimensions: {...(descriptor.dimensions || {})}, validation_status: 'failed'} : descriptor),
      correct: false, timings_seconds: [], memory_bytes: null, memory_metric: MEMORY_METRIC, error: null,
      measurement_version: 'independent-v1', timing_status: 'UNAVAILABLE', timing_error: 'Timing not reached',
      memory_status: 'UNAVAILABLE', memory_error: 'Memory not reached'};
    result.cases.push(entry);
    const behavior = {version: VALIDATION_VERSION, status: 'UNVERIFIED', validated_calls: 0, reason: 'No completed validation'};
    entry.behavioral_validation = behavior;
    const original = generic ? descriptor.args : [makeInput(descriptor.size, descriptor.distribution, payload.seed ?? 42)];
    const expected = generic ? null : [...original[0]].sort((a, b) => a - b);
    const clone = () => JSON.parse(JSON.stringify(original));
    const check = (output, args) => {
      if (generic) checkFunctionResult(output, args, descriptor, payload.contract);
      else checkResult(output, args[0], expected);
      behavior.validated_calls++;
    };
    const invoke = () => { const args = clone(); check(fn(...args), args); };
    try {
      for (let i = 0; i < 2; i++) invoke();
      let timingError = null, timingInvalid = false;
      for (let i = 0; i < payload.repetitions; i++) {
        const args = clone();
        let start = null;
        try { start = clock(); } catch { timingError = 'Timing instrumentation unavailable'; }
        const output = fn(...args);
        let elapsed = null;
        try { if (start !== null) elapsed = (clock() - start) / 1000; } catch { timingError = 'Timing instrumentation unavailable'; }
        check(output, args);
        if (elapsed !== null) {
          if (!Number.isFinite(elapsed) || elapsed < 0) { timingError = 'Invalid clock measurement'; timingInvalid = true; }
          else entry.timings_seconds.push(elapsed);
        }
      }
      if (timingError) Object.assign(entry, {timings_seconds: [], timing_status: timingInvalid ? 'INVALID' : 'UNAVAILABLE', timing_error: timingError});
      else if (entry.timings_seconds.every(t => t > 0)) Object.assign(entry, {timing_status: 'AVAILABLE', timing_error: null});
      else Object.assign(entry, {timing_status: 'INVALID', timing_error: 'Zero-duration timing samples'});
      const args = clone();
      let before = null, after = null;
      try { if (global.gc) global.gc(); before = memory(); } catch { entry.memory_error = 'Memory instrumentation unavailable'; }
      const output = fn(...args);
      try { after = memory(); } catch { entry.memory_error = 'Memory instrumentation unavailable'; }
      check(output, args); // A memory-phase behavioral failure remains correctness failure.
      if (before !== null && after !== null) {
        const bytes = after - before;
        if (Number.isSafeInteger(bytes)) Object.assign(entry, {memory_bytes: bytes, memory_status: 'AVAILABLE', memory_error: null});
        else Object.assign(entry, {memory_status: 'INVALID', memory_error: 'Invalid heap delta'});
      }
      const verified = !generic || payload.contract.correctness === 'expected';
      entry.correct = verified ? true : null;
      if (generic) entry.validation_status = verified ? 'verified' : 'unverified';
      Object.assign(behavior, {status: verified ? 'PASS' : 'UNVERIFIED', reason: verified ? 'All configured invocations validated' : 'No correctness oracle'});
    } catch (error) {
      if (error instanceof ContractViolation) Object.assign(behavior, {status: 'FAIL', reason: 'Functional contract violation'});
      entry.error = String(error).slice(0, 1500) || 'Candidate invocation failed';
      if (entry.timings_seconds.length && entry.timings_seconds.length !== payload.repetitions) {
        Object.assign(entry, {timing_status: 'INVALID', timing_error: 'Incomplete timing due to invocation failure'});
      }
    }
  }
}

function compile(candidate, language) {
  const ts = typescript();
  let source = candidate.source;
  if (language === 'typescript') {
    // transpileModule reports syntax/options diagnostics, not whole-program type errors.
    const compiled = ts.transpileModule(source, {
      fileName: 'candidate.ts', reportDiagnostics: true,
      compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
        isolatedModules: true},
    });
    const errors = (compiled.diagnostics || []).filter(d => d.category === ts.DiagnosticCategory.Error);
    if (errors.length) {
      throw new Error('TypeScript transpilation failed: ' + errors.map(d =>
        ts.flattenDiagnosticMessageText(d.messageText, '\n')).join('; ').slice(0, 1500));
    }
    source = compiled.outputText;
  }
  const module = {exports: {}};
  // vm supplies a lexical namespace, NOT a security boundary. Docker is the boundary.
  const context = vm.createContext({module, exports: module.exports, require, console, process,
    Buffer, setTimeout, clearTimeout, setInterval, clearInterval});
  new vm.Script(source, {filename: 'candidate.js'}).runInContext(context);
  const functionValue = new vm.Script(
    `typeof ${candidate.entrypoint} !== 'undefined' ? ${candidate.entrypoint} : module.exports[${JSON.stringify(candidate.entrypoint)}]`
  ).runInContext(context);
  if (typeof functionValue !== 'function' ||
      ['AsyncFunction', 'GeneratorFunction', 'AsyncGeneratorFunction'].includes(functionValue.constructor.name)) {
    throw new Error('entrypoint must be a named synchronous function');
  }
  return functionValue;
}

function benchmark(payload) {
  const ts = typescript();
  const candidate = payload.candidates[0];
  const result = {candidate: candidate.name, cases: [], error: null,
    structure: analyzeStructure(candidate, payload.language)};
  const message = {
    environment: {runtime: process.version, platform: `${os.platform()} ${os.arch()}`,
      warmups: 2, input_generator: isGeneric(payload) ? 'explicit-json-v1' : 'lcg32-v1'},
    result,
    tools: {node: process.version, typescript: ts.version,
      timing: 'node:perf_hooks.performance.now repeated samples', memory: MEMORY_METRIC},
  };
  if (payload.measurement_protocol === 'independent-v1') message.environment.measurement_protocol = 'independent-v1';
  if (payload.operation === 'structure') return message;
  let fn;
  try {
    if (isGeneric(payload)) validateFunctionPayload(payload);
    fn = compile(candidate, payload.language);
  }
  catch (error) { result.error = String(error).slice(0, 1500) || 'candidate compilation failed'; return message; }
  if (payload.measurement_protocol === 'independent-v1') {
    benchmarkIndependentCases(payload, fn, result);
    return message;
  }
  if (isGeneric(payload)) {
    benchmarkFunctionCases(payload, fn, result);
    return message;
  }
  for (const size of payload.sizes) {
    for (const distribution of payload.distributions) {
      const data = makeInput(size, distribution, payload.seed);
      const expected = [...data].sort((a, b) => a - b);
      const entry = {size, distribution, correct: false, timings_seconds: [],
        memory_bytes: null, memory_metric: MEMORY_METRIC, error: null};
      result.cases.push(entry);
      try {
        for (let i = 0; i < 2; i++) {
          const argument = [...data];
          checkResult(fn(argument), argument, expected);
        }
        for (let i = 0; i < payload.repetitions; i++) {
          const argument = [...data];
          const start = performance.now();
          const output = fn(argument);
          const elapsed = (performance.now() - start) / 1000;
          checkResult(output, argument, expected);
          entry.timings_seconds.push(elapsed);
        }
        // Separate run. Signed heapUsed delta is neither peak memory nor allocations.
        const argument = [...data];
        if (global.gc) global.gc();
        const before = process.memoryUsage().heapUsed;
        const output = fn(argument);
        const after = process.memoryUsage().heapUsed;
        checkResult(output, argument, expected);
        entry.memory_bytes = after - before;
        entry.correct = true;
      } catch (error) { entry.error = String(error).slice(0, 1500); }
    }
  }
  return message;
}

function supervise() {
  // Bounded stdin read, including when this entrypoint is invoked outside the controller.
  const chunks = [];
  let total = 0;
  const buffer = Buffer.alloc(65536);
  for (;;) {
    const count = fs.readSync(0, buffer, 0, buffer.length, null);
    if (!count) break;
    total += count;
    if (total > 1300000) throw new Error('worker input too large');
    chunks.push(Buffer.from(buffer.subarray(0, count)));
  }
  const directory = fs.mkdtempSync('/tmp/benchmark-');
  const resultPath = path.join(directory, 'result.json');
  try {
    const child = spawnSync(process.execPath, ['--expose-gc', __filename, '--child', resultPath], {
      input: Buffer.concat(chunks), stdio: ['pipe', 'ignore', 'ignore'], timeout: 115000,
    });
    if (child.error) throw child.error;
    if (child.status !== 0) throw new Error(`candidate harness exited with status ${child.status}`);
    const fd = fs.openSync(resultPath, 'r');
    try {
      const output = Buffer.alloc(2000001);
      let count = 0;
      while (count < output.length) {
        const read = fs.readSync(fd, output, count, output.length - count, null);
        if (!read) break;
        count += read;
      }
      if (count > 2000000) throw new Error('worker result too large');
      fs.writeSync(1, output.subarray(0, count));
    } finally { fs.closeSync(fd); }
  } finally { fs.rmSync(directory, {recursive: true, force: true}); }
}

if (require.main === module) {
  if (process.argv[2] === '--child') {
    const report = benchmark(JSON.parse(fs.readFileSync(0, 'utf8')));
    fs.writeFileSync(process.argv[3], JSON.stringify(report));
  } else supervise();
}
module.exports = {makeInput, checkResult, isGeneric, portableJSON, sameJSON,
  validateSchema, validateFunctionPayload, checkFunctionResult, analyzeStructure, benchmarkIndependentCases, matchesExpected};
