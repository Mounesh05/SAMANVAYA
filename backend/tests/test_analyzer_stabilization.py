"""Trusted fixtures only; no live database, GitHub source execution or benchmarks."""
import asyncio
from unittest.mock import AsyncMock

import pytest

from intelligence.algorithms.discovery.service import discover_sources
from intelligence.evidence.models import CodeQualityEvidence


TRAVERSAL = '''
from collections import deque
def inspect_nodes(edges, origin):
    pending = deque([origin])
    seen = {origin}
    while pending:
        item = pending.popleft()
        for adjacent in edges.get(item, []):
            if adjacent not in seen:
                seen.add(adjacent)
                pending.append(adjacent)
    return seen
'''


def discover(sources):
    return asyncio.run(discover_sources(sources, "fixture-repository", "fixture-revision"))


@pytest.mark.parametrize("lifo,wrapped", [(False, False), (False, True), (True, False), (True, True)])
def test_get_adjacency_with_optional_reversed(lifo, wrapped):
    source = TRAVERSAL.replace("popleft()", "pop()") if lifo else TRAVERSAL
    if wrapped:
        source = source.replace("edges.get(item, [])", "reversed(edges.get(item, []))")
    function = discover({"module.py": source}).functions[0]
    expected = "lifo_graph_exploration" if lifo else "fifo_graph_traversal"
    assert expected in {p.kind for p in function.detected_patterns}
    assert function.verified_contract is None
    assert "shortest" not in str(function.task_hypotheses)
    assert all(e.source_revision == "fixture-revision" for e in function.evidence)


@pytest.mark.parametrize("before,after", [
    ("edges.get(item, [])", "edges.get(other, [])"),
    ("pending.append(adjacent)", "unrelated.append(adjacent)"),
    ("pending.append(adjacent)", "pending.append(item)"),
    ("item = pending.popleft()", "item = pending.popleft()\n        item = origin"),
    ("for adjacent in edges.get(item, []):", "for adjacent in edges.get(item, []):\n            adjacent = origin"),
    ("seen = {origin}", "seen = {origin}\n    edges = other"),
    ("edges.get(item, [])", "lookup.get(item, [])"),
])
def test_unconnected_or_rebound_values_do_not_establish_traversal(before, after):
    function = discover({"module.py": TRAVERSAL.replace(before, after)}).functions[0]
    assert not {"fifo_graph_traversal", "lifo_graph_exploration"} & {p.kind for p in function.detected_patterns}


def test_shadowed_reversed_is_not_treated_as_builtin():
    source = TRAVERSAL.replace("edges, origin", "edges, origin, reversed").replace("edges.get(item, [])", "reversed(edges.get(item, []))")
    function = discover({"module.py": source}).functions[0]
    assert "fifo_graph_traversal" not in {p.kind for p in function.detected_patterns}


def test_shadowed_queue_constructor_remains_uncertain():
    source = TRAVERSAL.replace("edges, origin", "edges, origin, deque")
    assert "fifo_graph_traversal" not in {p.kind for p in discover({"module.py": source}).functions[0].detected_patterns}


@pytest.mark.parametrize("root", ["service", "packages/runtime", "source-tree"])
def test_package_layout_links_imported_assertions(root):
    report = discover({f"{root}/pkg/__init__.py": "", f"{root}/pkg/logic.py": "def apply(value): return value * 2",
                       f"{root}/tests/test_logic.py": "from pkg.logic import apply\ndef test_it():\n    assert apply(3) == 6"})
    function = next(f for f in report.functions if f.name == "apply")
    assert function.callers and function.requirement_evidence_refs
    assert function.verified_contract is None


def test_ambiguous_package_roots_are_not_linked():
    sources = {f"{root}/pkg/{name}": source for root in ("one", "two") for name, source in
               [("__init__.py", ""), ("logic.py", "def apply(value): return value") ]}
    sources["tests/test_logic.py"] = "from pkg.logic import apply\ndef test_it():\n    assert apply(1) == 1"
    assert not any(f.callers for f in discover(sources).functions if f.name == "apply")


def test_package_import_shadowing_does_not_link_evidence():
    report = discover({"service/pkg/__init__.py": "", "service/pkg/logic.py": "def apply(value): return value",
        "tests/test_logic.py": "from pkg.logic import apply\ndef test_it():\n    apply = replacement\n    assert apply(1) == 1"})
    assert not next(f for f in report.functions if f.name == "apply").callers


@pytest.mark.parametrize("suffix", ["js", "ts", "tsx"])
def test_named_and_arrow_function_parser_provenance(suffix):
    report = discover({f"module.{suffix}": "export function twice(value) { return value * 2; }\nexport const apply = value => twice(value);"})
    assert report.status == "available"
    function = next(f for f in report.functions if f.name == "apply")
    assert function.parameters[0]["name"] == "value"
    assert function.calls[0]["resolved_function_id"]
    assert function.source_revision == "fixture-revision" and len(function.source_hash) == 64


@pytest.mark.asyncio
async def test_missing_selected_source_does_not_count_as_analyzed(tmp_path):
    from domain.services.code_quality_service import CodeQualityService
    evidence = await CodeQualityService().analyze_pr(["missing.py", "../escape.py"], {"repo_path": str(tmp_path)})
    assert evidence.files_analyzed == 0 and evidence.tools_skipped


@pytest.mark.asyncio
async def test_bandit_invalid_response_is_explicit_failure(monkeypatch):
    import intelligence.analyzers.python.analyzer as py
    analyzer = py.PythonAnalyzer()
    monkeypatch.setattr(analyzer, "_tool_available", lambda _: True)
    monkeypatch.setattr(py, "_run", AsyncMock(return_value='{"error": "configuration failed"}'))
    evidence = CodeQualityEvidence(repository_id="fixture", primary_language="python")
    assert await analyzer._security(["module.py"], ".", evidence) == []
    assert "bandit-failed" in evidence.tools_skipped and "bandit" not in evidence.tools_executed


@pytest.mark.asyncio
async def test_empty_coverage_totals_stay_unknown(tmp_path, monkeypatch):
    import intelligence.analyzers.python.analyzer as py
    analyzer = py.PythonAnalyzer()
    (tmp_path / ".coverage").write_bytes(b"controlled coverage data")
    monkeypatch.setattr(analyzer, "_tool_available", lambda _: True)
    monkeypatch.setattr(py, "_run", AsyncMock(return_value='{"totals": {}}'))
    evidence = CodeQualityEvidence(repository_id="fixture", primary_language="python")
    assert (await analyzer._testing(str(tmp_path), evidence)).coverage_percentage is None
    assert "coverage" in evidence.tools_skipped


@pytest.mark.asyncio
async def test_tsc_global_failure_is_a_finding(tmp_path, monkeypatch):
    import intelligence.analyzers.javascript.analyzer as js
    (tmp_path / "tsconfig.json").write_text('{}')
    monkeypatch.setattr(js, "_run", AsyncMock(return_value="error TS18003: No inputs were found in config file"))
    evidence = CodeQualityEvidence(repository_id="fixture", primary_language="typescript")
    findings = await js.JavaScriptAnalyzer()._tsc(str(tmp_path), evidence)
    assert findings[0].rule_id == "TSC-TS18003"


@pytest.mark.asyncio
async def test_source_snapshot_never_falls_back_to_host_working_directory(monkeypatch):
    from domain.services.code_quality_service import CodeQualityService
    from intelligence.analyzers.python.analyzer import PythonAnalyzer
    analyze = AsyncMock(side_effect=AssertionError("Host analyzer must not read unrelated files"))
    monkeypatch.setattr(PythonAnalyzer, "analyze", analyze)
    evidence = await CodeQualityService().analyze_pr(["module.py"], {
        "project_id": "fixture", "source_files": {"module.py": "def apply(x): return x"}, "commit_sha": "sha"})
    assert evidence.files_analyzed == 0
    assert evidence.tools_skipped and evidence.analysis_quality.reason
    assert evidence.function_discovery.functions
    analyze.assert_not_awaited()


@pytest.mark.asyncio
async def test_tsconfig_in_subproject_uses_correct_cwd_and_paths(tmp_path, monkeypatch):
    import intelligence.analyzers.javascript.analyzer as js
    root = tmp_path / "client"
    root.mkdir()
    (root / "tsconfig.json").write_text('{}')
    runner = AsyncMock(return_value="src/main.ts(2,1): error TS2322: wrong type")
    monkeypatch.setattr(js, "_run", runner)
    evidence = CodeQualityEvidence(repository_id="fixture", primary_language="typescript")
    findings = await js.JavaScriptAnalyzer()._tsc(str(tmp_path), evidence, ["client/src/main.ts"])
    assert runner.await_args.kwargs["cwd"] == str(root)
    assert findings[0].file_path == "client/src/main.ts"
    assert findings[0].source_tool == "tsc"


@pytest.mark.asyncio
async def test_python_static_tests_are_not_pytest_execution(tmp_path, monkeypatch):
    from intelligence.analyzers.python.analyzer import PythonAnalyzer
    (tmp_path / "test_fixture.py").write_text("def test_case(): assert True")
    analyzer = PythonAnalyzer()
    monkeypatch.setattr(analyzer, "_tool_available", lambda _: False)
    evidence = CodeQualityEvidence(repository_id="fixture", primary_language="python")
    testing = await analyzer._testing(str(tmp_path), evidence)
    assert testing.total_tests == 1 and testing.coverage_percentage is None
    assert "pytest-collect" not in evidence.tools_executed
    assert "ast-test-discovery" in evidence.tools_executed


def test_purpose_only_quality_projection_is_explicit_and_non_mutating():
    from api.routes.code_quality import analysis_scope
    run = {"status": "completed", "analysis_level": "purpose_discovery", "quality_score": None}
    result = analysis_scope(run)
    assert result["quality_analysis_status"] == "not_run"
    assert result["analysis_scope"] == "purpose_discovery"
    assert result["quality_unavailable_reason"]
    assert "analysis_scope" not in run


@pytest.mark.asyncio
async def test_unsupported_windows_subprocess_reports_docker_unavailable(monkeypatch):
    from intelligence.algorithms.runner import DockerBenchmarkRunner
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(side_effect=NotImplementedError))
    result = await DockerBenchmarkRunner().availability()
    assert result["available"] is False
    assert "without --reload" in result["error"]


@pytest.mark.anyio
async def test_source_only_run_never_scores_or_updates_baseline(mock_db, monkeypatch):
    from api.routes import code_quality
    from intelligence.quality_engine import QualityEngine
    from intelligence.risk_engine import RiskEngine
    from intelligence.baselines.repository_baseline import RepositoryBaseline
    monkeypatch.setattr(code_quality, "col", lambda name: mock_db[name])
    monkeypatch.setattr(code_quality.cq_service, "analyze_pr", AsyncMock(return_value=
        CodeQualityEvidence(repository_id="fixture", primary_language="python", commit_sha="exact-sha")))
    quality, risk, baseline = AsyncMock(), AsyncMock(), AsyncMock()
    monkeypatch.setattr(QualityEngine, "calculate", quality)
    monkeypatch.setattr(RiskEngine, "analyze_evidence", risk)
    monkeypatch.setattr(RepositoryBaseline, "update_baseline", baseline)
    await mock_db.code_quality_runs.insert_one({"run_id": "fixture"})
    await code_quality._run_analysis("fixture", code_quality.AnalyzeRequest(repository_id="fixture",
        changed_files=["module.py"], use_ai=False), None)
    saved = await mock_db.code_quality_runs.find_one({"run_id": "fixture"})
    assert saved["status"] == "completed" and saved["quality_analysis_status"] == "not_run"
    assert saved["quality_score"] is None and saved["risk_score"] is None
    assert saved["commit_sha"] == "exact-sha"
    quality.assert_not_awaited()
    risk.assert_not_awaited()
    baseline.assert_not_awaited()
