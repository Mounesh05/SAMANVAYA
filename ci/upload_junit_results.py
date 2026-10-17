"""Upload a JUnit XML result to Samanvaya from GitHub Actions."""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing required CI environment variable: {name}")
    return value


def _endpoint_url(base_url: str) -> str:
    """Normalize a public Samanvaya URL to the QA ingestion endpoint."""
    base = base_url.rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(
            "SAMANVAYA_API_URL must be an absolute http(s) URL for the running "
            "Samanvaya API (not a GitHub URL or a URL to a frontend-only host)."
        )

    path = parsed.path.rstrip("/")
    if path.endswith("/api/qa/test-runs"):
        normalized_path = path
    elif path.endswith("/api/qa"):
        normalized_path = path + "/test-runs"
    elif path.endswith("/api"):
        normalized_path = path + "/qa/test-runs"
    else:
        normalized_path = path + "/api/qa/test-runs"

    return parsed._replace(path=normalized_path, query="", fragment="").geturl()


def _suites(root: ET.Element) -> list[ET.Element]:
    if root.tag.endswith("testsuite"):
        return [root]
    suites = root.findall(".//testsuite")
    if not suites:
        raise ValueError("JUnit file contains no testsuite elements")
    return suites


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit", required=True)
    args = parser.parse_args()

    root = ET.parse(args.junit).getroot()
    suites = _suites(root)
    tests_run = sum(int(float(s.get("tests", 0))) for s in suites)
    failures = sum(int(float(s.get("failures", 0))) for s in suites)
    errors = sum(int(float(s.get("errors", 0))) for s in suites)
    skipped = sum(int(float(s.get("skipped", 0))) for s in suites)
    failed = failures + errors

    payload = {
        "project_id": _required_environment("SAMANVAYA_PROJECT_ID"),
        "repository": _required_environment("GITHUB_REPOSITORY"),
        "branch": os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME", ""),
        "commit_sha": _required_environment("GITHUB_SHA"),
        "test_suite": os.environ.get("SAMANVAYA_TEST_SUITE", "backend"),
        "tests_run": tests_run,
        "tests_passed": max(tests_run - failed - skipped, 0),
        "tests_failed": failed,
        "tests_skipped": skipped,
        "duration_seconds": sum(float(s.get("time", 0) or 0) for s in suites),
        "status": "passed" if failed == 0 else "failed",
    }
    endpoint = _endpoint_url(_required_environment("SAMANVAYA_API_URL"))
    token = _required_environment("SAMANVAYA_TEST_RESULTS_TOKEN")
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Test-Results-Token": token,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status not in (200, 201):
                raise RuntimeError(
                    f"Samanvaya rejected test result (HTTP {response.status}) "
                    f"at {urlsplit(endpoint).path}"
                )
    except urllib.error.HTTPError as exc:
        detail = exc.read(1000).decode("utf-8", errors="replace")
        host = urlsplit(endpoint).netloc
        if exc.code == 404:
            raise RuntimeError(
                f"QA ingestion endpoint returned HTTP 404 at {urlsplit(endpoint).path} "
                f"on {host}. The route in this repository is POST /api/qa/test-runs. "
                "Check that SAMANVAYA_API_URL points to the running FastAPI deployment "
                "and that the reverse proxy exposes the /api/qa path. "
                f"Response: {detail}"
            ) from exc
        raise RuntimeError(
            f"Samanvaya rejected test result (HTTP {exc.code}) at "
            f"{urlsplit(endpoint).path}: {detail}"
        ) from exc
    print(f"Uploaded JUnit results to {urlsplit(endpoint).path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Failed to upload JUnit results: {exc}", file=sys.stderr)
        raise SystemExit(1)
