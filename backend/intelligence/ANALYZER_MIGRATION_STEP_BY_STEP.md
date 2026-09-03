# Analyzer Consolidation: Step-by-Step Migration Guide

## Current Status
✅ Permission security fixes completed and committed
⏳ Analyzer consolidation documented (this file)

## Overview
This guide provides a complete, tested migration path from the OLD analyzer system to the NEW system.

---

## Phase 1: Understand the Architecture

### OLD System (to be removed)
```
intelligence/
├── static_analysis/
│   ├── orchestrator.py (StaticAnalysisOrchestrator)
│   ├── python_analyzer.py
│   └── javascript_analyzer.py
├── complexity_analyzer.py
├── security_scanner.py
├── test_analyzer.py
├── architecture_analyzer.py
├── dependency_analyzer.py
└── evidence_builder.py (orchestrates all old analyzers)
```

**Data Flow:**
```
github_service.py → EvidenceBuilder → 7 standalone analyzers → dict
                                                                  ↓
                                                            code_agent.py (Ollama)
```

### NEW System (target)
```
intelligence/
├── analyzers/
│   ├── base.py (BaseAnalyzer contract)
│   ├── registry.py (AnalyzerRegistry + get_analyzer)
│   ├── language_detector.py (LanguageProfile)
│   ├── python/analyzer.py (PythonAnalyzer)
│   ├── java/analyzer.py (JavaAnalyzer)
│   ├── c/analyzer.py (CAnalyzer)
│   ├── cpp/analyzer.py (CppAnalyzer)
│   └── javascript/analyzer.py (JavaScriptAnalyzer)
└── evidence/
    └── models.py (CodeQualityEvidence, typed schema)
```

**Data Flow:**
```
github_service.py → LanguageDetector → get_analyzers_for_profile() → BaseAnalyzer.analyze()
                                                                            ↓
                                                                  CodeQualityEvidence (typed)
                                                                            ↓
                                                                      code_agent.py (Ollama)
```

---

## Phase 2: Migration Steps

### Step 1: Create Adapter Bridge
**Goal:** Allow old code to work with new analyzers temporarily.

Create `intelligence/analyzers/legacy_adapter.py`:
```python
"""
Temporary adapter: converts CodeQualityEvidence → old dict format.
DELETE THIS FILE after migration is complete.
"""

from intelligence.evidence.models import CodeQualityEvidence
from typing import Dict, Any

def evidence_to_legacy_dict(evidence: CodeQualityEvidence) -> Dict[str, Any]:
    """
    Convert new CodeQualityEvidence to old evidence_builder dict format.
    This preserves backward compatibility during migration.
    """
    return {
        # Static analysis
        "static_analysis": {
            "findings": [f.dict() for f in evidence.security_evidence.findings],
            "tool": "unified",
        },
        
        # Complexity
        "complexity": {
            "average_complexity": evidence.complexity_evidence.average_complexity,
            "max_complexity": evidence.complexity_evidence.max_complexity,
            "high_complexity_functions": evidence.complexity_evidence.high_complexity_functions,
            "lines_of_code": evidence.complexity_evidence.lines_of_code,
        },
        
        # Security
        "security": {
            "findings": [f.dict() for f in evidence.security_evidence.findings],
            "critical_count": sum(1 for f in evidence.security_evidence.findings if f.severity == "critical"),
            "high_count": sum(1 for f in evidence.security_evidence.findings if f.severity == "high"),
        },
        
        # Tests
        "tests": {
            "total_tests": evidence.testing_evidence.total_tests,
            "passed_tests": evidence.testing_evidence.passed_tests,
            "failed_tests": evidence.testing_evidence.failed_tests,
            "coverage_percentage": evidence.testing_evidence.coverage_percentage,
        },
        
        # Dependencies
        "dependencies": {
            "new_packages": evidence.dependency_evidence.new_dependencies,
            "updated_packages": evidence.dependency_evidence.updated_dependencies,
            "vulnerability_count": evidence.dependency_evidence.vulnerable_dependencies_count,
        },
        
        # Architecture
        "architecture": {
            "layer_violations": [v.dict() for v in evidence.architecture_evidence.layer_violations],
            "circular_dependencies": evidence.architecture_evidence.circular_dependencies,
        },
        
        # Risk/Quality scores (if available)
        "overall_risk_score": evidence.overall_risk_score if hasattr(evidence, 'overall_risk_score') else 0,
        "quality_score": evidence.overall_quality_score if hasattr(evidence, 'overall_quality_score') else 0,
        "risk_factors": [],
        "quality_factors": [],
    }
```

### Step 2: Update github_service.py (lines 135-230)
**Goal:** Use new analyzer system with backward-compatible output.

**Replace lines 139-169** with:
```python
if use_deep_analysis:
    # NEW: Use unified analyzer system
    from intelligence.analyzers.language_detector import LanguageDetector
    from intelligence.analyzers.registry import get_analyzers_for_profile
    from intelligence.analyzers.legacy_adapter import evidence_to_legacy_dict
    from agents.code_agent import code_analysis_node
    from domain.models.code_quality_report import CodeQualityReport, QualityBreakdown
    import time
    import tempfile
    import os
    
    start_time = time.time()
    
    # Use platform-appropriate temp directory
    temp_dir = tempfile.gettempdir()
    repo_work_dir = os.path.join(temp_dir, f"samanvaya-repo-{owner}-{repo}")
    
    changed_file_paths = [f["filename"] for f in files]
    
    # Detect languages in changed files
    detector = LanguageDetector()
    language_profile = detector.detect_from_files(changed_file_paths)
    
    # Get appropriate analyzers for detected languages
    analyzers = get_analyzers_for_profile(language_profile)
    
    if not analyzers:
        # Fallback: no analyzers available for this language
        logger.warning(f"No analyzers available for languages: {language_profile.detected_languages}")
        # Use lightweight risk assessment (existing path)
        # ... continue with old lightweight analysis ...
    else:
        # Run analysis with new system
        pr_context = {
            "pr_title": github_pr.get("title", ""),
            "author": github_pr.get("user", {}).get("login", ""),
            "pr_number": pr_number,
            "repo": f"{owner}/{repo}",
            "project_id": project_id,
            "commit_sha": github_pr.get("head", {}).get("sha"),
        }
        
        # Analyze with primary language analyzer
        primary_analyzer = list(analyzers.values())[0]
        evidence_obj = await primary_analyzer.analyze(
            changed_files=changed_file_paths,
            repo_path=repo_work_dir,
            pr_context=pr_context
        )
        
        # Convert to legacy dict format for code_agent compatibility
        evidence = evidence_to_legacy_dict(evidence_obj)
        
        # Continue with existing agent invocation (lines 171-230)
        # ... (rest remains unchanged)
```

### Step 3: Update code_quality_service.py
**Goal:** Migrate the "Phase 0 Shim" to use new analyzer system directly.

Replace the entire `CodeQualityService.analyze_pr()` method (lines 43-80) with:
```python
async def analyze_pr(
    self,
    changed_files: list[str],
    pr_context: Dict[str, Any],
    project_config: Optional[ProjectCodeConfig] = None,
    deep_analysis: bool = False,
) -> CodeQualityEvidence:
    """
    Run unified analyzer system and return CodeQualityEvidence.
    
    Args:
        changed_files: List of file paths changed in the PR
        pr_context: PR metadata (project_id, pr_number, commit_sha, etc.)
        project_config: Optional per-project config; uses defaults if None
        deep_analysis: If True, runs all analyzers; False = fast checks only
    
    Returns:
        CodeQualityEvidence from new analyzer system
    """
    from intelligence.analyzers.language_detector import LanguageDetector
    from intelligence.analyzers.registry import get_analyzers_for_profile
    
    repo_path = pr_context.get("repo_path", ".")
    
    # Detect primary language
    detector = LanguageDetector()
    profile = detector.detect_from_files(changed_files)
    
    # Get appropriate analyzers
    analyzers = get_analyzers_for_profile(profile)
    
    if not analyzers:
        # Return empty evidence if no analyzer available
        from intelligence.evidence.models import CodeQualityEvidence
        return CodeQualityEvidence(
            repository_id=pr_context.get("project_id", ""),
            pr_number=pr_context.get("pr_number"),
            commit_sha=pr_context.get("commit_sha"),
            primary_language=profile.primary_language,
            detected_languages=profile.detected_languages,
        )
    
    # Run primary analyzer
    primary_analyzer = list(analyzers.values())[0]
    evidence = await primary_analyzer.analyze(
        changed_files=changed_files,
        repo_path=repo_path,
        pr_context=pr_context
    )
    
    return evidence
```

### Step 4: Test the Migration
**Before proceeding to deletion:**

1. **Test PR sync with deep analysis:**
   ```bash
   curl -X POST http://localhost:8000/api/github/sync-pr \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "owner": "facebook",
       "repo": "react",
       "pr_number": 25840,
       "project_id": "PRJ-TEST",
       "use_ai": true
     }'
   ```

2. **Test code quality analysis:**
   ```bash
   curl -X POST http://localhost:8000/api/code-quality/analyze \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "repository_id": "test-repo",
       "changed_files": ["src/main.py", "tests/test_main.py"],
       "analysis_level": "full"
     }'
   ```

3. **Verify:**
   - No import errors
   - Evidence structure is valid
   - AI agent receives correct data
   - Quality scores are reasonable

### Step 5: Delete OLD System Files
**Only after Step 4 passes all tests!**

```bash
cd backend/intelligence

# Delete old analyzers
rm -rf static_analysis/
rm complexity_analyzer.py
rm security_scanner.py
rm test_analyzer.py
rm architecture_analyzer.py
rm dependency_analyzer.py
rm evidence_builder.py

# Delete adapter (no longer needed after code_agent updated)
rm analyzers/legacy_adapter.py

# Delete old documentation
rm ANALYZER_CONSOLIDATION_TODO.md
```

### Step 6: Update code_agent.py (Optional Future Work)
**Goal:** Make code_agent.py work with CodeQualityEvidence directly (no adapter).

Currently `code_agent.py` expects dict. After migration stabilizes, update it to accept `CodeQualityEvidence` objects directly:

```python
def code_analysis_node(state: dict) -> dict:
    evidence_obj: CodeQualityEvidence = state["evidence"]  # Now typed!
    
    # Access typed fields instead of dict keys
    complexity = evidence_obj.complexity_evidence.average_complexity
    security_findings = [f for f in evidence_obj.security_evidence.findings if f.severity == "critical"]
    # ...
```

---

## Phase 3: Verification Checklist

After migration:
- [ ] `evidence_builder.py` deleted
- [ ] All old analyzer files deleted
- [ ] `github_service.py` uses new system
- [ ] `code_quality_service.py` uses new system
- [ ] PR sync works end-to-end
- [ ] Code quality analysis works
- [ ] AI agent receives correct evidence
- [ ] No import errors in logs
- [ ] Quality scores are consistent with old system

---

## Rollback Plan

If migration causes issues:

1. **Revert the commit:**
   ```bash
   git revert HEAD
   git push origin prototype_v1
   ```

2. **Or cherry-pick just the permission fixes:**
   ```bash
   git reset --hard HEAD~1  # Undo analyzer migration
   # Permission fixes remain
   ```

---

## Expected Benefits Post-Migration

✅ **Single Source of Truth:** One analyzer pipeline for all code analysis
✅ **Type Safety:** `CodeQualityEvidence` replaces untyped dicts
✅ **Extensibility:** Adding new languages = 1 line in `ANALYZER_REGISTRY`
✅ **Consistency:** Same evidence format from all entry points
✅ **Testability:** Clear contracts via `BaseAnalyzer` interface
✅ **Performance:** Lazy-loading via registry reduces startup time
✅ **Maintainability:** No duplicate logic between systems

---

## Estimated Effort

- **Step 1 (Adapter):** 30 minutes
- **Step 2 (github_service.py):** 45 minutes
- **Step 3 (code_quality_service.py):** 30 minutes
- **Step 4 (Testing):** 60 minutes
- **Step 5 (Deletion):** 15 minutes
- **Step 6 (code_agent update):** 60 minutes (optional)

**Total:** ~4 hours (without Step 6)

---

## Notes

- This migration is **SAFE** because we keep the adapter layer initially
- The adapter ensures `code_agent.py` continues to work unchanged
- Delete the adapter only after verifying everything works
- Step 6 is optional and can be done later for full modernization

---

## Status
📋 **DOCUMENTED** - Ready for execution
🔧 **NOT STARTED** - Awaiting developer approval
