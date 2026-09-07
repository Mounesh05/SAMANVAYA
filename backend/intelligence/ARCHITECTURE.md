# Intelligence Layer Architecture

## Overview
Samanvaya's intelligence layer provides **evidence-based** analysis of code quality, risk, and developer performance using deterministic engines and language-specific analyzers.

---

## Authoritative Architecture (Current)

### Single Source of Truth: Engine-Based Scoring

```
┌─────────────────────────────────────────────────────────────┐
│                    AUTHORITATIVE PATH                        │
└─────────────────────────────────────────────────────────────┘

1. Language-Specific Analyzers
   ├── PythonAnalyzer
   ├── JavaScriptAnalyzer  
   ├── JavaAnalyzer
   ├── CppAnalyzer
   └── CAnalyzer
         ↓
   • Run static analysis tools (ruff, eslint, checkstyle, etc.)
   • Collect complexity metrics (radon, lizard, etc.)
   • Detect security issues (bandit, semgrep)
   • Gather testing evidence (pytest, jest, junit)
   • Generate CodeQualityEvidence objects

2. Evidence Merger
   ├── Combines evidence from multiple language analyzers
   ├── Weighted aggregation (LOC-based for complexity)
   ├── Accurate duplication percentage calculation
   └── Produces unified CodeQualityEvidence
         ↓

3. Deterministic Engines (AUTHORITATIVE)
   ┌────────────────────────────────────┐
   │ QualityEngine                      │
   │ • Input: CodeQualityEvidence       │
   │ • Output: quality_score (0-100)    │
   │ • Penalties: complexity, coverage, │
   │   duplication, architecture        │
   └────────────────────────────────────┘
   
   ┌────────────────────────────────────┐
   │ RiskEngine                         │
   │ • Input: CodeQualityEvidence       │
   │ • Output: risk_score (0-100)       │
   │ • Factors: size, security, tests,  │
   │   hotspots, complexity             │
   └────────────────────────────────────┘
         ↓

4. LLM Layer (EXPLANATORY, NOT AUTHORITATIVE)
   ├── Receives: quality_score + risk_score + evidence
   ├── Generates: explanations, recommendations, insights
   └── DOES NOT: calculate scores or override engine results
```

### Key Principles

1. **Deterministic Engines = Authoritative**
   - QualityEngine and RiskEngine provide **final scores**
   - Scores are reproducible and auditable
   - Based on measurable evidence, not LLM interpretation

2. **LLMs = Explanatory**
   - LLMs explain the evidence and scores
   - LLMs provide actionable recommendations
   - LLMs do NOT generate technical scores

3. **Evidence-First Evaluation**
   - 90% evidence-based (from engines)
   - 10% human feedback (optional calibration)
   - Never manufacture scores when data is missing

4. **None Semantics**
   - `None` = data unavailable / not measured
   - `0` = measured zero value
   - Missing data reduces **confidence**, not **quality**

---

## Deprecated Architecture (Legacy)

### ⚠️ ORPHANED: Old Metrics Modules

The following modules exist in `backend/intelligence/metrics/` but are **NOT USED**:

1. **QualityMetrics** (`quality_metrics.py`)
   - Calculates independent risk scores for test health, bug density, coverage
   - ❌ NOT imported anywhere
   - ❌ Conflicts with QualityEngine authority

2. **DevOpsMetrics** (`devops_metrics.py`)
   - Calculates independent risk scores for CI/CD health, deployment reliability
   - ❌ NOT imported anywhere
   - ❌ Conflicts with RiskEngine deployment analysis

3. **CodeMetrics** (`code_metrics.py`)
   - Calculates independent risk scores for PR size, file types, commit patterns
   - ❌ NOT imported anywhere
   - ❌ Conflicts with RiskEngine PR analysis

4. **SprintMetrics** (`sprint_metrics.py`)
   - Calculates independent risk scores for sprint progress, velocity, scope creep
   - ❌ NOT imported anywhere
   - ❌ Would conflict with sprint planning features

### Why They Were Deprecated

These modules represent an **older parallel architecture** where individual metric calculators each computed their own risk scores. This created:

- **Dual source of truth**: Multiple modules calculating "risk_score" independently
- **Inconsistent thresholds**: Different modules used different risk formulas
- **No unified aggregation**: No clear way to combine metrics into final assessment
- **LLM confusion**: Unclear which scores were authoritative for AI analysis

The newer **Engine-Based Architecture** solves these issues by:
- Single authoritative scoring path (QualityEngine + RiskEngine)
- Unified evidence model (CodeQualityEvidence)
- Clear aggregation strategy (EvidenceMerger)
- Explicit LLM role (explanatory, not scoring)

### Removal Plan

**Status**: Scheduled for removal (safe to delete)

**Verification**:
```bash
# Confirmed no imports:
grep -r "from intelligence.metrics" backend/
grep -r "import.*Metrics" backend/
# Result: No matches (orphaned code)
```

**Action Items**:
1. Delete `backend/intelligence/metrics/quality_metrics.py`
2. Delete `backend/intelligence/metrics/devops_metrics.py`
3. Delete `backend/intelligence/metrics/code_metrics.py`
4. Delete `backend/intelligence/metrics/sprint_metrics.py`
5. Keep `backend/intelligence/metrics/__init__.py` if other modules added

---

## Active Components

### Language Analyzers
**Location**: `backend/intelligence/analyzers/<language>/`

Each analyzer follows the `BaseAnalyzer` contract:
- Returns `CodeQualityEvidence` (never raises on missing tools)
- Degrades confidence when tools unavailable
- Filters files by language extension
- Runs async analysis passes (lint, security, complexity, testing)

### Evidence Models
**Location**: `backend/intelligence/evidence/models.py`

Core data structures:
- `CodeQualityEvidence`: Complete evidence package
- `ComplexityEvidence`: Cyclomatic complexity, LOC, nesting
- `SecurityEvidence`: Vulnerabilities, secrets, dependency issues
- `TestingEvidence`: Coverage, test counts, framework detection
- `DuplicationEvidence`: Code duplication metrics
- `ArchitectureEvidence`: Layer violations, circular dependencies
- `CICDEvidence`: Build/deployment status
- `AnalysisQuality`: Confidence tracking for degraded analysis

### Evidence Merger
**Location**: `backend/intelligence/evidence/merger.py`

Combines evidence from multiple language analyzers:
- Weighted averages for complexity (by LOC)
- Weighted averages for coverage (by test count)
- Accurate duplication percentage (from total LOC)
- Conservative approach (lowest confidence, worst case values)

### Quality Engine
**Location**: `backend/intelligence/quality_engine.py`

Calculates **authoritative quality score** (0-100):
- Base score: 100 (perfect quality)
- Penalties applied for:
  - Low test coverage (missing coverage reduces confidence, not quality)
  - High complexity
  - Code duplication
  - Architecture violations
  - Security findings
- Returns: `quality_score`, `quality_level`, `breakdown`

### Risk Engine
**Location**: `backend/intelligence/risk_engine.py`

Calculates **authoritative risk score** (0-100):
- Factors:
  - PR size (files changed, lines added/deleted)
  - Security vulnerabilities (critical, high, medium)
  - Missing tests (coverage gaps)
  - Complexity spikes
  - Hot path modifications
  - Dependency changes
- Returns: `risk_score`, `risk_level`, `risk_factors`
- None semantics: Returns `risk_score=None` when data unavailable

### Risk Rules
**Location**: `backend/intelligence/rules/risk_rules.py`

Threshold-based risk calculations:
- PR size thresholds (files, lines)
- Security severity weights
- Testing gap penalties
- Complexity thresholds
- Deployment failure thresholds

**Note**: Legacy Z-score fields (`alpha_size_zscore`, `zeta_complexity`) still present in schema but **never used** (baseline=None always). Full removal requires database migration.

---

## Data Flow Example: PR Analysis

### Step 1: GitHub Webhook
```python
# api/routes/webhooks.py
POST /webhooks/github
  ↓ triggers
github_analysis_service.analyze_pr()
```

### Step 2: Language Detection & Analysis
```python
# domain/services/github_analysis_service.py
detected_languages = detect_languages_in_files(changed_files)
# → ["python", "javascript"]

for lang in detected_languages:
    analyzer = get_analyzer(lang)
    lang_files = filter_files_for_language(changed_files, lang)
    evidence = await analyzer.analyze(lang_files, repo_path, pr_context)
    evidence_list.append(evidence)
```

### Step 3: Evidence Merging
```python
# intelligence/evidence/merger.py
merged_evidence = EvidenceMerger.merge(evidence_list)
# → Single CodeQualityEvidence with:
#   - All findings from all languages
#   - Weighted complexity averages
#   - Accurate duplication percentage
#   - Lowest confidence (most conservative)
```

### Step 4: Authoritative Scoring
```python
# intelligence/quality_engine.py
quality_result = QualityEngine().calculate_quality(merged_evidence)
# → quality_score: 78, quality_level: "GOOD"

# intelligence/risk_engine.py
risk_result = await RiskEngine().analyze_pr(
    files_changed=len(changed_files),
    evidence=merged_evidence,
    pr_context=pr_context
)
# → risk_score: 35, risk_level: "MEDIUM"
```

### Step 5: LLM Explanation (Optional)
```python
# agents/code_agent.py
if use_ai:
    ai_insights = await code_agent.analyze_code_changes(
        evidence=merged_evidence,
        quality_score=quality_result["quality_score"],
        risk_score=risk_result["risk_score"]
    )
    # LLM receives scores, explains evidence, provides recommendations
    # LLM does NOT calculate or override scores
```

### Step 6: Storage & Response
```python
# Store in database with authoritative scores
await db.create_code_quality_report(
    pr_id=pr_id,
    quality_score=quality_result["quality_score"],
    risk_score=risk_result["risk_score"],
    evidence=merged_evidence,
    ai_insights=ai_insights  # Optional
)
```

---

## Configuration

### Risk Dimension Weights
**Location**: `backend/intelligence/rules/risk_rules.py`

```python
RISK_DIMENSION_WEIGHTS = {
    "alpha_size_zscore": 0.20,      # Legacy (unused, baseline=None)
    "beta_hotspot": 0.15,
    "gamma_dependency": 0.10,
    "delta_missing_tests": 0.25,
    "epsilon_security": 0.20,
    "zeta_complexity": 0.10,        # Legacy (unused, baseline=None)
}
```

**Note**: Z-score fields are schema debt. With `baseline=None`, code falls back to simple threshold-based calculation.

### Quality Thresholds
**Location**: `backend/intelligence/quality_engine.py`

```python
MIN_COVERAGE_THRESHOLD = 80.0       # Target coverage percentage
MAX_COMPLEXITY = 15.0               # Cyclomatic complexity limit
MAX_DUPLICATION = 5.0               # Duplication percentage limit
```

---

## Testing Strategy

### Unit Tests
- Each analyzer has test coverage in `backend/tests/`
- Engine calculations tested with known inputs/outputs
- Evidence merger tested with multi-language scenarios

### Integration Tests
- Full PR analysis flow tested end-to-end
- GitHub webhook handling verified
- Database storage confirmed

### Quality Checks
- `ruff` for Python linting
- `mypy` for type checking
- `pytest` for test execution
- Pre-commit hooks enforce standards

---

## Future Improvements

### Planned Enhancements
1. **Machine Learning Risk Models** (Phase 2)
   - Train models on historical PR data
   - Predict risk based on patterns
   - Augment (not replace) deterministic engines

2. **Team Performance Metrics** (Phase 2)
   - Sprint velocity tracking
   - Bug density trends
   - Deployment frequency (DORA metrics)

3. **Custom Risk Rules** (Phase 2)
   - Per-project thresholds
   - Domain-specific risk factors
   - Customizable weights

### Technical Debt
1. **Z-score Field Removal**
   - Requires database migration
   - Remove from `RiskDimensionWeights` model
   - Clean up `risk_config_service.py`

2. **Orphaned Metrics Deletion**
   - Remove old metrics modules
   - Confirm no hidden dependencies

---

## Decision Log

### 2026-09-01: Engine-Based Architecture Finalized
**Decision**: QualityEngine and RiskEngine are the single source of truth for scoring.

**Rationale**:
- Eliminates dual-source-of-truth problem
- Makes LLM role clear (explanatory, not authoritative)
- Enables 90% evidence / 10% human evaluation model
- Provides reproducible, auditable scores

**Impact**:
- Old metrics modules deprecated
- All scoring flows through engines
- LLM prompts explicitly state scores are given, not generated

### 2026-09-01: None Semantics Enforced
**Decision**: `None` always means "unavailable," never conflated with zero.

**Rationale**:
- Prevents treating missing data as poor quality
- Enables proper confidence tracking
- Makes data quality transparent to users

**Impact**:
- All engines return `None` for missing data scenarios
- Analyzers degrade confidence when tools unavailable
- Quality scores unaffected by missing coverage (confidence reduced instead)

### 2026-09-01: Evidence-First Evaluation
**Decision**: 90% evidence-based, 10% human feedback (not 30/70 AI-generated).

**Rationale**:
- Aligns with Samanvaya's evidence-driven philosophy
- Deterministic engines provide objective foundation
- Human input is optional calibration, not primary signal

**Impact**:
- Evaluation endpoint refactored
- LLM generates insights, not scores
- No manufactured human assessments

---

**Last Updated**: 2026-09-01  
**Architecture Version**: 2.0 (Engine-Based)  
**Status**: Production-ready
