"""v4 CI-09 / CI-11: a report in which nothing passed is never recorded as "passed".

Observed with an independent JUnit oracle: a published report whose five
test cases were all skipped was imported with ``status: passed`` and 0 passed
tests, and the CI upload route accepted ``status: passed`` together with failed
tests. "No report, no successful assertion" (phase 2A).
"""

import io
import os
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from api.routes import qa_test_runs
from integrations.github.test_artifacts import parse_archive

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integrations" / "github" / "qa_templates"))
import upload_junit_results  # noqa: E402

CASE = {"pass": "", "fail": "<failure message='x'/>", "error": "<error message='e'/>", "skip": "<skipped/>"}


def junit(kinds):
    attrs = (f"tests='{len(kinds)}' failures='{kinds.count('fail')}' errors='{kinds.count('error')}' "
             f"skipped='{kinds.count('skip')}'")
    cases = "".join(f"<testcase classname='c' name='t{i}'>{CASE[k]}</testcase>" for i, k in enumerate(kinds))
    return f"<testsuite name='s' {attrs}>{cases}</testsuite>"


def archive(xml):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipped:
        zipped.writestr("report.xml", xml)
    return buffer.getvalue()


# ── Artifact import ─────────────────────────────────────────────────────────

def test_all_skipped_report_is_not_passed():
    (report,), _ = parse_archive(archive(junit(["skip"] * 5)))
    assert (report["tests_run"], report["tests_passed"], report["tests_skipped"]) == (5, 0, 5)
    assert report["status"] == "skipped"


@pytest.mark.parametrize("kinds,status", [(["pass", "skip"], "passed"), (["pass", "fail"], "failed"),
                                          (["skip", "error"], "failed")])
def test_other_outcomes_are_unchanged(kinds, status):
    (report,), _ = parse_archive(archive(junit(kinds)))
    assert report["status"] == status


# ── CI upload route ─────────────────────────────────────────────────────────

def submission(**changes):
    body = {"project_id": "P-QA-A", "repository": "qa-a/app", "branch": "main", "commit_sha": "a" * 40,
            "test_suite": "backend", "tests_run": 5, "tests_passed": 0, "tests_failed": 0, "tests_skipped": 5,
            "status": "passed"}
    body.update(changes)
    return qa_test_runs.TestRunSubmission.model_validate(body)


def test_passed_status_with_failed_tests_is_rejected():
    with pytest.raises(ValidationError, match="passed status cannot report failed tests"):
        submission(tests_passed=3, tests_failed=2, tests_skipped=0)


@pytest.mark.anyio
async def test_reported_pass_without_any_passing_test_is_stored_as_skipped(mock_db):
    await mock_db.qa_ci_configs.insert_one({"project_id": "P-QA-A", "repository": "qa-a/app", "enabled": True})
    with patch.object(qa_test_runs, "col", lambda name: mock_db[name]), \
            patch.object(qa_test_runs, "_verify_ci_token", lambda token, body: "shared_token"):
        await qa_test_runs.submit_test_run(submission(), x_test_results_token="t")
        await qa_test_runs.submit_test_run(submission(test_suite="real", tests_passed=4, tests_skipped=1),
                                           x_test_results_token="t")
    stored = {row["test_suite"]: row async for row in mock_db.test_runs.find({})}
    assert stored["backend"]["status"] == "skipped" and stored["backend"]["reported_status"] == "passed"
    assert stored["real"]["status"] == "passed" and "reported_status" not in stored["real"]


# ── Uploader template ───────────────────────────────────────────────────────

@pytest.mark.parametrize("kinds,status", [(["skip"] * 3, "skipped"), (["pass", "skip"], "passed"), (["fail"], "failed")])
def test_uploader_sends_skipped_when_nothing_passed(tmp_path, kinds, status):
    report = tmp_path / "junit.xml"
    report.write_text(junit(kinds))
    env = {"SAMANVAYA_API_URL": "https://api.example.com", "SAMANVAYA_PROJECT_ID": "P-QA-A",
           "SAMANVAYA_TEST_RESULTS_TOKEN": "t", "GITHUB_REPOSITORY": "qa-a/app", "GITHUB_SHA": "a" * 40}
    sent = {}

    class Response:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def urlopen(request, *args, **kwargs):
        import json
        sent.update(json.loads(request.data))
        return Response()

    with patch.dict(os.environ, env, clear=True), patch("urllib.request.urlopen", urlopen), \
            patch("sys.argv", ["upload_junit_results.py", "--junit", str(report)]):
        assert upload_junit_results.main() == 0
    assert sent["status"] == status
