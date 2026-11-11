"""Repository discovery and context linking, with explicit partial-analysis bounds."""

import hashlib
import json
import os
import posixpath
from pathlib import Path

from intelligence.analyzers.base import EXCLUDED_DIRS
from intelligence.analyzers.registry import get_function_extractor
from intelligence.algorithms.discovery.rules import resolve
from intelligence.evidence.function_purpose import DiscoveredFunction, FunctionDiscovery, PurposeEvidence

MAX_FILES = 100
MAX_SOURCE_BYTES = 200_000
MAX_TOTAL_BYTES = 2_000_000
MAX_FUNCTIONS = 256
MAX_REPORT_BYTES = 4_000_000
EXTENSIONS = {".py": "python", ".pyi": "python", ".js": "javascript", ".jsx": "javascript",
              ".mjs": "javascript", ".cjs": "javascript", ".ts": "typescript", ".tsx": "typescript"}


def identifier(*parts):
    return hashlib.sha256(json.dumps(parts, ensure_ascii=True).encode()).hexdigest()[:24]


def source_language(path):
    return EXTENSIONS.get(Path(path).suffix.lower())


def safe_relative_path(path):
    normalized = posixpath.normpath(path.replace("\\", "/"))
    return bool(normalized and not normalized.startswith(("/", "../")) and ":" not in normalized
                and normalized != ".." and not any(p.lower() in EXCLUDED_DIRS for p in normalized.split("/")[:-1]))


def _module(path):
    return path.rsplit(".", 1)[0].replace("/", ".").removesuffix(".__init__")


def _resolve_calls(records, raw_records):
    by_location = {}
    for function in records:
        by_location.setdefault((function.path, function.qualified_name), []).append(function)
    by_module = {}
    for function in records:
        if "." not in function.qualified_name:
            by_module.setdefault((_module(function.path), function.qualified_name), []).append(function)

    def target_for(caller, label, imports):
        if label.split(".")[0] in {p["name"] for p in caller.parameters}:
            return None
        parts = caller.qualified_name.split(".")[:-1]
        if label.startswith(("self.", "this.")):
            label = label.split(".", 1)[1]
        if "." not in label:
            for depth in range(len(parts), -1, -1):
                found = by_location.get((caller.path, ".".join(parts[:depth] + [label])), [])
                if len(found) == 1:
                    return found[0]
        root, _, suffix = label.partition(".")
        if root in imports:
            imported = imports[root] + ("." + suffix if suffix else "")
            module, _, name = imported.rpartition(".")
            if caller.language == "python":
                if module.startswith("."):
                    level = len(module) - len(module.lstrip("."))
                    base = _module(caller.path).split(".")[:-level]
                    module = ".".join(base + [module.lstrip(".")]).strip(".")
            elif module.startswith("."):
                module = _module(posixpath.normpath(posixpath.join(posixpath.dirname(caller.path), module)) + ".js")
            candidates = by_module.get((module, name), [])
            return candidates[0] if len(candidates) == 1 else None
        return None

    for caller in records:
        raw = raw_records[caller.function_id]
        for call in caller.calls:
            target = target_for(caller, call["target"], raw.get("imports", {}))
            call["resolved_function_id"] = target.function_id if target else None
            call["resolution"] = "lexical_candidate" if target else "unresolved"
            if target and len(target.callers) < 64:
                target.callers.append({"function_id": caller.function_id, "path": caller.path,
                                       "line": call["line"], "resolution": "lexical_candidate"})
        for assertion in raw.get("assertions", []):
            target = target_for(caller, assertion["target"], raw.get("imports", {}))
            if not target or len(target.evidence) >= 144:
                continue
            evidence = PurposeEvidence(
                id=identifier(target.function_id, caller.source_hash, assertion["line"], "test_expectation"),
                kind="test_expectation", path=caller.path, line=assertion["line"], end_line=assertion["line"],
                source_revision=caller.source_revision, source_hash=caller.source_hash,
                subject=target.qualified_name, detail=assertion["detail"],
            )
            if any(existing.id == evidence.id for existing in target.evidence):
                continue
            target.evidence.append(evidence)
            target.requirement_evidence_refs.append(evidence.id)


async def discover_sources(sources: dict[str, str], repository_id: str, revision=None, diagnostics=()) -> FunctionDiscovery:
    report = FunctionDiscovery(status="available", source_revision=revision, diagnostics=list(diagnostics))
    raw_records = {}
    total_bytes = 0
    for index, (path, source) in enumerate(sorted(sources.items())):
        if path == ".samanvaya/requirements.json":
            try:
                from domain.schemas.requirement_discovery import RequirementDeclaration
                if len(source.encode()) > 32000:
                    raise ValueError("Repository requirement configuration exceeds its bound")
                document = json.loads(source)
                if not isinstance(document, dict) or set(document) != {"version", "requirements"} or document["version"] != "1" or not isinstance(document["requirements"], list) or not 1 <= len(document["requirements"]) <= 32:
                    raise ValueError("Expected bounded version 1 requirements document")
                declarations = [RequirementDeclaration.model_validate(r).model_dump() for r in document["requirements"]]
                report.requirement_sources.append({"path": path, "source_revision": revision,
                    "source_hash": hashlib.sha256(source.encode()).hexdigest(), "requirements": declarations,
                    "authority_status": "SUGGESTED", "extraction_method": "repository-configuration-v1"})
            except (ValueError, TypeError, RecursionError):
                report.diagnostics.append({"path": path, "kind": "invalid_requirement_configuration"})
            continue
        if not safe_relative_path(path) or not source_language(path):
            report.diagnostics.append({"path": path[:240], "kind": "unsupported_or_unsafe_path"})
            continue
        if index >= MAX_FILES or len(report.functions) >= MAX_FUNCTIONS:
            report.diagnostics.append({"kind": "analysis_bound", "message": "File/function limit reached."})
            break
        size = len(source.encode("utf-8"))
        if size > MAX_SOURCE_BYTES or total_bytes + size > MAX_TOTAL_BYTES:
            report.diagnostics.append({"path": path, "kind": "source_bound"})
            continue
        total_bytes += size
        digest = hashlib.sha256(source.encode()).hexdigest()
        language = source_language(path)
        try:
            extractor = get_function_extractor(language)
            parsed = await extractor(source, path)
            report.diagnostics.extend({"path": path, **d} for d in parsed.get("diagnostics", []))
            if parsed.get("truncated"):
                report.diagnostics.append({"path": path, "kind": "function_bound"})
            for raw in parsed["functions"]:
                if len(report.functions) >= MAX_FUNCTIONS:
                    report.diagnostics.append({"path": path, "kind": "function_bound"})
                    break
                fid = identifier(repository_id, path, digest, raw["qualified_name"], raw["line"], raw.get("column", 0))
                evidence = [PurposeEvidence(
                    id=identifier(fid, i, fact["kind"], fact["line"]), path=path,
                    source_revision=revision, source_hash=digest, **fact,
                ) for i, fact in enumerate(raw.get("facts", []))]
                function = DiscoveredFunction(
                    function_id=fid, repository_id=repository_id, path=path, language=language,
                    source_revision=revision, source_hash=digest, evidence=evidence,
                    end_column=raw.get("end_column"), definition_line=raw.get("definition_line"),
                    **{key: raw[key] for key in ("name", "qualified_name", "line", "end_line", "column", "is_async",
                                                 "parameters", "return_annotation", "calls", "returns", "structure")},
                )
                raw_records[fid] = raw
                report.functions.append(function)
        except (SyntaxError, ValueError, TypeError, RecursionError, MemoryError, UnicodeError, OSError, NotImplementedError) as error:
            report.diagnostics.append({"path": path, "kind": type(error).__name__,
                                       "line": getattr(error, "lineno", None),
                                       "message": "Static extraction unavailable for this source; no task conclusion was made."})
    _resolve_calls(report.functions, raw_records)
    for function in report.functions:
        resolve(function)
    # Bound embedded MongoDB evidence independently of source-file bounds.
    while len(report.model_dump_json().encode()) > MAX_REPORT_BYTES and report.functions:
        report.functions.pop()
        if not any(d.get("kind") == "report_bound" for d in report.diagnostics):
            report.diagnostics.append({"kind": "report_bound"})
    retained = {f.function_id for f in report.functions}
    for function in report.functions:
        function.callers = [caller for caller in function.callers if caller["function_id"] in retained]
        for call in function.calls:
            if call.get("resolved_function_id") and call["resolved_function_id"] not in retained:
                call.update(resolved_function_id=None, resolution="outside_retained_snapshot")
    if report.diagnostics:
        report.status = "partial" if report.functions else "unavailable"
    return report


async def discover_repository(repo_path, repository_id, revision=None, changed_files=()):
    if not repo_path or not Path(repo_path).is_dir():
        return FunctionDiscovery(status="unavailable", source_revision=revision, diagnostics=[
            {"kind": "source_unavailable", "message": "No repository source snapshot is available."}])
    root = Path(repo_path).resolve()
    paths = set(changed_files)
    if (root / ".samanvaya/requirements.json").is_file():
        paths.add(".samanvaya/requirements.json")
    diagnostics = []
    # Include callers and tests, not just changed files, within a bounded snapshot.
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d.lower() not in EXCLUDED_DIRS and not d.startswith(".") and not (Path(current) / d).is_symlink())
        for name in sorted(files):
            path = (Path(current) / name).relative_to(root).as_posix()
            if source_language(path):
                paths.add(path)
        if len(paths) > MAX_FILES:
            diagnostics.append({"kind": "file_bound", "message": "Repository context truncated to 100 files."})
            break
    sources = {}
    total = 0
    ordered = list(dict.fromkeys([*sorted(changed_files), *sorted(paths - set(changed_files))]))
    for path in ordered[:MAX_FILES]:
        if not safe_relative_path(path) or not (source_language(path) or path == ".samanvaya/requirements.json"):
            diagnostics.append({"path": path[:240], "kind": "unsupported_or_unsafe_path"})
            continue
        absolute = (root / path).resolve()
        if not absolute.is_relative_to(root):
            diagnostics.append({"path": path, "kind": "outside_repository"})
            continue
        try:
            with absolute.open("rb") as handle:
                data = handle.read(MAX_SOURCE_BYTES + 1)
            if len(data) > MAX_SOURCE_BYTES or total + len(data) > MAX_TOTAL_BYTES:
                diagnostics.append({"path": path, "kind": "source_bound"})
                continue
            sources[path] = data.decode("utf-8-sig")
            total += len(data)
        except (OSError, UnicodeError):
            diagnostics.append({"path": path, "kind": "source_unavailable"})
    return await discover_sources(sources, repository_id, revision, diagnostics)
