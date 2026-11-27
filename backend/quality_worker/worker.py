"""Static tools only: no checkout hooks, package installation, or test execution."""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

from domain.services.code_quality_service import CodeQualityService
from intelligence.analyzers.isolated import snapshot_payload, PROTOCOL


async def main():
    raw = sys.stdin.buffer.read(4_000_001)
    if len(raw) > 4_000_000:
        raise ValueError("Payload limit exceeded")
    data = json.loads(raw)
    context = {**data["context"], "source_files": data["sources"]}
    payload = snapshot_payload(data["changed_files"], context)
    if data.get("protocol") != PROTOCOL:
        raise ValueError("Unsupported worker protocol")
    with tempfile.TemporaryDirectory(prefix="quality-") as directory:
        root = Path(directory)
        for path, source in payload["sources"].items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.encode("utf-8"))
        # Analyzer imports are image-owned. Submitted modules/tests are never imported.
        context["repo_path"] = str(root)
        context["isolated_quality_worker"] = True
        evidence = await CodeQualityService()._analyze_quality_pr(payload["changed_files"], context, deep_analysis=True)
        if evidence.analysis_quality.reason:
            evidence.analysis_quality.reason = evidence.analysis_quality.reason.replace('on host', 'in isolated worker')
        for finding in [*evidence.static_findings, *evidence.security.findings]:
            name = Path(finding.file_path)
            if name.is_absolute():
                finding.file_path = name.relative_to(root).as_posix()
        for function in evidence.complexity.high_complexity_functions:
            path = Path(function.get("file", ""))
            if path.is_absolute():
                function["file"] = path.relative_to(root).as_posix()
        print(json.dumps({"protocol": PROTOCOL, "revision": context["commit_sha"],
            "source_hashes": context["source_provenance"]["source_hashes"], "evidence": evidence.model_dump(mode="json")}))


if __name__ == "__main__":
    asyncio.run(main())
