# Phase 1 baseline (actual, 2026-11-28)

| Item | Value |
|---|---|
| Spec baseline | `testing` at `4dbbd17a78e6d91bdc92920f71e5461a37df7b61` |
| PR base | `feature/algorithm-intelligence-v2` at `8b5601885a69efc0109ca2dbee3a57b89daaef2e` (Mounesh, "large diff"), merged into this branch with a merge commit; his history is unchanged |
| Branch | `fix/algorithm-v2-tests` (PR Mounesh05/SAMANVAYA#5); 0 commits behind `testing` |
| Code commit verified | `aebcac6` (reports added on top) |
| Worker image | `samanvaya-quality:3`, rebuilt from `backend/quality_worker/Dockerfile` at `aebcac6`: `sha256:af82a219f1d4e063fca831466b154ecc67b9532c21d85cb06e755ea49b9c49b2` |
| Worker tools | ruff, bandit, mypy, radon, lizard, eslint; tsc when a tsconfig exists; offline dependency advisories |
| API image (live runs) | `samanvaya-backend:algo-v2-e2e` `sha256:6b29c771…` built at `9af65a9`. The AI and report path is unchanged since then, except the new `scope_truncated` reason |
| Model | Ollama `llama3.2:3b` (local), reached through a disposable relay bound to the test network gateway |
| Languages | Runtime-verified: Python, JavaScript, TypeScript. Experimental (adapters kept, not claimed): C, C++, Java |

## Isolation

- Database: disposable `samanvaya_intel_e2e` on container `samanvaya-intel-mongo`. The real `samanvaya` database, the `samanvaya-api` container and `.env` were never touched.
- Disposable containers: `algo-e2e-api` (8041, model), `algo-e2e-api-noai` (8042, model down), `algo-e2e-broker`, `algo-e2e-ollama-relay`. They are kept for review and removed on approval.
- Accounts: disposable test users in `E2E-ORG-A` using the existing roles QA, PM and HR. No real employee records or passwords were used.
- Worker flags: `--pull=never --network=none --cap-drop=ALL --security-opt=no-new-privileges:true --user=65532:65532 --read-only --tmpfs=/tmp:rw,noexec,nosuid,nodev,size=128m --memory=768m --cpus=1 --pids-limit=64 --init`.

## What was known before this work (from the spec's source inspection)

- The PR comparison parent had no AI interpretation. Quick runs and `use_ai=false` produced reports without AI.
- Run detail was looked up before tenant scoping.
- Discovered functions rendered before findings.
- The automatic PR path could bypass AI (DEF-CQ1-02).
