"""Server-pinned quality snapshots cannot select host paths or execute on host."""
import hashlib
from unittest.mock import AsyncMock

import pytest

from intelligence.analyzers.isolated import DockerQualityRunner, snapshot_payload
from intelligence.evidence.models import CodeQualityEvidence


def context():
    source = "def increment(value):\n    return value + 1\n"
    return {"project_id": "P", "commit_sha": "a" * 40, "source_files": {"module.py": source},
            "source_provenance": {"method": "github-contents-v1", "project_id": "P", "repository": "example/service",
                "revision": "a" * 40, "source_hashes": {"module.py": hashlib.sha256(source.encode()).hexdigest()}}}


@pytest.mark.parametrize("path", ["../private.py", "/private.py", "C:/private.py", "a\\private.py", ".git/hooks/run.py", "a/../private.py"])
def test_quality_snapshot_rejects_unsafe_paths(path):
    data = context()
    data["source_files"] = {path: "pass"}
    with pytest.raises(ValueError):
        snapshot_payload([path], data)


@pytest.mark.parametrize("field,value", [("project_id", "FOREIGN"), ("revision", "b" * 40), ("method", "SERVER_VERIFIED")])
def test_quality_snapshot_requires_exact_server_scope(field, value):
    data = context()
    data["source_provenance"][field] = value
    with pytest.raises(ValueError):
        snapshot_payload(["module.py"], data)


def test_quality_snapshot_hashes_and_case_collisions_are_checked():
    data = context()
    data["source_files"]["module.py"] = "forged source"
    with pytest.raises(ValueError):
        snapshot_payload(["module.py"], data)
    data = context()
    data["source_files"]["MODULE.py"] = data["source_files"]["module.py"]
    with pytest.raises(ValueError):
        snapshot_payload(["module.py"], data)


@pytest.mark.anyio
async def test_offline_python_worker_reports_advisory_limit_with_nested_manifest(monkeypatch, tmp_path):
    from intelligence.analyzers.python.analyzer import PythonAnalyzer

    project = tmp_path / "backend"
    project.mkdir()
    (project / "requirements.txt").write_text("pydantic==2.9.2", encoding="utf-8")
    (project / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    audit = AsyncMock()
    monkeypatch.setattr(PythonAnalyzer, "_dependencies", audit)
    evidence = await PythonAnalyzer().analyze(
        ["backend/app.py"], str(tmp_path), {"isolated_quality_worker": True},
    )
    audit.assert_not_awaited()
    assert "dependency-advisories-offline" in evidence.tools_skipped
    assert "dependency-manifest-unavailable" not in evidence.tools_skipped
    assert evidence.testing.coverage_percentage is None


@pytest.mark.anyio
async def test_quality_container_uses_existing_isolation_and_retains_provenance(monkeypatch):
    import json
    from intelligence.algorithms.runner import DockerBenchmarkRunner

    data = context()
    evidence = CodeQualityEvidence(repository_id="P", commit_sha="a" * 40, files_analyzed=1, primary_language="python",
                                   tools_executed=["ruff"])
    response = {"protocol": "quality-snapshot-v1", "revision": "a" * 40,
                "source_hashes": data["source_provenance"]["source_hashes"], "evidence": evidence.model_dump(mode="json")}
    command = AsyncMock(return_value=(0, json.dumps(response).encode(), b""))
    monkeypatch.setattr(DockerBenchmarkRunner, "_inspect", AsyncMock(return_value={"images": {"samanvaya-quality:2": "sha256:trusted"}}))
    monkeypatch.setattr(DockerBenchmarkRunner, "_command", command)
    cleanup = AsyncMock()
    monkeypatch.setattr(DockerBenchmarkRunner, "_remove", cleanup)
    result = await DockerQualityRunner().analyze(["module.py"], data)
    args = command.call_args.args
    assert "--network=none" in args and "--read-only" in args and "--pull=never" in args
    assert "--user=65532:65532" in args and "--cap-drop=ALL" in args
    assert not any("docker.sock" in str(a) or str(a).startswith("--volume") for a in args)
    assert result.files_analyzed == 1 and result.execution_provenance["revision"] == "a" * 40
    cleanup.assert_awaited_once()
