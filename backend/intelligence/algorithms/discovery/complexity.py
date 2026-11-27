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
    best = max(_key(term) for term in unique)
    kept = [term for term in unique if _key(term) == best]
    return kept[0] if len(kept) == 1 else ("add", kept)


_SUPERS = {2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹"}


def render(term, precedence=0):
    kind = term[0]
    if kind == "unknown":
        return "unknown"
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
    kinds: dict = field(default_factory=dict)           # name -> collection kind
    dims: dict = field(default_factory=dict)            # name -> canonical dimension term
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
        if name in self.dims:
            return self.dims[name]
        letter = LETTERS[len(self.bindings)]
        if letter in self.bindings.values():
            for candidate in LETTERS:
                if candidate not in self.bindings.values():
                    letter = candidate
                    break
        term = D(letter)
        self.dims[name] = term
        self.bindings[letter] = label or name
        return term


_ANNOTATION_KINDS = (
    (("dict", "Mapping", "Dict", "DefaultDict", "TypedDict"), "mapping"),
    (("set", "Set", "frozenset", "FrozenSet"), "set"),
    (("list", "List", "Sequence", "tuple", "Tuple", "deque", "Deque", "Iterable"), "sequence"),
)


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
        return UNK("size of an indexed element is not statically known") if allow_unknown else C(1)
    if isinstance(expr, (ast.ListComp, ast.SetComp, ast.DictComp)):
        return C(1)
    return UNK("size of this expression is not statically known") if allow_unknown else C(1)


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
        return C(1)
    if isinstance(expr, ast.Lambda):
        return C(1)
    if isinstance(expr, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        return comprehension_cost(expr, ctx, depth)
    if isinstance(expr, ast.BoolOp):
        return ADD(*(expression_cost(v, ctx, depth=depth + 1) for v in expr.values))
    if isinstance(expr, ast.BinOp):
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
        return expression_cost(expr.value, ctx, depth=depth + 1)
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
    total = C(1)
    for generator in expr.generators:
        trips = iteration_trips(generator.iter, ctx)
        body = ADD(C(1), *(expression_cost(cond, ctx, depth=depth + 1) for cond in generator.ifs))
        body = ADD(body, expression_cost(expr.value if isinstance(expr, ast.DictComp) else expr.elt,
                                         ctx, depth=depth + 1))
        total = ADD(total, MUL(trips, body))
    return total


def _operation_cost(node, ctx, depth=0):
    label = _call_label(node) or ""
    tail = label.rsplit(".", 1)[-1]
    receiver = node.func.value if isinstance(node.func, ast.Attribute) else None

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
        if tail in ("pop", "popitem") and node.args and isinstance(node.args[0], ast.Constant):
            size = collection_size(receiver, ctx)
            return size  # pop(0) / pop(index) shifts the remaining sequence
        return C(1)
    if tail in _GROWING_METHODS and receiver is not None:
        if tail in ("extend", "update", "insert", "appendleft"):
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
    start = expression_cost(node.args[0], ctx)
    stop = collection_size(node.args[1], ctx)
    if len(node.args) == 2:
        return stop if start[0] != "unknown" else stop
    step = node.args[2]
    if isinstance(step, ast.BinOp) and isinstance(step.op, (ast.FloorDiv, ast.Div)):
        base = collection_size(step.left, ctx)
        ctx.assume("A range step that divides the bound each iteration yields a logarithmic trip count.")
        return LOG(base) if base[0] != "unknown" else base
    if isinstance(step, ast.Constant) and isinstance(step.value, int) and abs(step.value) >= 1:
        return stop
    return UNK("range() step does not establish a trip count")


# --------------------------------------------------------------------------- #
# Statement / block analysis
# --------------------------------------------------------------------------- #

def _enclosing_loops(node, root):
    loops = []
    parent = getattr(node, "_parent", None)
    while parent is not None and parent is not root:
        if isinstance(parent, (ast.For, ast.AsyncFor, ast.While)):
            loops.append(parent)
        parent = getattr(parent, "_parent", None)
    return loops


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
        return ADD(block_cost(statement.body, ctx, depth + 1), block_cost(statement.orelse, ctx, depth + 1))
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


def _removals_inside(loop, ctx):
    """Subjects reduced inside the loop body and the lines that reduce them."""
    found = []
    for child in ast.walk(loop):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) and child is not loop:
            continue
        if not isinstance(child, ast.Call):
            continue
        label = _call_label(child) or ""
        tail = label.rsplit(".", 1)[-1]
        receiver = child.func.value if isinstance(child.func, ast.Attribute) else None
        if tail in _REMOVING_METHODS and isinstance(receiver, ast.Name):
            found.append((receiver.id, getattr(child, "lineno", 0)))
        elif tail == "heappop" and child.args and isinstance(child.args[0], ast.Name):
            found.append((child.args[0].id, getattr(child, "lineno", 0)))
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
    body = block_cost(loop.body, ctx, depth + 1)
    trailing = block_cost(getattr(loop, "orelse", None), ctx, depth + 1)
    if trips[0] == "unknown":
        return ADD(MUL(UNK(trips[1]), body), trailing)
    return ADD(MUL(trips, body), trailing)


def while_trips(loop, ctx):
    test = loop.test
    if isinstance(test, ast.Name):
        subject = test.id
        removals = [line for name, line in _removals_inside(loop, ctx) if name == subject]
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
        return UNK("while-loop trip count depends on a runtime comparison")
    if isinstance(test, ast.Call) and (_call_label(test) or "") in ("len", "bool"):
        return collection_size(test.args[0], ctx) if test.args else UNK("while-loop bound is not visible")
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


def _argument_shape(argument):
    if isinstance(argument, ast.BinOp) and isinstance(argument.op, (ast.Sub, ast.Add)):
        if isinstance(argument.right, ast.Constant) and isinstance(argument.right.value, (int, float)):
            return "decrease" if isinstance(argument.op, ast.Sub) else "increase"
    if isinstance(argument, ast.BinOp) and isinstance(argument.op, (ast.FloorDiv, ast.Div, ast.RShift)):
        return "halving"
    if isinstance(argument, ast.Name):
        return "same"
    return "unknown"


def recursion_cost(node, name, ctx):
    calls = _self_calls(node, name)
    if not calls:
        return None
    shapes = sorted({_argument_shape(argument) for call in calls for argument in call.args} or {"unknown"})
    inside_loops = sum(1 for call in calls if _enclosing_loops(call, node))
    if shapes == ["decrease"] or shapes == ["decrease", "unknown"]:
        ctx.note(f"Direct recursion decrements an argument on every self-call, giving T(n) = T(n-1) + work.")
        return "linear", D("n")
    if shapes == ["halving"]:
        ctx.note("Direct recursion halves an argument on every self-call, giving T(n) = T(n/2) + work.")
        return "logarithmic", LOG(D("n"))
    if "increase" in shapes or (len(shapes) > 1 and "same" in shapes and inside_loops == 0 and len(calls) > 1):
        ctx.assume("Several self-calls per invocation without a shrinking argument can expand exponentially.")
        return "exponential", UNK("recursion branch factor is not bounded by syntax")
    if inside_loops:
        ctx.assume("Self-calls inside an iteration are bounded only when each element is expanded once; "
                   "the guard that would establish that is reported with the traversal evidence.")
        return "structure_bound", UNK("recursive work per element is not established")
    ctx.unknown("Direct recursion has no argument-shape evidence establishing a recurrence")
    return "unknown", UNK("recurrence cannot be established from syntax")


# --------------------------------------------------------------------------- #
# Structural refinements
# --------------------------------------------------------------------------- #

def _fact_kinds(facts, kind):
    return [fact for fact in facts if fact.kind == kind]


def traversal_refinement(facts, ctx):
    """Bound total work when an observed guard ensures each element is processed once."""
    adjacency = _fact_kinds(facts, "adjacency_iteration")
    if adjacency:
        bindings = {fact.binding for fact in adjacency if fact.binding}
        guarded = any(
            update.kind == "set_add" and any(
                guard.kind == "membership_guard" and guard.subject == update.subject
                and guard.related in bindings for guard in facts)
            for update in _fact_kinds(facts, "set_add"))
        if guarded:
            ctx.note("A membership guard precedes insertion into the tracked set on every adjacency path, "
                     "so each discovered element is expanded at most once.")
            return "V", "E"
    sentinel_tables: dict = {}
    for write in _fact_kinds(facts, "constant_indexed_write"):
        sentinel_tables.setdefault(write.subject, set()).add(write.related)
    qualified = {table: values for table, values in sentinel_tables.items() if len(values) >= 2}
    if qualified and _fact_kinds(facts, "constant_return") and _fact_kinds(facts, "while_loop") \
            and _fact_kinds(facts, "indexed_read"):
        table, values = sorted(qualified.items())[0]
        ctx.note(f"'{table}' is written with {len(values)} distinct constant sentinel states and read before "
                 "further exploration, so each element changes state a bounded number of times.")
        ctx.assume("The state guard is checked before an element is re-expanded on every inspected path.")
        return "V", "E"
    return None


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #

def estimate(node, name, facts=(), parameter_annotations=None, language="python"):
    """Return a bounded, auditable complexity record for one function."""
    context = Context(parameters=dict(parameter_annotations or {}))
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
        local_time = block_cost(list(getattr(node, "body", []) or [node.body] if isinstance(node, ast.Lambda) else node.body),
                                context)
        local_space, space_notes = _space(node, context)
    except (RecursionError, ValueError, TypeError, AttributeError) as error:  # pragma: no cover - defensive
        return _unknown_record(f"structural analysis could not be completed ({type(error).__name__})")

    refinement = traversal_refinement(facts, context)
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

    if any(_argument_shape(argument) in ("decrease", "halving")
           for call in _self_calls(node, name) for argument in call.args):
        depth_term = D("n")
        space_term = ADD(space_term, depth_term)
        derivation.append("Recursive calls consume call-stack space proportional to the recursion depth.")

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
        if isinstance(current, ast.Assign) and isinstance(current.value, (ast.ListComp, ast.SetComp, ast.DictComp)):
            trips = comprehension_cost(current.value, ctx, 0)
            term = trips
            for loop_trips in reversed(loops):
                term = MUL(loop_trips, term) if loop_trips[0] != "unknown" else UNK(loop_trips[1])
            terms.append(term)
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
