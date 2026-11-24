# Rehearse a multi-PR release in TaskFlow

This procedure exercises the gate on a GitHub Actions job that verifies an artifact and writes a job summary. It uses the pilot repository `Mounesh05/taskflow-samanvaya-lab`. This live rehearsal is **NOT RUN**.

## Prepare the repository

1. Rotate the previously exposed webhook secret in Samanvaya and GitHub. Confirm that a fresh GitHub ping is accepted after restarting the API.
2. Review the two workflow templates. Copy [the trusted build](samanvaya-release-build.example.yml) to `.github/workflows/samanvaya-release-build.yml` and [the manual rehearsal](samanvaya-release-rehearsal.example.yml) to `.github/workflows/samanvaya-release-rehearsal.yml`. Copy both files from [the composite action](../../.github/actions/samanvaya-release-gate/) to the same path in TaskFlow. Keep the existing `ci.yml` and PR #4 available for the single-PR pilot.
3. Require review for changes to the workflow files and the composite action. Protect `main`, restrict the GitHub `production` environment to that branch, and require the appropriate environment reviewers. Only the manually dispatched, protected job needs the Samanvaya release-gate credential. The build job has read-only GitHub access.
4. After the setup changes are reviewed and merged, hash the workflow bytes as stored on GitHub. For example, in Bash run `git show origin/main:.github/workflows/samanvaya-release-build.yml | sha256sum`. Configure `RELEASE_TRUSTED_WORKFLOW_PATH=.github/workflows/samanvaya-release-build.yml`, `RELEASE_TRUSTED_WORKFLOW_SHA256` with the lowercase hex output, `RELEASE_TRUSTED_BUILD_REF=main`, and `RELEASE_REQUIRED_TEST_SUITES=samanvaya-release-qa/junit.xml`. Enable multi-PR releases and restart the API using the [release-gate runbook](production-release-gate.md).
5. In GitHub's `production` environment, set `SAMANVAYA_API_URL` and `SAMANVAYA_PROJECT_ID` as variables. The API URL is the HTTPS server base before `/api`. Set `SAMANVAYA_RELEASE_GATE_TOKEN` as an environment secret using the credential issued by the assigned DevOps reviewer in Samanvaya.

## Create the candidate

1. Use a known deployed baseline in the pilot environment. For a first rehearsal with no deployment history, have the authorized reviewer initialize the baseline to the exact agreed reference commit after setup and before the pilot changes, with the reason recorded in Samanvaya.
2. Create at least two tasks and PRs against the baseline. One can adjust harmless TaskFlow help text and another can extend its regression test. Record the expected helper text, the exact assertion and the expected passing backend suite as acceptance criteria. Link each PR to its task in Samanvaya and merge through the ordinary review process. Keep the target limited to the pilot changes. A direct commit or an extra unreviewed PR can make the release incomplete.
3. Use the successful protected-branch push run at the combined target commit. The trusted build publishes JUnit evidence from that exact commit and packages the tested source for this rehearsal. Its summary contains the run ID, artifact ID, archive SHA-256 and target commit. Use the run ID and artifact ID to create the release in Samanvaya. Compare the resulting manifest, QA report and artifact digest with the GitHub run before submitting it.
4. Ask the QA reviewer to check the included tasks, their acceptance criteria and the combined JUnit report, then record release verification. Ask an independently assigned DevOps reviewer to record the hold or approval. Each reviewer should use their own account.

## Record the results

| Scenario | Run in GitHub Actions | Expected evidence |
| --- | --- | --- |
| Hold | Dispatch the manual rehearsal from protected `main` with the candidate's Samanvaya release ID, target commit, artifact ID and archive digest. | The gate step fails. The rehearsal marker is skipped. |
| Current approval | Use the same four inputs after current QA verification and independent DevOps approval. | The archive hash matches, the gate passes and the marker appears in the job summary. |
| Artifact mismatch | Dispatch against the approved candidate with a different digest. | Archive verification fails and the marker is skipped. |
| Changed evidence | Rerun the same trusted workflow after approval and verify that the previous build attempt is stale. In a local controlled fixture, supply a newer failed required report and repeat the check. | Samanvaya denies old evidence. The marker is skipped until the current candidate evidence receives fresh review. |

Keep the GitHub run URLs, both Samanvaya decisions and the release manifest digest with the pilot results. GitHub may emit environment events for the rehearsal job. The rehearsal summary records a successful check, and deployment history requires a separately matched observation. The gate checks evidence immediately before the protected step. A hold recorded after a successful check takes effect on subsequent checks.
