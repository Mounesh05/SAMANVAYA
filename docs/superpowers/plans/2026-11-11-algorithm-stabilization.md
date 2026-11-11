# Phase 1–5 Stabilization Audit Plan

> **For agentic workers:** Execute inline using systematic debugging and test-driven regression fixes. Preserve the current branch and user files.

**Goal:** Reproduce and repair confirmed integration defects in the existing algorithm-intelligence implementation.

**Architecture:** Preserve the existing services, schemas, workers and APIs. Trace each failing invariant to its producer and make the smallest compatible correction.

**Tech Stack:** Python/FastAPI, TypeScript compiler API, MongoDB, Docker, React/Vitest.

**Spec:** User attachment, “SAMANVAYA — Phase 1–5 Bug Audit, Integration Fixes & Regression Verification”.

## Global constraints

- No features, architecture redesign, new benchmark framework, RAG or training.
- Do not switch branches, reset files, erase historical evidence or weaken authorization/isolation.
- Leave existing unrelated local notes and editor configuration untouched.
- Add a failing regression before each production fix; record unconfirmed suspicions honestly.
- Do not commit or push this stabilization work without a separate request.

## Review focus

- Client constraint IDs must not silently remove mandatory policies.
- Superseded job state must invalidate pending recommendations even before PR metadata catches up.
- Source ranges must distinguish adjacent functions on one line.
- Requirement supersession must remain correct after interrupted multi-step persistence.
- Frontend comparisons must respect the deterministic engine's methodology and revision status.

## Execution

- [x] Verify branch, tree, repository structure and existing regression coverage.
- [x] Run the full backend baseline; record pre-existing failures and environment exclusions.
- [x] Add minimal repros for the review-focus paths and any additional defect proven by inspection.
- [x] For each failing repro: identify root cause, fix its owning service/parser/component, then rerun its regression and adjacent tests.
- [x] Verify Phases 1–5, authorization, manual benchmarks, Docker workers, frontend tests/build and optional MongoDB concurrency.
- [x] Produce the requested audit report with confirmed fixes, commands/counts, changed files and separate remaining defects/risks/blockers.

Results: [full audit report](../../reports/2026-11-11-algorithm-stabilization-audit.md). No commit/push, branch switch, API addition or architecture redesign was performed.
