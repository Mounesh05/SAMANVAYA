"""Source-only control flow and reaching definitions for bounded structured functions."""

import ast


LIMIT = 96


def python_statements(function):
    count = 0

    def lower(statement):
        nonlocal count
        count += 1
        if count > LIMIT:
            raise ValueError("control-flow operation limit")
        body = otherwise = []
        op = "simple"
        roots = [statement]
        if isinstance(statement, (ast.If, ast.For, ast.While)):
            op = "branch" if isinstance(statement, ast.If) else "loop"
            body = [lower(s) for s in statement.body]
            otherwise = [lower(s) for s in statement.orelse]
            roots = [statement.iter, statement.target] if isinstance(statement, ast.For) else [statement.test]
        elif isinstance(statement, ast.Return):
            op = "return"
        elif isinstance(statement, ast.Break):
            op = "break"
        elif isinstance(statement, ast.Continue):
            op = "continue"
        elif isinstance(statement, ast.Raise):
            op = "raise"
        elif not isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Expr, ast.Pass)):
            op, roots = "unknown", []
        nodes = [n for root in roots for n in ast.walk(root)]
        writes = {n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        reads = {n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        if isinstance(statement, ast.AugAssign) and isinstance(statement.target, ast.Name):
            reads.add(statement.target.id)
        if any(isinstance(n, (ast.Lambda, ast.comprehension, ast.NamedExpr, ast.Await, ast.Yield,
                              ast.BoolOp, ast.IfExp, ast.YieldFrom)) for n in nodes):
            op = "unknown"
        aliases = {}
        if isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Name):
            aliases = {t.id: statement.value.id for t in statement.targets if isinstance(t, ast.Name)}
        if len(reads | writes) > 64 or any(len(name) > 128 for name in reads | writes):
            raise ValueError("control-flow symbol limit")
        if isinstance(statement, ast.For):
            # The target is defined only on an iteration edge, including for an
            # empty iterable whose target already has an outer binding.
            body.insert(0, {"op": "bind", "line": statement.lineno, "end": statement.lineno,
                            "reads": [], "writes": sorted(writes), "aliases": {}, "body": [], "otherwise": []})
            writes.clear()
        return {"op": op, "line": statement.lineno, "end": statement.end_lineno,
                "reads": sorted(reads), "writes": sorted(writes), "aliases": aliases,
                "body": body, "otherwise": otherwise}

    try:
        return [lower(stmt) for stmt in function.body] if isinstance(function.body, list) else None
    except (ValueError, RecursionError):
        return None


def analyze(statements, parameters):
    """Edges and may-reaching definitions in normal synchronous control flow."""
    blocks = [{"id": 0, "op": "entry", "reads": [], "writes": list(parameters)}]
    edges = []
    partial = statements is None

    def sequence(stmts, incoming, loop=None):
        nonlocal partial
        for stmt in stmts:
            if not incoming:
                break
            if len(blocks) > LIMIT:
                raise ValueError
            index = len(blocks)
            op = stmt["op"]
            blocks.append({"id": index, **{k: stmt[k] for k in ("op", "line", "end", "reads", "writes", "aliases")}})
            edges.extend((source, index, label) for source, label in incoming)
            incoming = [(index, "next")]
            if op == "branch":
                incoming = sequence(stmt["body"], [(index, "true")], loop) + sequence(stmt["otherwise"], [(index, "false")], loop)
            elif op == "loop":
                exits = []
                back = sequence(stmt["body"], [(index, "iterate")], (index, exits))
                edges.extend((source, index, "back") for source, _ in back)
                incoming = sequence(stmt["otherwise"], [(index, "exhausted")], loop) + exits
            elif op in ("return", "raise"):
                incoming = []
            elif op == "break" and loop:
                loop[1].append((index, "break"))
                incoming = []
            elif op == "continue" and loop:
                edges.append((index, loop[0], "continue"))
                incoming = []
            elif op == "unknown":
                partial = True
        return incoming

    try:
        sequence(statements or [], [(0, "next")])
    except (ValueError, RecursionError):
        return {"version": 1, "status": "partial", "reason": "control-flow limit"}
    predecessors = [[] for _ in blocks]
    for source, target, _ in edges:
        predecessors[target].append(source)
    outgoing = [{} for _ in blocks]
    for _ in range(len(blocks) + 1):
        changed = False
        for block in blocks:
            index = block["id"]
            definitions = {}
            for pred in predecessors[index]:
                for name, sites in outgoing[pred].items():
                    definitions.setdefault(name, set()).update(sites)
            block["reaching"] = {name: sorted(definitions.get(name, ())) for name in block["reads"]}
            definitions.update({name: {index} for name in block["writes"]})
            if definitions != outgoing[index]:
                outgoing[index] = definitions
                changed = True
        if not changed:
            break
    return {"version": 1, "status": "partial" if partial else "available",
            "scope": "normal synchronous flow", "blocks": blocks, "edges": edges}
