# Code Quality AI interpretation (Phase 1)

Every normal Code Quality report has a compulsory **advisory** AI interpretation. Static analysis measures; the AI only explains what was measured. It never sets or changes a score, a severity or a finding.

## When it runs

| Report | AI |
|---|---|
| Whole repository, selected files and directories | Required |
| Manual PR comparison (the parent run) | Required, once; the base and head child runs carry none |
| Automatic PR comparison (GitHub webhook) | Required, under the server-owned automation authority for the exact head revision |
| Function discovery only (`analysis_level: purpose_discovery`) | Not applicable. It is labelled `report_status: not_a_quality_report` |

**Legacy `use_ai=false`:** for a normal report it is normalised to `true`. The run records `use_ai: true`, `use_ai_requested: false` and `ai_required: true`, and the report page says so. No normal report is ever completed without an AI interpretation. Old runs keep their original fields and are shown as "legacy run, not recorded"; nothing is backfilled.

**Duplicate deliveries:** an automatic PR comparison is identified by organisation, project, repository, PR, base SHA, head SHA and policy version. A repeated delivery replays the stored report without calling the analyzers or the model again.

## Input (server-built only)

Implemented by `domain/services/quality_interpretation.py` (`build_request`):

- up to 20 findings, ordered by severity, path, line, rule and ID, each with its server-owned ID; `omitted_findings` counts the rest;
- files analysed, measured complexity, test coverage (null when not measured), dependency audit state, quality and risk score;
- for a PR parent, the comparison: base and head score, delta when comparable, and new/existing/resolved counts only when the revisions were measured alike.

Source text and tool messages are data, never instructions.

## Output contract `code-quality-advisory-v1`

`ai_analysis.advisory`, enforced server-side by `domain/services/quality_advisory.py`:

| Field | Limit | Rule |
|---|---|---|
| `summary` | 300 characters | The model's summary only when every number in it is measured, it claims nothing unmeasured, it does not inflate severity and it contains no injected instruction or credential-like text. Otherwise a server-written factual summary. |
| `suggestions` | 3 | Each bound to exactly one real finding by its `[file:line rule]` citation. `why` is the analyzer's own message (180). `action` is the model's advice (240). |
| `limitations` | 3 × 160 characters | Server-written from measured gaps: coverage not measured, dependencies not checked, comparison withheld, findings omitted. |

A suggestion is withheld when it:

- cites no finding, a foreign finding or a wrong location, or cites more than one finding;
- is a duplicate;
- suppresses checks (`# nosec`, `noqa`, `eslint-disable`, "disable the linter"), runs code (`curl | sh`, `rm -rf`, `eval(`), claims unmeasured facts ("tests pass", "100% coverage", "bug-free"), inflates severity, echoes injected instructions, contains credential-like text, or is unrelated to the cited finding.

There is no score or confidence field. A clean measured scope gives zero suggestions and says this is not proof the code is defect-free.

## Status

| Field | Values |
|---|---|
| `status` (job) | unchanged |
| `ai_status` | `completed`, `failed`, `unavailable`, `blocked` (no usable static evidence), `not_applicable` (discovery) |
| `report_status` | `complete` only with full static evidence and a validated AI interpretation; otherwise `partial`, or `failed` when there is no static evidence. `report_incomplete_reasons` says why. |

Expected environment gaps in the isolated worker do not by themselves make static evidence partial. These are: no live dependency advisories, no repository test run or coverage, TypeScript without a project configuration, and npm audit without a manifest. They are always shown as limitations. Any other skipped tool makes the report partial. For example, `complexity:unparsable-source` is recorded when a Python file cannot be parsed. A selection cut at the file limit is partial too (`scope_truncated`), and the page header says "Truncated (partial scope)".

## AI-only retry

`POST /api/code-quality/runs/{run_id}/ai-retry`:

- needs `TRIGGER_CODE_ANALYSIS`;
- re-checks the run's tenant (absent and foreign runs both return 404) and project access, then re-resolves the caller's AI authority;
- reuses the exact stored input and never re-runs static analysis;
- allows at most 3 attempts in total;
- an atomic claim stops concurrent retries, with a 15-minute lease so a crashed retry does not leave the report stuck;
- only the current claim may write the result.

The stored input (`ai_request`) is never returned by the API.

## Provenance

`ai_provenance` records the policy version, model name, latency and the `sha256` digest of the exact AI input. A retry records the same digest, because it uses the same evidence.
