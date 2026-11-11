# Phase 2: static algorithm-purpose discovery

Discovery extends the existing analyzer registry, `CodeQualityService`, unified
`CodeQualityEvidence`, code-quality runs, GitHub sync and analysis-run UI.
The existing manual benchmark interface and worker protocol are unchanged.

## Automatic collection and viewing

- Code-quality analysis automatically extracts functions from the available
  repository snapshot. A server-supplied `repo_path` uses local source; otherwise
  a connected project's GitHub configuration resolves the PR head or configured
  default branch to a commit SHA and fetches source through the existing client.
- PR synchronization collects a static discovery snapshot even with `use_ai=false`
  or unavailable Ollama. Changed files, available tests and caller context are
  fetched at the same head SHA, never reconstructed from diff hunks.
- Snapshots use `code_quality_runs`, with `analysis_level=purpose_discovery` for
  discovery-only sync runs. Such runs do not claim quality/risk measurements.
- Authorized users can read `GET /api/code-quality/runs/{run_id}/functions` with
  `limit` (1–256, default 50) and `skip`. Authorization matches reading the run.
  Legacy runs explicitly return `not_analyzed`.
- In Code Quality, enter the existing project ID in the analysis-history field,
  open a run, and inspect **Discovered functions**. This is read-only.

## Parsing setup

Python uses the existing AST discovery/structure helpers. JavaScript, JSX,
TypeScript and TSX use the TypeScript compiler API, sharing the benchmark
worker's existing pinned dependency and structure observer. This is a host-side,
source-only parser process, independent of benchmark opt-in and Docker.

Install the parser from the repository root:

```powershell
npm ci --prefix backend/benchmark_worker --ignore-scripts --no-audit --no-fund
```

Node must be on the backend host's PATH for JS/TS static discovery. Candidate
code is never required/imported, evaluated or executed; TypeScript is parsed,
not type-checked or transpiled for execution. No developer configuration,
compiler plugin, test module, decorator or default expression is executed.
Without Node/the parser, JS/TS source is marked unavailable and Python continues.
Benchmark worker images still contain their own runtime dependencies.

## Evidence model and interpretation

Method `function-purpose-v1` records repository/path, qualified identity and source
range, source SHA-256 and supplied revision, parameters/type annotations, return
observations, async behavior, syntactic structure and lexical calls/callers.
`OBSERVED` refers to syntax, not a guarantee about runtime binding or behavior.

Pattern rules are registered through `PatternRule` / `register_rule`; extractor
dispatch lives in `FUNCTION_EXTRACTOR_REGISTRY`. Unrecognized functions retain
their structural metadata. Rules never select algorithms by function names,
comments or a fixed list of candidate algorithm identities.

Linked FIFO/LIFO removal, append operations and adjacency iteration can support
BFS/DFS-like patterns. Tracked returned membership collections can suggest
reachability. Those observations never establish shortest paths. Heap operations,
sorting, filtering, searching, accumulation and memoized-recursion indicators
are additional structural rules, not an exhaustive taxonomy of algorithms.

Each inferred pattern/task includes evidence IDs, supported conclusions, missing
information, method and source revision. Multiple plausible tasks produce
`AMBIGUOUS`; unsupported purposes produce `UNKNOWN`. There are no numeric purpose
confidence scores. Type annotations, names and lexical calls remain contextual.
Call targets are lexical candidates only; parameters, ambiguous definitions,
dynamic dispatch and unhandled import/alias resolution remain unresolved.

Directly linked static assert/expect expressions are recorded as test expectations
with their own paths, hashes and evidence IDs. Tests are not run, passing status
is not invented and test authority is not inferred. There is currently no trusted
function-contract binding in the repository analysis path, so `verified_contract`
stays null; no result is promoted to `VERIFIED_BY_CONTRACT`. The status vocabulary
reserves that distinction for actual authoritative evidence, not pattern matching.

Ollama is optional and is not invoked for purpose inference in this phase. Existing
AI analysis remains separate. Generated text cannot overwrite deterministic
discovery evidence, establish requirements or guarantee correctness. No training,
RAG, equivalence determination or automatic benchmark orchestration is added.

## Bounds and limitations

At most 100 supported files, 200 KB per source, 2 MB combined source, 128 functions
per file and 256 per snapshot are retained. Node ASTs are limited to 50,000 nodes,
128 MB heap and ten seconds per file; Python uses the existing 50,000-node AST
bound. Each function retains at most 128 observations, 64 calls, 32 parameters and
16 returns. Stored discovery JSON is capped at 4 MB, below the MongoDB document
limit. Truncation, unavailable files, parse errors and missing context are explicit.
Repository traversal prunes dependencies/build output and rejects outside-root
paths/symlinks. Remote snapshots do not follow Git symlinks.

Malformed files produce diagnostics rather than purpose claims; valid files in
the same snapshot continue. Local/supplied revision labels are not independently
verified against Git; hashes identify the actual bytes parsed. GitHub source reads
are pinned to the resolved head SHA. This is a bounded, conservative static
analysis framework, not a general proof of what arbitrary programs do.

## Focused verification

```powershell
cd backend
.venv/Scripts/python.exe -m pytest -q tests/test_function_discovery.py tests/test_function_discovery_integration.py
```

Frontend coverage is in `frontend/src/tests/functionDiscovery.test.jsx`. Existing
analyzer, quality-engine and manual benchmark suites are regression gates.
