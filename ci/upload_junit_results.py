"""Upload a JUnit XML result to Samanvaya from CI."""

import argparse
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(
            f"Missing required CI environment variable: {name}. "
            "Add it as a GitHub Actions repository secret."
        )
    return value


def _optional_environment(name: str) -> str | None:
    """Get environment variable or return None if missing/empty."""
    return os.environ.get(name, "").strip() or None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit", required=True)
    args = parser.parse_args()

    # Check for required secrets - gracefully handle absence
    api_url = _optional_environment("SAMANVAYA_API_URL")
    project_id = _optional_environment("SAMANVAYA_PROJECT_ID")
    token = _optional_environment("SAMANVAYA_TEST_RESULTS_TOKEN")
    
    if not all([api_url, project_id, token]):
        print("=" * 70)
        print("Samanvaya secrets not configured. Skipping test result upload.")
        print("To enable automated test result upload, configure these repository secrets:")
        print("  - SAMANVAYA_API_URL")
        print("  - SAMANVAYA_PROJECT_ID")
        print("  - SAMANVAYA_TEST_RESULTS_TOKEN")
        print("=" * 70)
        return 0  # Exit gracefully without failing workflow

    root = ET.parse(args.junit).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites:
        raise ValueError("JUnit file contains no testsuite elements")

    tests_run = sum(int(float(s.get("tests", 0))) for s in suites)
    failures = sum(int(float(s.get("failures", 0))) for s in suites)
    errors = sum(int(float(s.get("errors", 0))) for s in suites)
    skipped = sum(int(float(s.get("skipped", 0))) for s in suites)
    tests_failed = failures + errors
    api_url = api_url.rstrip("/")
    project_id = project_id
    token = token
    payload = {
        "project_id": project_id,
        "repository": os.environ["GITHUB_REPOSITORY"],
        "branch": os.environ.get("GITHUB_REF_NAME", ""),
        "commit_sha": os.environ["GITHUB_SHA"],
        "test_suite": os.environ.get("SAMANVAYA_TEST_SUITE", "backend"),
        "tests_run": tests_run,
        "tests_passed": max(tests_run - tests_failed - skipped, 0),
        "tests_failed": tests_failed,
        "tests_skipped": skipped,
        "duration_seconds": sum(float(s.get("time", 0) or 0) for s in suites),
        "status": "passed" if tests_failed == 0 else "failed",
    }
    request = urllib.request.Request(
        api_url + "/api/qa/test-runs",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Test-Results-Token": token,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status not in (200, 201):
            raise RuntimeError(f"Samanvaya rejected test result: HTTP {response.status}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Failed to upload JUnit results: {exc}", file=sys.stderr)
        raise
