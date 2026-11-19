"""Bounded GitHub Actions observations, not synthetic Checks or test proof."""

import asyncio
import hashlib
import json
import re
from datetime import datetime, timezone

import httpx

MAX_PAGES = 3
MAX_RUNS = 20


def failure_details(error: Exception) -> dict:
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    headers = getattr(response, "headers", {})
    rate_limited = status == 429 or (status == 403 and (
        headers.get("x-ratelimit-remaining") == "0" or bool(headers.get("retry-after"))))
    kind = ("rate_limited" if rate_limited else "permission_denied" if status in (401, 403)
            else "transient_error" if status in (500, 502, 503, 504) or isinstance(error, httpx.TransportError)
            else "invalid_response" if isinstance(error, (ValueError, TypeError, KeyError)) else "provider_error")
    details = {"kind": kind, "http_status": status}
    if rate_limited:
        details["retry_after"] = headers.get("retry-after")
        details["rate_limit_reset"] = headers.get("x-ratelimit-reset")
    return details


async def _read(call):
    """One short transient retry; defer rate limits instead of sleeping past them."""
    for attempt in range(2):
        try:
            return await call()
        except Exception as error:
            if attempt == 0 and failure_details(error)["kind"] == "transient_error":
                await asyncio.sleep(0.1)
                continue
            raise


async def _pages(call, key):
    rows = []
    for page in range(1, MAX_PAGES + 1):
        payload = await _read(lambda: call(page))
        if (not isinstance(payload, dict) or not isinstance(payload.get(key), list)
                or type(payload.get("total_count")) is not int or payload["total_count"] < 0
                or any(not isinstance(row, dict) for row in payload[key])):
            raise ValueError("Malformed paginated Actions response")
        rows.extend(payload[key])
        if len(rows) >= payload["total_count"]:
            return rows, False
        if not payload[key]:
            return rows, True
    return rows, True


def _positive(value):
    return type(value) is int and value > 0


def _outcome(runs):
    observations = [row for run in runs for row in [run, *run["jobs"]]]
    if any(row.get("conclusion") in ("failure", "timed_out", "action_required", "startup_failure") for row in observations):
        return "failure"
    if any(row.get("status") in ("in_progress", "queued", "waiting", "requested", "pending") for row in observations):
        return "pending"
    if any(row.get("conclusion") == "cancelled" for row in observations):
        return "cancelled"
    if observations and all(row.get("status") == "completed" and row.get("conclusion") == "success" for row in observations):
        return "success"
    return "unknown"


def _new_evidence(owner, repo, sha):
    return {"schema_version": "github-actions-ci-v1", "source": "github_actions",
        "authority": "GITHUB_REPORTED_OUTCOME", "verification_scope": "SOURCE_IDENTITY_ONLY",
        "repository": f"{owner}/{repo}", "commit_sha": sha, "status": "unavailable", "reported_outcome": "unknown",
        "runs": [], "errors": [], "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "limitations": ["Workflow/job conclusions are GitHub-reported outcomes, not independent test results or correctness proof",
                         "Only exact-head GitHub Actions runs are covered; third-party check providers are not covered"]}


def _seal(evidence):
    material = {k: v for k, v in evidence.items() if k not in ("retrieved_at", "content_sha256")}
    evidence["content_sha256"] = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return evidence


def unavailable_actions_ci(owner, repo, sha, failure):
    evidence = _new_evidence(owner, repo, sha)
    evidence["errors"].append(failure)
    return _seal(evidence)


async def collect_actions_ci(client, owner: str, repo: str, sha: str) -> dict:
    repository = f"{owner}/{repo}"
    evidence = _new_evidence(owner, repo, sha)

    def finish():
        return _seal(evidence)

    if (not re.fullmatch(r"[A-Za-z0-9_-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo)
            or repo in (".", "..") or not isinstance(sha, str) or not re.fullmatch(r"[a-fA-F0-9]{40}", sha)):
        evidence["errors"].append({"kind": "invalid_scope"})
        return finish()
    try:
        runs, truncated = await _pages(lambda page: client.list_workflow_runs(owner, repo, sha, page=page), "workflow_runs")
    except Exception as error:
        evidence["errors"].append({"resource": "workflow_runs", **failure_details(error)})
        return finish()
    if truncated or len(runs) > MAX_RUNS:
        evidence["errors"].append({"kind": "workflow_run_bound"})
    seen = set()
    for run in runs[:MAX_RUNS]:
        run_id, attempt = run.get("id"), run.get("run_attempt")
        run_repo = run.get("repository") or {}
        if (not isinstance(run_repo, dict) or str(run_repo.get("full_name", "")).casefold() != repository.casefold()
                or run.get("head_sha") != sha or not _positive(run_id) or not _positive(attempt)
                or not _positive(run.get("workflow_id")) or (run_id, attempt) in seen):
            evidence["errors"].append({"kind": "run_scope_mismatch_or_duplicate"})
            continue
        seen.add((run_id, attempt))
        run_url = f"https://api.github.com/repos/{repository}/actions/runs/{run_id}"
        record = {"run_id": run_id, "run_attempt": attempt, "workflow_id": run["workflow_id"],
            "repository": repository, "commit_sha": sha, "name": run.get("name"), "event": run.get("event"),
            "status": run.get("status"), "conclusion": run.get("conclusion"),
            "source_reference": run_url, "html_url": f"https://github.com/{repository}/actions/runs/{run_id}", "jobs": []}
        evidence["runs"].append(record)
        try:
            jobs, jobs_truncated = await _pages(lambda page: client.list_workflow_jobs(owner, repo, run_id, attempt, page=page), "jobs")
            if jobs_truncated:
                evidence["errors"].append({"kind": "workflow_job_bound", "run_id": run_id})
        except Exception as error:
            evidence["errors"].append({"resource": "workflow_jobs", "run_id": run_id, **failure_details(error)})
            continue
        job_ids = set()
        for job in jobs:
            job_id = job.get("id")
            if (not _positive(job_id) or job_id in job_ids or not _positive(job.get("run_id")) or job.get("run_id") != run_id
                    or not _positive(job.get("run_attempt", attempt)) or job.get("run_attempt", attempt) != attempt or job.get("head_sha") != sha
                    or str(job.get("run_url", "")).casefold() != run_url.casefold()):
                evidence["errors"].append({"kind": "job_scope_mismatch_or_duplicate", "run_id": run_id})
                continue
            job_ids.add(job_id)
            record["jobs"].append({"job_id": job_id, "run_id": run_id, "run_attempt": attempt,
                "repository": repository, "commit_sha": sha, "name": job.get("name"),
                "status": job.get("status"), "conclusion": job.get("conclusion"),
                "source_reference": f"{run_url}/attempts/{attempt}/jobs#job-{job_id}"})
        if not jobs and run.get("status") == "completed":
            evidence["errors"].append({"kind": "completed_run_jobs_missing", "run_id": run_id})
    evidence["status"] = "partial" if evidence["errors"] else "available" if evidence["runs"] else "missing"
    if evidence["status"] == "available":
        evidence["reported_outcome"] = _outcome(evidence["runs"])
    return finish()
