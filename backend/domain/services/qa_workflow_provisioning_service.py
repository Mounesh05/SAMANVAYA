"""Provision the standard GitHub Actions QA workflow for a repository."""

from typing import Any, Dict

from core.config import settings
from integrations.github.client import GitHubClient


WORKFLOW_PATH = ".github/workflows/samanvaya-qa.yml"


def _workflow_content() -> str:
    return """name: Samanvaya QA

on:
  workflow_dispatch:
  push:
    branches: ["**"]
  pull_request:

jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install test dependencies
        run: |
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
          if [ -f backend/requirements.txt ]; then pip install -r backend/requirements.txt; fi
      - name: Run tests
        shell: bash
        run: |
          set +e
          if [ -d backend/tests ]; then
            pytest backend/tests -q --junitxml=test-results.xml
          elif [ -d tests ]; then
            pytest tests -q --junitxml=test-results.xml
          else
            echo "No Python test directory found"
            printf '<testsuite tests="0" failures="0"></testsuite>' > test-results.xml
            echo "TEST_EXIT_CODE=1" >> "$GITHUB_ENV"
            exit 1
          fi
          echo "TEST_EXIT_CODE=$?" >> "$GITHUB_ENV"
      - name: Upload results to Samanvaya
        if: always() && github.event_name != 'pull_request'
        env:
          SAMANVAYA_API_URL: ${{ secrets.SAMANVAYA_API_URL }}
          SAMANVAYA_PROJECT_ID: ${{ secrets.SAMANVAYA_PROJECT_ID }}
          SAMANVAYA_TEST_RESULTS_TOKEN: ${{ secrets.SAMANVAYA_TEST_RESULTS_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          GITHUB_REF_NAME: ${{ github.ref_name }}
          GITHUB_SHA: ${{ github.sha }}
          SAMANVAYA_TEST_SUITE: github-actions
        run: |
          python - <<'PY'
          import os
          import xml.etree.ElementTree as ET
          import urllib.request
          root = ET.parse("test-results.xml").getroot()
          suites = [root] if root.tag == "testsuite" else root.findall(".//testsuite")
          tests = sum(int(float(s.attrib.get("tests", 0))) for s in suites)
          failures = sum(
              int(float(s.attrib.get("failures", 0))) +
              int(float(s.attrib.get("errors", 0)))
              for s in suites
          )
          exit_code = int(os.environ.get("TEST_EXIT_CODE", "1"))
          payload = {
              "project_id": os.environ["SAMANVAYA_PROJECT_ID"],
              "repository": os.environ["GITHUB_REPOSITORY"],
              "branch": os.environ["GITHUB_REF_NAME"],
              "commit_sha": os.environ["GITHUB_SHA"],
              "test_suite": os.environ["SAMANVAYA_TEST_SUITE"],
              "tests_run": tests,
              "tests_passed": max(tests - failures, 0),
              "tests_failed": failures,
              "status": "passed" if exit_code == 0 and failures == 0 else "failed",
          }
          request = urllib.request.Request(
              os.environ["SAMANVAYA_API_URL"].rstrip("/") + "/api/qa/test-runs",
              data=__import__("json").dumps(payload).encode(),
              headers={
                  "Content-Type": "application/json",
                  "X-Test-Results-Token": os.environ["SAMANVAYA_TEST_RESULTS_TOKEN"],
              },
              method="POST",
          )
          with urllib.request.urlopen(request) as response:
              if response.status >= 300:
                  raise RuntimeError(f"Samanvaya rejected test results: {response.status}")
          PY
      - name: Fail workflow when tests fail
        if: always()
        run: exit "${TEST_EXIT_CODE:-0}"
"""


class QAWorkflowProvisioningService:
    """Installs the managed QA workflow and its encrypted repository secrets."""

    def __init__(self, github_client: GitHubClient | None = None):
        self.github = github_client or GitHubClient()

    async def provision(
        self, owner: str, repo: str, project_id: str, branch: str | None = None
    ) -> Dict[str, Any]:
        if not settings.SAMANVAYA_PUBLIC_API_URL:
            raise ValueError("SAMANVAYA_PUBLIC_API_URL must be configured before provisioning")
        if not settings.SAMANVAYA_PUBLIC_API_URL.startswith("https://"):
            raise ValueError("SAMANVAYA_PUBLIC_API_URL must be an HTTPS public URL")
        if not settings.QA_TEST_RESULTS_TOKEN:
            raise ValueError("QA_TEST_RESULTS_TOKEN must be configured before provisioning")

        repository = await self.github.get_repository(owner, repo)
        public_key = await self.github.get_actions_public_key(owner, repo)
        for name, value in {
            "SAMANVAYA_API_URL": settings.SAMANVAYA_PUBLIC_API_URL,
            "SAMANVAYA_PROJECT_ID": project_id,
            "SAMANVAYA_TEST_RESULTS_TOKEN": settings.QA_TEST_RESULTS_TOKEN,
        }.items():
            await self.github.set_actions_secret(owner, repo, name, value, public_key)

        target_branch = branch or repository.get("default_branch")
        existing = await self.github.get_file(owner, repo, WORKFLOW_PATH, ref=target_branch)
        result = await self.github.upsert_file(
            owner,
            repo,
            WORKFLOW_PATH,
            _workflow_content(),
            "chore: provision Samanvaya QA workflow",
            branch=target_branch,
            sha=existing.get("sha") if existing else None,
        )
        return {
            "repository": f"{owner}/{repo}",
            "project_id": project_id,
            "branch": target_branch,
            "workflow_path": WORKFLOW_PATH,
            "workflow_url": result.get("content", {}).get("html_url"),
            "status": "provisioned",
        }
