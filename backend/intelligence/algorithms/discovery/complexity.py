"""Static, evidence-referenced time and auxiliary-space complexity estimation.

Syntax only: submitted source is never executed, no measurement is inferred and
any bound that cannot be established is reported as unknown together with the
reason. Every estimate carries its dimensions, derivation and assumptions so a
reviewer can audit it without trusting a number.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

METHOD = "static-ast-complexity-v1"
LETTERS = ("n", "m", "p", "q", "r", "s", "t", "u", "w", "x", "y", "z")

_LIMITATIONS = (
    "Static syntax-derived bound: it is not a measurement and does not prove a runtime Big-O class.",
    "Dimensions denote the size of the referenced input or intermediate collection; the binding for each symbol is listed separately.",
    "Library costs use documented typical bounds (sorting, heap, hash membership); unresolved call targets make the bound unknown.",
    "The worst case is reported unless a case is explicitly labelled otherwise; average and amortized cases are not inferred from syntax.",
    "A bound derived from structural guards assumes the observed guard holds on every inspected path.",
)

_REMOVING_METHODS = frozenset({"pop", "popleft", "remove", "popitem"})
_GROWING_METHODS = frozenset({"append", "add", "extend", "insert", "update", "appendleft"})


# --------------------------------------------------------------------------- #
# Symbolic algebra
# --------------------------------------------------------------------------- #

def C(value):
    return ("const", int(value))


def UNK(reason):
    return ("unknown", str(reason)[:240])


def D(name):
    return ("dim", str(name))


def LOG(term):
    return ("log", term)


def _dims(term):
    if term[0] == "dim":
        return {term[1]: 1}
    if term[0] == "pow":
        return {term[1][1]: term[2]} if term[1][0] == "dim" else {}
    if term[0] in ("mul", "log"):
        out = {}
        for child in term[1:]:
            for name, exp in _dims(child).items():
                out[name] = out.get(name, 0) + exp
        return out
    if term[0] == "add":
        out = {}
        for child in term[1]:
            for name, exp in _dims(child).items():
                out[name] = max(out.get(name, 0), exp)
        return out
    return {}


def _logs(term):
    if term[0] == "log":
        return 1 + _logs(term[1])
    if term[0] == "pow":
        return _logs(term[1]) * term[2]
    if term[0] in ("mul", "add"):
        children = term[1] if term[0] == "add" else term[1:]
        return max((_logs(c) for c in children), default=0)
    return 0


def _key(term):
    dims = _dims(term)
    return (sum(dims.values()), len(dims), _logs(term))


def MUL(left, right):
    for term in (left, right):
        if term[0] == "unknown":
            return term
    if left[0] == "const" and left[1] == 1:
        return right
    if right[0] == "const" and right[1] == 1:
        return left
    if left[0] == "const" and right[0] == "const":
        return C(left[1] * right[1])
    if left == right and left[0] in ("dim", "log"):
        return ("pow", left, 2)
    return ("mul", left, right)


def ADD(*terms):
    flat = []
    for term in terms:
        if term[0] == "unknown":
            return term
        if term[0] == "add":
            flat.extend(term[1])
        elif term[0] == "const" and term[1] <= 1:
            continue
        else:
            flat.append(term)
    unique = []
    for term in flat:
        if term not in unique:
            unique.append(term)
    if not unique:
        return C(1)
    if len(unique) == 1:
        return unique[0]
    # Degree alone cannot compare independent dimensions (n² and m).
    # Drop a term only when the same monomial factors are dominated.
    def factors(term):
        kind = term[0]
        if kind == "const":
            return {}
        if kind in ("dim", "log"):
            return {render(term): 1}
        if kind == "pow":
            base = factors(term[1])
            return None if base is None else {k: v * term[2] for k, v in base.items()}
        if kind == "mul":
            left, right = factors(term[1]), factors(term[2])
            if left is None or right is None:
                return None
            return {k: left.get(k, 0) + right.get(k, 0) for k in left.keys() | right.keys()}
        return None

    forms = [factors(term) for term in unique]
    kept = []
    for index, term in enumerate(unique):
        form = forms[index]
        dominated = form is not None and any(
            other is not None and all(other.get(k, 0) >= v for k, v in form.items())
            and (other != form or other_index < index)
            for other_index, other in enumerate(forms) if other_index != index)
        if not dominated:
            kept.append(term)
    return kept[0] if len(kept) == 1 else ("add", kept)


_SUPERS = {2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹"}


def render(term, precedence=0):
    kind = term[0]
    if kind == "unknown":
        return "unknown"
    if kind == "exponential":
        return f"{term[1]}^{render(term[2])}"
    if kind == "const":
        return str(term[1])
    if kind == "dim":
        return str(term[1])
    if kind == "log":
        return "log " + render(term[1], 3)
    if kind == "pow":
        base = render(term[1], 3)
        exponent = term[2]
        return base + (_SUPERS.get(exponent, f"^{exponent}") if term[1][0] == "dim" else f"^{exponent}")
    if kind == "mul":
        left, right = term[1], term[2]
        body = render(left, 2) + ("·" if left[0] == "dim" and right[0] == "dim" else " ") + render(right, 2)
        return f"({body})" if precedence > 2 else body
    body = " + ".join(render(child, 1) for child in term[1])
    return f"({body})" if precedence > 1 else body


def big_o(term):
    if term[0] == "unknown":
        return None
    return "O(" + render(term) + ")" if term[0] != "const" or term[1] > 1 else "O(1)"


# --------------------------------------------------------------------------- #
# Analysis context
# --------------------------------------------------------------------------- #

@dataclass
class Context:
    parameters: dict = field(default_factory=dict)      # name -> annotation text
    shadowed: set = field(default_factory=set)
    functions: dict = field(default_factory=dict)
    active_calls: tuple = ()
    heap_module: bool = True
    kinds: dict = field(default_factory=dict)           # name -> collection kind
    dims: dict = field(default_factory=dict)            # name -> canonical dimension term
    elements: dict = field(default_factory=dict)        # loop scalars -> source collections
    bindings: dict = field(default_factory=dict)        # canonical letter -> source label
    derivation: list = field(default_factory=list)
    assumptions: list = field(default_factory=list)
    unknown_reasons: list = field(default_factory=list)
    evidence_lines: list = field(default_factory=list)  # (line, kind) hints for evidence refs
    refinements: list = field(default_factory=list)

    def note(self, text):
        if text not in self.derivation:
            self.derivation.append(text)

    def assume(self, text):
        if text not in self.assumptions:
            self.assumptions.append(text)

    def unknown(self, reason):
        if reason not in self.unknown_reasons:
            self.unknown_reasons.append(reason)

    def size(self, name, label=None):
        if not isinstance(name, str) or not name:
            return UNK("collection size is not statically known")
        if name in self.elements:
            owner = self.elements[name]
            return self.size(owner + ":element", owner + ":maximum element magnitude")
        if name in self.dims:
            return self.dims[name]
        if len(self.bindings) >= len(LETTERS):
            return UNK("input dimension limit reached")
        letter = LETTERS[len(self.bindings)]
        term = D(letter)
        self.dims[name] = term
        self.bindings[letter] = label or name
        return term


_ANNOTATION_KINDS = (
    (("dict", "Mapping", "Dict", "DefaultDict", "TypedDict"), "mapping"),
    (("set", "Set", "frozenset", "FrozenSet"), "set"),
    (("list", "List", "Sequence", "tuple", "Tuple", "deque", "Deque", "Iterable"), "sequence"),
)


_LITERAL_KINDS = ((ast.List, ast.ListComp, "list", "sequence"), (ast.Set, ast.SetComp, "set", "set"),
                  (ast.Dict, ast.DictComp, "dict", "mapping"))


def _bind_local_kinds(node, ctx):
    """Give a local the built-in kind it is created with, when that cannot change.

    Only a single top-level assignment from a list/set/dict literal, comprehension or
    unshadowed constructor qualifies; any other store (augmented, loop, nested or
    tuple target) leaves the local untyped, so its methods keep an unknown cost.
    """
    stores = {}
    for item in ast.walk(node):
        if isinstance(item, ast.Name) and isinstance(item.ctx, (ast.Store, ast.Del)):
            stores[item.id] = stores.get(item.id, 0) + 1
    for stmt in node.body:
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            continue
        name, value = stmt.targets[0].id, stmt.value
        if stores.get(name) != 1 or name in ctx.parameters or name in ctx.kinds:
            continue
        for literal, comprehension, constructor, kind in _LITERAL_KINDS:
            if (isinstance(value, (literal, comprehension))
                    or isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                    and value.func.id == constructor and constructor not in ctx.shadowed
                    and constructor not in ctx.parameters
                    and stores.get(constructor) is None):
                ctx.kinds[name] = kind
                break


def annotation_kind(annotation):
    if not isinstance(annotation, str):
        return None
    text = annotation.replace(" ", "")
    for needles, kind in _ANNOTATION_KINDS:
        if any(needle in text for needle in needles):
            return kind
    return None


# --------------------------------------------------------------------------- #
# Expression analysis
# --------------------------------------------------------------------------- #

def _call_label(node):
    parts = []
    value = node.func if isinstance(node, ast.Call) else node
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if not isinstance(value, ast.Name):
        return None
    parts.append(value.id)
    return ".".join(reversed(parts))


def _literal_size(node):
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return C(max(1, abs(node.value)))
    if isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        return C(len(node.elts if not isinstance(node, ast.Dict) else node.keys))
    return None


def collection_size(expr, ctx, *, allow_unknown=True):
    """Symbolic size of an expression, or an explicit unknown."""
    if expr is None:
        return UNK("expression is absent")
    literal = _literal_size(expr)
    if literal is not None:
        return literal
    if isinstance(expr, ast.Name):
        return ctx.size(expr.id)
    if isinstance(expr, ast.Call):
        label = _call_label(expr) or ""
        tail = label.rsplit(".", 1)[-1]
        if tail == "len" and expr.args:
            return collection_size(expr.args[0], ctx, allow_unknown=allow_unknown)
        if tail in ("list", "set", "tuple", "deque", "frozenset", "enumerate", "reversed", "sorted", "copy") and expr.args:
            return collection_size(expr.args[0], ctx, allow_unknown=allow_unknown)
        if tail in ("keys", "values", "items") and isinstance(expr.func, ast.Attribute):
            return collection_size(expr.func.value, ctx, allow_unknown=allow_unknown)
        if tail == "update" and expr.args:
            return collection_size(expr.args[0], ctx, allow_unknown=allow_unknown)
        if tail in ("get", "pop", "popitem") and isinstance(expr.func, ast.Attribute):
            return collection_size(expr.func.value, ctx, allow_unknown=allow_unknown)
        return UNK(f"size of call '{label}' is not statically known") if allow_unknown else C(1)
    if isinstance(expr, ast.Attribute):
        return collection_size(expr.value, ctx, allow_unknown=allow_unknown)
    if isinstance(expr, ast.Subscript):
        if isinstance(expr.slice, ast.Slice):
            return collection_size(expr.value, ctx, allow_unknown=allow_unknown)
        return UNK("size of an indexed element is not statically known") if allow_unknown else C(1)
    if isinstance(expr, (ast.ListComp, ast.SetComp, ast.DictComp)):
        cardinality = C(1)
        for generator in expr.generators:
            cardinality = MUL(cardinality, iteration_trips(generator.iter, ctx))
        return cardinality
    return UNK("size of this expression is not statically known") if allow_unknown else C(1)


def _alias_size(statement, ctx):
    """Let a collection copied from an input share that input's dimension.

    ``remaining = list(tasks)`` or ``heap = [... for t in tasks]`` has the size of
    ``tasks``; giving it a fresh letter would invent an unrelated input.
    """
    value = getattr(statement, "value", None)
    targets = getattr(statement, "targets", None) or [getattr(statement, "target", None)]
    if value is None or len(targets) != 1 or not isinstance(targets[0], ast.Name):
        return
    name = targets[0].id
    if name in ctx.dims or name in ctx.parameters:
        return
    if isinstance(value, ast.Name) or _literal_size(value) is not None:
        return
    source = value
    while isinstance(source, ast.Call) and source.args:
        source = source.args[0]
    if isinstance(source, (ast.ListComp, ast.SetComp, ast.DictComp)) and len(source.generators) == 1:
        source = source.generators[0].iter
    if not isinstance(source, ast.Name):
        return
    size = collection_size(value, ctx)
    if size[0] == "dim":
        ctx.dims[name] = size


def _sorted_cost(value, ctx):
    size = collection_size(value, ctx)
    return MUL(size, LOG(size)) if size[0] != "unknown" else size


def expression_cost(expr, ctx, *, depth=0):
    """Worst-case cost of evaluating an expression once."""
    if expr is None or depth > 24:
        return C(1) if expr is None else UNK("expression nesting exceeded the analysis bound")
    if isinstance(expr, ast.Constant):
        return C(1)
    if isinstance(expr, ast.Name):
        return C(1)
    if isinstance(expr, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        children = [*expr.keys, *expr.values] if isinstance(expr, ast.Dict) else expr.elts
        return ADD(C(1), *(expression_cost(child, ctx, depth=depth + 1) for child in children))
    if isinstance(expr, ast.Lambda):
        return C(1)
    if isinstance(expr, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        return comprehension_cost(expr, ctx, depth)
    if isinstance(expr, ast.BoolOp):
        return ADD(*(expression_cost(v, ctx, depth=depth + 1) for v in expr.values))
    if isinstance(expr, ast.BinOp):
        if isinstance(expr.op, ast.Mult):
            for value, count in ((expr.left, expr.right), (expr.right, expr.left)):
                if isinstance(value, (ast.List, ast.Tuple)):
                    return ADD(expression_cost(value, ctx, depth=depth + 1),
                               MUL(collection_size(value, ctx), collection_size(count, ctx)))
        return ADD(expression_cost(expr.left, ctx, depth=depth + 1),
                   expression_cost(expr.right, ctx, depth=depth + 1))
    if isinstance(expr, ast.UnaryOp):
        return expression_cost(expr.operand, ctx, depth=depth + 1)
    if isinstance(expr, ast.Compare):
        costs = [expression_cost(expr.left, ctx, depth=depth + 1)]
        for op, other in zip(expr.ops, expr.comparators):
            if isinstance(op, (ast.In, ast.NotIn)):
                costs.append(_membership_cost(other, expr.left, ctx))
            else:
                costs.append(expression_cost(other, ctx, depth=depth + 1))
        return ADD(*costs)
    if isinstance(expr, ast.IfExp):
        return ADD(expression_cost(expr.test, ctx, depth=depth + 1),
                   expression_cost(expr.body, ctx, depth=depth + 1),
                   expression_cost(expr.orelse, ctx, depth=depth + 1))
    if isinstance(expr, ast.Subscript):
        base = expression_cost(expr.value, ctx, depth=depth + 1)
        if isinstance(expr.slice, ast.Slice):
            ctx.assume("Slicing uses ordinary built-in list semantics and copies at most the input length.")
            bounds = (expr.slice.lower, expr.slice.upper, expr.slice.step)
            return ADD(base, collection_size(expr.value, ctx),
                       *(expression_cost(bound, ctx, depth=depth + 1) for bound in bounds))
        return ADD(base, expression_cost(expr.slice, ctx, depth=depth + 1))
    if isinstance(expr, ast.Attribute):
        return expression_cost(expr.value, ctx, depth=depth + 1)
    if isinstance(expr, ast.Starred):
        return expression_cost(expr.value, ctx, depth=depth + 1)
    if isinstance(expr, ast.JoinedStr):
        return ADD(*(expression_cost(v, ctx, depth=depth + 1) for v in expr.values))
    if isinstance(expr, ast.FormattedValue):
        return expression_cost(expr.value, ctx, depth=depth + 1)
    if isinstance(expr, ast.Await):
        return expression_cost(expr.value, ctx, depth=depth + 1)
    if isinstance(expr, ast.Yield):
        return expression_cost(expr.value, ctx, depth=depth + 1)
    if isinstance(expr, ast.YieldFrom):
        return expression_cost(expr.value, ctx, depth=depth + 1)
    if isinstance(expr, ast.Call):
        return call_cost(expr, ctx, depth)
    return UNK(f"expression form '{type(expr).__name__}' is not costed")


def _membership_cost(container, subject, ctx):
    size = collection_size(container, ctx)
    ctx.assume("A membership test is bounded by the container size; hash-based containers are typically constant time.")
    return size


def comprehension_cost(expr, ctx, depth):
    body = expression_cost(expr.value if isinstance(expr, ast.DictComp) else expr.elt, ctx, depth=depth + 1)
    if isinstance(expr, ast.DictComp):
        body = ADD(body, expression_cost(expr.key, ctx, depth=depth + 1))
    for generator in reversed(expr.generators):
        trips = iteration_trips(generator.iter, ctx)
        conditions = ADD(C(1), *(expression_cost(cond, ctx, depth=depth + 1) for cond in generator.ifs))
        body = ADD(expression_cost(generator.iter, ctx, depth=depth + 1), MUL(trips, ADD(conditions, body)))
    return body


def _operation_cost(node, ctx, depth=0):
    label = _call_label(node) or ""
    tail = label.rsplit(".", 1)[-1]
    receiver = node.func.value if isinstance(node.func, ast.Attribute) else None
    if label in ctx.functions:
        callee = ctx.functions[label]
        formal = [*callee.args.posonlyargs, *callee.args.args]
        if (callee.decorator_list or callee.args.vararg or callee.args.kwarg or callee.args.kwonlyargs
                or node.keywords or len(formal) != len(node.args) or label in ctx.active_calls
                or len(ctx.active_calls) >= 3 or len(callee.body) != 1 or not isinstance(callee.body[0], ast.Return)):
            return UNK(f"Body or signature of '{label}' exceeds the supported call summary")
        nested = Context(parameters={p.arg: "" for p in formal}, shadowed=ctx.shadowed | {p.arg for p in formal},
                         functions=ctx.functions, active_calls=(*ctx.active_calls, label), heap_module=ctx.heap_module)
        nested.dims = {p.arg: collection_size(arg, ctx) for p, arg in zip(formal, node.args)}
        result = expression_cost(callee.body[0].value, nested, depth=depth + 1)
        if set(nested.bindings):
            return UNK(f"'{label}' depends on an unbound dimension")
        for assumption in nested.assumptions:
            ctx.assume(assumption)
        ctx.note(f"Line {node.lineno} uses the body of '{label}' at line {callee.lineno} with substituted arguments.")
        return result
    if receiver is None and label in ctx.shadowed:
        return UNK(f"'{label}' is shadowed and cannot use a built-in cost")
    if receiver is not None and tail not in {"heapify", "heappop", "heappush"}:
        if not isinstance(receiver, ast.Name) or receiver.id not in ctx.kinds:
            return UNK(f"The receiver of '{label}' has no established built-in collection type")
    if tail in {"heapify", "heappop", "heappush"} and (label != "heapq." + tail or not ctx.heap_module):
        return UNK(f"'{label}' does not resolve to the heapq module")

    if tail == "sorted":
        return _sorted_cost(node.args[0], ctx) if node.args else UNK("sorted() without a visible argument")
    if tail == "sort" and receiver is not None:
        return _sorted_cost(receiver, ctx)
    if tail in ("heapify",):
        return collection_size(node.args[0], ctx) if node.args else UNK("heapify() without a visible argument")
    if tail in ("heappush", "heappop"):
        target = node.args[0] if node.args else receiver
        size = collection_size(target, ctx) if target is not None else UNK("heap operation target is unknown")
        return LOG(size) if size[0] != "unknown" else size
    if tail in _REMOVING_METHODS and receiver is not None:
        if tail == "remove" or tail == "pop" and node.args:
            size = collection_size(receiver, ctx)
            return size  # pop(0) / pop(index) shifts the remaining sequence
        return C(1)
    if tail in _GROWING_METHODS and receiver is not None:
        if tail == "insert":
            return collection_size(receiver, ctx)
        if tail in ("extend", "update"):
            argument = node.args[0] if node.args else None
            return collection_size(argument, ctx) if argument is not None else C(1)
        return C(1)
    if tail in ("get", "setdefault", "has_key", "contains", "index", "count") and receiver is not None:
        if tail == "index":
            return collection_size(receiver, ctx)
        if tail == "count":
            return collection_size(receiver, ctx)
        return C(1)
    if tail in ("keys", "values", "items") and receiver is not None:
        return C(1)
    if tail in ("add", "difference_update", "intersection_update", "symmetric_difference_update") and receiver is not None:
        return C(1)
    if tail in ("update",) and receiver is not None:
        return collection_size(node.args[0], ctx) if node.args else C(1)
    if label in ("len", "abs", "hash", "id", "bool", "int", "float", "str", "ord", "divmod"):
        return C(1)
    if label in ("deque", "list", "set", "tuple", "frozenset", "Counter", "defaultdict", "OrderedDict",
                 "LifoQueue", "Queue", "PriorityQueue", "deque_popleft"):
        return collection_size(node.args[0], ctx) if node.args else C(1)
    if label in ("min", "max", "sum", "any", "all", "list", "set", "tuple", "dict", "frozenset", "join", "enumerate", "zip"):
        if node.args:
            return collection_size(node.args[0], ctx, allow_unknown=False) if label in (
                "min", "max", "sum", "any", "all", "list", "set", "tuple", "dict", "frozenset", "enumerate", "zip") else C(1)
        return C(1)
    if label == "range":
        return C(1)
    if receiver is not None and isinstance(receiver, ast.Name) and receiver.id in ctx.kinds:
        ctx.unknown(f"call '{label}' on a collection is not a documented operation; its cost is unknown")
        return UNK(f"cost of '{label}' is unknown")
    if label and "." not in label and label in ctx.parameters:
        ctx.unknown(f"call '{label}' targets a parameter; its cost is unknown")
        return UNK(f"cost of call '{label}' is unknown")
    if label:
        ctx.unknown(f"call target '{label}' is not statically resolvable to a documented operation")
        return UNK(f"cost of call '{label}' is unknown")
    return UNK("call target is not a lexical name")


def call_cost(node, ctx, depth=0):
    """A call costs its documented operation plus the cost of its arguments."""
    operation = _operation_cost(node, ctx, depth)
    arguments = [expression_cost(argument, ctx, depth=depth + 1)
                 for argument in (getattr(node, "args", None) or [])]
    if isinstance(node.func, ast.Attribute):
        arguments.append(expression_cost(node.func.value, ctx, depth=depth + 1))
    arguments.extend(expression_cost(keyword.value, ctx, depth=depth + 1) for keyword in node.keywords)
    return ADD(operation, *arguments)


def iteration_trips(iterable, ctx):
    """Trip count of a single iteration clause."""
    if iterable is None:
        return UNK("iterable is absent")
    if isinstance(iterable, ast.Call):
        label = _call_label(iterable) or ""
        tail = label.rsplit(".", 1)[-1]
        if tail == "range":
            return _range_trips(iterable, ctx)
        if tail in ("enumerate", "reversed", "sorted", "list", "set", "tuple", "zip", "keys", "values", "items") and iterable.args:
            if tail == "zip":
                return collection_size(iterable.args[0], ctx)
            if tail in ("keys", "values", "items") and isinstance(iterable.func, ast.Attribute):
                return collection_size(iterable.func.value, ctx)
            return collection_size(iterable.args[0], ctx)
        if tail in ("keys", "values", "items") and isinstance(iterable.func, ast.Attribute):
            return collection_size(iterable.func.value, ctx)
        return UNK(f"iterable '{label}' has no statically known trip count")
    if isinstance(iterable, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
        return _literal_size(iterable)
    if isinstance(iterable, ast.Name):
        return ctx.size(iterable.id)
    if isinstance(iterable, ast.Attribute):
        return collection_size(iterable, ctx)
    if isinstance(iterable, ast.Subscript):
        return collection_size(iterable, ctx)
    return UNK("iterable form has no statically known trip count")


def _range_trips(node, ctx):
    if not node.args:
        return UNK("range() has no arguments")
    if len(node.args) == 1:
        return collection_size(node.args[0], ctx)
    # With independent signed endpoints, |stop-start| <= |start|+|stop|.
    start = collection_size(node.args[0], ctx)
    stop = collection_size(node.args[1], ctx)
    if len(node.args) == 2:
        return ADD(start, stop)
    step = node.args[2]
    # range evaluates a fixed additive step once, not a multiplicative update.
    if isinstance(step, ast.BinOp) and isinstance(step.op, (ast.FloorDiv, ast.Div)):
        return UNK("range step is computed once; its positivity and magnitude are not established")
    if isinstance(step, ast.Constant) and isinstance(step.value, int) and abs(step.value) >= 1:
        return ADD(start, stop)
    return UNK("range() step does not establish a trip count")


def _bind_copied_sizes(node, ctx):
    """A nonescaping local copy subject only to permutation/removal cannot grow."""
    uses = {}
    for item in ast.walk(node):
        if isinstance(item, ast.Name):
            uses.setdefault(item.id, []).append(item)
    for stmt in node.body:
        if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            continue
        target, value = stmt.targets[0], stmt.value
        if isinstance(value, ast.Call) and _call_label(value) == "list" and len(value.args) == 1:
            iterable = value.args[0]
        elif isinstance(value, ast.ListComp) and len(value.generators) == 1:
            iterable = value.generators[0].iter
        else:
            continue
        if not isinstance(iterable, ast.Name) or iterable.id not in ctx.parameters:
            continue
        for use in uses[target.id]:
            parent = use._parent
            if use is target or isinstance(parent, ast.While) and parent.test is use:
                continue
            if isinstance(parent, ast.Attribute) and parent.attr in {"sort", "pop", "reverse"}:
                call = parent._parent
                if isinstance(call, ast.Call) and call.func is parent:
                    continue
            if isinstance(parent, ast.Call) and _call_label(parent) in {"heapq.heapify", "heapq.heappop"}:
                continue
            break
        else:
            ctx.dims[target.id] = ctx.size(iterable.id)
            ctx.note(f"'{target.id}' is a fresh list bounded by the length of '{iterable.id}' throughout its uses.")


# --------------------------------------------------------------------------- #
# Statement / block analysis
# --------------------------------------------------------------------------- #

def _index_parents(node):
    for child in ast.walk(node):
        for field_name in ("body", "orelse", "finalbody", "handlers"):
            value = getattr(child, field_name, None)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST):
                        setattr(item, "_parent", child)
        for field_name, value in ast.iter_fields(child):
            if field_name in ("body", "orelse", "finalbody", "handlers"):
                continue
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, ast.AST) and not hasattr(item, "_parent"):
                        setattr(item, "_parent", child)
            elif isinstance(value, ast.AST) and not hasattr(value, "_parent"):
                setattr(value, "_parent", child)


def block_cost(statements, ctx, depth=0):
    total = C(1)
    for statement in statements or []:
        total = ADD(total, statement_cost(statement, ctx, depth))
    return total


def statement_cost(statement, ctx, depth=0):
    if depth > 32:
        return UNK("statement nesting exceeded the analysis bound")
    if statement is None:
        return C(1)
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return C(1)  # nested definitions are analysed as their own functions
    if isinstance(statement, (ast.For, ast.AsyncFor, ast.While)):
        return loop_cost(statement, ctx, depth)
    if isinstance(statement, ast.If):
        return ADD(expression_cost(statement.test, ctx, depth=depth + 1),
                   block_cost(statement.body, ctx, depth + 1), block_cost(statement.orelse, ctx, depth + 1))
    if isinstance(statement, _tries()):
        total = block_cost(statement.body, ctx, depth + 1)
        for handler in statement.handlers:
            total = ADD(total, block_cost(handler.body, ctx, depth + 1))
        return ADD(total, block_cost(getattr(statement, "finalbody", None), ctx, depth + 1))
    if isinstance(statement, (ast.With, ast.AsyncWith)):
        return ADD(*(expression_cost(item.context_expr, ctx, depth=depth + 1) for item in statement.items),
                   block_cost(statement.body, ctx, depth + 1))
    if isinstance(statement, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
        value = statement.value
        _alias_size(statement, ctx)
        return expression_cost(value, ctx, depth=depth + 1) if value is not None else C(1)
    if isinstance(statement, ast.AugAssign):
        return ADD(expression_cost(statement.value, ctx, depth=depth + 1),
                   expression_cost(statement.target, ctx, depth=depth + 1))
    if isinstance(statement, ast.Return):
        return expression_cost(statement.value, ctx, depth=depth + 1)
    if isinstance(statement, ast.Expr):
        return expression_cost(statement.value, ctx, depth=depth + 1)
    if isinstance(statement, (ast.Raise, ast.Assert)):
        parts = [getattr(statement, "exc", None), getattr(statement, "cause", None)]
        if isinstance(statement, ast.Assert):
            parts = [statement.test]
        return ADD(*(expression_cost(part, ctx, depth=depth + 1) for part in parts if part is not None) or (C(1),))
    if isinstance(statement, (ast.Delete, ast.Pass, ast.Break, ast.Continue)):
        return C(1)
    if isinstance(statement, (ast.Global, ast.Nonlocal, ast.Import, ast.ImportFrom)):
        return C(1)
    if isinstance(statement, ast.Match):  # pragma: no cover - Python 3.10+
        total = C(1)
        for case in statement.cases:
            total = ADD(total, block_cost(case.body, ctx, depth + 1))
        return total
    return C(1)


def _tries():
    return (ast.Try,) + ((ast.TryStar,) if hasattr(ast, "TryStar") else ())


def _removals_inside(loop):
    """Only eager calls in the straight-line prefix can establish progress."""
    found = []
    for statement in loop.body:
        if not isinstance(statement, (ast.Expr, ast.Assign, ast.AnnAssign, ast.Pass)):
            break
        value = getattr(statement, "value", None)
        if not isinstance(value, ast.Call):
            continue
        calls = [value]
        while calls:
            child = calls.pop()
            calls.extend(arg for arg in child.args if isinstance(arg, ast.Call))
            label = _call_label(child) or ""
            receiver = child.func.value if isinstance(child.func, ast.Attribute) else None
            if label.rsplit(".", 1)[-1] in _REMOVING_METHODS and isinstance(receiver, ast.Name):
                found.append((receiver.id, child.lineno))
            elif label == "heapq.heappop" and child.args and isinstance(child.args[0], ast.Name):
                found.append((child.args[0].id, child.lineno))
    return found


def _growth_inside(loop):
    found = set()
    for child in ast.walk(loop):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) and child is not loop:
            continue
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
            receiver = child.func.value
            if isinstance(receiver, ast.Name) and child.func.attr in _GROWING_METHODS:
                found.add(receiver.id)
    return found


def loop_cost(loop, ctx, depth=0):
    trips = while_trips(loop, ctx) if isinstance(loop, ast.While) else iteration_trips(loop.iter, ctx)
    target = loop.target.id if isinstance(loop, ast.For) and isinstance(loop.target, ast.Name) else None
    if target:
        previous = ctx.dims.pop(target, None)
        previous_element = ctx.elements.pop(target, None)
        iterable = loop.iter
        if any(isinstance(n, ast.Name) and n.id == target and isinstance(n.ctx, ast.Store)
               for statement in loop.body for n in ast.walk(statement)):
            ctx.dims[target] = UNK("The loop binding is reassigned in the body")
        elif isinstance(iterable, ast.Call) and _call_label(iterable) == "range" and len(iterable.args) == 1:
            ctx.dims[target] = trips
        elif isinstance(iterable, ast.Name) and iterable.id in ctx.parameters:
            ctx.elements[target] = iterable.id
    body = block_cost(loop.body, ctx, depth + 1)
    if target:
        ctx.dims.pop(target, None)
        ctx.elements.pop(target, None)
        if previous is not None:
            ctx.dims[target] = previous
        if previous_element is not None:
            ctx.elements[target] = previous_element
    trailing = block_cost(getattr(loop, "orelse", None), ctx, depth + 1)
    if trips[0] == "unknown":
        return ADD(MUL(UNK(trips[1]), body), trailing)
    return ADD(MUL(trips, body), trailing)


def while_trips(loop, ctx):
    test = loop.test
    if isinstance(test, ast.Name):
        subject = test.id
        removals = [line for name, line in _removals_inside(loop) if name == subject]
        if removals:
            growth = _growth_inside(loop)
            if subject not in growth:
                size = ctx.size(subject)
                ctx.note(f"while loop over '{subject}' removes an element on every iteration and never grows it, "
                         f"so its trip count is bounded by the size of '{subject}'.")
                ctx.evidence_lines.extend(("call", line) for line in removals)
                return size
            ctx.assume(f"'{subject}' is both grown and reduced inside the loop; its trip count is not bounded by "
                       "its current size alone.")
        return UNK(f"while-loop trip count over '{subject}' depends on runtime mutation")
    if isinstance(test, ast.Compare):
        if (isinstance(test.left, ast.Name) and len(test.ops) == 1 and isinstance(test.ops[0], (ast.Gt, ast.GtE))
                and isinstance(test.comparators[0], ast.Constant) and type(test.comparators[0].value) is int
                and test.comparators[0].value >= int(isinstance(test.ops[0], ast.GtE))):
            subject = test.left.id
            writes = [n for s in loop.body for n in ast.walk(s)
                      if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id == subject]
            for s in loop.body:
                if not isinstance(s, (ast.AugAssign, ast.Assign, ast.Expr, ast.Pass)):
                    break
                if len(writes) != 1 or not isinstance(s, ast.AugAssign) or s.target is not writes[0]:
                    continue
                if not isinstance(s.value, ast.Constant) or type(s.value.value) is not int:
                    continue
                if isinstance(s.op, ast.FloorDiv) and s.value.value >= 2:
                    ctx.assume("Nonnegative integer loop counter with constant-cost arithmetic.")
                    ctx.note(f"Line {s.lineno} floor-divides '{subject}' by {s.value.value} on every continuing iteration.")
                    return LOG(ctx.size(subject))
                if isinstance(s.op, ast.Sub) and s.value.value > 0:
                    ctx.assume("Nonnegative integer loop counter with constant-cost arithmetic.")
                    return ctx.size(subject)
        return UNK("while-loop trip count depends on a runtime comparison")
    if isinstance(test, ast.Call) and (_call_label(test) or "") in ("len", "bool"):
        return UNK("while-loop progress is not established by a collection length check alone")
    if isinstance(test, ast.UnaryOp):
        return UNK("while-loop trip count depends on runtime state")
    return UNK("while-loop trip count is not statically established")


# --------------------------------------------------------------------------- #
# Recursion
# --------------------------------------------------------------------------- #

def _self_calls(node, name):
    calls = []
    for child in ast.walk(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) and child is not node:
            continue
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == name:
            calls.append(child)
    return calls


def recursion_cost(node, name, ctx):
    """A guarded one-parameter recurrence over fixed-cost integer expressions."""
    if not isinstance(node, ast.FunctionDef) or len(ctx.parameters) != 1 or len(node.body) != 2 or node.decorator_list:
        return None
    parameter, = ctx.parameters
    guard, step = node.body
    if not isinstance(guard, ast.If) or guard.orelse or len(guard.body) != 1 or not isinstance(guard.body[0], ast.Return):
        return None
    test = guard.test
    if (not isinstance(test, ast.Compare) or not isinstance(test.left, ast.Name) or test.left.id != parameter
            or len(test.ops) != 1 or not isinstance(test.ops[0], (ast.Lt, ast.LtE))
            or not isinstance(test.comparators[0], ast.Constant) or type(test.comparators[0].value) is not int):
        return None
    threshold = test.comparators[0].value - int(isinstance(test.ops[0], ast.Lt))
    if threshold < 0 or not isinstance(step, ast.Return):
        return None

    def scalar(expr):
        return ((isinstance(expr, ast.Constant) and type(expr.value) is int)
                or (isinstance(expr, ast.Name) and expr.id == parameter))

    if not scalar(guard.body[0].value):
        return None
    factors = []
    pending = [step.value]
    while pending:
        expr = pending.pop()
        if scalar(expr):
            continue
        if isinstance(expr, ast.BinOp) and isinstance(expr.op, (ast.Add, ast.Sub, ast.Mult)):
            pending.extend([expr.left, expr.right])
            continue
        if (not isinstance(expr, ast.Call) or _call_label(expr) != name or expr.keywords or len(expr.args) != 1):
            return None
        arg = expr.args[0]
        if (not isinstance(arg, ast.BinOp) or not isinstance(arg.left, ast.Name) or arg.left.id != parameter
                or not isinstance(arg.right, ast.Constant) or type(arg.right.value) is not int):
            return None
        if isinstance(arg.op, ast.Sub) and arg.right.value >= 1:
            factors.append("decreasing")
        elif isinstance(arg.op, ast.FloorDiv) and arg.right.value >= 2:
            factors.append("dividing")
        else:
            return None
    if not factors:
        return None
    size = ctx.size(parameter)
    depth = LOG(size) if set(factors) == {"dividing"} else size
    if len(factors) > 1 and depth != size:
        return None
    time = depth if len(factors) == 1 else ("exponential", len(factors), size)
    ctx.assume("Nonnegative integer input, fixed-cost scalar arithmetic and storage, unchanged function binding.")
    ctx.note(f"The base guard terminates inputs at or below {threshold}. Each remaining frame makes "
             f"{len(factors)} shrinking call(s) with constant local work; depth is bounded by {render(depth)}.")
    return time, depth


# --------------------------------------------------------------------------- #
# Structural refinements
# --------------------------------------------------------------------------- #

def _fact_kinds(facts, kind):
    return [fact for fact in facts if fact.kind == kind]


def traversal_refinement(node, facts, ctx):
    """Discharge a worklist bound only when the complete loop is accounted for."""
    adjacency = _fact_kinds(facts, "adjacency_iteration")
    if len(adjacency) != 1 or "traversal_unresolved" in adjacency[0].arguments:
        return None
    loops = [s for s in node.body if isinstance(s, ast.While)]
    if len(loops) != 1 or not isinstance(loops[0].test, ast.Name):
        return None
    loop = loops[0]
    queue = loop.test.id
    if loop.orelse or len(loop.body) != 2:
        return None
    remove, scan = loop.body
    if (not isinstance(remove, ast.Assign) or not isinstance(remove.value, ast.Call)
            or _call_label(remove.value) not in {queue + ".popleft", queue + ".pop"}
            or remove.value.args or remove.value.keywords):
        return None
    if (not isinstance(scan, ast.For) or not isinstance(scan.target, ast.Name) or scan.orelse
            or len(scan.body) != 1 or not isinstance(scan.body[0], ast.If)):
        return None
    guard = scan.body[0]
    test = guard.test
    if (not isinstance(test, ast.Compare) or len(test.ops) != 1 or not isinstance(test.ops[0], ast.NotIn)
            or not isinstance(test.left, ast.Name) or test.left.id != scan.target.id
            or not isinstance(test.comparators[0], ast.Name) or guard.orelse or len(guard.body) != 2):
        return None
    seen = test.comparators[0].id
    for stmt, label in zip(guard.body, (seen + ".add", queue + ".append")):
        if (not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call)
                or _call_label(stmt.value) != label or stmt.value.keywords or len(stmt.value.args) != 1
                or not isinstance(stmt.value.args[0], ast.Name) or stmt.value.args[0].id != scan.target.id):
            return None
    # No unrelated work or subsequent mutation may be hidden by this refinement.
    initial = {}
    for stmt in node.body:
        if stmt is loop:
            continue
        if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Name) and stmt.value.id == seen:
            continue
        if (not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name)
                or stmt.lineno >= loop.lineno or stmt.targets[0].id in initial):
            return None
        initial[stmt.targets[0].id] = stmt.value
    if set(initial) != {seen, queue} or not isinstance(initial[seen], ast.Set):
        return None
    seed = initial[queue]
    if isinstance(seed, ast.Call) and _call_label(seed) in {"deque", "collections.deque"} and len(seed.args) == 1 and not seed.keywords:
        seed = seed.args[0]
    elif _call_label(remove.value).endswith(".popleft"):
        return None
    if (not isinstance(seed, ast.List) or len(seed.elts) != 1 or not isinstance(seed.elts[0], ast.Name)
            or len(initial[seen].elts) != 1 or not isinstance(initial[seen].elts[0], ast.Name)
            or initial[seen].elts[0].id != seed.elts[0].id):
        return None
    ctx.assume("Finite adjacency lists, constant-cost deque operations and expected constant-time hashing of fixed-size vertices.")
    ctx.note("The membership guard adds the neighbor before enqueueing it. Each reachable vertex is queued once and each outgoing adjacency entry is visited once.")
    return "V", "E"


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #

def estimate(node, name, facts=(), parameter_annotations=None, language="python"):
    """Return a bounded, auditable complexity record for one function."""
    parameters = {arg.arg: "" for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)} if isinstance(
        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) else {}
    parameters.update(parameter_annotations or {})
    context = Context(parameters=parameters)
    for parameter, annotation in context.parameters.items():
        kind = annotation_kind(annotation)
        if kind:
            context.kinds[parameter] = kind

    if language != "python":
        return {
            "method": METHOD, "status": "unknown", "language": language,
            "time_complexity": None, "space_complexity": None,
            "dimensions": [], "dimension_bindings": {}, "derivation": [],
            "assumptions": [], "evidence_refs": [], "confidence": "none",
            "unknown_reasons": ["Static complexity estimation is implemented for Python in this milestone; "
                                "no bound is claimed for this language."],
            "limitations": list(_LIMITATIONS),
        }

    try:
        _index_parents(node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _bind_local_kinds(node, context)
            _bind_copied_sizes(node, context)
        local_time = (expression_cost(node.body, context) if isinstance(node, ast.Lambda)
                      else block_cost(node.body, context))
        local_space, space_notes = _space(node, context)
    except (RecursionError, ValueError, TypeError, AttributeError) as error:  # pragma: no cover - defensive
        return _unknown_record(f"structural analysis could not be completed ({type(error).__name__})")

    refinement = traversal_refinement(node, facts, context)
    dimensions = list(context.bindings)
    derivation = list(context.derivation)

    if refinement:
        nodes_dim, edges_dim = refinement
        if nodes_dim not in dimensions:
            dimensions.append(nodes_dim)
            context.bindings[nodes_dim] = dict(_GRAPH_BINDINGS)[nodes_dim]
        if edges_dim not in dimensions:
            dimensions.append(edges_dim)
            context.bindings[edges_dim] = dict(_GRAPH_BINDINGS)[edges_dim]
        derivation.append("Local loop algebra leaves the worklist trip count unbounded; the structural guard "
                          "above supplies the bound instead.")
        time_term = ADD(D(nodes_dim), D(edges_dim))
        space_term = local_space if local_space[0] != "unknown" else D(nodes_dim)
        status = "estimated"
        confidence = "medium"
        unknown_reasons = []
    else:
        time_term = local_time
        space_term = local_space
        status = "estimated" if time_term[0] != "unknown" and space_term[0] != "unknown" else (
            "partial" if time_term[0] != "unknown" or space_term[0] != "unknown" else "unknown")
        confidence = "high" if status == "estimated" and _key(time_term)[0] <= 2 else ("medium" if status == "estimated" else "low")
        unknown_reasons = list(context.unknown_reasons)
        if time_term[0] == "unknown":
            unknown_reasons.insert(0, "time: " + time_term[1])
        if space_term[0] == "unknown":
            unknown_reasons.insert(0, "space: " + space_term[1])

    if _self_calls(node, name) and not refinement:
        recurrence = recursion_cost(node, name, context)
        if recurrence:
            time_term, space_term = recurrence
            unknown_reasons = []
            derivation = list(context.derivation)
            dimensions = list(context.bindings)
            space_notes = ["One fixed-size stack frame per active call."]
            status, confidence = "estimated", "medium"
        else:
            time_term = UNK("Recursive recurrence and termination are not established")
            space_term = UNK("Recursive stack depth and retained allocations are not established")
            status, confidence = "unknown", "none"
            unknown_reasons.extend([time_term[1], space_term[1]])

    record = {
        "method": METHOD, "status": status, "language": language,
        "time_complexity": big_o(time_term), "space_complexity": big_o(space_term),
        "dimensions": dimensions, "dimension_bindings": dict(context.bindings),
        "derivation": derivation, "space_derivation": space_notes,
        "assumptions": list(context.assumptions), "evidence_refs": [],
        "evidence_lines": list(dict.fromkeys(context.evidence_lines)),
        "confidence": confidence, "unknown_reasons": list(dict.fromkeys(unknown_reasons)),
        "limitations": list(_LIMITATIONS),
    }
    if not record["time_complexity"]:
        record["time_complexity_reason"] = time_term[1] if time_term[0] == "unknown" else None
    if not record["space_complexity"]:
        record["space_complexity_reason"] = space_term[1] if space_term[0] == "unknown" else None
    return record


_GRAPH_BINDINGS = (
    ("V", "distinct elements reachable through the iterated adjacency structure"),
    ("E", "adjacency entries examined across the expanded elements"),
)


def _unknown_record(reason):
    return {
        "method": METHOD, "status": "unknown", "language": "python",
        "time_complexity": None, "space_complexity": None,
        "dimensions": [], "dimension_bindings": {}, "derivation": [],
        "space_derivation": [], "assumptions": [], "evidence_refs": [],
        "evidence_lines": [], "confidence": "none", "unknown_reasons": [reason],
        "limitations": list(_LIMITATIONS),
    }


def _space(node, ctx):
    """Auxiliary space: collections that grow, plus any recursion depth."""
    terms = []
    notes = []
    body = list(node.body) if not isinstance(node, ast.Lambda) else [node.body]
    stack = [(child, ()) for child in reversed(body)]
    seen = set()
    while stack:
        current, loops = stack.pop()
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and current is not node:
            continue
        if isinstance(current, ast.Lambda) and current is not node:
            continue
        if isinstance(current, (ast.For, ast.AsyncFor, ast.While)):
            trips = while_trips(current, ctx) if isinstance(current, ast.While) else iteration_trips(current.iter, ctx)
            stack.extend((child, loops + (trips,)) for child in reversed(list(current.body)))
            stack.extend((child, loops) for child in reversed(list(getattr(current, "orelse", None) or [])))
            continue
        if isinstance(current, (ast.If, ast.Try, ast.TryStar if hasattr(ast, "TryStar") else ast.Try,
                                ast.With, ast.AsyncWith, ast.Match)):
            for field_name in ("body", "orelse", "finalbody"):
                stack.extend((child, loops) for child in reversed(list(getattr(current, field_name, None) or [])))
            for handler in getattr(current, "handlers", None) or []:
                stack.extend((child, loops) for child in reversed(handler.body))
            if isinstance(current, ast.Match):
                for case in current.cases:
                    stack.extend((child, loops) for child in reversed(case.body))
            continue
        growth = _growth_term(current, ctx)
        if growth is not None and id(current) not in seen:
            seen.add(id(current))
            term = growth
            for trips in reversed(loops):
                term = MUL(trips, term) if trips[0] != "unknown" else UNK(trips[1])
            terms.append(term)
            notes.append(f"Collection growth at line {getattr(current, 'lineno', '?')} contributes "
                         f"{render(term) if term[0] != 'unknown' else 'an unknown amount'} of auxiliary space.")
        allocation = None
        if isinstance(current, ast.Subscript) and isinstance(current.slice, ast.Slice):
            allocation = collection_size(current.value, ctx)
            notes.append(f"Copied slice at line {current.lineno} includes storage for the resulting list.")
        if isinstance(current, ast.BinOp) and isinstance(current.op, ast.Mult):
            for value, count in ((current.left, current.right), (current.right, current.left)):
                if isinstance(value, (ast.List, ast.Tuple)):
                    allocation = MUL(collection_size(value, ctx), collection_size(count, ctx))
                    break
        if isinstance(current, (ast.ListComp, ast.SetComp, ast.DictComp)):
            allocation = collection_size(current, ctx)
            notes.append(f"Comprehension at line {current.lineno} materializes at most one entry per generator tuple.")
        if allocation is not None:
            for trips in loops:
                allocation = MUL(trips, allocation)
            terms.append(allocation)
        if isinstance(current, (ast.List, ast.Set, ast.Dict, ast.ListComp, ast.SetComp, ast.DictComp)):
            parent = getattr(current, "_parent", None)
            if isinstance(parent, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
                continue  # already counted through its comprehension trips
            if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Attribute):
                continue
            terms.append(C(1))
        stack.extend((child, loops) for child in reversed(list(ast.iter_child_nodes(current)))
                     if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)))
    if not terms:
        return C(1), notes
    return ADD(*terms), notes


def _growth_term(current, ctx):
    if not isinstance(current, ast.Call) or not isinstance(current.func, ast.Attribute):
        return None
    receiver = current.func.value
    if not isinstance(receiver, ast.Name) or current.func.attr not in _GROWING_METHODS:
        return None
    if current.func.attr in ("extend", "update", "insert"):
        argument = current.args[0] if current.args else None
        size = collection_size(argument, ctx) if argument is not None else C(1)
        return size if size[0] != "unknown" else C(1)
    return C(1)
