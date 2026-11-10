# SAMANVAYA metrics vs reference tools

Files compared: **167** (skipped: 0).
Reference tools: radon 6.0.1, lizard 1.17.10, cognitive_complexity 1.3.0.

## Cyclomatic complexity (per function)

| Comparison | n | Exact match | Close match | Mean abs. error | Pearson r | Spearman ρ |
|---|---|---|---|---|---|---|
| Cyclomatic vs radon | 863 | 99.9% | 100.0% (±1) | 0.00 | 1.000 | 1.000 |
| Cyclomatic vs radon, after known rule differences | 863 | 100.0% | 100.0% (±1) | 0.00 | 1.000 | 1.000 |
| Cyclomatic vs lizard | 863 | 99.1% | 99.8% (±1) | 0.02 | 0.998 | 0.999 |
| Cyclomatic vs lizard, after known rule differences | 863 | 100.0% | 100.0% (±1) | 0.00 | 1.000 | 1.000 |

- Differences with radon: **1**, of which **1** are explained by known rule differences.
- Differences with lizard: **8**, of which **8** are explained by known rule differences.
- radon adds +1 for `assert`, `try … else` and loop `else`; SAMANVAYA, following McCabe, counts only branch points.
- lizard reads tokens, not syntax: it does not understand `match`, cannot see decisions inside f-strings (e.g. `f"{a if b else c}"`) and counts `finally`, which always runs and is not a branch.

## Cognitive complexity (per function)

| Comparison | n | Exact match | Close match | Mean abs. error | Pearson r | Spearman ρ |
|---|---|---|---|---|---|---|
| Cognitive vs cognitive_complexity | 855 | 82.1% | 89.7% (±1) | 0.61 | 0.959 | 0.958 |
| Cognitive vs cognitive_complexity, comparable functions | 698 | 100.0% | 100.0% (±1) | 0.00 | 1.000 | 1.000 |

- Differences: **153**, of which **153** are in functions using constructs the package scores differently from SonarSource's specification. Each was confirmed with a small test function:
  - comprehensions and `match`: ignored by the package
  - `async for`: ignored by the package (no +1, no nesting for its body)
  - `else:` followed by a nested `if`: scored like `elif` (2 instead of 4)
  - a structure nested in an `if`/`elif` branch that is followed by another `elif`: nesting penalty missed
  - nested functions and lambdas: no nesting penalty
- "Comparable functions" excludes those constructs: this is the like-for-like check of the shared rules.

## Maintainability index and Halstead volume (per file)

| Comparison | n | Exact match | Close match | Mean abs. error | Pearson r | Spearman ρ |
|---|---|---|---|---|---|---|
| Maintainability index vs radon (file) | 167 | 12.6% | 13.2% (±5) | 36.52 | 0.755 | 0.866 |
| MI formula check: our formula on radon's inputs | 167 | 38.9% | 100.0% (±5) | 0.11 | 1.000 | 1.000 |
| MI formula check, radon's comment constant (2.46) | 167 | 100.0% | 100.0% (±5) | 0.00 | 1.000 | 1.000 |
| Halstead volume vs radon (file) | 167 | 11.4% | 11.4% (±5) | 5133.09 | 0.845 | 0.842 |

- The MI values differ **by design**: radon uses logical lines (LLOC), operator-only Halstead counting and always adds the comment bonus (constant 2.46); SAMANVAYA uses NCLOC, token-based Halstead and no comment bonus by default.
- The **formula check** feeds radon's own inputs into SAMANVAYA's formula. With the published comment constant (2.4) the results are within ±5; with radon's constant (2.46) they are identical, so the formula is implemented correctly and every MI difference comes from the inputs (line counting, Halstead definition, comment bonus).
- Halstead volume uses different operator/operand definitions, so compare ranking (Spearman ρ), not values.
