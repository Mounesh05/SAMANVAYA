#!/usr/bin/env bash
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
        find target/surefire-reports -name "TEST-*.xml" -exec cat {} \; > test-results-java.xml
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
        find build/test-results/test -name "*.xml" -exec cat {} \; > test-results-java.xml
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
