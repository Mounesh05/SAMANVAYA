# Phase 5: automatic PR algorithm intelligence

The existing signed GitHub webhook route, WebhookEventProcessor and
GitHubSyncService now queue automatic algorithm analysis for open, synchronize and
reopen events. Manual PR synchronization uses the same continuation. Ordinary
security scanning, risk scoring, traceability and quality recommendations retain
their existing paths. Algorithm analysis is queued before optional AI analysis and
is independent of the high-risk recommendation gate.

## Prerequisites and authority

- The repository has exactly one saved GitHub-to-project configuration.
- The project is active and has an organization.
- GitHub webhook HMAC verification remains mandatory.
- Static discovery runs even without Ollama or Docker execution enabled.
- Automatic execution requires the existing administrator-controlled
  `ALGORITHM_BENCHMARK_ENABLED` flag, an approved applicable functional contract,
  available approved fixtures and supported validation/worker semantics.

The background service creates a server-owned automation identity from the
resolved project organization. PR bodies cannot grant permissions, approve
contracts or select arbitrary external validators. User-facing history and
comparison access reuse engineering role, project and organization checks.

## Approved function registration

Phase 3 contracts may now carry an independently reviewed `automatic_scope`:

```json
{
  "repository": "owner/repository",
  "path": "src/graph.py",
  "qualified_name": "explore"
}
```

It is part of the approved content fingerprint. Existing contracts without this
field remain valid for their previous manual workflows. An existing approved
Phase 3 function binding can also locate a contract when the bound source is a
server-recorded exact GitHub snapshot matching the actual base file hash, path,
lexical identity and language. A supplied Git revision label alone is insufficient.
Contract names, signatures, comments, inferred tasks and unapproved tests never
establish automatic applicability. Multiple applicable contracts are reported as
ambiguous; the service does not choose the newest one silently.

The contract and fixtures are registered and reviewed once for the intended
operation. Subsequent supported PRs do not require pasting code, supplying project
IDs or authoring benchmark JSON. When no approved binding exists, findings retain
static evidence and explain exactly what functional evidence is missing.

## Execution path

1. Save PR metadata with a stable PR ID and atomic revision checks. Exact current
   GitHub head/base checks protect commits sharing the same update timestamp.
2. Deduplicate webhook payloads and automatic jobs by project/repository/PR,
   immutable base/head revisions and analysis version.
3. Persist the job manifest in the existing `code_quality_runs` collection.
4. Retrieve bounded source at immutable base and head SHAs. Preserve both Phase 2
   snapshots and GitHub provenance in the same evidence store.
5. Identify changed function bodies by exact lexical identity and path, including
   explicit GitHub file-renaming metadata. New, ambiguous, nested or async functions
   remain static-only where the existing execution protocol cannot support them.
6. Resolve one approved functional contract, reuse its required fixtures, and
   capture fixture fingerprints, contract versions, observed input characteristics,
   validation method and source references.
7. Use Phase 3 BehavioralCompatibilityService and Phase 4 requirement preparation.
   PR text and exact task/story IDs contribute proposals only. Unresolved authority,
   applicability, conflicts and unavailable validators prevent automatic execution.
8. Use existing AlgorithmBenchmarkService leases, project duplicate-job prevention,
   bounded concurrency and Docker workers. Worker isolation, image pinning, network
   disabling, non-root user, read-only filesystem, CPU/memory/PID limits and timeouts
   are unchanged. Developer source never executes on the FastAPI host.
9. Validate both versions on identical approved inputs. Existing workers can collect
   measurements during validation, but incompatible or unverified pairs cannot
   qualify for replacement rankings. Phase 1 is the only decision engine.
10. Check the live GitHub revision before every comparison and before publishing.
    Preserve superseded records as history. Newer PR metadata cannot be overwritten
    by older analysis results, and stale recommendations are excluded from pending
    recommendation reads.

Recommendations use the existing recommendation collection and status lifecycle.
They contain deterministic finding status, evidence links, exact revision and
benchmark references. Numerical model confidence is null. There is no second AI
ranking system, code rewriting, PR merging, GitHub comment publication or RAG.
The existing explanation endpoint may ask Ollama to select deterministic evidence
facts; unsupported model output or an unavailable model leaves the fallback facts.

## Findings and interface

The Code Quality page leads with automatic PR summaries. Manual numeric sorting,
generic functions, contract validation and custom experiments remain available
under advanced workflows. PR rows offer algorithm findings using the existing PR
identity. Authorized project mappings determine scope without manual project IDs.

`GET /api/algorithms/pr-intelligence` accepts optional `pr_id` or `project_id`; with
neither, it returns recent analyses in accessible projects in the user's
organization. Historical revisions are labeled. Each function links to the existing
benchmark result endpoint for compatibility, requirements, constraints, measurements,
environment, deterministic workload comparisons and explanations.

Statuses include pending, analyzing, benchmarking, completed, insufficient evidence,
unsupported, failed and superseded. Finding statuses distinguish conditional
findings, correctness failure, constraint failure, insufficient evidence and verified
findings within tested workloads. Unknown latency/memory budgets and production
workloads remain explicit. No global or production-optimality claim is made.

## Bounds and operational limitations

This milestone retains the existing local asynchronous executor; it does not add a
distributed queue. Parent jobs have an eight-minute lease and a six-minute total
execution deadline. Interrupted/expired jobs fail explicitly without automatically
replaying developer code. Explicit later revisions create new jobs; duplicate
deliveries do not rerun a comparison. Candidate cancellation uses existing worker
cleanup and lease release.

Source fetching is limited to 100 changed files plus bounded available context.
Discovery retains its existing source/report limits. Automatic analysis reports at
most 64 changed function identities and executes at most four comparisons per PR.
Both analysis and benchmark concurrency remain bounded. Existing occupied project
slots produce an explicit insufficient-evidence outcome instead of bypassing them.
File/function truncation is shown in results. Dependencies must already be present
in worker images; repository dependencies are never installed automatically.
Service-owned deduplication fields use unique sparse indexes, allowing ordinary
function snapshots and legacy records without those fields in the same store.
Unchanged caller behavior, dynamic dispatch and unsupported cross-file imports
remain limitations rather than invented guarantees.

Production use still requires a reachable signed webhook endpoint, connected
repository configuration and suitably isolated Linux Docker host. Local tests do
not certify a separate production deployment or GitHub webhook delivery.

## Validation

Deterministic integration coverage lives in `tests/test_pr_algorithm_intelligence.py`
and `tests/test_pr_algorithm_workflow_api.py`; UI coverage is in
`frontend/src/tests/prAlgorithmIntelligence.test.jsx`. Opt-in Docker coverage in
`tests/test_pr_algorithm_docker.py` exercises BFS-to-DFS reachability and shortest
path failures for Python, JavaScript and TypeScript. All source execution occurs
inside the existing isolated workers. Run existing Phase 1–4, analyzer, authorization,
project-management and frontend regression suites alongside these tests.
`tests/test_pr_algorithm_mongo.py` provides an optional real MongoDB concurrency
check with `SAMANVAYA_MONGO_TESTS=1`. It creates and removes only its uniquely named
temporary collections in the test database.
