# Evaluation placeholder citation repair

The reported PR #4 request failed because the model copied the literal `path/to/changed-file` from the evaluation prompt. The same prompt also contained an invalid extra brace layer around its example dimensions object, and its unrestricted citation arrays allowed the small local model to repeat citations until truncation. Ollama's active context was 4096 tokens for an evidence-heavy request. The existing citation validator correctly rejected the fabricated references.

## Change

- Build a bounded citation catalog from the actual retrieved manifest. Model-selected IDs resolve to exact file/added-line/single-line excerpt, commit, check, review, comment or impact references on the server.
- Reject unknown IDs and references that mix an ID with invented source fields. Legacy explicit citations still undergo the original validation; nothing is silently discarded or replaced by guesses.
- Generate a typed JSON response with actual eligible dimensions, dimension-specific citation choices, string recommendations and short bounded evidence arrays. Remove the invalid JSON example and duplicate patch text.
- Request a bounded 16384-token model context and 2048 output tokens. Keep the existing total 150-second inference deadline. If exactly one dimension has unrelated reasoning, allow one small evidence-only model re-evaluation within the remaining deadline, capped at 30 seconds and 512 tokens; validate the revised score and references again. Multiple unrelated dimensions or invalid corrections still fail closed.
- Preserve authorization, evidence eligibility, public response projection, deterministic scoring formulas and all canonical performance policies.

Production change: [evaluation route](../../../backend/api/routes/evaluation.py). Regression files: [new citation tests](../../../backend/tests/test_evaluation_citation_prompt.py) and [existing evaluation tests](../../../backend/tests/test_evaluation_engine.py); the timeout fixture now accepts provider keyword arguments without changing its timeout assertion. The unfinished Actions artifact-import work remains separate and uncommitted.

## Executed evidence

- Before repair, new regressions reproduced placeholder paths, malformed example JSON, missing source-ID resolution and the unrelated-dimension failure.
- Final focused backend evaluation/person-access/role regression selection: **87 passed, 0 failed, 0 skipped**, exit 0. Existing evaluation frontend tests: **3 passed**, exit 0.
- Real GitHub PR #4 evidence and real `qwen2.5-coder:3b` execution completed validation in **56.75 seconds**, using two bounded model calls. Head: `8ad02ac50587c6bb668dc480ae68efdc9f411b68`. No evaluation/person record was persisted by the probe. See [validated result](./live-model-validation.json) and [actual model replies](./live-model-responses.json).
- Earlier intermediate live attempts remained rejected for invalid format, unrelated delivery reasoning, truncation or timeout; a separate transient GitHub DNS failure prevented one evidence fetch. No such failed output was stored as successful evaluation.
- Scoped editor diagnostics report no errors. Ruff still reports the pre-existing unused `fastapi.Query` import. Mypy reports the same three pre-existing findings as HEAD: two missing local annotations and an existing result-dictionary type mismatch. The only newly surfaced helper annotation issue was corrected. No unrelated lint/type cleanup was applied.

## Reproduce and retry

1. Use the normal local frontend sign-in as the authorized Lead and open AI Evaluation.
2. Select employee `MOUNESH`, GitHub user `Mounesh05`, repository `Mounesh05/taskflow-samanvaya-lab`, PR `4`, and Code Quality focus. Use the existing account credentials privately; do not modify role access or invent a JWT.
3. Submit once and allow the model time to finish. The frontend already permits a 180-second request; backend inference remains capped at 150 seconds across the initial and optional corrective call.
4. Accepted citations must show actual paths such as `backend/app/advanced_algorithms.py` or the real commit SHA. `path/to/changed-file`, unknown source IDs, invalid line/excerpt values and unsupported claims must still be rejected.
5. Do not interpret successful format/citation validation as proof of software correctness or model-score accuracy. Output is PR-scoped advisory analysis. The observed model still uses subjective wording and can make overbroad statements; human review remains necessary.

GitHub Checks still returns HTTP 403 with this credential; the separate Actions fallback remains successful. This permission limitation did not cause the placeholder-citation 502 and was not bypassed. No contract was approved, GitHub content changed, official performance score activated, commit created or push performed for this repair.
