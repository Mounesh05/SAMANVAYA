"""Exercise real analyzer control flow rather than mock-only assertions."""

import asyncio
import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from intelligence.analyzers.javascript import analyzer as js
from intelligence.analyzers.python import analyzer as py
from intelligence.evidence.models import CodeQualityEvidence


@pytest.mark.parametrize("module", [py, js], ids=["python", "javascript"])
def test_subprocess_runner_preserves_arguments_without_shell(module, tmp_path):
    value = "spaces ; & $(not-a-command)"
    result = asyncio.run(module._run(
        [sys.executable, "-c", "import sys; print(sys.argv[1])", value], str(tmp_path)
    ))
    assert result is not None
    assert result.strip() == value


@pytest.mark.parametrize("module", [py, js], ids=["python", "javascript"])
@pytest.mark.parametrize("cancelled", [False, True], ids=["timeout", "cancellation"])
@pytest.mark.parametrize("already_exited", [False, True], ids=["running", "exit-race"])
def test_subprocess_failure_kills_and_reaps_child(module, monkeypatch, cancelled, already_exited):
    error = asyncio.CancelledError() if cancelled else asyncio.TimeoutError()
    proc = SimpleNamespace(
        communicate=AsyncMock(side_effect=error),
        kill=Mock(side_effect=ProcessLookupError() if already_exited else None),
        wait=AsyncMock(return_value=-9),
    )
    spawn = AsyncMock(return_value=proc)
    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", spawn)
    if cancelled:
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(module._run([sys.executable, "-V"]))
    else:
        assert asyncio.run(module._run([sys.executable, "-V"])) is None
    proc.kill.assert_called_once()
    proc.wait.assert_awaited_once()
    assert "shell" not in spawn.call_args.kwargs


def test_missing_and_empty_commands_never_spawn(monkeypatch):
    monkeypatch.setattr(js.shutil, "which", lambda *args, **kwargs: None)
    spawn = AsyncMock()
    monkeypatch.setattr(js.asyncio, "create_subprocess_exec", spawn)
    assert asyncio.run(js._run([])) is None
    assert asyncio.run(js._run(["missing-analyzer-binary"])) is None
    spawn.assert_not_awaited()


@pytest.mark.parametrize("module", [py, js], ids=["python", "javascript"])
def test_quiet_process_failure_is_not_a_clean_scan(module):
    assert asyncio.run(module._run([sys.executable, "-c", "raise SystemExit(2)"])) is None
    assert asyncio.run(module._run([sys.executable, "-c", "pass"])) == ""


@pytest.mark.parametrize("payload,available", [
    ('{"vulnerabilities":{}}', True),
    ('{"error":{"code":"ENOTFOUND"}}', False),
    ('{"vulnerabilities":null}', False),
    ("not JSON", False),
])
def test_audit_failure_is_distinct_from_zero_vulnerabilities(monkeypatch, tmp_path, payload, available):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(js, "_run", AsyncMock(return_value=payload))
    evidence = CodeQualityEvidence(repository_id="test", primary_language="javascript")
    assert asyncio.run(js.JavaScriptAnalyzer()._npm_audit(str(tmp_path), evidence)) == []
    assert ("npm-audit" in evidence.tools_executed) is available
    assert ("npm-audit" in evidence.tools_skipped) is not available


def test_local_windows_node_cli_is_invoked_directly(monkeypatch, tmp_path):
    wrapper = tmp_path / "node_modules" / ".bin" / "tsc.cmd"
    wrapper.parent.mkdir(parents=True)
    wrapper.touch()
    script = tmp_path / "node_modules" / "typescript" / "bin" / "tsc"
    script.parent.mkdir(parents=True)
    script.write_text("// test CLI", encoding="utf-8")
    monkeypatch.setattr(js, "os", SimpleNamespace(name="nt"))

    def which(binary, path=None):
        if binary == "node":
            return "node.exe"
        if binary == "tsc" and path == str(wrapper.parent):
            return str(wrapper)
        return None

    monkeypatch.setattr(js.shutil, "which", which)
    assert js._resolve_command(["tsc", "--noEmit"], str(tmp_path)) == [
        "node.exe", str(script), "--noEmit",
    ]


def test_tsc_fallback_runs_and_partitions_absolute_windows_paths(monkeypatch, tmp_path):
    (tmp_path / "tsconfig.json").write_text("{}", encoding="utf-8")
    run = AsyncMock(side_effect=[None, "src\\Changed.ts(1,2): error TS2322: Wrong type.\n"
                                      "legacy/old.ts(3,4): error TS2304: Missing name.\n"])
    monkeypatch.setattr(js, "_run", run)
    evidence = CodeQualityEvidence(repository_id="test", primary_language="typescript")
    findings = asyncio.run(js.JavaScriptAnalyzer()._tsc(
        str(tmp_path), evidence, changed_files=["src/changed.ts"],
    ))
    assert [call.args[0][0] for call in run.await_args_list] == ["tsc", "npx"]
    assert [f.source_tool for f in findings] == ["tsc", "tsc-repo-wide"]
    assert findings[1].rule_id == "TSC-REPO-TS2304"
    absolute = js.JavaScriptAnalyzer._parse_tsc(
        "C:\\repo\\src\\Changed.ts(1,2): error TS2322: Wrong type.",
        changed_files=["src/changed.ts"], repo_path="C:/repo",
    )
    assert absolute[0].file_path == "src/Changed.ts"
    assert absolute[0].source_tool == "tsc"


def test_eslint_paths_are_relative_to_repository():
    output = json.dumps([{"filePath": "C:\\repo\\src\\app.ts", "messages": [
        {"line": 1, "severity": 2, "ruleId": "no-unused-vars", "message": "Unused value"},
    ]}])
    findings = js.JavaScriptAnalyzer._parse_eslint(output, ["src/app.ts"], "C:/repo")
    assert findings[0].file_path == "src/app.ts"


@pytest.mark.parametrize("output", ["[]", "null", '{"vulnerabilities":null}',
                                      '{"vulnerabilities":{"bad":null}}'])
def test_malformed_audit_shapes_do_not_raise(output):
    assert js.JavaScriptAnalyzer._parse_npm_audit(output) == []


def test_audit_preserves_multiple_advisories_after_transitive_reference():
    payload = {"vulnerabilities": {"pkg": {"severity": None, "via": [
        "transitive-parent", {"url": "GHSA-one", "title": "First issue"},
        {"source": 1234, "title": "Second issue"}, {"url": None, "title": None},
    ]}}}
    result = js.JavaScriptAnalyzer._parse_npm_audit(json.dumps(payload))
    assert result == [{"package": "pkg", "severity": "unknown", "cve": "GHSA-one; 1234",
                       "description": "First issue; Second issue"}]
