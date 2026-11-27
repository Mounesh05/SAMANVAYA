# Algorithm Intelligence v2 — workspace and requirement review

This commit extends the isolated feature branch, not the completed Phase 2 release.

- Dedicated Analyses, Experiments, Requirements and History sections; only the selected section is mounted.
- Project selector and project/session scoped requirement and history queries.
- Concise expandable PR function summaries; no compulsory sorting preset or two-candidate default in the actual workspace.
- Existing finite contract/source proposal and independent approval APIs are reused. Review is per immutable fingerprint, with explicit rationale and scope confirmation. Self-approval and foreign project records are not offered. Backend remains authoritative.
- Expert manual proposal payloads remain available in a disclosure; automatic AI proposals, rejection/revocation and automatic continuation after approval have not been implemented here.
- Existing benchmark/contract storage, legacy numeric sorting protocol, and historical Code Quality evidence links are preserved. Manual experiment inputs still use the existing generic JSON schema; no unsupported validator or new authority was introduced.

Verification: source changes reviewed; focused UI regression tests added/updated, not executed in this connector-only session. Browser, accessibility, CI, actual approvals and runtime tests remain pending. No model, benchmark or mathematical correctness claim is made by this commit. Full Phase 2 implementation remains incomplete.
