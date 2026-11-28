"""Python AST extraction. Never import, compile or evaluate submitted source."""

import ast

from intelligence.algorithms.structure import _discover, _observe, _call_name

FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def symbol(node):
    return _call_name(node) or ""


def extract(source: str, path: str) -> dict:
    tree = ast.parse(source, filename=path)
    discovered = _discover(tree)
    imports = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports[alias.asname or alias.name] = alias.name
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports[alias.asname or alias.name] = "." * node.level + (node.module or "") + "." + alias.name
    records = []
    truncated = len(discovered) > 128
    module_bindings = set(imports)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            module_bindings.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                if isinstance(target, ast.Name):
                    module_bindings.add(target.id)
    for function, qualified_name, binding in discovered[:128]:
        structure = _observe(function, qualified_name, binding, {"calls": 512, "allocations": 1024, "truncated": False})
        facts: list[dict] = []
        calls: list[dict] = []
        returns, assertions = [], []
        collections = {}
        queue = list(function.body if not isinstance(function, ast.Lambda) else [function.body])
        nodes = []
        while queue:
            node = queue.pop()
            if isinstance(node, FUNCTIONS + (ast.ClassDef,)):
                continue
            nodes.append(node)
            queue.extend(ast.iter_child_nodes(node))

        def fact(kind, node, subject="", related="", detail="", binding="", arguments=()):
            nonlocal truncated
            if len(facts) < 128:
                facts.append(dict(kind=kind, line=node.lineno, end_line=node.end_lineno,
                                  subject=subject[:120], related=related[:120], detail=detail[:160],
                                  binding=binding[:120], arguments=list(arguments)[:32]))
            else:
                truncated = True

        def collection_kind(value):
            if isinstance(value, (ast.List, ast.ListComp)):
                return "sequence"
            if isinstance(value, (ast.Set, ast.SetComp)):
                return "set"
            if isinstance(value, (ast.Dict, ast.DictComp)):
                return "mapping"
            if isinstance(value, ast.Call):
                label = symbol(value.func)
                canonical = imports.get(label, label)
                if label.split(".")[0] in local_bindings or label in {"list", "set", "dict"} & module_bindings:
                    return None
                return {"list": "sequence", "set": "set", "dict": "mapping",
                        "collections.deque": "sequence"}.get(canonical)
            return None

        local_bindings = {arg.arg for arg in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]}
        for node in nodes:
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                local_bindings.add(node.id)
        shadowed = module_bindings | local_bindings

        def adjacency(value):
            # Only a known builtin wrapper is transparent. Calls are syntax,
            # never evaluated, and arbitrary wrappers remain unknown.
            if (isinstance(value, ast.Call) and symbol(value.func) == "reversed"
                    and "reversed" not in shadowed and len(value.args) == 1 and not value.keywords):
                value = value.args[0]
            if isinstance(value, ast.Subscript):
                return value.value, value.slice
            if (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
                    and value.func.attr == "get" and len(value.args) == 2 and not value.keywords
                    and isinstance(value.args[1], (ast.List, ast.Tuple)) and not value.args[1].elts):
                return value.func.value, value.args[0]
            return None

        def linked_removals(loop, receiver, key, neighbor):
            """Conservative lexical dominance, not runtime/data-flow proof."""
            if not all(isinstance(n, ast.Name) for n in (receiver, key, loop.target)):
                return []
            parameters = {a.arg for a in [*function.args.posonlyargs, *function.args.args, *function.args.kwonlyargs]}
            if receiver.id not in parameters:
                return []
            stores = [n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]
            if stores.count(receiver.id) or stores.count(key.id) != 1 or stores.count(neighbor) != 1:
                return []
            for outer in nodes:
                if not isinstance(outer, ast.While) or not isinstance(outer.test, ast.Name):
                    continue
                sequence = outer.test.id
                if loop not in outer.body or stores.count(sequence) != 1:
                    continue
                initializers = [n for n in nodes if isinstance(n, (ast.Assign, ast.AnnAssign))
                                and n.lineno < outer.lineno and collection_kind(n.value) == "sequence"
                                and any(isinstance(t, ast.Name) and t.id == sequence for t in
                                        (n.targets if isinstance(n, ast.Assign) else [n.target]))]
                if not initializers:
                    continue
                preceding = outer.body[:outer.body.index(loop)]
                for take in preceding:
                    if not (isinstance(take, ast.Assign) and len(take.targets) == 1
                            and isinstance(take.targets[0], ast.Name) and take.targets[0].id == key.id
                            and isinstance(take.value, ast.Call) and isinstance(take.value.func, ast.Attribute)
                            and symbol(take.value.func.value) == sequence):
                        continue
                    appends = [n for n in ast.walk(loop) if isinstance(n, ast.Call)
                               and symbol(n.func) == sequence + ".append" and len(n.args) == 1
                               and symbol(n.args[0]) == neighbor]
                    if appends:
                        return [f"remove_line:{take.value.lineno}"]
            return []

        # Generic sentinel detection: names bound to literal constants inside this
        # function (e.g. `WHITE, GRAY, BLACK = 0, 1, 2`). No identifiers are named
        # in advance; a binding qualifies only because its value is a literal.
        literal_bindings: dict[str, str] = {}
        for bound in nodes:
            if not isinstance(bound, (ast.Assign, ast.AnnAssign)):
                continue
            targets = bound.targets if isinstance(bound, ast.Assign) else [bound.target]
            flat_targets = [t for target in targets
                            for t in (target.elts if isinstance(target, ast.Tuple) else [target])]
            values = bound.value.elts if isinstance(bound.value, ast.Tuple) else [bound.value]
            if len(flat_targets) != len(values):
                continue
            for target, value in zip(flat_targets, values):
                if isinstance(target, ast.Name) and isinstance(value, ast.Constant) \
                        and isinstance(value.value, (int, bool)):
                    literal_bindings[target.id] = repr(value.value)

        for node in nodes:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name) and node.value is not None:
                        kind = collection_kind(node.value)
                        if kind:
                            collections[target.id] = kind
                            fact("collection_binding", node, target.id, kind)
                    if isinstance(target, ast.Subscript):
                        fact("indexed_write", node, symbol(target.value), symbol(target.slice))
                        written = node.value
                        if isinstance(written, ast.Constant) and isinstance(written.value, (int, bool)):
                            fact("constant_indexed_write", node, symbol(target.value),
                                 repr(written.value), "Subscript write of a literal sentinel.")
                        elif isinstance(written, ast.Name) and written.id in literal_bindings:
                            fact("constant_indexed_write", node, symbol(target.value),
                                 literal_bindings[written.id],
                                 "Subscript write of a name bound to a literal sentinel.")
                    if isinstance(node.value, ast.Call) and isinstance(target, ast.Name):
                        call = node.value
                        if isinstance(call.func, ast.Attribute):
                            receiver, method = symbol(call.func.value), call.func.attr
                            if method == "popleft" or (method == "pop" and call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == 0):
                                fact("fifo_remove", call, receiver, target.id)
                            elif method == "pop" and not call.args:
                                fact("lifo_remove", call, receiver, target.id)
            if isinstance(node, (ast.For, ast.AsyncFor)):
                fact("iteration", node, symbol(node.iter), symbol(node.target))
                indexed = adjacency(node.iter)
                if indexed:
                    receiver, key = indexed
                    links = linked_removals(node, receiver, key, symbol(node.target))
                    fact("adjacency_iteration", node, symbol(receiver), symbol(key),
                         "Static adjacency access; graph interpretation requires connected traversal evidence.",
                         binding=symbol(node.target), arguments=links or ["traversal_unresolved"])
            if isinstance(node, ast.While):
                fact("while_loop", node, symbol(node.test))
            if isinstance(node, ast.If):
                fact("conditional", node)
                if isinstance(node.test, ast.Compare):
                    test = node.test
                    for operator, other in zip(test.ops, test.comparators):
                        if isinstance(operator, (ast.In, ast.NotIn)):
                            fact("membership_guard", node, symbol(other), symbol(test.left))
                if any(isinstance(n, ast.Return) for n in node.body):
                    fact("conditional_return", node)
            if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
                fact("indexed_read", node, symbol(node.value), symbol(node.slice))
            if isinstance(node, ast.Call):
                label = symbol(node.func)
                if label and len(calls) < 64:
                    calls.append(dict(target=label, line=node.lineno))
                    fact("call", node, label)
                if label == binding:
                    fact("direct_recursion", node, label, detail="Lexical self-call, not runtime binding proof.", arguments=[symbol(arg) for arg in node.args])
                if label in {"sorted", "sum", "filter", "any", "all", "min", "max"} and label not in shadowed:
                    fact({"sorted": "sorting_call", "sum": "aggregation_call", "filter": "filtering_call"}.get(label, "searching_call"), node, label)
                canonical = imports.get(label.split(".")[0], label.split(".")[0]) + ("." + label.split(".", 1)[1] if "." in label else "")
                if canonical in {"heapq.heappush", "heapq.heappop", "heapq.heapify"}:
                    fact("heap_operation", node, symbol(node.args[0]) if node.args else "", canonical)
                if isinstance(node.func, ast.Attribute):
                    receiver, method = symbol(node.func.value), node.func.attr
                    if method in {"append", "add", "sort"}:
                        fact({"append": "sequence_append", "add": "set_add", "sort": "sorting_call"}[method], node,
                             receiver, symbol(node.args[0]) if node.args else "")
            if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)) and any(g.ifs for g in node.generators):
                fact("filtering_comprehension", node)
            if isinstance(node, ast.AugAssign) and isinstance(node.op, ast.Add):
                fact("accumulator_update", node, symbol(node.target))
            if isinstance(node, ast.Return) or isinstance(function, ast.Lambda) and node is function.body:
                value = node.value if isinstance(node, ast.Return) else node
                label = symbol(value)
                kind = collection_kind(value) or ("call_result" if isinstance(value, ast.Call) else "expression")
                returns.append(dict(line=node.lineno, symbol=label, kind=kind))
                fact("return_value", node, label, kind)
                returned = node.value if isinstance(node, ast.Return) else value
                if isinstance(returned, ast.Constant) and isinstance(returned.value, (int, bool)):
                    fact("constant_return", node, repr(returned.value), "Returns a literal sentinel.")
                elif isinstance(returned, ast.Name) and returned.id in literal_bindings:
                    fact("constant_return", node, literal_bindings[returned.id],
                         "Returns a name bound to a literal sentinel.")
            if isinstance(node, ast.Assert):
                # v4 AL-16: two calls are peers only when the assertion compares them with each
                # other as equals (``assert f(x) == g(x)``), not when one feeds the other or both
                # merely appear on the same line.
                peers = {}
                test = node.test
                if (isinstance(test, ast.Compare) and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)
                        and isinstance(test.left, ast.Call) and isinstance(test.comparators[0], ast.Call)):
                    left, right = symbol(test.left.func), symbol(test.comparators[0].func)
                    if left and right and left != right:
                        peers = {id(test.left): right, id(test.comparators[0]): left}
                for child in ast.walk(node.test):
                    if isinstance(child, ast.Call) and symbol(child.func):
                        assertions.append(dict(target=symbol(child.func), line=node.lineno, peer=peers.get(id(child), ""),
                                               detail="Static assert references this call; not executed or proven authoritative."))
        # Parameters are labels/type syntax only; defaults and annotations never run.
        parameters = []
        args = function.args
        positional = [*args.posonlyargs, *args.args]
        defaults = {arg.arg for arg in positional[len(positional) - len(args.defaults):]} if args.defaults else set()
        defaults.update(arg.arg for arg, value in zip(args.kwonlyargs, args.kw_defaults) if value is not None)
        for arg in [*positional, *args.kwonlyargs]:
            parameters.append(dict(name=arg.arg, annotation=ast.unparse(arg.annotation)[:120] if arg.annotation else None,
                                   has_default=arg.arg in defaults, kind="keyword_only" if arg in args.kwonlyargs else "positional"))
        for arg in [args.vararg, args.kwarg]:
            if arg:
                parameters.append(dict(name=arg.arg, variadic=True))
        for returned in returns:
            returned["kind"] = collections.get(returned["symbol"], returned["kind"])
        for item in facts:
            if item["kind"] == "return_value":
                item["related"] = collections.get(item["subject"], item["related"])
        records.append(dict(name=binding or qualified_name, qualified_name=qualified_name,
                            line=function.lineno, end_line=function.end_lineno, column=function.col_offset,
                            end_column=function.end_col_offset,
                            definition_line=min([function.lineno, *(d.lineno for d in getattr(function, "decorator_list", []))]),
                            is_async=isinstance(function, ast.AsyncFunctionDef), parameters=parameters[:32],
                            return_annotation=ast.unparse(function.returns)[:120] if getattr(function, "returns", None) else None,
                            facts=sorted(facts, key=lambda f: (f["line"], f["kind"])), calls=calls,
                            returns=returns[:16], structure=structure, collections=collections,
                            imports={key: value for key, value in imports.items()
                                     if not any(isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store) and n.id == key for n in nodes)},
                            assertions=assertions[:32]))
    return {"functions": records, "diagnostics": [], "truncated": truncated}
