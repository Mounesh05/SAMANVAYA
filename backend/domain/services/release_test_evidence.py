"""Exact-candidate test evidence from the trusted GitHub build attempt."""
import hashlib

import httpx
from fastapi import HTTPException

from core.config import settings
from core.database import col
from domain.services.release_discovery import artifact_inventory, verify_trusted_run
from integrations.github.client import GitHubClient
from integrations.github.test_artifacts import parse_archive
from repositories.pr_repository import PRRepository


def _evidence(status, reason, runs=(), coverage=None):
    return {"qa": {"status": status, "reason": reason, "runs": list(runs)},
            "coverage_status": "reported" if coverage else "missing", "coverage": coverage}


async def release_tests(manifest):
    artifact = manifest.get("artifact")
    if not artifact:
        return _evidence("unknown", "Verified build provenance is required.")
    required = {name.strip() for name in settings.RELEASE_REQUIRED_TEST_SUITES.split(",") if name.strip()}
    if not required or len(required) > 20 or any("/" not in suite for suite in required):
        return _evidence("unknown", "Configure the required release JUnit report identities.")
    client = GitHubClient()
    owner, name = manifest["repository"].split("/")
    target = manifest["target_sha"]
    run_id = artifact["run_id"]
    try:
        current_attempt = await col("webhook_events").find_one({
            **PRRepository._project_scope([manifest["project_id"]], manifest["organization_id"]),
            "source": "github", "event_type": "workflow_run", "payload.repository.id": manifest["repository_id"],
            "payload.workflow_run.id": run_id, "payload.workflow_run.head_sha": target,
            "payload.workflow_run.run_attempt": {"$gt": artifact["run_attempt"]},
        }, {"_id": 1})
        if current_attempt:
            return _evidence("unknown", "A newer webhook attempt requires a fresh artifact and review.")
        listing = await client.list_workflow_runs(owner, name, target)
        runs = listing["workflow_runs"]
        if listing["total_count"] != len(runs):
            return _evidence("unknown", "The target workflow history is incomplete.")
        current = max((r for r in runs if r.get("workflow_id") == artifact["workflow_id"]
                       and r.get("head_branch") == settings.RELEASE_TRUSTED_BUILD_REF
                       and r.get("head_sha") == target and r.get("event") == "push"),
                      key=lambda r: r["run_number"], default=None)
        if not current:
            return _evidence("unknown", "The current trusted workflow run could not be found.")
        if current.get("conclusion") in {"failure", "timed_out", "startup_failure", "action_required"}:
            return _evidence("failed", "The latest trusted workflow attempt failed.")
        if current.get("id") != run_id or current.get("run_attempt") != artifact["run_attempt"]:
            return _evidence("unknown", "A newer build attempt requires a fresh artifact and review.")
        run, workflow_digest = await verify_trusted_run(
            client, owner, name, manifest["repository_id"], target, run_id
        )
        if run["run_attempt"] != artifact["run_attempt"] or workflow_digest != artifact["workflow_sha256"]:
            return _evidence("unknown", "The trusted workflow attempt changed.")
        inventory = await artifact_inventory(client, owner, name, manifest["repository_id"], target, run)
        if not any(item["id"] == artifact["id"] and item["digest"] == artifact["digest"] for item in inventory):
            return _evidence("unknown", "The approved build artifact is unavailable.")
        suffix = f"-{run_id}-{run['run_attempt']}"
        reports, coverage = [], None
        expected_names = {suite.split("/", 1)[0] for suite in required}
        for item in inventory:
            logical = item["name"].removesuffix(suffix)
            if logical not in expected_names:
                continue
            raw = await client.download_workflow_artifact(owner, name, item["id"])
            if len(raw) != item["size_bytes"] or hashlib.sha256(raw).hexdigest() != item["digest"]:
                return _evidence("unknown", "A release test report failed artifact integrity verification.")
            parsed, measured = parse_archive(raw)
            if measured and coverage:
                return _evidence("unknown", "Multiple coverage reports require an explicit mapping.")
            coverage = measured or coverage
            for report in parsed:
                reports.append({**report, "test_suite": f"{logical}/{report['report_path']}",
                                "workflow_run_id": run_id, "run_attempt": run["run_attempt"],
                                "artifact_id": item["id"], "artifact_digest": item["digest"]})
        reports.sort(key=lambda report: report["test_suite"])
        suites = [report["test_suite"] for report in reports]
        if any(report["tests_failed"] for report in reports):
            return _evidence("failed", "The combined release test evidence contains failures.", reports, coverage)
        if set(suites) != required or len(suites) != len(required) or any(
            report["tests_skipped"] or not report["tests_passed"] for report in reports
        ):
            return _evidence("unknown", "Required reports are missing, duplicate or skipped.", reports, coverage)
        minimum = settings.RELEASE_MIN_COVERAGE_PERCENT
        if minimum and not coverage:
            return _evidence("unknown", "This release policy requires a measured coverage report.", reports)
        if minimum and coverage["coverage_percentage"] < minimum:
            return _evidence("failed", "Measured coverage falls below the release policy threshold.", reports, coverage)
        latest = await client.get_workflow_run(owner, name, run_id)
        if any(latest.get(key) != run.get(key) for key in ("run_attempt", "head_sha", "status", "conclusion")):
            return _evidence("unknown", "The build attempt changed during verification.")
        return _evidence("passed", "Required combined-revision suites passed.", reports, coverage)
    except (HTTPException, httpx.HTTPError, ValueError, KeyError, TypeError):
        return _evidence("unknown", "Trusted combined-revision evidence could not be verified.")
