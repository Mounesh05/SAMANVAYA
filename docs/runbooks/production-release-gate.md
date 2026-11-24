# Require human release approval in GitHub Actions

The manifest-aware gate covers one repository and multiple PRs when release management is enabled. See the [architecture and activation guide](multi-pr-release-management.md) and [TaskFlow workflow templates](taskflow-multi-pr-pilot.md).

The pilot supports a production candidate delivered by one task and one merged pull request in one connected repository. The workflow supplies the full commit of the immutable artifact it will deploy. A fresh check reads Samanvaya’s current evidence and both human decisions. Multi-task candidates need a release manifest and are outside this pilot.

## Connect a deployment job

1. In **GitHub Sync**, open the project’s repository configuration as its DevOps reviewer. Under **Production release gate**, issue a credential. Save the displayed value as the GitHub production environment secret `SAMANVAYA_RELEASE_GATE_TOKEN`. Set the environment variables `SAMANVAYA_PROJECT_ID` and `SAMANVAYA_API_URL`. The URL is the HTTPS server base before `/api`.
2. Include the two files in [.github/actions/samanvaya-release-gate](../../.github/actions/samanvaya-release-gate) in the trusted deployment workflow checkout. The composite action uses Python 3 and Bash. Protect the workflow and gate code with the repository’s normal deployment change review.
3. In the job that deploys to the `production` environment, add the step below **immediately before** the existing deployment command. This example assumes a preceding `build` job exposes the task ID and the exact commit used to build its artifact. Adapt the output names to the build. Deploy the artifact identified by that build, with ordinary GitHub Actions success semantics on the deploy step. Apply the check to each production entry point.

```yaml
- name: Check Samanvaya release approval
  uses: ./.github/actions/samanvaya-release-gate
  with:
    api-url: ${{ vars.SAMANVAYA_API_URL }}
    project-id: ${{ vars.SAMANVAYA_PROJECT_ID }}
    task-id: ${{ needs.build.outputs.task_id }}
    revision: ${{ needs.build.outputs.commit_sha }}
    token: ${{ secrets.SAMANVAYA_RELEASE_GATE_TOKEN }}
```

4. Validate the wiring in a rehearsal workflow with a harmless step in place of deployment. Record a hold and confirm the following step is skipped. After QA verifies the merged revision’s test evidence and a different DevOps reviewer approves it, rerun the job for the same artifact. Confirm the following step runs. Change the test evidence and confirm a fresh check denies the old approval.

The action performs one read-only check. It exits with failure on a denial, timeout, redirect, invalid response or identity mismatch. The latest ingested evidence is authoritative for that check. A later hold applies to subsequent checks. Production status in the task screen comes separately from a matching deployment observation.

Reopening a task invalidates its recorded verification and approval. Closing it again requires fresh review. If a newer attempt reports only some of the suites previously seen in that workflow run, wait for the missing reports and review the updated evidence.

**Credential changes.** Replace a credential in GitHub Sync and update the environment secret with the newly displayed value. Replacement invalidates the previous credential immediately. Revocation makes the checker fail until a new credential is issued. A credential grants access only to this project’s gate outcome.

GitHub documents the step condition and environment behavior in its [workflow syntax reference](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).
