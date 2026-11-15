# F01/F02 security and evidence provenance verification

13 November 2026. Status ready for review.

## Baseline and branch

Read the Phase 0 audit and the complete F03–F06 stabilization verification
report before implementation. The checkout initially contained the reviewed
F03–F06 changes on `fix/ai-provider-legacy-contracts` as uncommitted work over
`771b41cc037ed24e2b9b763021149c49f14a2267`.

Saved only that reviewed 13-file set as
`56264de7614c1bff83b3f9823707ba371314714d`, then created
`codex/ai-run-security-evidence` from it. The F01/F02 changes in this report are
uncommitted for review. Pre-existing untracked audit deliverables and unrelated
workspace files were preserved.

## Confirmed gaps and implementation

The original route authorized stored client context, allowed unscoped runs
across users, granted PM a tenant bypass and filtered lists after pagination.
The initial new regression run reproduced **67 failures and 3 passes**.

### F01 access boundary

New generic and uploaded-log runs receive server-generated `ai-run-access-v1`
metadata with authenticated employee ownership, project and organization.
Unscoped runs belong exclusively to their authenticated creator, including when
the reader has CEO or administrator privileges. Private assistance can continue
when an account has no organization metadata.

Scoped access resolves current project records and current membership. PM
access requires the same organization. Assigned-project and team membership
require the same organization. CEO retains the existing global access role for
properly scoped project runs. Administrator status alone grants no tenant
bypass. A run's stamped organization must still match the current project.

Both HTTP reads use an authorization predicate inside MongoDB queries.
Repository counts and pagination operate on that predicate, combined with the
existing protected-artifact exclusion. Unknown and unauthorized run identities
return 404. Current-account permission failures return 403.

Historical records without the version and authenticated owner are withheld.
Scoped records also require provable tenant metadata and a current project.
Legacy email addresses and nested client context cannot supply missing
ownership. Integration adapters still writing the legacy format produce runs
withheld by these generic HTTP read endpoints. Restoring those records requires
verified provenance rather than guessed ownership.

HR receives an allowlist of lifecycle identifiers and timestamps. Input payloads,
context, model analysis/recommendations, provenance, model names, error messages
and trigger email are withheld. Generic model prose has no independent HR-safe
approval, so authorized HR reads contain empty input/output dictionaries and
redacted sensitive metadata. This applies to HR administrators too.

The existing authentication dependency already reloads current account authority
and checks token revocation. The routes use that principal. Real signed-token
tests verify removed team/project access, role permission removal, account
deactivation, deleted accounts and logged-out tokens.

Source references include [access resolution](../../backend/domain/services/ai_run_access.py#L24),
[read predicate](../../backend/domain/services/ai_run_access.py#L47),
[HTTP list/read](../../backend/api/routes/ai.py#L156),
[HR allowlist](../../backend/api/routes/ai.py#L193) and
[log ownership](../../backend/api/routes/cicd_logs.py#L177).

### F02 evidence provenance

Client evidence and context are stored under `input_data.caller_supplied`.
Server-generated `ai-evidence-v1` provenance labels that package `UNVERIFIED`,
with a canonical SHA-256 digest. Caller strings such as `SERVER_VERIFIED`,
`VERIFIED_BY_CONTRACT`, `APPROVED` and nested trust flags remain inert caller
data. They cannot populate ownership or server-source provenance. Model
interpretations are explicitly `ADVISORY` in the provenance envelope.

Uploaded logs retain their original request as unverified caller input.
Deterministic observations derived from those logs remain separately identified
as derived observations. Parsing an uploaded log confers no source authority.

The additive `evidence_sources_v1` field supports GitHub file references for
scoped `code_review` assistance. The server resolves the existing connected
repository from project configuration. It requires one project binding and one
case-insensitive repository binding, rejects conflicting tenant labels and
checks the exact full commit SHA, regular-file tree entry, file path, byte size,
Git blob SHA-1 and requested SHA-256. Missing, malformed, ambiguous, mismatched,
symlink and truncated-tree evidence fails before model invocation or persistence.
Provider/network failure produces a sanitized unavailable response.

Successful source provenance records project, organization, repository, path,
commit, both hashes and verification scope `GITHUB_BLOB_AT_COMMIT`. Verification
covers exact file identity and bytes. Computational correctness, approved
functional requirements and performance conclusions remain advisory.

File content and caller claims are explicitly separated in the Code prompt.
Other legacy tasks retain their existing input interpretation and receive an
unverified caller package in persisted provenance. HR cannot resolve technical
file references, including with administrator privileges.

Source references include [versioned references](../../backend/domain/models/ai_evidence.py#L8),
[repository binding](../../backend/domain/services/ai_evidence_service.py#L23),
[source integrity checks](../../backend/domain/services/ai_evidence_service.py#L45) and
[provenance preparation](../../backend/domain/services/ai_evidence_service.py#L79).

## Changed files

| File | Purpose |
|---|---|
| `backend/api/routes/ai.py` | Authorize invocation/read/list, versioned optional evidence references, provenance storage and HR allowlist |
| `backend/api/routes/cicd_logs.py` | Preserve creator access to new private log runs and label uploaded inputs as unverified |
| `backend/domain/models/ai_run.py` | Add optional versioned ownership, scope and provenance fields while parsing historical records |
| `backend/domain/models/ai_evidence.py` | Strict exact-revision file-reference v1 schema |
| `backend/domain/services/ai_run_access.py` | AI-specific current-account, project and tenant boundary |
| `backend/domain/services/ai_evidence_service.py` | Read-only source resolution, byte/hash verification and caller/source separation |
| `backend/repositories/ai_run_repository.py` | Persist metadata and accept a scoped detail-read predicate |
| `backend/tests/test_ai_run_security.py` | 85 new security and provenance regression cases |
| `backend/tests/test_agent_stabilization_api.py` | Replace the legacy project-access mock with a real project fixture |
| `backend/tests/test_ai_authorization.py` | Assert HR disclosure prevention and remove the obsolete project-list mock |
| This report | Results, compatibility effects and review handoff |

## Executed checks

Python checks used the existing Python 3.12 environment. The broad backend runs
used the existing baseline runner, including its audit-log isolation and short
Windows test IDs. Mongo opt-in was enabled, and Docker opt-in was disabled.

| Check | Observed result |
|---|---|
| Initial F01/F02 reproduction | 67 failed, 3 passed |
| Focused security, specialist, transport and existing authorization tests before the final log test | **289 passed**, 94 warnings, 19.65 s |
| Final security module, including private log ownership | **85 passed**, 24 warnings, 4.14 s |
| Final complete backend suite | **2,996 passed, 111 skipped**, 170 warnings, 77.62 s |
| Existing native Mongo checks | Passed within the complete backend run, including lifecycle arbitration, PR job deduplication and two process-recovery cases |
| Frontend initial default run alongside broad checks | 170 passed, 2 failed in `TestsPage.test.jsx`, including a 10-second timeout and an execution-call assertion timeout |
| Frontend documented two-worker retry with 30-second test timeout | **172 passed**, 23 files, 24.73 s |
| Frontend final default-settings retry after broad backend verification | **172 passed**, 23 files, 12.20 s |
| Frontend build | Passed, exit 0 |
| Frontend lint | Exit 0, 10 existing warnings |
| Ruff on changed runtime, new security tests and updated stabilization API tests | Passed |
| Whole backend default Ruff | 160 existing findings |
| Whole backend Ruff F821/E9 | Passed |
| Scoped Mypy on new reference/access/evidence components | Passed for 3 source files |
| Whole backend Mypy | 2 existing blocking errors, preventing further checking |
| Editor diagnostics on changed runtime and new security tests | No errors reported |
| `pip check` | No broken requirements found |
| `git diff --check` | Passed |

Focused and complete-suite counts overlap. The final complete backend run
included Hypothesis and the previously blocked test module successfully, with
no module exclusion or plugin disablement. Its prior Windows load failure was
unobserved in this execution. Dependencies and machine security settings were
preserved during this work.

The 111 skipped cases remain unverified. Live GitHub source retrieval, live
Ollama generation and live Docker worker execution were unverified here.
GitHub methods were replaced with deterministic transport-boundary responses
while the actual scope resolver, tree/blob/hash checks, API and repository ran.
The existing transport tests separately use loopback HTTP.

Both frontend retries passed with the existing source and configuration. The
initial timing failures remain recorded as intermittent test behavior.

Whole-backend Ruff retains the audited counts of 84 F401, 27 F811, 24 F841,
19 E402, 2 E712, 2 F541, 1 E731 and 1 E741. The touched legacy authorization test
retains three pre-existing lint findings. Mypy still stops on the missing
`domain.models.qa_ci_config` module and duplicate module identity for
`services/transfer_service.py`. Existing Pydantic and naive-UTC warnings persist.

## Compatibility effects and limits

The successful invocation response retains its nine existing keys and the six
specialist identifiers. Existing errors-in-body behavior, model-health 503,
permission 403, input validation and optional save behavior remain covered by
the stabilization tests. New source failures use 409 for integrity/applicability
conflicts and 503 for unavailable source retrieval.

Run reads add optional top-level access/provenance fields. New persisted inputs
use `caller_supplied`, `server_sources` and optional `derived_observations`.
Consumers of raw persisted input dictionaries must use those versioned
semantics. Caller content has no authoritative status through those dictionaries.

Listing remains a JSON array and now accepts `skip`. Limits must be between
1 and 500, and skip must be nonnegative. Default limit remains 50.
Private runs from another employee and unprovable legacy records now return
404. HR receives metadata only, including for previously visible model prose.

The chosen source adapter supports up to four UTF-8 regular files of 32 KiB
each, safe ASCII repository paths and full lowercase 40-character Git commit
SHAs. A 30-second overall source retrieval deadline bounds the adapter.
The server uses the existing configured GitHub credential and trusted
project/repository connection records. Other source types and independent
functional validators require separate explicit support. These are engineering
bounds and source scope, with no scoring-policy significance.

AI-specific authorization closes the audited bypass here. The shared legacy
project helper used elsewhere still contains its documented single-organization
PM behavior. This implementation does not establish application-wide tenant
isolation or audit the provisioning authority of every existing integration.
Repository connection records must be managed through trusted provisioning.

F07 internal adapter permission/error propagation and false-complete persistence
remain open. The uploaded-log change stamps ownership and provenance while
preserving that deferred status behavior. F08 engine/legacy breakdown unit
translation remains open. Generic reads continue to exclude all signed
performance artifact types, and their dedicated protected APIs retain authority.

## Review handoff

F01/F02 are implemented and tested within the generic AI-run and private-log
surfaces described above. Review the conservative historical visibility policy,
HR metadata-only disclosure, server repository mapping trust, versioned input
storage and narrow GitHub source support before acceptance. The remaining
F07/F08 work requires its own review scope.

## Reproduction

From `backend`, use the configured Python environment.

```powershell
.venv/Scripts/python.exe -m pytest tests/test_ai_run_security.py tests/test_agent_stabilization.py tests/test_agent_provider_transport.py tests/test_agent_stabilization_api.py tests/test_ai_authorization.py -q --tb=short -p no:cacheprovider
$env:SAMANVAYA_MONGO_TESTS='1'
Remove-Item Env:SAMANVAYA_DOCKER_BENCHMARK_TESTS -ErrorAction SilentlyContinue
Remove-Item Env:PYTEST_ADDOPTS -ErrorAction SilentlyContinue
.venv/Scripts/python.exe tests/audits/run_scoring_baseline.py
```

From `frontend`, run the existing checks. The second test command reproduces
the documented lower-concurrency retry.

```powershell
npm run test -- --run
npm run test -- --run --maxWorkers=2 --testTimeout=30000
npm run build
npm run lint
```
