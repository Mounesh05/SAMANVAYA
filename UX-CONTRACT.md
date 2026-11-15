# Scoring integration UI contract

Scope: Phase 6 performance/history and assigned-observation workflows. Existing
unrelated application routes are outside this migration; no full UI rewrite.

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Select/Listbox | frontend/src/components/common/Select.jsx | Native platform popup; DESIGN.md | Employee and assignment selection | Keyboard/component/browser tests |
| Form | frontend/src/components/common/Input.jsx and Textarea.jsx | Frozen API schemas | Appeal and unscored observation | Validation, stale revision, duplicate tests |
| Scrollbar | frontend/src/index.css | Existing global CSS baseline | Natural page and table overflow | Narrow viewport/browser check |
| Toast | frontend/src/components/common/Toast.jsx | Existing provider | Supplemental feedback | Existing tests; inline status is primary |
| CRUD | frontend/src/api/performance.api.js | Scoped server lifecycle APIs | Append, never overwrite | Service/API/component tests |

All new query keys include actor identity. Authentication/authorization failure
must never be described as an Ollama outage. Loading, empty, failed and retry
states are explicit. Request failure retains entered notes; revision conflicts
do not retry with a newer digest automatically. Drafts are memory-only, scoped
to the current account and assignment, and cleared on sign-out/account change.

Legacy numbers are explicitly historical/unverified; provisional is not approved.
No missing score, confidence, dimension or grade receives a fabricated fallback.
Retired numerical feedback/evaluation controls are removed. CEO has no routine
numeric submission action. Only server-returned eligible assignments can be
used for observation intake; there is no employee-ID substitution field.

New observations remain unscored while rating anchors and source validation are
pending. Reasons are required for N/O, N/A and under-review states. No default
rating of three/four or assumed percentage appears in a form. Earlier numerical
observations can be read but require an explicit correction to an unscored state
before editing through this pending-policy interface.

No numerical release activation occurs from the UI. Readiness lists missing
calibration evidence and sign-off; software tests are not organizational approval.
