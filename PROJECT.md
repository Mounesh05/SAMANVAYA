# Project: Code Intelligence Analyzers Reliability & Correctness

## Architecture
The code intelligence system analyzes source code repositories across multiple programming languages. It consists of:
1. **Base & Registry (`base.py`, `registry.py`)**: Abstract analyzer contracts, file filtering, language-to-analyzer mapping, quality degradation tracking.
2. **Language Detector (`language_detector.py`)**: Detects repository languages from files and file trees, mapping build tools and test frameworks.
3. **Common Analyzers (`common/`)**:
   - `secrets_scanner.py`: Regex-based secret detection with sequential redaction, fixture handling, and lockfile filtering.
   - `complexity.py`: Shared cyclomatic complexity (AST and Lizard/Radon) and maintainability index analysis.
4. **Language-Specific Analyzers**:
   - `python/analyzer.py`: AST parsing, Flake8 linting, pip-audit dependency auditing, architecture rule enforcement, and static test counting.
   - `javascript/analyzer.py`: Windows-safe subprocess execution, ESLint linting, TypeScript compilation diagnostics partitioning, and npm audit parsing.
5. **Evidence Models & Merging (`evidence/`)**: Data models (`models.py`) and evidence synthesizer (`merger.py`) compiling findings into unified repository reports.

---

## Feature Inventory

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Lockfile Filtering | Exclude all dependency lockfiles (`package-lock.json`, `npm-shrinkwrap.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`, `packages.lock.json`, `gradle.lockfile`, etc.) by explicit names, suffixes, and compound patterns | M1 | Survey 1 (Task 1.2) |
| 2 | Complete Sequential Redaction | Redact all credentials sequentially across the entire line before creating snippets or storing findings, handling multiple distinct or identical credentials on a single line | M1 | Survey 1 (Task 1.2) |
| 3 | Obvious Test Fixture Handling | Distinguish documented dummy/example keys and placeholder tokens (downgrading to `SeverityEnum.LOW` with rule suffix `-FIXTURE`) without suppressing genuine leaked credentials | M1 | Survey 1 (Task 1.2) |
| 4 | Raw Secret Prevention | Guarantee that raw credentials never appear in findings, rule IDs, messages, or logs; snippet slicing occurs after complete redaction | M1 | Survey 1 (Task 1.2) |
| 5 | Maintainability Index Separation | Separate Maintainability Index (MI) from `comment_ratio` by adding `maintainability_index` to `ComplexityEvidence` and preserving true comment density | M4 | Survey 1 (Task 1.5) |
| 6 | Radon Supplement Schema Reconciliation | Support both Radon Cyclomatic Complexity (CC) metrics and Maintainability Index (MI) dictionaries in `_merge_radon_supplement` | M4 | Survey 1 (Task 1.5) |
| 7 | Documented Python AST Branch Metric | McCabe CC metric definition ($CC = 1 + B$), including ternary expressions (`IfExp`), comprehensions, match cases, and boolean operators (`N - 1` branches) | M4 | Survey 1 (Task 1.5) |
| 8 | Nested Function Scoping | Prevent double-counting branches in nested functions, closures, and inner classes within outer function complexity | M4 | Survey 1 (Task 1.5) |
| 9 | Unavailable Complexity Representation | Represent missing language tooling as `is_available = False` and `average_complexity = None` rather than misleading zero, handled gracefully in `EvidenceMerger` | M4 | Survey 1 (Task 1.5) |
| 10 | Canonical Directory Exclusion | Define case-insensitive canonical `EXCLUDED_DIRS` (`node_modules`, `venv`, `build`, `dist`, `target`, `bin`, `obj`, `__pycache__`, `vendor`, `generated`, `.gradle`, `.mvn`, `.git`) | M5 | Survey 2 (Task 1.6) |
| 11 | Case-Insensitive File & Extension Filtering | Normalize path segments and extension lookups case-insensitively in `BaseAnalyzer._filter_files` and `LanguageDetector` | M5 | Survey 2 (Task 1.6) |
| 12 | Optimized Directory Traversal | Prune excluded directories in-place during `os.walk` to prevent expensive deep traversals into `node_modules` or virtual environments | M5 | Survey 2 (Task 1.6) |
| 13 | Case-Insensitive Build & Tool Hints | Support lowercase/uppercase build file names (`makefile`, `PACKAGE.JSON`, etc.) in `BUILD_FILE_MAP` and `TEST_FRAMEWORK_HINTS` | M5 | Survey 2 (Task 1.6) |
| 14 | Pip-Audit Format Handling | Parse both dictionary format `{"dependencies": [...]}` and list format `[{"name": ..., "vulns": [...]}]`, extracting package version, CVE aliases, and advisory details | M2 | Survey 2 (Task 1.3) |
| 15 | Explicit Dependency Tool Failure Handling | Check `result is not None`, record explicit tool degradation upon failure, and prevent premature fallthrough on clean scans with 0 vulnerabilities | M2 | Survey 2 (Task 1.3) |
| 16 | Flake8 Clean Run & Format Compatibility | Distinguish clean lint runs (empty string stdout) from tool failures, support JSON output templates, and broaden regex parsing | M2 | Survey 2 (Task 1.3) |
| 17 | Python-Aware AST Architecture Rules | Replace naive substring searches with AST `ast.Import` and `ast.ImportFrom` visitors to ignore comments/strings and detect package-qualified imports | M2 | Survey 2 (Task 1.3) |
| 18 | Static AST Test Counting | Safely count tests statically via AST without executing arbitrary untrusted project test code during static analysis, with regex fallback for pytest output | M2 | Survey 2 (Task 1.3) |
| 19 | Windows Subprocess Resolution | Resolve Node executables (`npm`, `npx`, `eslint`, `tsc`) safely via `shutil.which` without `shell=True`, adding local `node_modules/.bin` support and empty command guards | M3 | Survey 3 (Task 1.4) |
| 20 | Subprocess Lifecycle & Timeout Cleanup | Terminate and reap orphaned child processes (`proc.kill()`, `await proc.wait()`) upon `asyncio.TimeoutError` | M3 | Survey 3 (Task 1.4) |
| 21 | Fixed TSC Fallback Loop | Fix loop control in `_tsc` so that failures with `tsc` correctly fall back to `npx tsc` instead of prematurely breaking | M3 | Survey 3 (Task 1.4) |
| 22 | npm Audit Null & Field Type Safety | Eliminate `TypeError: 'NoneType' object is not subscriptable` when `title` or `cve` is null, preserve transitive advisory metadata across all `via` items, and ensure strict field types | M3 | Survey 3 (Task 1.4) |
| 23 | Partition TypeScript Diagnostics | Distinguish changed-file TypeScript diagnostics (`source_tool="tsc"`) from pre-existing repository-wide diagnostics (`source_tool="tsc-repo-wide"`), normalizing Windows path separators | M3 | Survey 3 (Task 1.4) |
| 24 | E2E Test Infrastructure & Test Suite | Requirement-driven multi-tier test suite covering all features with Category-Partition, BVA, Pairwise, and real-world scenarios | E2E | Survey 3 (Test Infra) |
| 25 | 100% E2E Pass & Adversarial Hardening | Phase 1: 100% pass on Tiers 1-4; Phase 2: Adversarial white-box coverage hardening (Tier 5) with challenger loop | M6 | Survey Master |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Secrets Scanner Correctness & Redaction (Task 1.2) | Features 1, 2, 3, 4 | none | **DONE** |
| M4 | Shared Complexity Analyzer Corrections (Task 1.5) | Features 5, 6, 7, 8, 9 | none | **DONE** |
| M5 | Language Detection & Filtering (Task 1.6) | Features 10, 11, 12, 13 | none | **DONE** |
| M2 | Python Analyzer Reliability (Task 1.3) | Features 14, 15, 16, 17, 18 | M5 | PLANNED |
| M3 | JavaScript & TypeScript Analyzer Reliability (Task 1.4) | Features 19, 20, 21, 22, 23 | M5 | PLANNED |
| E2E | E2E Testing Track | Feature 24 (Tiers 1-4 Test Infra & Suites) | none (parallel) | **DONE** |
| M6 | Final Milestone: 100% E2E Pass & Adversarial Hardening | Feature 25 (Phase 1: Pass Tiers 1-4; Phase 2: Tier 5 Adversarial) | M1, M2, M3, M4, M5, E2E | PLANNED |

---

## Code Layout & Exclusive File Ownership

Each concurrent worker/milestone has exclusive write boundaries:
- **Milestone 1 (Task 1.2)**:
  - Exclusive write ownership: `backend/intelligence/analyzers/common/secrets_scanner.py`
  - Test write ownership: `backend/tests/test_secrets_scanner_regression.py`, `backend/tests/test_secrets_scanner_adversarial.py`
  - Output: 148 passing tests, gate signed off.
- **Milestone 4 (Task 1.5)**:
  - Exclusive write ownership: `backend/intelligence/analyzers/common/complexity.py`, `backend/intelligence/evidence/models.py`, `backend/intelligence/evidence/merger.py`
  - Test write ownership: `backend/tests/test_complexity_analyzer_regression.py`
- **Milestone 5 (Task 1.6)**:
  - Exclusive write ownership: `backend/intelligence/analyzers/language_detector.py`, `backend/intelligence/analyzers/base.py`
  - Test write ownership: `backend/tests/test_language_detector_regression.py`
- **Milestone 2 (Task 1.3)**:
  - Exclusive write ownership: `backend/intelligence/analyzers/python/analyzer.py`
  - Test write ownership: `backend/tests/test_python_analyzer_regression.py`
- **Milestone 3 (Task 1.4)**:
  - Exclusive write ownership: `backend/intelligence/analyzers/javascript/analyzer.py`
  - Test write ownership: `backend/tests/test_javascript_analyzer_regression.py`
- **E2E Testing Track**:
  - Exclusive write ownership: `backend/tests/test_code_intelligence_analyzers.py`, `TEST_INFRA.md`, `TEST_READY.md`
