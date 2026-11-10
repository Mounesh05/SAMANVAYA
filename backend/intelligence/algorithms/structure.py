"""Bounded source-only Python structure observations; never load submitted code."""

import ast


__all__ = ["analyze_python"]

_MAX_SOURCE_BYTES = 200_000
_MAX_AST_NODES = 50_000
_MAX_FUNCTIONS = 128
_MAX_CALLS = 512
_MAX_ALLOCATIONS = 1024
_MAX_TEXT = 120
_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
_LOOPS = (ast.For, ast.AsyncFor, ast.While)
_TRIES = (ast.Try,) + ((ast.TryStar,) if hasattr(ast, "TryStar") else ())
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_ALLOCATIONS = {
    ast.List: "list_literal", ast.Tuple: "tuple_literal", ast.Set: "set_literal",
    ast.Dict: "dict_literal", ast.ListComp: "list_comprehension",
    ast.SetComp: "set_comprehension", ast.DictComp: "dict_comprehension",
    ast.GeneratorExp: "generator_expression",
}
_LIMITATIONS = (
    "Static observations only: no proven asymptotic complexity or Big-O bound, execution time, "
    "or runtime call graph is inferred.",
    "Calls are lexical names or dotted attributes only. Direct recursive calls count bare calls "
    "to the function's syntactic name, not runtime-resolved recursion; aliases, shadowing, "
    "dynamic dispatch, decorators and rebinding can change behavior.",
    "Loops include comprehension generator clauses. Nesting is syntactic, including generator "
    "expressions, not a statement about evaluation frequency or laziness.",
    "Branches are descriptive syntax counts, not McCabe/cyclomatic complexity: if, ifexp, "
    "match, match cases, boolop expressions, try blocks, except handlers and comprehension filters.",
    "Allocations are collection literal/comprehension and generator-expression sites only, "
    "not allocated bytes or peak allocation. Constructor calls are not proven allocations; "
    "constant folding and runtime behavior may differ.",
    "Function bodies exclude nested function/lambda bodies; their defaults, annotations and "
    "decorators are observed in the enclosing scope. Module-level code is not summarized. "
    "Names and entrypoint are labels only; entrypoint existence or callability is not validated.",
    "Lexical labels are limited to 120 characters and can be shortened; call labels are unique "
        "per function, not call-frequency counts.",
        "This source-only report is not a replacement for security review, quality analysis or testing.",
)


def _text(value):
    return value if len(value) <= _MAX_TEXT else value[:_MAX_TEXT - 3] + "..."


def _header(node):
    """Expressions evaluated outside a nested function's body."""
    return [child for field, value in ast.iter_fields(node) if field != "body"
            for child in (value if isinstance(value, list) else [value])
            if isinstance(child, ast.AST)]


def _discover(tree):
    functions = []
    stack = [(tree, "", None)]
    count = 0
    while stack:
        node, scope, binding = stack.pop()
        count += 1
        if count > _MAX_AST_NODES:
            raise ValueError(f"AST exceeds {_MAX_AST_NODES} nodes")
        child_scope = scope
        if isinstance(node, _FUNCTIONS):
            local = (binding or f"<lambda>@{node.lineno}:{node.col_offset}"
                     if isinstance(node, ast.Lambda) else node.name)
            name = f"{scope}.{local}" if scope else local
            functions.append((node, _text(name), binding if isinstance(node, ast.Lambda) else node.name))
            child_scope = name
        elif isinstance(node, ast.ClassDef):
            child_scope = f"{scope}.{node.name}" if scope else node.name
        assigned = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            assigned = node.targets[0].id
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and isinstance(node.target, ast.Name):
            assigned = node.target.id
        children = []
        for field, value in ast.iter_fields(node):
            for child in value if isinstance(value, list) else [value]:
                if isinstance(child, ast.AST):
                    # Defaults and decorators belong to the surrounding lexical scope.
                    scope_for_child = child_scope if field == "body" else scope
                    if not isinstance(node, _FUNCTIONS + (ast.ClassDef,)):
                        scope_for_child = scope
                    children.append((child, scope_for_child,
                                     assigned if field == "value" and isinstance(child, ast.Lambda) else None))
        stack.extend(reversed(children))
    return functions


def _call_name(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return _text(".".join(reversed(parts)))


def _observe(node, name, self_name, budget):
    result = {
        "name": name, "line": node.lineno, "end_line": node.end_lineno,
        "loops": 0, "max_loop_nesting": 0,
        "branches": dict.fromkeys(("if", "ifexp", "match", "match_cases", "boolop", "try",
                                   "except_handlers", "comprehension_filters"), 0),
        "direct_recursive_calls": 0, "calls": [], "allocations": [],
    }
    body = [node.body] if isinstance(node, ast.Lambda) else node.body
    stack = [(child, 0) for child in reversed(body)]
    seen_calls = set()
    while stack:
        current, depth = stack.pop()
        if isinstance(current, _FUNCTIONS):
            stack.extend((child, depth) for child in reversed(_header(current)))
            continue
        branches = result["branches"]
        if isinstance(current, ast.If):
            branches["if"] += 1
        elif isinstance(current, ast.IfExp):
            branches["ifexp"] += 1
        elif isinstance(current, ast.Match):
            branches["match"] += 1
            branches["match_cases"] += len(current.cases)
        elif isinstance(current, ast.BoolOp):
            branches["boolop"] += 1
        elif isinstance(current, _TRIES):
            branches["try"] += 1
        elif isinstance(current, ast.ExceptHandler):
            branches["except_handlers"] += 1
        if isinstance(current, ast.Call):
            if isinstance(current.func, ast.Name) and current.func.id == self_name:
                result["direct_recursive_calls"] += 1
            call = _call_name(current.func)
            if call is not None and call not in seen_calls:
                seen_calls.add(call)
                if budget["calls"]:
                    result["calls"].append(call)
                    budget["calls"] -= 1
                else:
                    budget["truncated"] = True
        kind = _ALLOCATIONS.get(type(current))
        if kind and not isinstance(getattr(current, "ctx", None), (ast.Store, ast.Del)):
            if budget["allocations"]:
                result["allocations"].append({"kind": kind, "line": current.lineno})
                budget["allocations"] -= 1
            else:
                budget["truncated"] = True
        if isinstance(current, _COMPREHENSIONS):
            # An iterable runs before its own generator loop, but within prior clauses.
            for index, generator in enumerate(current.generators):
                level = depth + index
                stack.append((generator.iter, level))
                stack.append((generator.target, level + 1))
                stack.extend((condition, level + 1) for condition in generator.ifs)
                branches["comprehension_filters"] += len(generator.ifs)
            level = depth + len(current.generators)
            result["loops"] += len(current.generators)
            result["max_loop_nesting"] = max(result["max_loop_nesting"], level)
            fields = [current.key, current.value] if isinstance(current, ast.DictComp) else [current.elt]
            stack.extend((child, level) for child in fields)
            continue
        if isinstance(current, _LOOPS):
            result["loops"] += 1
            result["max_loop_nesting"] = max(result["max_loop_nesting"], depth + 1)
            # Loop iterables/tests and else blocks are not inside that loop's body.
            for field, value in ast.iter_fields(current):
                for child in value if isinstance(value, list) else [value]:
                    if isinstance(child, ast.AST):
                        stack.append((child, depth + 1 if field == "body" else depth))
            continue
        stack.extend((child, depth) for child in reversed(list(ast.iter_child_nodes(current))))
    result["allocations"].sort(key=lambda site: site["line"])
    return result


def analyze_python(source, entrypoint):
    """Return a JSON-compatible, bounded report without executing or importing source.

    ``branches`` contains syntax-category counts; ``calls`` contains unique lexical
    labels per function. Reports are bounded below 1 MB even with JSON ASCII escaping.
    Missing entrypoints do not suppress observations of other functions.
    """
    report = {"status": "unavailable", "parser": "python.ast",
              "entrypoint": _text(entrypoint) if isinstance(entrypoint, str) else None,
              "functions": [], "limitations": list(_LIMITATIONS)}
    try:
        if not isinstance(source, str):
            raise ValueError("source must be a string")
        if not isinstance(entrypoint, str) or not entrypoint or len(entrypoint) > _MAX_TEXT:
            raise ValueError(f"entrypoint must be a nonempty string of at most {_MAX_TEXT} characters")
        if len(source) > _MAX_SOURCE_BYTES or len(source.encode("utf-8")) > _MAX_SOURCE_BYTES:
            raise ValueError(f"source exceeds {_MAX_SOURCE_BYTES} UTF-8 bytes")
        tree = ast.parse(source, filename="<submitted-source>", mode="exec")
        functions = _discover(tree)
        budget = {"calls": _MAX_CALLS, "allocations": _MAX_ALLOCATIONS,
                  "truncated": len(functions) > _MAX_FUNCTIONS}
        observed = [_observe(node, name, self_name, budget)
                    for node, name, self_name in functions[:_MAX_FUNCTIONS]]
        report.update(status="available", functions=observed)
        if budget["truncated"]:
            report["limitations"].append(
                "Output truncated: at most 128 functions, 512 call labels and 1024 allocation "
                "sites are retained across the report; retained function counts remain complete.")

    except (SyntaxError, RecursionError, ValueError, TypeError, UnicodeError, MemoryError, OverflowError) as exc:
        diagnostic = {"kind": type(exc).__name__, "message": _text(str(exc))}
        if isinstance(exc, SyntaxError):
            diagnostic.update(line=exc.lineno, column=exc.offset)
        report["diagnostics"] = [diagnostic]
    return report
