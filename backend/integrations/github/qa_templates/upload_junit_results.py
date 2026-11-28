"""Upload a JUnit XML result to Samanvaya from CI."""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def _optional_environment(name: str) -> str | None:
    return os.environ.get(name, "").strip() or None


def _github_metadata() -> dict:
    """Preserve Actions identity; a PR uses its head, never GitHub's merge SHA."""
    result = {"source": "github_actions", "commit_sha": os.environ.get("GITHUB_SHA", ""),
              "branch": os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME", ""),
              "workflow_name": os.environ.get("GITHUB_WORKFLOW")}
    run_id, attempt = os.environ.get("GITHUB_RUN_ID", ""), os.environ.get("GITHUB_RUN_ATTEMPT", "")
    if run_id.isdigit() and int(run_id) > 0:
        result["workflow_run_id"] = run_id
    if attempt.isdigit() and int(attempt) > 0:
        result["run_attempt"] = int(attempt)
    if os.environ.get("GITHUB_EVENT_NAME") in {"pull_request", "pull_request_target"}:
        path = os.environ.get("GITHUB_EVENT_PATH")
        if not path or os.path.getsize(path) > 1000000:
            raise ValueError("Bounded PR event metadata is required")
        with open(path, encoding="utf-8") as handle:
            event = json.load(handle)
        pr = event.get("pull_request") or {}
        head, base = pr.get("head") or {}, pr.get("base") or {}
        sha, number = head.get("sha"), pr.get("number", event.get("number"))
        if (not isinstance(sha, str) or len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha)
                or type(number) is not int or number < 1
                or base.get("repo", {}).get("full_name") != os.environ.get("GITHUB_REPOSITORY")):
            raise ValueError("Exact PR repository/head identity is required")
        result.update(commit_sha=sha, pr_number=number, branch=head.get("ref") or result["branch"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit", required=True)
    args = parser.parse_args()

    api_url = _optional_environment("SAMANVAYA_API_URL")
    project_id = _optional_environment("SAMANVAYA_PROJECT_ID")
    token = _optional_environment("SAMANVAYA_TEST_RESULTS_TOKEN")

    if not api_url or not project_id or not token:
        print("=" * 70)
        print("Samanvaya secrets not configured. Skipping test result upload.")
        print("To enable automated test result upload, configure these repository secrets:")
        print("  - SAMANVAYA_API_URL")
        print("  - SAMANVAYA_PROJECT_ID")
        print("  - SAMANVAYA_TEST_RESULTS_TOKEN")
        print("=" * 70)
        return 0

    with open(args.junit, "rb") as handle:
        document = handle.read()
    # Reports are untrusted: no DTDs or entity declarations (XML bomb / XXE).
    if b"<!DOCTYPE" in document.upper() or b"<!ENTITY" in document.upper():
        raise ValueError("JUnit XML must not declare a DOCTYPE or entities")
    # Bandit B314: DTD/entity declarations rejected above.
    root = ET.fromstring(document)  # nosec B314
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites:
        raise ValueError("JUnit file contains no testsuite elements")

    tests_run = sum(int(float(s.get("tests", 0))) for s in suites)
    failures = sum(int(float(s.get("failures", 0))) for s in suites)
    errors = sum(int(float(s.get("errors", 0))) for s in suites)
    skipped = sum(int(float(s.get("skipped", 0))) for s in suites)
    tests_failed = failures + errors
    api_url = api_url.rstrip("/")
    if urllib.parse.urlsplit(api_url).scheme not in {"https", "http"}:
        raise ValueError("SAMANVAYA_API_URL must be an http(s) URL")
    tests_passed = max(tests_run - tests_failed - skipped, 0)
    payload = {
        "project_id": project_id,
        "repository": os.environ["GITHUB_REPOSITORY"],
        "branch": os.environ.get("GITHUB_REF_NAME", ""),
        "commit_sha": os.environ["GITHUB_SHA"],
        "test_suite": os.environ.get("SAMANVAYA_TEST_SUITE", "backend"),
        "tests_run": tests_run,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
        "tests_skipped": skipped,
        "duration_seconds": sum(float(s.get("time", 0) or 0) for s in suites),
        # v4 CI-09: a report in which nothing passed is not a pass.
        "status": "failed" if tests_failed else ("passed" if tests_passed else "skipped"),
    }
    payload.update(_github_metadata())
    request = urllib.request.Request(
        api_url + "/api/qa/test-runs",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Test-Results-Token": token,
        },
        method="POST",
    )
    # Bandit B310: scheme validated above.
    with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310
        if response.status not in (200, 201):
            raise RuntimeError(f"Samanvaya rejected test result: HTTP {response.status}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Failed to upload JUnit results: {exc}", file=sys.stderr)
        raise
