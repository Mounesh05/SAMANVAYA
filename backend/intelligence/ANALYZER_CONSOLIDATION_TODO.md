# Analyzer Architecture Consolidation

## Problem
Two parallel analyzer systems exist with duplicate functionality and different schemas:

### OLD System (Dict-based, monolithic)
- `intelligence/static_analysis/` folder
  - `orchestrator.py` - Routes to language-specific analyzers
  - `python_analyzer.py` - Python static analysis
  - `javascript_analyzer.py` - JavaScript static analysis
- Standalone analyzers:
  - `complexity_analyzer.py`
  - `security_scanner.py`
  - `test_analyzer.py`
  - `architecture_analyzer.py`
  - `dependency_analyzer.py`
- `evidence_builder.py` - Orchestrates all OLD analyzers

**Used by:**
- `domain/services/github_service.py` (PR sync deep analysis)
- `domain/services/code_quality_service.py` (marked "Phase 0 Shim")
- `api/routes/code_quality.py` (one endpoint)

### NEW System (Typed, plugin-based, clean architecture)
- `intelligence/analyzers/base.py` - `BaseAnalyzer` abstract contract
- `intelligence/analyzers/registry.py` - `AnalyzerRegistry` plugin system
- Language adapters:
  - `analyzers/python/analyzer.py` - `PythonAnalyzer`
  - `analyzers/java/analyzer.py` - `JavaAnalyzer`
  - `analyzers/c/analyzer.py` - `CAnalyzer`
  - `analyzers/cpp/analyzer.py` - `CppAnalyzer`
  - `analyzers/javascript/analyzer.py` - `JavaScriptAnalyzer`
- `intelligence/evidence/models.py` - Typed `CodeQualityEvidence` schema
- `intelligence/analyzers/language_detector.py` - Language detection

**Used by:**
- `api/routes/code_quality.py` (main analysis endpoints)

## Impact
- **Maintenance burden**: Changes must be made in two places
- **Schema drift**: Different scoring formulas, different evidence structures
- **Answer inconsistency**: Same code analyzed twice may produce different results
- **Code duplication**: Similar logic in both systems

## Solution

### Phase 1: Migrate github_service.py
**File:** `domain/services/github_service.py`

Replace lines 139-180 (EvidenceBuilder usage) with:
```python
from intelligence.analyzers.language_detector import LanguageDetector
from intelligence.analyzers.registry import get_analyzers_for_profile
from intelligence.evidence.models import CodeQualityEvidence

# Detect languages
detector = LanguageDetector()
language_profile = detector.detect_languages(changed_file_paths)

# Get appropriate analyzers
analyzers = get_analyzers_for_profile(language_profile)

# Run analysis
evidence_results = {}
for lang, analyzer in analyzers.items():
    evidence_results[lang] = await analyzer.analyze(
        files=[f for f in changed_file_paths if f.endswith(tuple(analyzer.supported_extensions))],
        context=pr_context
    )

# Combine into single CodeQualityEvidence
combined_evidence = CodeQualityEvidence.combine(evidence_results.values())
```

### Phase 2: Delete code_quality_service.py
This file is explicitly marked as "Phase 0 Shim" and should be deleted.

**Update imports in:**
- Check if any other files import from `code_quality_service.py`
- Redirect to direct `AnalyzerRegistry` usage

### Phase 3: Delete OLD system files
```bash
# Delete OLD analyzer system
rm -rf backend/intelligence/static_analysis/
rm backend/intelligence/complexity_analyzer.py
rm backend/intelligence/security_scanner.py
rm backend/intelligence/test_analyzer.py
rm backend/intelligence/architecture_analyzer.py
rm backend/intelligence/dependency_analyzer.py
rm backend/intelligence/evidence_builder.py
```

### Phase 4: Update imports
Search and replace:
```bash
# Find any remaining imports
grep -r "from intelligence.evidence_builder import" backend/
grep -r "from intelligence.static_analysis" backend/
grep -r "EvidenceBuilder" backend/
```

### Phase 5: Test
- Test PR sync with deep analysis
- Test code quality analysis endpoints
- Verify evidence schemas are consistent
- Run integration tests

## Risks
- **github_service.py** is the main PR analysis flow - breaking it would be critical
- Evidence format must remain compatible with `code_agent.py` Ollama prompts
- May need to update `CodeQualityReport` schema if evidence structure changes

## Recommendation
This consolidation should be done carefully with full testing. For now, the OLD system remains operational with a deprecation warning in `evidence_builder.py`.
