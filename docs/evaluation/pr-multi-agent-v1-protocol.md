# PR multi-agent evaluation protocol v1

Declared before executing the Task 5 corpus on 2026-11-14. Baseline:
`57c68623daf4d6ca605f6f715b482619faf0a9f9`. Evaluation is read-only,
development/test only. No application feature flag or production policy changes.

## Questions and limits

Does the real collaborative graph preserve independently established observations,
isolate unsupported claims, and expose typed disagreement? Does it improve actual
model finding accuracy enough to justify a second inference?

The first question is testable with controlled responses. The second requires
approved live model runs and independent adjudication; a scripted QA contribution
is not evidence of improved model intelligence. Agreement is never ground truth.

The [corpus](../../backend/tests/fixtures/pr_multi_agent_evaluation_v1.json)
contains nine PR cases, three each for Python, JavaScript and TypeScript.
Expected facts are author-specified function counts and recorded CI failure counts.
These are deliberately within the existing evidence resolver's supported scope.
Source descriptions document limitations; they are not additional model evidence.
No submitted function is executed. CI counts describe local submissions, not proof
of execution. The corpus is small and synthetic, not statistically representative
of production repositories, security defects or arbitrary semantic reasoning.

## Matched comparison

- Execute the existing `ainvoke_agent('code_review', ...)` graph and the real
  `pr_multi_agent_v1` sequential Code/QA graph. Do not replace either graph.
- Resolve each fixture through the existing authorized GitHub evidence collector
  using controlled transport and the existing Python/JS/TS parsers. Freeze one
  snapshot per fixture. Both modes receive exactly that snapshot's information.
- Give the legacy Code specialist the complete snapshot in its existing
  `evidence_summary` field. Code and QA receive the same snapshot through their
  existing typed views. Actual production prompt builders and parsers run.
- Deterministic scripted inference emits the **same multiset of substantive
  assertions** in both modes, in their respective supported response formats.
  Legacy receives both the Code and QA assertions in its one response. This
  avoids manufacturing a recall gain merely by withholding QA facts from it.
- Collaborative uses two controlled calls versus one legacy call. Report this
  budget difference explicitly. It is not an equal-token live quality comparison.
- Five paired repetitions per case, alternating which mode runs first. No sleeps
  or mocked clocks. Measure `perf_counter` elapsed time and actual prompt/response
  UTF-8 bytes. Evidence preparation is excluded equally; model, network and queue
  latencies are absent. Timing describes this local controlled harness only.
- Preserve per-run results and aggregate median/nearest-rank p95. Count unique
  findings by metric/value; repeated agent agreement does not increase coverage.

## Metrics and denominators

Each fixture declares positive factual findings and a negative control:
`function_count = expected + 1`. Literal typed value equality is required.

- TP: expected factual metric/value pairs emitted at least once.
- FN: expected factual pairs not emitted.
- FP: declared negative controls emitted.
- TN: declared negative controls not emitted.
- Precision: TP/(TP+FP); recall: TP/(TP+FN); false-positive rate: FP/(FP+TN).
  Empty denominators are `null`, never invented zeroes.
- Unknown/unsupported assertions: unique assertions outside that finite fact
  catalogue, counted separately. They are not silently relabeled false negatives,
  true findings or validated facts. Interpretations remain advisory.
- Report both the raw attempted assertion metrics and the collaborative
  `SUPPORTED` structured-observation metrics. Filtering changes the presentation
  tier, not the model's underlying accuracy. Legacy has no equivalent typed
  supported tier; do not fabricate one.
- Disagreement detection: typed conflicting observation cases detected / seeded
  conflicting cases. Separate this from general natural-language consistency.
- Unsupported promotions: any unsupported interpretation reaching `SUPPORTED`.
- Resource accounting: actual controlled call/byte counts; Ollama CPU, RAM, VRAM,
  token throughput and inference latency are **null/unverified** without live
  inference. Python elapsed time is not Ollama resource usage.

## Predetermined gates

| Gate | Required evidence | Meaning |
| --- | --- | --- |
| Controlled fidelity | Both modes see identical snapshot and substantive assertions; all nine cases, five repetitions | Required before comparing metrics |
| Fact preservation | Supported-tier recall at least legacy raw recall; no observed false fact promoted | Safeguard gate, not model superiority |
| Unsupported/consensus handling | Zero unsupported promotions; agreement does not promote interpretation | Mandatory |
| Typed disagreement | All three seeded factual disagreements detected | Limited to declared scope |
| Security/reliability | All focused adversarial, authorization, durability, MongoDB and UI cases pass | Mandatory |
| Backward compatibility | Existing available regression checks pass; any collection/lint/type blockers explicitly retained | No unconditional full-suite pass with errors |
| Live accuracy | Independently adjudicated paired Python/JS/TS findings; precision >=95%, recall no lower than legacy, and at least one additional supported relevant finding in each language | Proposed evaluation criterion, not production policy; cannot be met by scripts |
| Live latency | Warm/cold reported separately, >=30 counterbalanced paired runs per language; p95 ratio <=2.5 and existing 180-second attempt limit respected | Proposed pilot criterion; no host SLO inferred |
| Live resources | Measured Ollama peak RAM/VRAM, CPU/GPU and token usage; fit an explicitly approved host capacity budget | Unknown budget or missing measurements blocks readiness |

Final verdict must distinguish evaluation tooling completion, controlled safeguard
readiness and production rollout readiness. Missing approved live runs or a blocked
mandatory regression environment prevents a production-ready verdict. Do not tune
criteria after seeing corpus results. This protocol and fixture SHA-256 digests are
recorded in the machine-readable output.

## Approved live follow-up and rollback

Live work requires explicit nonproduction repository/PR, revision, endpoint/model
and credential authorization. Never print credentials, post comments or mutate a
repository. Record model digest/version, generation parameters, warm/cold state,
host capacity and output provenance; independently adjudicate observations and
interpretations. Credentials merely existing locally are not approval.

Keep both backend flags and frontend opt-in off. A later approved pilot must stop
on any unauthorized exposure, unsupported promotion, stale publication, duplicate
canonical report or resource-budget breach. Disable manual intake/display, stop
and await the lifecycle worker, retain immutable records and let leases recover
only after authorized restart. Do not delete histories or relax fencing.
