"""
Security analysis of Python code: pattern rules + intra-procedural taint
analysis, every finding mapped to a CWE (MITRE's Common Weakness Enumeration).

1. Pattern rules: dangerous calls that are risky whatever their input
   (yaml.load without a safe loader, verify=False, MD5 for security, ...).

2. Taint analysis: follows user-controlled data inside one function from a
   SOURCE to a SINK, so injection is reported only when user input can
   actually reach the dangerous call.

   sources      parameters of web route handlers (FastAPI / Flask / Starlette
                decorators such as @router.post) except those filled by
                Depends()/Security(); `request.<attr>` (json, form, args,
                query_params, headers, cookies, body, ...); input()
   propagation  assignment, f-strings, + and % formatting, str.format/join,
                string methods (strip, lower, replace, ...), attribute and item
                access, containers, Path(...); if/else branches are merged and
                loop bodies are visited twice
   sanitizers   int, float, bool, re.escape, html.escape, shlex.quote,
                urllib.parse.quote, uuid.UUID, ObjectId, secure_filename,
                os.path.basename; calls to other functions are assumed to
                return clean data (fewer false alarms, may miss some flows)
   sinks        SQL execute/text (CWE-89), shell commands (CWE-78), eval/exec
                (CWE-95), deserialization (CWE-502), file paths (CWE-22),
                outgoing HTTP URLs / SSRF (CWE-918), templates (CWE-1336),
                redirects (CWE-601), MongoDB $where / $regex (CWE-943),
                regular expressions (CWE-1333)

Limits (documented, not hidden): one function at a time (no flow between
functions or files), Python only, and no knowledge of what unknown
functions do.

Rating (SonarQube's Security Rating): A no vulnerabilities, B worst is low,
C medium, D high, E critical.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

CWE_TITLES: Dict[int, str] = {
    22: "Path traversal",
    78: "OS command injection",
    89: "SQL injection",
    95: "Code injection (eval)",
    259: "Hard-coded password",
    295: "Improper certificate validation",
    327: "Broken or risky cryptographic algorithm",
    330: "Insufficiently random values",
    347: "Improper verification of cryptographic signature",
    377: "Insecure temporary file",
    489: "Active debug code",
    502: "Deserialization of untrusted data",
    601: "Open redirect",
    605: "Binding to all network interfaces",
    798: "Hard-coded credentials",
    918: "Server-side request forgery (SSRF)",
    943: "NoSQL injection",
    1333: "Inefficient regular expression (ReDoS)",
    1336: "Server-side template injection",
}


@dataclass(frozen=True)
class SecurityFinding:
    rule: str            # e.g. "SAM-S203"
    cwe: int
    severity: str        # critical | high | medium | low
    confidence: str      # high (taint-confirmed) | medium (pattern only)
    path: str
    line: int
    message: str
    fix: str
    source: str = "samanvaya-security"

    @property
    def title(self) -> str:
        return CWE_TITLES.get(self.cwe, f"CWE-{self.cwe}")

    def to_dict(self) -> Dict[str, object]:
        return {
            "rule": self.rule,
            "cwe": self.cwe,
            "title": self.title,
            "severity": self.severity,
            "confidence": self.confidence,
            "path": self.path,
            "line": self.line,
            "message": self.message,
            "fix": self.fix,
            "source": self.source,
        }


# ── names and helpers ─────────────────────────────────────────────

ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "route", "api_route", "websocket"}
DEPENDENCY_DEFAULTS = {"Depends", "Security"}
REQUEST_NAMES = {"request", "req"}
REQUEST_ATTRS = {
    "args", "form", "json", "values", "data", "files", "cookies", "headers",
    "query_params", "path_params", "query", "params", "body", "stream", "get_json", "get_data",
}
SANITIZERS = {
    "int", "float", "bool", "len", "abs", "round", "escape", "quote", "quote_plus",
    "UUID", "ObjectId", "secure_filename", "basename", "hash",
}
PROPAGATING_METHODS = {
    "strip", "lstrip", "rstrip", "lower", "upper", "title", "casefold", "capitalize",
    "replace", "split", "rsplit", "splitlines", "encode", "decode", "get", "items",
    "values", "keys", "copy", "pop", "dict", "model_dump", "format_map", "removeprefix", "removesuffix",
}
PROPAGATING_FUNCTIONS = {"str", "repr", "list", "dict", "tuple", "set", "sorted", "reversed", "Path", "PurePath", "unquote", "loads"}
TOKEN_WORDS = ("token", "secret", "passw", "otp", "nonce", "salt", "api_key", "apikey", "session")


def dotted_name(node: ast.AST) -> str:
    """os.path.join -> "os.path.join"; unknown parts become "?"."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{dotted_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Call):
        return f"{dotted_name(node.func)}()"
    return "?"


def last_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _keyword(call: ast.Call, name: str) -> Optional[ast.AST]:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _is_const(node: Optional[ast.AST], value: object) -> bool:
    return isinstance(node, ast.Constant) and node.value is value


def _arg(call: ast.Call, index: int, keyword: Optional[str] = None) -> Optional[ast.AST]:
    if len(call.args) > index and not isinstance(call.args[index], ast.Starred):
        return call.args[index]
    return _keyword(call, keyword) if keyword else None


def _is_dynamic_string(node: Optional[ast.AST]) -> bool:
    """A string built at runtime: f-string, + / % formatting or .format()."""
    if isinstance(node, ast.JoinedStr):
        return any(isinstance(v, ast.FormattedValue) for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return True
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "format"


_FIXED_HOST = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://[^/{}]+/")


def _fixed_host(url: Optional[ast.AST]) -> bool:
    """f"https://api.example.com/{x}" or "https://api.example.com/" + x: the host
    is fixed in code, so user input cannot redirect the request (not SSRF)."""
    if isinstance(url, ast.JoinedStr) and url.values and isinstance(url.values[0], ast.Constant):
        return bool(_FIXED_HOST.match(str(url.values[0].value)))
    if isinstance(url, ast.BinOp) and isinstance(url.op, ast.Add):
        left = url.left
        while isinstance(left, ast.BinOp) and isinstance(left.op, ast.Add):
            left = left.left
        return isinstance(left, ast.Constant) and bool(_FIXED_HOST.match(str(left.value)))
    return False


def _route_handler(func: ast.AST) -> bool:
    for deco in getattr(func, "decorator_list", []):
        target = deco.func if isinstance(deco, ast.Call) else deco
        if isinstance(target, ast.Attribute) and target.attr in ROUTE_METHODS:
            return True
    return False


def _source_params(func: ast.AST) -> Dict[str, str]:
    """Route-handler parameters filled from the request (not by Depends)."""
    if not _route_handler(func):
        return {}
    args = func.args
    positional = args.posonlyargs + args.args
    defaults: Dict[str, ast.AST] = {}
    for param, default in zip(positional[len(positional) - len(args.defaults):], args.defaults):
        defaults[param.arg] = default
    for param, default in zip(args.kwonlyargs, args.kw_defaults):
        if default is not None:
            defaults[param.arg] = default
    sources: Dict[str, str] = {}
    for param in positional + args.kwonlyargs:
        if param.arg in ("self", "cls"):
            continue
        default = defaults.get(param.arg)
        if isinstance(default, ast.Call) and last_name(default.func) in DEPENDENCY_DEFAULTS:
            continue
        annotation = dotted_name(param.annotation) if param.annotation is not None else ""
        if annotation.split(".")[-1] in ("Request", "BackgroundTasks", "Response", "WebSocket"):
            continue  # framework objects; request.<attr> access is handled separately
        sources[param.arg] = f"request parameter `{param.arg}`"
    return sources


# ── taint analysis ────────────────────────────────────────────────

Env = Dict[str, str]  # variable -> description of where its tainted value came from


class _TaintChecker:
    def __init__(self, func: ast.AST, path: str, report: "_Report") -> None:
        self.func = func
        self.path = path
        self.report = report

    # expression -> source description (or None if clean)
    def taint(self, node: Optional[ast.AST], env: Env) -> Optional[str]:
        if node is None:
            return None
        if isinstance(node, ast.Name):
            return env.get(node.id)
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id in REQUEST_NAMES and node.attr in REQUEST_ATTRS:
                return f"`{node.value.id}.{node.attr}`"
            return self.taint(node.value, env)
        if isinstance(node, ast.Subscript):
            return self.taint(node.value, env)
        if isinstance(node, ast.Await):
            return self.taint(node.value, env)
        if isinstance(node, ast.Call):
            return self._call_taint(node, env)
        if isinstance(node, ast.JoinedStr):
            return next((t for v in node.values if isinstance(v, ast.FormattedValue)
                         for t in [self.taint(v.value, env)] if t), None)
        if isinstance(node, ast.BinOp):
            return self.taint(node.left, env) or self.taint(node.right, env)
        if isinstance(node, (ast.BoolOp,)):
            return next((t for v in node.values for t in [self.taint(v, env)] if t), None)
        if isinstance(node, ast.IfExp):
            return self.taint(node.body, env) or self.taint(node.orelse, env)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return next((t for v in node.elts for t in [self.taint(v, env)] if t), None)
        if isinstance(node, ast.Dict):
            return next((t for v in list(node.values) + [k for k in node.keys if k is not None]
                         for t in [self.taint(v, env)] if t), None)
        if isinstance(node, (ast.Starred, ast.NamedExpr)):
            return self.taint(node.value, env)
        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            return next((t for g in node.generators for t in [self.taint(g.iter, env)] if t), None)
        return None

    def _call_taint(self, call: ast.Call, env: Env) -> Optional[str]:
        func = call.func
        name = last_name(func)
        if isinstance(func, ast.Name) and func.id == "input":
            return "`input()`"
        if isinstance(func, ast.Attribute):
            base = func.value
            if isinstance(base, ast.Name) and base.id in REQUEST_NAMES and func.attr in REQUEST_ATTRS:
                return f"`{base.id}.{func.attr}()`"
            if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) \
                    and base.value.id in REQUEST_NAMES and base.attr in REQUEST_ATTRS:
                return f"`{base.value.id}.{base.attr}.{func.attr}()`"
        if name in SANITIZERS:
            return None
        args = list(call.args) + [kw.value for kw in call.keywords]
        if isinstance(func, ast.Attribute):
            if func.attr in ("format", "join"):
                return self.taint(func.value, env) or next((t for a in args for t in [self.taint(a, env)] if t), None)
            if func.attr in PROPAGATING_METHODS:
                return self.taint(func.value, env)
        if name in PROPAGATING_FUNCTIONS:
            return next((t for a in args for t in [self.taint(a, env)] if t), None)
        return None

    # statements, in order, merging branches
    def run(self, sources: Env) -> None:
        self.block(getattr(self.func, "body", []), dict(sources))

    def block(self, body: Sequence[ast.stmt], env: Env) -> Env:
        for stmt in body:
            env = self.stmt(stmt, env)
        return env

    @staticmethod
    def _merge(*envs: Env) -> Env:
        merged: Env = {}
        for e in envs:
            merged.update(e)
        return merged

    def _assign(self, target: ast.AST, source: Optional[str], env: Env) -> None:
        if isinstance(target, ast.Name):
            if source:
                env[target.id] = source
            else:
                env.pop(target.id, None)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for elt in target.elts:
                self._assign(elt.value if isinstance(elt, ast.Starred) else elt, source, env)

    def stmt(self, stmt: ast.stmt, env: Env) -> Env:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return env  # analysed separately
        self.check_sinks(stmt, env)
        if isinstance(stmt, ast.Assign):
            source = self.taint(stmt.value, env)
            for target in stmt.targets:
                self._assign(target, source, env)
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            self._assign(stmt.target, self.taint(stmt.value, env), env)
        elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
            source = self.taint(stmt.value, env)
            if source:
                env[stmt.target.id] = source
        elif isinstance(stmt, (ast.For, ast.AsyncFor)):
            loop_env = dict(env)
            self._assign(stmt.target, self.taint(stmt.iter, env), loop_env)
            for _ in range(2):  # second pass lets taint flow around the loop
                loop_env = self._merge(loop_env, self.block(stmt.body, dict(loop_env)))
            env = self._merge(env, loop_env, self.block(stmt.orelse, dict(env)))
        elif isinstance(stmt, ast.While):
            loop_env = dict(env)
            for _ in range(2):
                loop_env = self._merge(loop_env, self.block(stmt.body, dict(loop_env)))
            env = self._merge(env, loop_env, self.block(stmt.orelse, dict(env)))
        elif isinstance(stmt, ast.If):
            env = self._merge(self.block(stmt.body, dict(env)), self.block(stmt.orelse, dict(env)))
        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            for item in stmt.items:
                if item.optional_vars is not None:
                    self._assign(item.optional_vars, self.taint(item.context_expr, env), env)
            env = self.block(stmt.body, env)
        elif isinstance(stmt, (ast.Try, getattr(ast, "TryStar", ast.Try))):
            after_try = self.block(stmt.body, dict(env))
            handled = [self.block(h.body, dict(after_try)) for h in stmt.handlers]
            env = self._merge(after_try, *handled)
            env = self.block(stmt.orelse, env)
            env = self.block(stmt.finalbody, env)
        elif isinstance(stmt, ast.Match):
            env = self._merge(env, *[self.block(case.body, dict(env)) for case in stmt.cases])
        return env

    def _own_calls(self, stmt: ast.stmt) -> Iterable[ast.Call]:
        """Calls in this statement's own expressions (not in nested blocks/defs)."""
        roots: List[ast.AST] = []
        for name, value in ast.iter_fields(stmt):
            if name in ("body", "orelse", "finalbody", "handlers", "cases"):
                continue
            roots.extend(value if isinstance(value, list) else [value])
        stack = [r for r in roots if isinstance(r, ast.AST)]
        while stack:
            node = stack.pop()
            if isinstance(node, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if isinstance(node, ast.Call):
                yield node
            if isinstance(node, ast.Dict):
                self._check_mongo(node, self._env_for_dict)
            stack.extend(ast.iter_child_nodes(node))

    def check_sinks(self, stmt: ast.stmt, env: Env) -> None:
        self._env_for_dict = env
        for call in self._own_calls(stmt):
            self._check_call(call, env)

    def _flag(self, node: ast.AST, rule: str, cwe: int, severity: str, source: str, sink: str, fix: str) -> None:
        self.report.add(SecurityFinding(
            rule=rule, cwe=cwe, severity=severity, confidence="high", path=self.path,
            line=getattr(node, "lineno", 0),
            message=f"User input from {source} reaches {sink}: {CWE_TITLES[cwe].lower()}",
            fix=fix,
        ))

    def _check_call(self, call: ast.Call, env: Env) -> None:
        full = dotted_name(call.func)
        name = last_name(call.func)
        first = _arg(call, 0)

        def tainted(node):
            return self.taint(node, env)

        if name in ("execute", "executemany", "executescript", "raw") or full in ("text", "sqlalchemy.text"):
            t = tainted(first)
            if t:
                self._flag(call, "SAM-S201", 89, "high", t, f"`{full}`",
                           "Use a parameterized query: pass values separately, e.g. execute(sql, (value,)).")
        if full in ("os.system", "os.popen", "subprocess.getoutput", "subprocess.getstatusoutput") or (
            full.startswith("subprocess.") and _is_const(_keyword(call, "shell"), True)
        ):
            t = tainted(first)
            if t:
                self._flag(call, "SAM-S202", 78, "high", t, f"`{full}`",
                           "Pass a list of arguments without shell=True, and validate the input against an allowlist.")
        if full in ("eval", "exec", "compile"):
            t = tainted(first)
            if t:
                self._flag(call, "SAM-S203", 95, "critical", t, f"`{full}()`",
                           "Never evaluate user input; parse it (json.loads, ast.literal_eval) or map it to allowed actions.")
        if full in ("pickle.loads", "pickle.load", "marshal.loads", "dill.loads", "yaml.load", "yaml.unsafe_load"):
            t = tainted(first)
            if t:
                self._flag(call, "SAM-S204", 502, "critical", t, f"`{full}`",
                           "Deserialize untrusted data only with safe formats (json) or yaml.safe_load.")
        if full in ("open", "io.open", "os.remove", "os.unlink", "os.rmdir", "os.rename", "shutil.rmtree",
                    "shutil.copy", "shutil.copyfile", "shutil.move", "FileResponse", "send_file", "send_from_directory"):
            t = tainted(first)
            if t:
                self._flag(call, "SAM-S205", 22, "high", t, f"`{full}`",
                           "Resolve the path and check it stays inside an allowed folder (Path.resolve + is_relative_to).")
        if isinstance(call.func, ast.Attribute) and call.func.attr in (
            "read_text", "read_bytes", "write_text", "write_bytes", "open", "unlink", "rmdir", "rename"
        ) and isinstance(call.func.value, ast.Call) and last_name(call.func.value.func) in ("Path", "PurePath"):
            t = tainted(call.func.value)
            if t:
                self._flag(call, "SAM-S205", 22, "high", t, f"`Path(...).{call.func.attr}`",
                           "Resolve the path and check it stays inside an allowed folder (Path.resolve + is_relative_to).")
        if full.split(".")[0] in ("requests", "httpx", "urllib3", "aiohttp") and name in (
            "get", "post", "put", "patch", "delete", "head", "request", "urlopen"
        ) or full in ("urllib.request.urlopen", "urlopen"):
            url = _arg(call, 1, "url") if name == "request" else _arg(call, 0, "url")
            t = None if _fixed_host(url) else tainted(url)
            if t:
                self._flag(call, "SAM-S206", 918, "high", t, f"`{full}`",
                           "Do not fetch user-supplied URLs; allow only known hosts and block internal addresses.")
        if full in ("render_template_string", "jinja2.Template", "Template") or name == "from_string":
            t = tainted(first)
            if t:
                self._flag(call, "SAM-S207", 1336, "high", t, f"`{full}`",
                           "Render fixed templates and pass user input only as template variables.")
        if full in ("redirect", "RedirectResponse", "flask.redirect"):
            t = tainted(first) or tainted(_keyword(call, "url"))
            if t:
                self._flag(call, "SAM-S208", 601, "medium", t, f"`{full}`",
                           "Redirect only to relative paths or an allowlist of hosts.")
        if full in ("re.compile", "re.match", "re.search", "re.fullmatch", "re.findall", "re.sub", "re.split"):
            t = tainted(first)
            if t:
                self._flag(call, "SAM-S209", 1333, "medium", t, f"`{full}` pattern",
                           "Escape user input with re.escape() before using it in a pattern.")

    def _check_mongo(self, node: ast.Dict, env: Env) -> None:
        for key, value in zip(node.keys, node.values):
            if isinstance(key, ast.Constant) and key.value in ("$where", "$regex", "$function", "$accumulator"):
                t = self.taint(value, env)
                if t:
                    regex = key.value == "$regex"
                    self._flag(node, "SAM-S210", 943, "medium" if regex else "high", t, f"MongoDB `{key.value}`",
                               "Escape user input with re.escape() for $regex; never put it in $where/$function."
                               if regex else "Never build $where/$function from user input; use normal query operators.")


# ── pattern rules ─────────────────────────────────────────────────

def _enclosing_names(stack: Sequence[ast.AST]) -> str:
    return " ".join(getattr(n, "name", "") for n in stack).lower()


class _PatternChecker(ast.NodeVisitor):
    def __init__(self, path: str, report: "_Report") -> None:
        self.path = path
        self.report = report
        self.funcs: List[ast.AST] = []
        self.assign_targets: List[str] = []

    def _flag(self, node: ast.AST, rule: str, cwe: int, severity: str, message: str, fix: str) -> None:
        self.report.add(SecurityFinding(rule=rule, cwe=cwe, severity=severity, confidence="medium",
                                        path=self.path, line=getattr(node, "lineno", 0), message=message, fix=fix))

    def visit_FunctionDef(self, node: ast.AST) -> None:
        self.funcs.append(node)
        self.generic_visit(node)
        self.funcs.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node: ast.Assign) -> None:
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        names += [t.attr for t in node.targets if isinstance(t, ast.Attribute)]
        self.assign_targets.append(" ".join(names).lower())
        self.generic_visit(node)
        self.assign_targets.pop()

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if dotted_name(node) in ("ssl.CERT_NONE",):
            self._flag(node, "SAM-S106", 295, "high", "TLS certificate checking disabled (ssl.CERT_NONE)",
                       "Keep certificate verification on (ssl.CERT_REQUIRED, the default).")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        full = dotted_name(node.func)
        name = last_name(node.func)
        first = _arg(node, 0)

        if full in ("eval", "exec") and first is not None and not isinstance(first, ast.Constant):
            self._flag(node, "SAM-S101", 95, "high", f"`{full}()` on a value computed at runtime",
                       "Avoid eval/exec; use ast.literal_eval or explicit parsing.")
        if full.startswith("subprocess.") and _is_const(_keyword(node, "shell"), True):
            self._flag(node, "SAM-S102", 78, "high", f"`{full}` with shell=True",
                       "Pass a list of arguments without shell=True.")
        if full in ("os.system", "os.popen") and first is not None and not isinstance(first, ast.Constant):
            self._flag(node, "SAM-S102", 78, "high", f"`{full}` with a command built at runtime",
                       "Use subprocess with a list of arguments.")
        if full in ("pickle.load", "pickle.loads", "marshal.load", "marshal.loads", "shelve.open", "dill.loads"):
            self._flag(node, "SAM-S103", 502, "medium", f"`{full}` can execute code from crafted data",
                       "Use json for data exchange; only unpickle data you produced yourself.")
        if full == "yaml.unsafe_load" or (full == "yaml.load" and last_name(_keyword(node, "Loader") or (
                node.args[1] if len(node.args) > 1 else ast.Name(id=""))) not in ("SafeLoader", "CSafeLoader", "BaseLoader")):
            self._flag(node, "SAM-S104", 502, "high", f"`{full}` without a safe loader can execute code",
                       "Use yaml.safe_load().")
        if _is_const(_keyword(node, "verify"), False):
            self._flag(node, "SAM-S105", 295, "high", f"`{full}` with verify=False disables TLS certificate checks",
                       "Remove verify=False; point verify= at a CA bundle if a private CA is needed.")
        if full in ("ssl._create_unverified_context",):
            self._flag(node, "SAM-S106", 295, "high", "Unverified TLS context", "Use ssl.create_default_context().")
        if full in ("hashlib.md5", "hashlib.sha1") or (
            full == "hashlib.new" and isinstance(first, ast.Constant) and str(first.value).lower() in ("md5", "sha1")
        ):
            if not _is_const(_keyword(node, "usedforsecurity"), False):
                self._flag(node, "SAM-S107", 327, "medium", f"`{full}` is a broken hash for security use",
                           "Use hashlib.sha256 (or bcrypt/argon2 for passwords); pass usedforsecurity=False for checksums.")
        if full.startswith("random.") and name in (
            "random", "randint", "randrange", "choice", "choices", "getrandbits", "sample", "uniform", "randbytes"
        ):
            context = (self.assign_targets[-1] if self.assign_targets else "") + " " + _enclosing_names(self.funcs)
            if any(word in context for word in TOKEN_WORDS):
                self._flag(node, "SAM-S108", 330, "medium", f"`{full}` is predictable; used for a secret value",
                           "Use the secrets module (secrets.token_urlsafe, secrets.choice).")
        if full in ("jwt.decode",):
            options = _keyword(node, "options")
            algorithms = _keyword(node, "algorithms")
            disabled = _is_const(_keyword(node, "verify"), False) or (
                isinstance(options, ast.Dict) and any(
                    isinstance(k, ast.Constant) and k.value == "verify_signature" and _is_const(v, False)
                    for k, v in zip(options.keys, options.values)
                )
            )
            none_alg = isinstance(algorithms, (ast.List, ast.Tuple)) and any(
                isinstance(e, ast.Constant) and str(e.value).lower() == "none" for e in algorithms.elts
            )
            if disabled or none_alg:
                self._flag(node, "SAM-S109", 347, "high", "JWT decoded without verifying its signature",
                           "Always verify signatures and pass an explicit list of allowed algorithms.")
        if full == "tempfile.mktemp":
            self._flag(node, "SAM-S110", 377, "medium", "`tempfile.mktemp` is open to race conditions",
                       "Use tempfile.mkstemp() or NamedTemporaryFile().")
        host = _keyword(node, "host") or (first if name in ("bind",) else None)
        if isinstance(host, ast.Constant) and host.value == "0.0.0.0":
            # report the line of the "0.0.0.0" argument, not of the (possibly multi-line) call
            self._flag(host, "SAM-S111", 605, "low", "Service listens on all network interfaces (0.0.0.0)",
                       "Bind to a specific interface unless the service must be reachable from outside.")
        if name == "run" and _is_const(_keyword(node, "debug"), True):
            self._flag(node, "SAM-S112", 489, "medium", "Application started with debug=True",
                       "Disable debug mode outside local development.")
        if (name in ("execute", "executemany") or full in ("text", "sqlalchemy.text")) and _is_dynamic_string(first):
            self._flag(node, "SAM-S113", 89, "medium", f"SQL built with string formatting passed to `{full}`",
                       "Use a parameterized query instead of formatting values into the SQL string.")
        self.generic_visit(node)


# ── running and reporting ─────────────────────────────────────────

class _Report:
    def __init__(self) -> None:
        self.findings: Dict[Tuple[str, int, int], SecurityFinding] = {}

    def add(self, finding: SecurityFinding) -> None:
        """One finding per (file, line, CWE): taint-confirmed beats pattern, then higher severity."""
        key = (finding.path, finding.line, finding.cwe)
        current = self.findings.get(key)
        rank = lambda f: (f.confidence == "high", SEVERITY_ORDER.get(f.severity, 0))  # noqa: E731
        if current is None or rank(finding) > rank(current):
            self.findings[key] = finding


@dataclass
class FileSecurity:
    path: str
    findings: List[SecurityFinding] = field(default_factory=list)
    parse_error: Optional[str] = None


def analyze_source(source: str, path: str = "<string>") -> FileSecurity:
    """Security findings for one Python file."""
    source = source.lstrip("﻿")
    try:
        tree = ast.parse(source, filename=path)
    except (SyntaxError, ValueError) as exc:
        return FileSecurity(path=path, parse_error=f"{type(exc).__name__}: {exc}")
    report = _Report()
    _PatternChecker(path, report).visit(tree)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _TaintChecker(node, path, report).run(_source_params(node))
    # module-level code (scripts): request objects and input() are still sources
    module = ast.Module(body=[s for s in tree.body if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))],
                        type_ignores=[])
    _TaintChecker(module, path, report).run({})
    findings = sorted(report.findings.values(), key=lambda f: (f.line, f.cwe))
    return FileSecurity(path=path, findings=findings)


def analyze_file(path: str | Path, display_path: Optional[str] = None) -> FileSecurity:
    p = Path(path)
    shown = display_path or p.as_posix()
    try:
        source = p.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        return FileSecurity(path=shown, parse_error=f"{type(exc).__name__}: {exc}")
    return analyze_source(source, path=shown)


# ── summary and rating ────────────────────────────────────────────

RATING_BY_SEVERITY = {"critical": "E", "high": "D", "medium": "C", "low": "B"}


def security_rating(severities: Iterable[str]) -> str:
    """SonarQube Security Rating: the worst vulnerability decides (A = none)."""
    worst = max((SEVERITY_ORDER.get(s, 0) for s in severities), default=0)
    for severity, rating in RATING_BY_SEVERITY.items():
        if SEVERITY_ORDER[severity] == worst:
            return rating
    return "A"


@dataclass
class SecuritySummary:
    findings: List[SecurityFinding]
    code_lines: int

    @property
    def by_severity(self) -> Dict[str, int]:
        counts = Counter(f.severity for f in self.findings)
        return {s: counts.get(s, 0) for s in ("critical", "high", "medium", "low")}

    @property
    def by_cwe(self) -> Dict[str, int]:
        counts = Counter(f.cwe for f in self.findings)
        return {f"CWE-{cwe} {CWE_TITLES.get(cwe, '')}".strip(): n for cwe, n in counts.most_common()}

    @property
    def density(self) -> float:
        """Vulnerabilities per 1,000 lines of code."""
        return round(len(self.findings) / (self.code_lines / 1000), 2) if self.code_lines else 0.0

    @property
    def rating(self) -> str:
        return security_rating(f.severity for f in self.findings)

    def to_dict(self) -> Dict[str, object]:
        return {
            "vulnerabilities": len(self.findings),
            "by_severity": self.by_severity,
            "by_cwe": self.by_cwe,
            "density": self.density,
            "rating": self.rating,
            "taint_confirmed": sum(1 for f in self.findings if f.confidence == "high"),
        }


def summarize(findings: Iterable[SecurityFinding], code_lines: int) -> SecuritySummary:
    return SecuritySummary(findings=list(findings), code_lines=code_lines)
