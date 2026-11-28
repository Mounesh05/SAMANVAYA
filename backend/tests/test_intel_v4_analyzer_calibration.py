"""v4 CQ-03: a Python file that does not parse must never look clean.

Ruff 0.6.9 (the version pinned in the quality worker image) reports a syntax
error as an item with ``"code": null``. The parser used to call
``None.startswith`` on it, the whole lint pass raised, the syntax error was
dropped, and because "ruff" was already recorded as executed the file scored
100 like a clean control (fixture A-PY03).
"""

import json

import pytest

from intelligence.analyzers.python.analyzer import PythonAnalyzer
from intelligence.evidence.models import CodeQualityEvidence, SeverityEnum
from intelligence.quality_engine import QualityEngine

# Captured from `ruff check --output-format=json` in samanvaya-quality (ruff 0.6.9)
# for fixture A-PY03: "def broken(x)\n    return x\n".
RUFF_SYNTAX_ERROR = [{
    "cell": None, "code": None, "end_location": {"column": 1, "row": 2},
    "filename": "/tmp/quality-x/broken.py", "fix": None, "location": {"column": 14, "row": 1},
    "message": "SyntaxError: Expected ':', found newline", "noqa_row": None, "url": None,
}]
RUFF_UNUSED_IMPORT = [{
    "cell": None, "code": "F401", "end_location": {"column": 12, "row": 1},
    "filename": "/tmp/quality-x/unused.py", "fix": None, "location": {"column": 8, "row": 1},
    "message": "`math` imported but unused", "noqa_row": 1, "url": None,
}]


def test_ruff_syntax_error_becomes_a_critical_syntax_finding():
    findings = PythonAnalyzer._parse_ruff(json.dumps(RUFF_SYNTAX_ERROR), ["broken.py"])
    assert len(findings) == 1
    finding = findings[0]
    assert finding.rule_id == "RUFF-SYNTAX-ERROR"
    assert finding.category == "syntax"
    assert finding.severity == SeverityEnum.CRITICAL
    assert finding.line_number == 1
    assert "Expected ':'" in finding.message


def test_syntax_error_is_kept_alongside_ordinary_lint_findings():
    findings = PythonAnalyzer._parse_ruff(json.dumps(RUFF_SYNTAX_ERROR + RUFF_UNUSED_IMPORT), [])
    assert [f.rule_id for f in findings] == ["RUFF-SYNTAX-ERROR", "RUFF-F401"]


def test_unparseable_file_does_not_score_as_clean():
    clean, broken = (CodeQualityEvidence(repository_id="P-QA-A", primary_language="python",
                                         detected_languages=["python"], tools_executed=["ruff"],
                                         execution_provenance={"method": "quality-snapshot-v1"})
                     for _ in range(2))
    broken.static_findings = PythonAnalyzer._parse_ruff(json.dumps(RUFF_SYNTAX_ERROR), ["broken.py"])
    engine = QualityEngine()
    assert engine._static_security_penalty(clean) == 0
    assert engine._static_security_penalty(broken) > 0


@pytest.mark.anyio
async def test_lint_pass_reports_the_syntax_error_instead_of_failing(monkeypatch, tmp_path):
    from intelligence.analyzers.python import analyzer as module

    (tmp_path / "broken.py").write_text("def broken(x)\n    return x\n")

    async def fake_run(command, cwd=None, **_):
        return json.dumps(RUFF_SYNTAX_ERROR) if command[0] == "ruff" else None

    monkeypatch.setattr(module, "_run", fake_run)
    analyzer = PythonAnalyzer()
    monkeypatch.setattr(analyzer, "_tool_available", lambda binary: binary == "ruff")
    evidence = CodeQualityEvidence(repository_id="P-QA-A", primary_language="python")
    findings = await analyzer._lint(["broken.py"], [str(tmp_path / "broken.py")], str(tmp_path), evidence)
    assert [f.rule_id for f in findings] == ["RUFF-SYNTAX-ERROR"]
    assert "ruff" in evidence.tools_executed


# ── v4 CQ-01 / CQ-17: unanalysed languages must not publish a quality score ──
# Observed through the candidate worker: a broken Java, C or C++ file (no
# toolchain in the image) and a Go file (no analyzer, 0 files analysed) each
# scored 100 because duplication alone was left as a "measured" dimension.

def _snapshot(**fields):
    evidence = CodeQualityEvidence(repository_id="P-QA-A", primary_language=fields.pop("language", "java"),
                                   execution_provenance={"method": "quality-snapshot-v1"}, **fields)
    evidence.detected_languages = [evidence.primary_language]
    return evidence


async def _score(evidence):
    engine = QualityEngine()

    async def default_config(project_id=None):
        return engine._config_service._create_default_configuration(project_id)

    engine._config_service.get_configuration = default_config
    return await engine.calculate(evidence)


@pytest.mark.anyio
@pytest.mark.parametrize("language,executed", [("java", ["java-regex-fallback"]), ("c", []), ("cpp", ["cpp-regex-fallback"])])
async def test_no_quality_score_without_lint_or_security_evidence(language, executed):
    result = await _score(_snapshot(language=language, files_analyzed=1, tools_executed=executed))
    assert result["quality_score"] is None and result["quality_grade"] is None


@pytest.mark.anyio
async def test_no_quality_score_when_no_file_was_analysed():
    evidence = _snapshot(language="go", files_analyzed=0)
    evidence.complexity.is_available = True
    evidence.complexity.average_complexity = 0.0
    result = await _score(evidence)
    assert result["quality_score"] is None


@pytest.mark.anyio
async def test_measured_python_snapshot_is_still_scored():
    result = await _score(_snapshot(language="python", files_analyzed=1, tools_executed=["ruff", "bandit"]))
    assert result["quality_score"] == 100


@pytest.mark.anyio
async def test_languages_endpoint_only_advertises_runtime_verified_languages():
    from api.routes.code_quality import supported_languages
    from intelligence.analyzers.registry import list_supported_languages

    body = await supported_languages()
    assert body["supported_languages"] == ["javascript", "python", "typescript"]
    assert body["experimental_languages"] == ["c", "cpp", "java"]
    # The adapters stay registered; only the claim changes.
    assert set(body["supported_languages"] + body["experimental_languages"]) == set(list_supported_languages())


# ── v4 CQ-11: control characters in snapshot paths ──────────────────────────

@pytest.mark.parametrize("character", ["\n", "\t", "\b", "\x1b", "\x7f"])
def test_snapshot_rejects_control_characters_in_paths(character):
    import hashlib

    from intelligence.analyzers.isolated import snapshot_payload

    path, sha = f"src/a{character}b.py", "a" * 40
    context = {"project_id": "P", "organization_id": "O", "commit_sha": sha, "source_files": {path: "x = 1\n"},
               "source_provenance": {"method": "github-contents-v1", "project_id": "P", "organization_id": "O",
                                     "repository": "o/r", "revision": sha,
                                     "source_hashes": {path: hashlib.sha256(b"x = 1\n").hexdigest()}}}
    with pytest.raises(ValueError, match="Unsafe or ambiguous snapshot path"):
        snapshot_payload([path], context)


# ── v4 CQ-10: a missing linter is disclosed and a parse check is not "lint" ─

@pytest.mark.anyio
async def test_missing_ruff_is_reported_and_static_dimension_is_not_scored(tmp_path):
    (tmp_path / "unused.py").write_text("import math\n\ndef add(a, b):\n    return a + b\n")
    analyzer = PythonAnalyzer()
    analyzer._tool_available = lambda binary: False
    evidence = await analyzer.analyze(["unused.py"], str(tmp_path), {"project_id": "P-QA-A", "isolated_quality_worker": True})
    assert "ruff" in evidence.tools_skipped
    evidence.execution_provenance = {"method": "quality-snapshot-v1"}
    assert "static_security" in QualityEngine._missing_dimensions(evidence)
    assert (await _score(evidence))["quality_score"] is None
