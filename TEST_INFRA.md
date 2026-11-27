# Test Infrastructure & Specification Document: Code Intelligence Analyzers

**Project**: Code Intelligence Analyzers Reliability & Correctness  
**Document**: Test Infrastructure (E2E Track)  
**Target Test Suite**: `backend/tests/test_code_intelligence_analyzers.py`  
**Test Runner**: `python -m pytest backend/tests/test_code_intelligence_analyzers.py -v`  

---

## 1. Test Philosophy & Principles

The test suite for the Code Intelligence Analyzers follows an **opaque-box, requirement-driven testing methodology** grounded in formal specification mining and software reliability engineering:

1. **Opaque-Box & Requirement-Driven**: Tests are derived strictly from documented requirements in `ORIGINAL_REQUEST.md` and feature contracts in `PROJECT.md`. Tests verify observable behavioral outputs, interface schemas, and side-effect guarantees rather than private internal implementation details.
2. **Zero-Side-Effect & Complete Isolation**: Every test is self-contained and reproducible. File system tests execute inside isolated temporary directories (`tempfile.TemporaryDirectory`). Subprocesses and external CLI tools (`radon`, `lizard`, `flake8`, `npm`, `tsc`, `pip-audit`) are tested using representative fixed JSON/text fixtures and mock resolution (`unittest.mock`), ensuring tests run consistently across Windows, Linux, and macOS without requiring host tool installations or network access.
3. **Progressive Testability & Defect Exposure**: Tests specify exact expected behaviors. When an implementation bug exists in production code, tests fail deterministically with actionable diagnostics, enabling clear defect escalation to milestone workers and serving as the objective acceptance gate for Milestone 6 (100% Pass).
4. **Adversarial & Multi-Tier Verification**: Beyond happy-path verification, the suite subjects every analyzer component to boundary-value analysis (BVA), malformed inputs, casing inconsistencies, path traversal edge cases, and complex multi-language monorepo interactions.

---

## 2. Feature Inventory (Features 1 to 24)

| # | ID | Feature Name | Description | Target Module | Task / Milestone |
|---|----|--------------|-------------|---------------|------------------|
| 1 | F1 | Lockfile Filtering | Exclude all dependency lockfiles (`package-lock.json`, `npm-shrinkwrap.json`, `pnpm-lock.yaml`, `pnpm-lock.yml`, `yarn.lock`, `bun.lockb`, `packages.lock.json`, `gradle.lockfile`, etc.) by explicit names, compound patterns, and suffixes. | `backend/intelligence/analyzers/common/secrets_scanner.py` | Task 1.2 / M1 |
| 2 | F2 | Complete Sequential Redaction | Redact all credentials sequentially across the entire line before creating snippets or storing findings, handling multiple distinct or identical credentials on a single line. | `backend/intelligence/analyzers/common/secrets_scanner.py` | Task 1.2 / M1 |
| 3 | F3 | Obvious Test Fixture Handling | Distinguish documented dummy/example keys and placeholder tokens (downgrading to `SeverityEnum.LOW` with rule suffix `-FIXTURE`) without suppressing genuine leaked credentials. | `backend/intelligence/analyzers/common/secrets_scanner.py` | Task 1.2 / M1 |
| 4 | F4 | Raw Secret Prevention | Guarantee that raw credentials never appear in findings, rule IDs, messages, or logs; snippet slicing occurs strictly after complete redaction. | `backend/intelligence/analyzers/common/secrets_scanner.py` | Task 1.2 / M1 |
| 5 | F5 | Maintainability Index Separation | Separate Maintainability Index (MI) from `comment_ratio` by adding `maintainability_index` to `ComplexityEvidence` and preserving true comment density. | `backend/intelligence/analyzers/common/complexity.py`, `backend/intelligence/evidence/models.py` | Task 1.5 / M4 |
| 6 | F6 | Radon Supplement Schema Reconciliation | Support both Radon Cyclomatic Complexity (CC) metrics and Maintainability Index (MI) dictionaries in `_merge_radon_supplement`. | `backend/intelligence/analyzers/common/complexity.py` | Task 1.5 / M4 |
| 7 | F7 | Documented Python AST Branch Metric | McCabe CC metric definition ($CC = 1 + B$), including ternary expressions (`IfExp`), comprehensions, match cases, assertions, and boolean operators (`N - 1` branches). | `backend/intelligence/analyzers/common/complexity.py` | Task 1.5 / M4 |
| 8 | F8 | Nested Function Scoping | Prevent double-counting branches in nested functions, closures, and inner classes within outer function complexity. | `backend/intelligence/analyzers/common/complexity.py` | Task 1.5 / M4 |
| 9 | F9 | Unavailable Complexity Representation | Represent missing language tooling as `is_available = False` and `average_complexity = None` rather than misleading zero, handled gracefully in `EvidenceMerger`. | `backend/intelligence/analyzers/common/complexity.py`, `backend/intelligence/evidence/merger.py` | Task 1.5 / M4 |
| 10 | F10 | Canonical Directory Exclusion | Define case-insensitive canonical `EXCLUDED_DIRS` (`node_modules`, `venv`, `.venv`, `build`, `dist`, `target`, `bin`, `obj`, `__pycache__`, `vendor`, `generated`, `.gradle`, `.mvn`, `.git`). | `backend/intelligence/analyzers/base.py`, `backend/intelligence/analyzers/language_detector.py` | Task 1.6 / M5 |
| 11 | F11 | Case-Insensitive File & Extension Filtering | Normalize path segments and extension lookups case-insensitively in `BaseAnalyzer._filter_files` and `LanguageDetector`. | `backend/intelligence/analyzers/base.py`, `backend/intelligence/analyzers/language_detector.py` | Task 1.6 / M5 |
| 12 | F12 | Optimized Directory Traversal | Prune excluded directories in-place during `os.walk` to prevent expensive deep traversals into `node_modules` or virtual environments. | `backend/intelligence/analyzers/language_detector.py` | Task 1.6 / M5 |
| 13 | F13 | Case-Insensitive Build & Tool Hints | Support lowercase/uppercase build file names (`makefile`, `PACKAGE.JSON`, etc.) in `BUILD_FILE_MAP` and `TEST_FRAMEWORK_HINTS`. | `backend/intelligence/analyzers/language_detector.py` | Task 1.6 / M5 |
| 14 | F14 | Pip-Audit Format Handling | Parse both dictionary format `{"dependencies": [...]}` and list format `[{"name": ..., "vulns": [...]}]`, extracting package version, CVE aliases, and advisory details. | `backend/intelligence/analyzers/python/analyzer.py` | Task 1.3 / M2 |
| 15 | F15 | Explicit Dependency Tool Failure Handling | Check `result is not None`, record explicit tool degradation upon failure, and prevent premature fallthrough on clean scans with 0 vulnerabilities. | `backend/intelligence/analyzers/python/analyzer.py` | Task 1.3 / M2 |
| 16 | F16 | Flake8 Clean Run & Format Compatibility | Distinguish clean lint runs (empty string stdout) from tool failures, support JSON output templates, and broaden regex parsing. | `backend/intelligence/analyzers/python/analyzer.py` | Task 1.3 / M2 |
| 17 | F17 | Python-Aware AST Architecture Rules | Replace naive substring searches with AST `ast.Import` and `ast.ImportFrom` visitors to ignore comments/strings and detect package-qualified imports. | `backend/intelligence/analyzers/python/analyzer.py` | Task 1.3 / M2 |
| 18 | F18 | Static AST Test Counting | Safely count tests statically via AST without executing arbitrary untrusted project test code during static analysis, with regex fallback for pytest output. | `backend/intelligence/analyzers/python/analyzer.py` | Task 1.3 / M2 |
| 19 | F19 | Windows Subprocess Resolution | Resolve Node executables (`npm`, `npx`, `eslint`, `tsc`) safely via `shutil.which` without `shell=True`, adding local `node_modules/.bin` support and empty command guards. | `backend/intelligence/analyzers/javascript/analyzer.py` | Task 1.4 / M3 |
| 20 | F20 | Subprocess Lifecycle & Timeout Cleanup | Terminate and reap orphaned child processes (`proc.kill()`, `await proc.wait()`) upon `asyncio.TimeoutError`. | `backend/intelligence/analyzers/javascript/analyzer.py` | Task 1.4 / M3 |
| 21 | F21 | Fixed TSC Fallback Loop | Fix loop control in `_tsc` so that failures with `tsc` correctly fall back to `npx tsc` instead of prematurely breaking. | `backend/intelligence/analyzers/javascript/analyzer.py` | Task 1.4 / M3 |
| 22 | F22 | npm Audit Null & Field Type Safety | Eliminate `TypeError: 'NoneType' object is not subscriptable` when `title` or `cve` is null, preserve transitive advisory metadata across all `via` items, and ensure strict field types. | `backend/intelligence/analyzers/javascript/analyzer.py` | Task 1.4 / M3 |
| 23 | F23 | Partition TypeScript Diagnostics | Distinguish changed-file TypeScript diagnostics (`source_tool="tsc"`) from pre-existing repository-wide diagnostics (`source_tool="tsc-repo-wide"`), normalizing Windows path separators. | `backend/intelligence/analyzers/javascript/analyzer.py` | Task 1.4 / M3 |
| 24 | F24 | E2E Multi-Tier Test Suite | Comprehensive multi-tier test infrastructure validating all 23 features across unit, boundary, pairwise, and realistic monorepo scenarios. | `backend/tests/test_code_intelligence_analyzers.py` | E2E Track |

---

## 3. Test Runner & Execution Environment

### 3.1 Primary Execution Command
```powershell
python -m pytest backend/tests/test_code_intelligence_analyzers.py -v
```

### 3.2 Environment Specifications
- **Python Runtime**: Python 3.12+ (standard library `ast`, `re`, `shutil`, `tempfile`, `pathlib`, `asyncio`, `json`).
- **Test Engine**: `pytest` 8.x with `pytest-asyncio` for asynchronous analyzer pipelines.
- **Root Directory**: `backend` (configured with `pytest.ini` and `conftest.py`).
- **Dependencies**: No external database or message broker required; all tests operate purely in-memory and on ephemeral temporary files.

### 3.3 Test Organization in `backend/tests/test_code_intelligence_analyzers.py`
The test file is partitioned into structured test classes representing the baseline regression suite and the four multi-tier evaluation levels:

1. **Existing Baseline Regressions**:
   - `TestDuplicationAnalyzer`: Interval union, sliding window duplication, line counting consistency (35 tests).
2. **Tier 1: Feature Coverage (Category-Partition Testing)**:
   - `TestTier1SecretsScanner`: Features F1, F2, F3, F4 (>=5 tests per feature).
   - `TestTier1ComplexityAnalyzer`: Features F5, F6, F7, F8, F9 (>=5 tests per feature).
   - `TestTier1LanguageDetectionAndFiltering`: Features F10, F11, F12, F13 (>=5 tests per feature).
   - `TestTier1PythonAnalyzer`: Features F14, F15, F16, F17, F18 (>=5 tests per feature).
   - `TestTier1JavaScriptTypeScriptAnalyzer`: Features F19, F20, F21, F22, F23 (>=5 tests per feature).
3. **Tier 2: Boundary Value Analysis & Edge Cases**:
   - `TestTier2BoundarySecretsScanner`: Long lines, extreme credential counts, empty files, regex metacharacters.
   - `TestTier2BoundaryComplexity`: Deeply nested structures, empty functions, zero-LOC files, boundary MI values.
   - `TestTier2BoundaryLanguageDetection`: Mixed-case nested directories, unusual extensions, symlink loops, empty repos.
   - `TestTier2BoundaryPythonAnalyzer`: Truncated JSON, SyntaxError files, malformed flake8 lines, empty test files.
   - `TestTier2BoundaryJavaScriptAnalyzer`: Null fields, empty command lists, malformed npm audit trees, trailing backslashes.
4. **Tier 3: Pairwise Cross-Feature Interactions**:
   - `TestTier3PairwiseCrossFeatureInteractions`: Multi-language repositories, detector-to-analyzer routing, EvidenceMerger aggregation with mixed tool outcomes.
5. **Tier 4: Real-World Application Scenarios**:
   - `TestTier4RealWorldScenarios`: Monorepo PR workflows, legacy debt vs PR findings, security leak handling in full project trees.

---

## 4. Multi-Tier Testing Methodology

```
┌─────────────────────────────────────────────────────────────┐
│ Tier 4: Real-World Scenarios                                │
│ Full Monorepo PRs, Legacy Debt Partitioning, Multi-Tool CI  │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ Tier 3: Pairwise Cross-Feature Interactions                 │
│ Detector -> Analyzers -> EvidenceMerger Composite Workflows │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ Tier 2: Boundary & Corner Cases                             │
│ BVA, Nulls, Empty Trees, Deep Nesting, Process Timeouts     │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ Tier 1: Core Feature Coverage (Category-Partition)          │
│ >=5 tests per feature for F1 through F23                    │
└─────────────────────────────────────────────────────────────┘
```

### 4.1 Tier 1: Core Feature Coverage
- **Objective**: Verify the fundamental specification contract of every individual feature under normal operating parameters.
- **Criteria**: Minimum 5 dedicated test cases per feature covering all expected input equivalence classes.

### 4.2 Tier 2: Boundary Value Analysis (BVA) & Corner Cases
- **Objective**: Stress-test edge conditions, null handling, type coercions, extreme sizes, and subprocess lifecycle boundaries.
- **Criteria**:
  - Null/None values in structured tool outputs (`title: null`, `cve: null`).
  - Empty inputs (0-byte files, 0 files, empty command list `[]`).
  - Single-line extremes (5+ distinct secrets on a 5000-character line).
  - Operating system path variations (Windows backslashes vs POSIX slashes, uppercase extensions, UNC paths).
  - Tool execution timeouts and clean child process termination.

### 4.3 Tier 3: Pairwise & Cross-Feature Interactions
- **Objective**: Validate interoperability when multiple features and analyzers operate on the same repository.
- **Criteria**:
  - `LanguageDetector` output fed directly into `BaseAnalyzer._filter_files`.
  - Python analyzer evidence + JavaScript analyzer evidence merged via `EvidenceMerger`.
  - Handling of repositories where one language has full tooling available and another has unmeasured complexity.
  - Secrets scanner operating across both Python, JS, TS, and ignored lockfiles in a single repository scan.

### 4.4 Tier 4: Real-World Application Scenarios
- **Objective**: Simulate end-to-end pull request analysis on realistic enterprise codebases.
- **Criteria**:
  - Full-stack monorepo with `api/` (Python FastAPI), `web/` (React/TypeScript), dependency trees, and generated files.
  - Pull request introducing new code while pre-existing repository debt exists (verifying `tsc` vs `tsc-repo-wide` tagging).
  - Security incident PR containing a mixture of documentation dummy keys (downgraded to LOW) and genuine leaked credentials (CRITICAL).
  - Resilient static analysis when external CLI linters fail or timeout without halting repository reporting.

---

## 5. Traceability Matrix

| Requirement | Tasks | Features Covered | Test Class |
|-------------|-------|------------------|------------|
| R1: Secrets Scanner Correctness | Task 1.2 | F1, F2, F3, F4 | `TestTier1SecretsScanner`, `TestTier2BoundarySecretsScanner`, `TestTier4RealWorldScenarios` |
| R2: Python Analyzer Reliability | Task 1.3 | F14, F15, F16, F17, F18 | `TestTier1PythonAnalyzer`, `TestTier2BoundaryPythonAnalyzer`, `TestTier3PairwiseCrossFeatureInteractions` |
| R3: JS & TS Analyzer Reliability | Task 1.4 | F19, F20, F21, F22, F23 | `TestTier1JavaScriptTypeScriptAnalyzer`, `TestTier2BoundaryJavaScriptAnalyzer`, `TestTier4RealWorldScenarios` |
| R4: Shared Complexity Corrections | Task 1.5 | F5, F6, F7, F8, F9 | `TestTier1ComplexityAnalyzer`, `TestTier2BoundaryComplexity`, `TestTier3PairwiseCrossFeatureInteractions` |
| R5: Language Detection & Filtering | Task 1.6 | F10, F11, F12, F13 | `TestTier1LanguageDetectionAndFiltering`, `TestTier2BoundaryLanguageDetection`, `TestTier3PairwiseCrossFeatureInteractions` |
