"""Bounded server snapshots analyzed in the existing Docker isolation model."""
import asyncio
import hashlib
import json
import re
import uuid
from pathlib import PurePosixPath

from intelligence.evidence.models import CodeQualityEvidence

IMAGE = "samanvaya-quality:2"  # v4 DEF-V4-026: worker ESLint config changed
PROTOCOL = "quality-snapshot-v1"


def source_provenance(project_id, repository, revision, sources, organization_id=None):
    return {"method": "github-contents-v1", "project_id": project_id, "repository": repository, "organization_id": organization_id,
            "revision": revision, "source_hashes": {p: hashlib.sha256(s.encode("utf-8")).hexdigest()
                                                     for p, s in sources.items()}}


def snapshot_payload(changed_files, context):
    sources, provenance = context.get("source_files"), context.get("source_provenance")
    if (not isinstance(sources, dict) or not 1 <= len(sources) <= 100 or not isinstance(provenance, dict)
            or provenance.get("method") != "github-contents-v1"
            or provenance.get("project_id") != context.get("project_id")
            or not isinstance(context.get("project_id"), str) or not context["project_id"]
            or provenance.get("revision") != context.get("commit_sha")
            or provenance.get("organization_id") != context.get("organization_id")
            or not isinstance(context.get("commit_sha"), str)
            or not re.fullmatch(r"[a-f0-9]{40}", context["commit_sha"])
            or not isinstance(provenance.get("repository"), str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", provenance["repository"])):
        raise ValueError("A pinned server-resolved repository snapshot is required")
    seen, total, hashes = set(), 0, {}
    for path, source in sources.items():
        if (not isinstance(path, str) or not path or len(path) > 500 or "\\" in path or ":" in path
                or any(ord(character) < 32 or ord(character) == 127 for character in path)
                or path.startswith("/") or any(p in {"", ".", "..", ".git", "node_modules", ".venv", "venv"} for p in path.split("/"))
                or str(PurePosixPath(path)) != path or path.casefold() in seen
                or not isinstance(source, str)):
            raise ValueError("Unsafe or ambiguous snapshot path")
        raw = source.encode("utf-8")
        total += len(raw)
        if len(raw) > 200_000 or total > 2_000_000 or "\x00" in source:
            raise ValueError("Snapshot source exceeds supported bounds")
        seen.add(path.casefold())
        hashes[path] = hashlib.sha256(raw).hexdigest()
    if hashes != provenance.get("source_hashes"):
        raise ValueError("Snapshot hash mismatch")
    if (not isinstance(changed_files, list) or not changed_files or len(changed_files) > 100
            or any(path not in sources for path in changed_files)):
        raise ValueError("Selected files must belong to the pinned snapshot")
    return {"protocol": PROTOCOL, "changed_files": list(dict.fromkeys(changed_files)),
            "context": {"project_id": context["project_id"], "commit_sha": context["commit_sha"],
                        "pr_number": context.get("pr_number"), "organization_id": context.get("organization_id"),
                        "source_provenance": provenance}, "sources": sources}


def verify_evidence(evidence, payload, context):
    """Accept measurements only for the exact snapshot that was sent to the worker."""
    if (evidence.commit_sha != context["commit_sha"] or evidence.repository_id != context["project_id"]
            or not 0 <= evidence.files_analyzed <= len(payload["changed_files"])
            or any(f.file_path not in payload["sources"] for f in evidence.static_findings)
            or any(f.file_path not in payload["sources"] for f in evidence.security.findings)):
        raise ValueError("Quality measurements do not belong to the selected source")
    return evidence


def verify_brokered_evidence(evidence, payload, context):
    """OPS-03: the API re-checks a broker result; it never trusts the broker's identity claims."""
    verify_evidence(evidence, payload, context)
    provenance = evidence.execution_provenance or {}
    if (provenance.get("method") != PROTOCOL or provenance.get("network") != "none"
            or provenance.get("host_source_execution") is not False
            or provenance.get("source_hashes") != payload["context"]["source_provenance"]["source_hashes"]
            or provenance.get("revision") != context["commit_sha"]):
        raise ValueError("Worker broker returned measurements without matching isolation provenance")
    return evidence


class DockerQualityRunner:
    async def analyze(self, changed_files, context):
        from intelligence.algorithms.runner import DockerBenchmarkRunner, BenchmarkFailure

        payload = snapshot_payload(changed_files, context)
        process = DockerBenchmarkRunner(timeout_seconds=120, max_output_bytes=4_000_000)
        name = "samanvaya-quality-" + uuid.uuid4().hex
        try:
            async with asyncio.timeout(120):
                environment = await process._inspect([IMAGE])
                code, raw, _ = await process._command(
                    "run", "--rm", "--pull=never", "--name", name, "--network=none", "--cap-drop=ALL",
                    "--security-opt=no-new-privileges:true", "--user=65532:65532", "--read-only",
                    "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=128m,mode=1777", "--memory=768m", "--memory-swap=768m",
                    "--cpus=1", "--pids-limit=64", "--ulimit=nofile=128:128", "--init", "--log-driver=none", "--interactive",
                    environment["images"][IMAGE], data=json.dumps(payload, ensure_ascii=False).encode("utf-8"))
                if code:
                    raise BenchmarkFailure("Isolated quality worker failed; no measurements accepted")
                result = json.loads(raw)
                if (result.get("protocol") != PROTOCOL or result.get("revision") != context["commit_sha"]
                        or result.get("source_hashes") != payload["context"]["source_provenance"]["source_hashes"]):
                    raise ValueError("Quality worker returned mismatched source identity")
                evidence = verify_evidence(CodeQualityEvidence.model_validate(result["evidence"]), payload, context)
                evidence.execution_provenance = {**payload["context"]["source_provenance"], **environment,
                    "method": PROTOCOL, "network": "none", "host_source_execution": False,
                    "limitations": ["Static tools do not establish correctness or test execution",
                                    "Dependency advisory access is unavailable in the offline worker"]}
                return evidence
        finally:
            cleanup = asyncio.create_task(process._remove(name))
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                await cleanup
                raise
