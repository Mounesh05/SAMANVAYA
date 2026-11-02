"""Provision the standard GitHub Actions QA workflow for a repository.

This service provisions a multi-language testing workflow that supports:
- Python (pytest)
- JavaScript/TypeScript (vitest, jest)
- Java (Maven, Gradle)

The provisioning process includes:
1. Setting GitHub Actions secrets (API URL, project ID, token)
2. Deploying CI test execution script (ci/run_tests.sh)
3. Deploying CI result upload script (ci/upload_junit_results.py)
4. Deploying GitHub Actions workflow (.github/workflows/samanvaya-qa.yml)
"""

from typing import Any, Dict

from core.config import settings
from integrations.github.client import GitHubClient


WORKFLOW_PATH = ".github/workflows/samanvaya-qa.yml"
RUN_TESTS_SCRIPT_PATH = "ci/run_tests.sh"
UPLOAD_SCRIPT_PATH = "ci/upload_junit_results.py"


def _workflow_content() -> str:
    """Return the enhanced multi-language GitHub Actions workflow content."""
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
      
      # Language runtime setup
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      
      - uses: actions/setup-node@v4
        if: hashFiles('package.json', 'frontend/package.json') != ''
        with:
          node-version: "20"
      
      # Install dependencies
      - name: Install dependencies
        run: |
          # Python dependencies
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
          if [ -f backend/requirements.txt ]; then pip install -r backend/requirements.txt; fi
          
          # Node.js dependencies (if package.json exists)
          if [ -f package.json ]; then
            npm ci || npm install
          fi
          if [ -f frontend/package.json ]; then
            cd frontend && (npm ci || npm install) && cd ..
          fi
      
      # Run tests with multi-language detection
      - name: Run tests
        shell: bash
        run: bash ci/run_tests.sh
      
      # Upload results to Samanvaya (includes failure reporting)
      - name: Upload results to Samanvaya
        if: always() && github.event_name != 'pull_request'
        env:
          SAMANVAYA_API_URL: ${{ secrets.SAMANVAYA_API_URL }}
          SAMANVAYA_PROJECT_ID: ${{ secrets.SAMANVAYA_PROJECT_ID }}
          SAMANVAYA_TEST_RESULTS_TOKEN: ${{ secrets.SAMANVAYA_TEST_RESULTS_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          GITHUB_REF_NAME: ${{ github.ref_name }}
          GITHUB_SHA: ${{ github.sha }}
        run: |
          if [ -n "$TEST_RESULTS_FILE" ] && [ -f "$TEST_RESULTS_FILE" ]; then
            echo "✅ Uploading test results: $TEST_RESULTS_FILE"
            SAMANVAYA_TEST_SUITE="${SAMANVAYA_TEST_SUITE}" python ci/upload_junit_results.py --junit "$TEST_RESULTS_FILE"
          else
            echo "⚠️  No test results file found - creating failure report for Samanvaya"
            cat > workflow-failure.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<testsuites>
  <testsuite name="workflow-failure" tests="1" failures="1" errors="0" time="0">
    <testcase classname="github-actions" name="workflow-execution">
      <failure message="GitHub Actions workflow failed before tests could complete">
Workflow Status: Failed
Exit Code: ${TEST_EXIT_CODE:-unknown}

Common Causes:
- No test files found (pytest exit code 5)
- Dependency installation failed
- Syntax errors in code or tests
- Missing configuration files

View detailed logs:
https://github.com/${GITHUB_REPOSITORY}/actions

Branch: ${GITHUB_REF_NAME}
Commit: ${GITHUB_SHA}
      </failure>
    </testcase>
  </testsuite>
</testsuites>
EOF
            SAMANVAYA_TEST_SUITE="workflow" python ci/upload_junit_results.py --junit workflow-failure.xml || echo "❌ Failed to upload failure report"
          fi
      
      # Fail workflow if tests failed
      - name: Fail workflow when tests fail
        if: always()
        run: exit "${TEST_EXIT_CODE:-0}"
"""


def _run_tests_script_content() -> str:
    """Return the multi-language test detection and execution script."""
    return """#!/usr/bin/env bash
#
# Multi-Language Test Detection and Execution Script
# Detects and runs tests for Python (pytest), JavaScript/TypeScript (vitest, jest), and Java (Maven, Gradle)
# Exports environment variables for GitHub Actions consumption

set -u  # Exit on undefined variables
# Do NOT set -e: we want to capture test exit codes without stopping

# Initialize tracking variables
OVERALL_EXIT_CODE=0
TESTS_RUN=0
DETECTED_SUITES=""

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

log_section() {
    echo ""
    echo "========================================================================"
    echo "$1"
    echo "========================================================================"
}

log_info() {
    echo "[INFO] $1"
}

log_error() {
    echo "[ERROR] $1" >&2
}

update_exit_code() {
    local new_code=$1
    if [ "$new_code" -ne 0 ]; then
        OVERALL_EXIT_CODE=$new_code
    fi
}

# ============================================================================
# TEST FRAMEWORK DETECTION
# ============================================================================

detect_python_tests() {
    if [ -d "backend/tests" ] || [ -d "tests" ] || [ -f "pytest.ini" ]; then
        return 0
    fi
    return 1
}

detect_vitest() {
    if [ -f "vitest.config.js" ] || [ -f "vitest.config.ts" ]; then
        return 0
    fi
    if [ -f "package.json" ] && grep -q '"vitest"' package.json 2>/dev/null; then
        return 0
    fi
    return 1
}

detect_jest() {
    if [ -f "jest.config.js" ] || [ -f "jest.config.ts" ]; then
        return 0
    fi
    if [ -f "package.json" ] && grep -q '"jest"' package.json 2>/dev/null; then
        return 0
    fi
    return 1
}

detect_maven() {
    [ -f "pom.xml" ]
}

detect_gradle() {
    [ -f "build.gradle" ] || [ -f "build.gradle.kts" ]
}

# ============================================================================
# PYTHON TEST EXECUTION
# ============================================================================

run_python_tests() {
    log_section "Running Python Tests (pytest)"
    
    local test_dir=""
    if [ -d "backend/tests" ]; then
        test_dir="backend/tests"
    elif [ -d "tests" ]; then
        test_dir="tests"
    else
        log_error "Python tests detected but no test directory found"
        return 1
    fi
    
    log_info "Test directory: $test_dir"
    log_info "Executing: pytest $test_dir -q --junitxml=test-results-python.xml"
    
    # Run pytest (allow non-zero exit)
    set +e
    pytest "$test_dir" -q --junitxml=test-results-python.xml
    local exit_code=$?
    set -e
    
    log_info "Python tests completed with exit code: $exit_code"
    
    # Export to GitHub Actions environment
    echo "SAMANVAYA_TEST_SUITE=python" >> "$GITHUB_ENV"
    echo "TEST_RESULTS_FILE=test-results-python.xml" >> "$GITHUB_ENV"
    
    TESTS_RUN=$((TESTS_RUN + 1))
    DETECTED_SUITES="${DETECTED_SUITES}python "
    update_exit_code $exit_code
    
    return $exit_code
}

# ============================================================================
# JAVASCRIPT/TYPESCRIPT TEST EXECUTION
# ============================================================================

run_vitest_tests() {
    log_section "Running JavaScript/TypeScript Tests (Vitest)"
    
    # Check if we're in the frontend directory or need to navigate
    local frontend_dir=""
    if [ -f "vitest.config.js" ] || [ -f "vitest.config.ts" ]; then
        frontend_dir="."
    elif [ -d "frontend" ] && ([ -f "frontend/vitest.config.js" ] || [ -f "frontend/vitest.config.ts" ]); then
        frontend_dir="frontend"
    fi
    
    if [ -z "$frontend_dir" ]; then
        log_error "Vitest detected but no configuration file found"
        return 1
    fi
    
    log_info "Frontend directory: $frontend_dir"
    
    # Install dependencies
    log_info "Installing Node.js dependencies..."
    if [ "$frontend_dir" != "." ]; then
        cd "$frontend_dir"
    fi
    
    if [ -f "package-lock.json" ]; then
        npm ci
    else
        npm install
    fi
    
    # Run vitest
    log_info "Executing: npx vitest run --reporter=junit --outputFile=test-results-frontend.xml"
    
    set +e
    npx vitest run --reporter=junit --outputFile=test-results-frontend.xml
    local exit_code=$?
    set -e
    
    # Move results file to root if we're in a subdirectory
    if [ "$frontend_dir" != "." ]; then
        if [ -f "test-results-frontend.xml" ]; then
            mv test-results-frontend.xml ../test-results-frontend.xml
        fi
        cd ..
    fi
    
    log_info "Vitest tests completed with exit code: $exit_code"
    
    # Export to GitHub Actions environment
    echo "SAMANVAYA_TEST_SUITE=javascript" >> "$GITHUB_ENV"
    echo "TEST_RESULTS_FILE=test-results-frontend.xml" >> "$GITHUB_ENV"
    
    TESTS_RUN=$((TESTS_RUN + 1))
    DETECTED_SUITES="${DETECTED_SUITES}javascript "
    update_exit_code $exit_code
    
    return $exit_code
}

run_jest_tests() {
    log_section "Running JavaScript/TypeScript Tests (Jest)"
    
    log_info "Installing Node.js dependencies..."
    if [ -f "package-lock.json" ]; then
        npm ci
    else
        npm install
    fi
    
    log_info "Executing: npm test -- --ci --reporters=jest-junit"
    
    # Configure jest-junit output
    export JEST_JUNIT_OUTPUT_DIR="."
    export JEST_JUNIT_OUTPUT_NAME="test-results-frontend.xml"
    
    set +e
    npm test -- --ci --reporters=jest-junit
    local exit_code=$?
    set -e
    
    log_info "Jest tests completed with exit code: $exit_code"
    
    # Export to GitHub Actions environment
    echo "SAMANVAYA_TEST_SUITE=javascript" >> "$GITHUB_ENV"
    echo "TEST_RESULTS_FILE=test-results-frontend.xml" >> "$GITHUB_ENV"
    
    TESTS_RUN=$((TESTS_RUN + 1))
    DETECTED_SUITES="${DETECTED_SUITES}javascript "
    update_exit_code $exit_code
    
    return $exit_code
}

# ============================================================================
# JAVA TEST EXECUTION
# ============================================================================

run_maven_tests() {
    log_section "Running Java Tests (Maven)"
    
    log_info "Executing: mvn test"
    
    set +e
    mvn test
    local exit_code=$?
    set -e
    
    # Locate and copy JUnit XML results
    if [ -d "target/surefire-reports" ]; then
        log_info "Copying Maven test results..."
        # Combine all TEST-*.xml files into one
        find target/surefire-reports -name "TEST-*.xml" -exec cat {} \\; > test-results-java.xml
    else
        log_error "Maven test results not found in target/surefire-reports"
        printf '<testsuite tests="0" failures="1"><testcase name="no-results"><failure>Test results not found</failure></testcase></testsuite>' > test-results-java.xml
    fi
    
    log_info "Maven tests completed with exit code: $exit_code"
    
    # Export to GitHub Actions environment
    echo "SAMANVAYA_TEST_SUITE=java" >> "$GITHUB_ENV"
    echo "TEST_RESULTS_FILE=test-results-java.xml" >> "$GITHUB_ENV"
    
    TESTS_RUN=$((TESTS_RUN + 1))
    DETECTED_SUITES="${DETECTED_SUITES}java "
    update_exit_code $exit_code
    
    return $exit_code
}

run_gradle_tests() {
    log_section "Running Java Tests (Gradle)"
    
    log_info "Executing: ./gradlew test --no-daemon"
    
    set +e
    ./gradlew test --no-daemon
    local exit_code=$?
    set -e
    
    # Locate and copy JUnit XML results
    if [ -d "build/test-results/test" ]; then
        log_info "Copying Gradle test results..."
        find build/test-results/test -name "*.xml" -exec cat {} \\; > test-results-java.xml
    else
        log_error "Gradle test results not found in build/test-results/test"
        printf '<testsuite tests="0" failures="1"><testcase name="no-results"><failure>Test results not found</failure></testcase></testsuite>' > test-results-java.xml
    fi
    
    log_info "Gradle tests completed with exit code: $exit_code"
    
    # Export to GitHub Actions environment
    echo "SAMANVAYA_TEST_SUITE=java" >> "$GITHUB_ENV"
    echo "TEST_RESULTS_FILE=test-results-java.xml" >> "$GITHUB_ENV"
    
    TESTS_RUN=$((TESTS_RUN + 1))
    DETECTED_SUITES="${DETECTED_SUITES}java "
    update_exit_code $exit_code
    
    return $exit_code
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    log_section "Multi-Language Test Detection Started"
    
    # Detect and run Python tests
    if detect_python_tests; then
        log_info "✓ Python tests detected"
        run_python_tests || true  # Continue even if tests fail
    fi
    
    # Detect and run JavaScript/TypeScript tests
    if detect_vitest; then
        log_info "✓ Vitest detected"
        run_vitest_tests || true
    elif detect_jest; then
        log_info "✓ Jest detected"
        run_jest_tests || true
    fi
    
    # Detect and run Java tests
    if detect_maven; then
        log_info "✓ Maven detected"
        run_maven_tests || true
    elif detect_gradle; then
        log_info "✓ Gradle detected"
        run_gradle_tests || true
    fi
    
    # Handle no tests detected
    if [ $TESTS_RUN -eq 0 ]; then
        log_section "No Test Framework Detected"
        log_info "Supported frameworks: pytest, vitest, jest, Maven, Gradle"
        log_info "Creating empty test results file..."
        
        printf '<testsuite tests="0" failures="0"></testsuite>' > test-results-none.xml
        
        echo "SAMANVAYA_TEST_SUITE=none" >> "$GITHUB_ENV"
        echo "TEST_RESULTS_FILE=test-results-none.xml" >> "$GITHUB_ENV"
        echo "TEST_EXIT_CODE=0" >> "$GITHUB_ENV"
        
        log_info "No tests to run - exiting successfully"
        exit 0
    fi
    
    # Summary
    log_section "Test Execution Summary"
    log_info "Test suites executed: $DETECTED_SUITES"
    log_info "Overall exit code: $OVERALL_EXIT_CODE"
    
    # Export overall exit code
    echo "TEST_EXIT_CODE=$OVERALL_EXIT_CODE" >> "$GITHUB_ENV"
    
    # Exit with the overall exit code
    exit $OVERALL_EXIT_CODE
}

# Execute main function
main
"""


def _upload_script_content() -> str:
    """Return the JUnit XML result upload script."""
    return '''"""Upload a JUnit XML result to Samanvaya from CI."""

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
'''


class QAWorkflowProvisioningService:
    """Installs the managed QA workflow and its encrypted repository secrets.
    
    This service provisions multi-language testing support for customer repositories
    by deploying:
    - GitHub Actions workflow with multi-language runtime setup
    - CI test execution script supporting Python, JavaScript/TypeScript, and Java
    - CI result upload script for submitting test results to Samanvaya
    - Repository secrets for API authentication
    """

    def __init__(self, github_client: GitHubClient | None = None):
        self.github = github_client or GitHubClient()

    async def provision(
        self, owner: str, repo: str, project_id: str, branch: str | None = None
    ) -> Dict[str, Any]:
        """Provision multi-language QA workflow and CI scripts to a repository.
        
        This method:
        1. Validates configuration (API URL, token)
        2. Sets GitHub Actions secrets (API URL, project ID, token)
        3. Deploys CI test execution script (ci/run_tests.sh)
        4. Deploys CI result upload script (ci/upload_junit_results.py)
        5. Deploys GitHub Actions workflow (.github/workflows/samanvaya-qa.yml)
        
        Args:
            owner: GitHub repository owner
            repo: GitHub repository name
            project_id: Samanvaya project ID
            branch: Target branch (defaults to repository's default branch)
            
        Returns:
            Dict containing repository info, project ID, branch, workflow path,
            workflow URL, and provisioning status.
        """
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
        
        # Deploy CI test execution script
        existing_run_tests = await self.github.get_file(owner, repo, RUN_TESTS_SCRIPT_PATH, ref=target_branch)
        await self.github.upsert_file(
            owner,
            repo,
            RUN_TESTS_SCRIPT_PATH,
            _run_tests_script_content(),
            "chore: provision Samanvaya CI test execution script",
            branch=target_branch,
            sha=existing_run_tests.get("sha") if existing_run_tests else None,
        )
        
        # Deploy CI result upload script
        existing_upload = await self.github.get_file(owner, repo, UPLOAD_SCRIPT_PATH, ref=target_branch)
        await self.github.upsert_file(
            owner,
            repo,
            UPLOAD_SCRIPT_PATH,
            _upload_script_content(),
            "chore: provision Samanvaya CI result upload script",
            branch=target_branch,
            sha=existing_upload.get("sha") if existing_upload else None,
        )
        
        # Deploy GitHub Actions workflow
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
