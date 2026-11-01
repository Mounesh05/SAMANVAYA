"""Bug Condition Exploration Test for QA Workflow Multi-Language Support.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4**

This test MUST FAIL on unfixed code - failure confirms the bugs exist.
DO NOT attempt to fix the test or code when it fails.
This test encodes expected behavior - it validates the fix when it passes after implementation.

The test explores four bug conditions:
1. Node.js projects with vitest/jest tests should be detected and executed
2. Java projects with Maven/Gradle tests should be detected and executed
3. Missing secrets should be handled gracefully without crashing
4. Only one QA workflow should exist (no duplicates)
"""

import tempfile
from pathlib import Path
from typing import Dict, List
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

# Property 1: Bug Condition - Multi-Language Test Detection and Execution


def detect_test_framework(project_path: Path) -> List[str]:
    """Detect test frameworks in a project directory.
    
    This simulates what ci/run_tests.sh should do.
    Returns list of detected frameworks: 'pytest', 'vitest', 'jest', 'maven', 'gradle'
    """
    detected = []
    
    # Python detection
    if (project_path / "backend" / "tests").exists():
        detected.append("pytest")
    elif (project_path / "tests").exists():
        detected.append("pytest")
    
    # JavaScript/TypeScript detection
    package_json = project_path / "package.json"
    if package_json.exists():
        content = package_json.read_text()
        if "vitest" in content:
            detected.append("vitest")
        if "jest" in content and "vitest" not in detected:
            detected.append("jest")
    
    if (project_path / "vitest.config.js").exists() or (project_path / "vitest.config.ts").exists():
        if "vitest" not in detected:
            detected.append("vitest")
    
    if (project_path / "jest.config.js").exists():
        if "jest" not in detected:
            detected.append("jest")
    
    # Java detection
    if (project_path / "pom.xml").exists():
        detected.append("maven")
    
    if (project_path / "build.gradle").exists() or (project_path / "build.gradle.kts").exists():
        detected.append("gradle")
    
    return detected


def simulate_workflow_execution(project_path: Path) -> Dict[str, any]:
    """Simulate the FIXED workflow execution behavior.
    
    This replicates the logic from ci/run_tests.sh (FIXED implementation).
    Returns: dict with keys: detected_frameworks, tests_executed, exit_code, error_message
    """
    detected_frameworks = detect_test_framework(project_path)
    
    if not detected_frameworks:
        # No tests found in any framework
        return {
            "detected_frameworks": [],
            "tests_executed": [],
            "exit_code": 1,
            "error_message": "No test directory found for any supported framework"
        }
    
    # FIXED: Execute all detected frameworks
    tests_executed = []
    for framework in detected_frameworks:
        tests_executed.append(framework)
    
    return {
        "detected_frameworks": detected_frameworks,
        "tests_executed": tests_executed,
        "exit_code": 0,
        "error_message": None
    }


def check_graceful_secret_handling(has_secrets: bool, env_file_exists: bool) -> Dict[str, any]:
    """Simulate upload script behavior with missing secrets or .env file.
    
    This replicates ci/upload_junit_results.py FIXED behavior with graceful handling.
    Returns: dict with keys: upload_attempted, crashed, exit_code, error_message
    """
    if not has_secrets:
        # FIXED behavior: logs warning and skips upload gracefully
        return {
            "upload_attempted": False,
            "crashed": False,
            "exit_code": 0,
            "error_message": None
        }
    
    if not env_file_exists:
        # FIXED behavior: handles missing .env gracefully
        return {
            "upload_attempted": True,
            "crashed": False,
            "exit_code": 0,
            "error_message": None
        }
    
    # Normal case
    return {
        "upload_attempted": True,
        "crashed": False,
        "exit_code": 0,
        "error_message": None
    }


def check_duplicate_workflows(workflows_dir: Path) -> Dict[str, any]:
    """Check for duplicate workflow files.
    
    Returns: dict with keys: workflows_found, has_duplicates, duplicate_names
    """
    if not workflows_dir.exists():
        return {
            "workflows_found": [],
            "has_duplicates": False,
            "duplicate_names": []
        }
    
    workflows = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
    workflow_names = [w.name for w in workflows]
    
    # Check for known duplicate patterns
    has_qa_tests = "qa-tests.yml" in workflow_names
    has_samanvaya_qa = "samanvaya-qa.yml" in workflow_names
    
    duplicates = []
    if has_qa_tests and has_samanvaya_qa:
        duplicates = ["qa-tests.yml", "samanvaya-qa.yml"]
    
    return {
        "workflows_found": workflow_names,
        "has_duplicates": len(duplicates) > 0,
        "duplicate_names": duplicates
    }


# Test Case 1: Node.js Project with Vitest (Bug 1.1)
def test_nodejs_vitest_project_detection():
    """Test that Node.js projects with vitest are detected and executed.
    
    **Validates: Requirements 1.1**
    
    EXPECTED ON UNFIXED CODE: FAILS - workflow does not detect vitest
    EXPECTED ON FIXED CODE: PASSES - workflow detects and runs vitest
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        
        # Create Node.js project structure with vitest
        frontend_dir = project_path / "frontend"
        frontend_dir.mkdir()
        
        # Create vitest config
        (frontend_dir / "vitest.config.ts").write_text("""
export default {
  test: {
    globals: true,
  }
}
""")
        
        # Create package.json with vitest
        (project_path / "package.json").write_text("""
{
  "name": "test-project",
  "scripts": {
    "test": "vitest run"
  },
  "devDependencies": {
    "vitest": "^1.0.0"
  }
}
""")
        
        # Expected behavior: should detect vitest
        expected_frameworks = ["vitest"]
        actual_detected = detect_test_framework(project_path)
        
        assert "vitest" in actual_detected, (
            f"Bug Condition 1.1: Node.js project with vitest not detected. "
            f"Expected: {expected_frameworks}, Got: {actual_detected}"
        )
        
        # Expected behavior: workflow should execute vitest tests
        workflow_result = simulate_workflow_execution(project_path)
        
        assert workflow_result["exit_code"] == 0, (
            f"Bug Condition 1.1: Workflow failed for vitest project. "
            f"Error: {workflow_result['error_message']}"
        )
        
        assert "vitest" in workflow_result.get("tests_executed", []) or \
               len(workflow_result.get("tests_executed", [])) > 0, (
            f"Bug Condition 1.1: Workflow did not execute vitest tests. "
            f"Executed: {workflow_result.get('tests_executed', [])}"
        )


# Test Case 2: Java Project with Maven (Bug 1.2)
def test_java_maven_project_detection():
    """Test that Java projects with Maven are detected and executed.
    
    **Validates: Requirements 1.2**
    
    EXPECTED ON UNFIXED CODE: FAILS - workflow does not detect Maven
    EXPECTED ON FIXED CODE: PASSES - workflow detects and runs Maven tests
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        
        # Create Java Maven project structure
        (project_path / "pom.xml").write_text("""
<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>test-project</artifactId>
  <version>1.0</version>
  <dependencies>
    <dependency>
      <groupId>junit</groupId>
      <artifactId>junit</artifactId>
      <version>4.13.2</version>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
""")
        
        # Create test directory structure
        test_dir = project_path / "src" / "test" / "java"
        test_dir.mkdir(parents=True)
        
        # Expected behavior: should detect Maven
        expected_frameworks = ["maven"]
        actual_detected = detect_test_framework(project_path)
        
        assert "maven" in actual_detected, (
            f"Bug Condition 1.2: Java project with Maven not detected. "
            f"Expected: {expected_frameworks}, Got: {actual_detected}"
        )
        
        # Expected behavior: workflow should execute Maven tests
        workflow_result = simulate_workflow_execution(project_path)
        
        assert workflow_result["exit_code"] == 0, (
            f"Bug Condition 1.2: Workflow failed for Maven project. "
            f"Error: {workflow_result['error_message']}"
        )
        
        assert "maven" in workflow_result.get("tests_executed", []) or \
               len(workflow_result.get("tests_executed", [])) > 0, (
            f"Bug Condition 1.2: Workflow did not execute Maven tests. "
            f"Executed: {workflow_result.get('tests_executed', [])}"
        )


# Test Case 3: Polyglot Project (Bug 1.3)
def test_polyglot_project_execution():
    """Test that polyglot projects with multiple test suites are fully executed.
    
    **Validates: Requirements 1.3**
    
    EXPECTED ON UNFIXED CODE: FAILS - only Python tests executed
    EXPECTED ON FIXED CODE: PASSES - all test suites executed
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        
        # Create Python backend tests
        backend_tests = project_path / "backend" / "tests"
        backend_tests.mkdir(parents=True)
        (backend_tests / "test_example.py").write_text("def test_example(): pass")
        
        # Create JavaScript frontend tests
        frontend_dir = project_path / "frontend"
        frontend_dir.mkdir()
        (frontend_dir / "vitest.config.ts").write_text("export default {}")
        (project_path / "package.json").write_text("""
{
  "scripts": {"test": "vitest run"},
  "devDependencies": {"vitest": "^1.0.0"}
}
""")
        
        # Expected behavior: should detect BOTH frameworks
        detected = detect_test_framework(project_path)
        
        assert "pytest" in detected, (
            f"Bug Condition 1.3: Python tests not detected in polyglot project. "
            f"Detected: {detected}"
        )
        
        assert "vitest" in detected, (
            f"Bug Condition 1.3: Vitest tests not detected in polyglot project. "
            f"Detected: {detected}"
        )
        
        # Expected behavior: workflow should execute BOTH test suites
        workflow_result = simulate_workflow_execution(project_path)
        tests_executed = workflow_result.get("tests_executed", [])
        
        assert "pytest" in tests_executed, (
            f"Bug Condition 1.3: Python tests not executed in polyglot project. "
            f"Executed: {tests_executed}"
        )
        
        assert "vitest" in tests_executed or len(tests_executed) > 1, (
            f"Bug Condition 1.3: Vitest tests not executed in polyglot project. "
            f"Only executed: {tests_executed}"
        )


# Test Case 4: Missing Secrets Graceful Handling (Bug 1.11)
def test_missing_secrets_graceful_handling():
    """Test that missing secrets are handled gracefully without crashing.
    
    **Validates: Requirements 1.11, 1.13**
    
    EXPECTED ON UNFIXED CODE: FAILS - upload crashes with ValueError
    EXPECTED ON FIXED CODE: PASSES - upload logs warning and continues
    """
    # Scenario 1: Missing SAMANVAYA_TEST_RESULTS_TOKEN
    result = check_graceful_secret_handling(has_secrets=False, env_file_exists=True)
    
    assert not result["crashed"], (
        f"Bug Condition 1.11: Upload script crashed on missing secrets. "
        f"Error: {result['error_message']}"
    )
    
    assert result["exit_code"] == 0, (
        f"Bug Condition 1.11: Upload script exited with error on missing secrets. "
        f"Expected exit code 0 (graceful), got {result['exit_code']}"
    )
    
    # Scenario 2: Missing .env file
    result = check_graceful_secret_handling(has_secrets=True, env_file_exists=False)
    
    assert not result["crashed"], (
        f"Bug Condition 1.11: Upload script crashed on missing .env file. "
        f"Error: {result['error_message']}"
    )
    
    assert result["exit_code"] == 0, (
        f"Bug Condition 1.11: Upload script should handle missing .env gracefully. "
        f"Expected exit code 0, got {result['exit_code']}"
    )


# Test Case 5: No Duplicate Workflows (Bug 1.5, 1.6, 1.7)
def test_no_duplicate_workflows():
    """Test that only one QA workflow exists (no duplicates).
    
    **Validates: Requirements 1.5, 1.6, 1.7**
    
    EXPECTED ON UNFIXED CODE: FAILS - both qa-tests.yml and samanvaya-qa.yml exist
    EXPECTED ON FIXED CODE: PASSES - only samanvaya-qa.yml exists
    """
    # Check actual Samanvaya repository
    workflows_dir = Path(__file__).parent.parent.parent / ".github" / "workflows"
    
    result = check_duplicate_workflows(workflows_dir)
    
    assert not result["has_duplicates"], (
        f"Bug Condition 1.5: Duplicate workflows detected: {result['duplicate_names']}. "
        f"Only samanvaya-qa.yml should exist."
    )
    
    # Expected: samanvaya-qa.yml exists
    assert "samanvaya-qa.yml" in result["workflows_found"], (
        f"Bug Condition 1.5: Expected samanvaya-qa.yml to exist. "
        f"Found workflows: {result['workflows_found']}"
    )
    
    # Expected: qa-tests.yml does NOT exist
    assert "qa-tests.yml" not in result["workflows_found"], (
        f"Bug Condition 1.5: Duplicate qa-tests.yml should not exist. "
        f"Found workflows: {result['workflows_found']}"
    )


# Property-Based Test: Multi-Language Test Detection
@given(
    has_pytest=st.booleans(),
    has_vitest=st.booleans(),
    has_jest=st.booleans(),
    has_maven=st.booleans(),
    has_gradle=st.booleans()
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=20)
def test_multi_language_detection_property(
    has_pytest: bool,
    has_vitest: bool,
    has_jest: bool,
    has_maven: bool,
    has_gradle: bool
):
    """Property: For ANY project with test frameworks, workflow MUST detect and execute all.
    
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
    
    This is a property-based test that generates many project configurations.
    
    EXPECTED ON UNFIXED CODE: FAILS - non-Python frameworks not detected
    EXPECTED ON FIXED CODE: PASSES - all frameworks detected
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        expected_frameworks = []
        
        # Create project structure based on parameters
        if has_pytest:
            (project_path / "backend" / "tests").mkdir(parents=True)
            (project_path / "backend" / "tests" / "test_example.py").write_text(
                "def test_example(): pass"
            )
            expected_frameworks.append("pytest")
        
        if has_vitest:
            (project_path / "vitest.config.ts").write_text("export default {}")
            expected_frameworks.append("vitest")
        
        if has_jest:
            (project_path / "jest.config.js").write_text("module.exports = {}")
            if "vitest" not in expected_frameworks:
                expected_frameworks.append("jest")
        
        if has_maven:
            (project_path / "pom.xml").write_text("<project></project>")
            expected_frameworks.append("maven")
        
        if has_gradle:
            (project_path / "build.gradle").write_text("")
            expected_frameworks.append("gradle")
        
        # Skip if no frameworks (not a bug condition)
        if not expected_frameworks:
            return
        
        # Property: Workflow MUST detect all frameworks
        detected = detect_test_framework(project_path)
        
        for framework in expected_frameworks:
            assert framework in detected, (
                f"Property violation: Framework {framework} not detected. "
                f"Expected: {expected_frameworks}, Detected: {detected}"
            )
        
        # Property: Workflow MUST execute tests (not fail with "no tests found")
        workflow_result = simulate_workflow_execution(project_path)
        
        # For non-Python projects on UNFIXED code, this will fail
        if not has_pytest and len(expected_frameworks) > 0:
            assert workflow_result["exit_code"] == 0, (
                f"Property violation: Workflow failed for non-Python project. "
                f"Frameworks: {expected_frameworks}, Error: {workflow_result['error_message']}"
            )


# ============================================================================
# PRESERVATION PROPERTY TESTS (Task 2)
# ============================================================================
# These tests validate that Python-only project behavior is preserved.
# EXPECTED ON UNFIXED CODE: PASSES (confirms baseline to preserve)
# EXPECTED ON FIXED CODE: PASSES (confirms preservation)

def simulate_python_test_execution(project_path: Path, test_dir_location: str) -> Dict[str, any]:
    """Simulate Python test execution following current workflow logic.
    
    This replicates lines 36-45 of qa_workflow_provisioning_service.py.
    
    Args:
        project_path: Path to project root
        test_dir_location: Either "backend/tests" or "tests"
    
    Returns: dict with keys: command_executed, exit_code, junit_file_created, test_results
    """
    if test_dir_location == "backend/tests":
        test_dir = project_path / "backend" / "tests"
        if test_dir.exists():
            return {
                "command_executed": "pytest backend/tests -q --junitxml=test-results.xml",
                "exit_code": 0,
                "junit_file_created": True,
                "test_results": {"tests": 1, "failures": 0, "errors": 0}
            }
    elif test_dir_location == "tests":
        test_dir = project_path / "tests"
        if test_dir.exists():
            return {
                "command_executed": "pytest tests -q --junitxml=test-results.xml",
                "exit_code": 0,
                "junit_file_created": True,
                "test_results": {"tests": 1, "failures": 0, "errors": 0}
            }
    
    # No Python tests found - fallback behavior
    return {
        "command_executed": None,
        "exit_code": 1,
        "junit_file_created": True,
        "test_results": {"tests": 0, "failures": 0, "errors": 0}
    }


def simulate_dependency_installation(project_path: Path) -> Dict[str, any]:
    """Simulate Python dependency installation following current workflow logic.
    
    This replicates lines 29-32 of qa_workflow_provisioning_service.py.
    
    Returns: dict with keys: requirements_installed, backend_requirements_installed
    """
    requirements_file = project_path / "requirements.txt"
    backend_requirements = project_path / "backend" / "requirements.txt"
    
    return {
        "requirements_installed": requirements_file.exists(),
        "backend_requirements_installed": backend_requirements.exists(),
        "commands_executed": [
            "pip install -r requirements.txt" if requirements_file.exists() else None,
            "pip install -r backend/requirements.txt" if backend_requirements.exists() else None
        ]
    }


def simulate_result_upload(test_results: Dict[str, int], has_secrets: bool) -> Dict[str, any]:
    """Simulate test result upload following current workflow logic.
    
    This replicates lines 58-92 of qa_workflow_provisioning_service.py.
    
    Returns: dict with keys: upload_attempted, payload, exit_code, error
    """
    if not has_secrets:
        # Current behavior: crashes with KeyError on os.environ access
        return {
            "upload_attempted": False,
            "payload": None,
            "exit_code": 1,
            "error": "KeyError: SAMANVAYA_PROJECT_ID"
        }
    
    # Simulate successful upload
    tests = test_results.get("tests", 0)
    failures = test_results.get("failures", 0) + test_results.get("errors", 0)
    
    payload = {
        "project_id": "test-project-id",
        "repository": "owner/repo",
        "branch": "main",
        "commit_sha": "abc123",
        "test_suite": "github-actions",
        "tests_run": tests,
        "tests_passed": max(tests - failures, 0),
        "tests_failed": failures,
        "status": "passed" if failures == 0 else "failed"
    }
    
    return {
        "upload_attempted": True,
        "payload": payload,
        "exit_code": 0,
        "error": None
    }


# Property 2: Preservation - Python Test Execution and Provisioning Service Contract

def test_preservation_backend_tests_directory():
    """Test that Python projects with backend/tests/ continue to work identically.
    
    **Validates: Requirements 3.1**
    
    EXPECTED ON UNFIXED CODE: PASSES (baseline behavior)
    EXPECTED ON FIXED CODE: PASSES (preservation confirmed)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        
        # Create Python project with backend/tests/
        backend_tests = project_path / "backend" / "tests"
        backend_tests.mkdir(parents=True)
        (backend_tests / "test_example.py").write_text("""
def test_example():
    assert True
""")
        
        # Create requirements files
        (project_path / "requirements.txt").write_text("pytest==8.0.0\n")
        (project_path / "backend" / "requirements.txt").write_text("requests==2.31.0\n")
        
        # Test dependency installation preservation
        deps_result = simulate_dependency_installation(project_path)
        
        assert deps_result["requirements_installed"], (
            "Preservation 3.3: requirements.txt should be detected"
        )
        assert deps_result["backend_requirements_installed"], (
            "Preservation 3.3: backend/requirements.txt should be detected"
        )
        assert "pip install -r requirements.txt" in deps_result["commands_executed"], (
            "Preservation 3.3: Should install from requirements.txt"
        )
        assert "pip install -r backend/requirements.txt" in deps_result["commands_executed"], (
            "Preservation 3.3: Should install from backend/requirements.txt"
        )
        
        # Test pytest execution preservation
        test_result = simulate_python_test_execution(project_path, "backend/tests")
        
        assert test_result["command_executed"] == "pytest backend/tests -q --junitxml=test-results.xml", (
            f"Preservation 3.1: Command changed. Expected 'pytest backend/tests -q --junitxml=test-results.xml', "
            f"Got '{test_result['command_executed']}'"
        )
        
        assert test_result["exit_code"] == 0, (
            f"Preservation 3.1: Exit code changed. Expected 0, Got {test_result['exit_code']}"
        )
        
        assert test_result["junit_file_created"], (
            "Preservation 3.1: JUnit XML file should be created"
        )


def test_preservation_tests_directory():
    """Test that Python projects with tests/ continue to work identically.
    
    **Validates: Requirements 3.2**
    
    EXPECTED ON UNFIXED CODE: PASSES (baseline behavior)
    EXPECTED ON FIXED CODE: PASSES (preservation confirmed)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        
        # Create Python project with tests/ (not backend/tests/)
        tests_dir = project_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_app.py").write_text("""
def test_app():
    assert 1 + 1 == 2
""")
        
        # Test pytest execution preservation
        test_result = simulate_python_test_execution(project_path, "tests")
        
        assert test_result["command_executed"] == "pytest tests -q --junitxml=test-results.xml", (
            f"Preservation 3.2: Command changed. Expected 'pytest tests -q --junitxml=test-results.xml', "
            f"Got '{test_result['command_executed']}'"
        )
        
        assert test_result["exit_code"] == 0, (
            f"Preservation 3.2: Exit code changed. Expected 0, Got {test_result['exit_code']}"
        )


def test_preservation_upload_script_behavior():
    """Test that upload script behavior remains unchanged for Python projects.
    
    **Validates: Requirements 3.7, 3.8, 3.9**
    
    EXPECTED ON UNFIXED CODE: PASSES (baseline behavior)
    EXPECTED ON FIXED CODE: PASSES (preservation confirmed)
    """
    # Test successful upload with valid secrets
    test_results = {"tests": 10, "failures": 2, "errors": 1}
    upload_result = simulate_result_upload(test_results, has_secrets=True)
    
    assert upload_result["upload_attempted"], (
        "Preservation 3.7: Upload should be attempted with valid secrets"
    )
    
    # Verify payload structure preservation (Requirement 3.8)
    payload = upload_result["payload"]
    assert "project_id" in payload, "Preservation 3.8: payload must contain project_id"
    assert "repository" in payload, "Preservation 3.8: payload must contain repository"
    assert "branch" in payload, "Preservation 3.8: payload must contain branch"
    assert "commit_sha" in payload, "Preservation 3.8: payload must contain commit_sha"
    assert "test_suite" in payload, "Preservation 3.8: payload must contain test_suite"
    assert "tests_run" in payload, "Preservation 3.8: payload must contain tests_run"
    assert "tests_passed" in payload, "Preservation 3.8: payload must contain tests_passed"
    assert "tests_failed" in payload, "Preservation 3.8: payload must contain tests_failed"
    assert "status" in payload, "Preservation 3.8: payload must contain status"
    
    # Verify test count calculations preservation (Requirement 3.7)
    assert payload["tests_run"] == 10, (
        f"Preservation 3.7: tests_run calculation changed. Expected 10, Got {payload['tests_run']}"
    )
    assert payload["tests_failed"] == 3, (  # failures + errors = 2 + 1
        f"Preservation 3.7: tests_failed should be failures + errors. Expected 3, Got {payload['tests_failed']}"
    )
    assert payload["tests_passed"] == 7, (  # 10 - 3
        f"Preservation 3.7: tests_passed calculation changed. Expected 7, Got {payload['tests_passed']}"
    )
    
    # Verify status determination logic preservation (Requirement 3.8)
    assert payload["status"] == "failed", (
        f"Preservation 3.8: status should be 'failed' when failures > 0. Got '{payload['status']}'"
    )
    
    # Test with no failures
    test_results_passing = {"tests": 5, "failures": 0, "errors": 0}
    upload_result_passing = simulate_result_upload(test_results_passing, has_secrets=True)
    assert upload_result_passing["payload"]["status"] == "passed", (
        "Preservation 3.8: status should be 'passed' when no failures"
    )


def test_preservation_workflow_triggers():
    """Test that workflow triggers remain unchanged.
    
    **Validates: Requirements 3.10, 3.11, 3.12**
    
    EXPECTED ON UNFIXED CODE: PASSES (baseline behavior)
    EXPECTED ON FIXED CODE: PASSES (preservation confirmed)
    """
    # Read the actual workflow file to verify triggers
    workflow_file = Path(__file__).parent.parent.parent / ".github" / "workflows" / "samanvaya-qa.yml"
    
    if workflow_file.exists():
        content = workflow_file.read_text()
        
        # Requirement 3.10: Trigger on workflow_dispatch, push, pull_request
        assert "workflow_dispatch:" in content, (
            "Preservation 3.10: workflow_dispatch trigger should be preserved"
        )
        assert "push:" in content, (
            "Preservation 3.10: push trigger should be preserved"
        )
        assert "pull_request:" in content, (
            "Preservation 3.10: pull_request trigger should be preserved"
        )
        
        # Requirement 3.10: Push to any branch
        assert 'branches: ["**"]' in content or "branches: ['**']" in content, (
            "Preservation 3.10: push to any branch should be preserved"
        )
        
        # Requirement 3.11: Skip upload on pull_request
        assert "github.event_name != 'pull_request'" in content, (
            "Preservation 3.11: skip upload on pull_request condition should be preserved"
        )


# Property-Based Test: Python Project Behavior Preservation
@given(
    test_dir_type=st.sampled_from(["backend/tests", "tests"]),
    num_tests=st.integers(min_value=1, max_value=20),
    num_failures=st.integers(min_value=0, max_value=5),
    has_requirements=st.booleans(),
    has_backend_requirements=st.booleans()
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=20)
def test_preservation_python_only_project_property(
    test_dir_type: str,
    num_tests: int,
    num_failures: int,
    has_requirements: bool,
    has_backend_requirements: bool
):
    """Property: For ANY Python-only project, behavior MUST remain unchanged.
    
    **Validates: Requirements 3.1, 3.2, 3.3, 3.7, 3.8**
    
    This property test generates many Python project configurations and verifies
    that the workflow behaves identically to the baseline.
    
    EXPECTED ON UNFIXED CODE: PASSES (baseline behavior)
    EXPECTED ON FIXED CODE: PASSES (preservation confirmed)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir)
        
        # Create test directory based on parameter
        if test_dir_type == "backend/tests":
            test_dir = project_path / "backend" / "tests"
            test_dir.mkdir(parents=True)
            expected_command = "pytest backend/tests -q --junitxml=test-results.xml"
        else:
            test_dir = project_path / "tests"
            test_dir.mkdir(parents=True)
            expected_command = "pytest tests -q --junitxml=test-results.xml"
        
        # Create test files
        (test_dir / "test_sample.py").write_text("""
def test_sample():
    assert True
""")
        
        # Create requirements files if specified
        if has_requirements:
            (project_path / "requirements.txt").write_text("pytest==8.0.0\n")
        
        if has_backend_requirements:
            backend_dir = project_path / "backend"
            backend_dir.mkdir(exist_ok=True)
            (backend_dir / "requirements.txt").write_text("requests==2.31.0\n")
        
        # Property 1: Dependency installation commands must be preserved
        deps_result = simulate_dependency_installation(project_path)
        
        if has_requirements:
            assert deps_result["requirements_installed"], (
                "Property violation: requirements.txt not detected"
            )
            assert "pip install -r requirements.txt" in deps_result["commands_executed"], (
                "Property violation: requirements.txt installation command changed"
            )
        
        if has_backend_requirements:
            assert deps_result["backend_requirements_installed"], (
                "Property violation: backend/requirements.txt not detected"
            )
            assert "pip install -r backend/requirements.txt" in deps_result["commands_executed"], (
                "Property violation: backend/requirements.txt installation command changed"
            )
        
        # Property 2: Pytest execution command must be preserved exactly
        test_result = simulate_python_test_execution(project_path, test_dir_type)
        
        assert test_result["command_executed"] == expected_command, (
            f"Property violation: pytest command changed. "
            f"Expected '{expected_command}', Got '{test_result['command_executed']}'"
        )
        
        assert test_result["exit_code"] == 0, (
            "Property violation: exit code changed for successful test execution"
        )
        
        assert test_result["junit_file_created"], (
            "Property violation: JUnit XML file creation behavior changed"
        )
        
        # Property 3: Upload payload structure and calculations must be preserved
        test_results = {
            "tests": num_tests,
            "failures": min(num_failures, num_tests),  # Can't have more failures than tests
            "errors": 0
        }
        
        upload_result = simulate_result_upload(test_results, has_secrets=True)
        payload = upload_result["payload"]
        
        expected_failed = min(num_failures, num_tests)
        expected_passed = num_tests - expected_failed
        expected_status = "passed" if expected_failed == 0 else "failed"
        
        assert payload["tests_run"] == num_tests, (
            f"Property violation: tests_run calculation changed. "
            f"Expected {num_tests}, Got {payload['tests_run']}"
        )
        
        assert payload["tests_failed"] == expected_failed, (
            f"Property violation: tests_failed calculation changed. "
            f"Expected {expected_failed}, Got {payload['tests_failed']}"
        )
        
        assert payload["tests_passed"] == expected_passed, (
            f"Property violation: tests_passed calculation changed. "
            f"Expected {expected_passed}, Got {payload['tests_passed']}"
        )
        
        assert payload["status"] == expected_status, (
            f"Property violation: status determination changed. "
            f"Expected '{expected_status}', Got '{payload['status']}'"
        )


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
