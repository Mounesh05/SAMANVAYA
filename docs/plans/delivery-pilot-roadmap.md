# Samanvaya delivery pilot

The first organization workflow follows one task from its requirement through a pull request, tests, human release review and an observed deployment. GitHub executes the workflow. Samanvaya assembles the evidence and supplies a decision that a deployment job can enforce.

## Pilot capabilities

| Who | What to try | What counts as evidence |
| --- | --- | --- |
| Developer and team lead | Open a task and inspect the linked story, PR, revision and test reports. | The report identifies its source, suite and run attempt. Missing or ambiguous links have an explicit unknown state. |
| Authorized analysis author | In development or test, enable the manual analysis feature and open your existing Code and QA advisory from a task with a synchronized PR. | The lookup matches the repository, PR and exact PR head. Opening a task does not start a model run. The release decision uses separate evidence for the merge commit. |
| QA | Review the acceptance criteria and the reports on the merged revision, then record verification. | The decision identifies the reviewer, revision and evidence they reviewed. |
| DevOps | Record a hold or approval, manage a project credential and check the candidate before deployment. | A passing gate requires current QA verification and an independent DevOps approval. A later deployment observation records the outcome. |
| DevOps | Open a day or outcome in the workflow chart and follow it to matching records. | The dashboard groups distinct GitHub workflow attempts across 14 UTC dates. Success rate uses attempts with a success or failure outcome. |
| PM | Select an age group in **Blocked work by age** and open the task. | Counts cover blocked tasks in active projects the PM manages. Tasks without a reliable blocking date have their own group. |
| Assigned human reviewer | Open **Feedback**, select your assignment and submit observations for the review period. | The assignment identifies the reviewer and scope. Observations remain unscored. Authorized HR authors can also read their historical workplace cases. |

The production gate currently supports a single task and a single merged PR in one repository. Adoption requires a repository owner to add the gate to each production deployment path and supply the exact revision of the artifact being deployed. [Deployment workflow and rehearsal procedure](../runbooks/production-release-gate.md)

The dashboard and its drilldowns use `/api/role/devops/reporting/dashboard`, `pipelines` and `deployments` under the same reporting prefix. Older integrations can still read scoped raw webhook rows from `/api/role/devops/pipelines` and `/api/role/devops/deployments`.

## PM reporting benchmark

On local MongoDB 8.3.7, a synthetic workload contained 600 projects, 24,000 tasks and 20,600 status changes. Four managed projects contained 4,000 blocked tasks, including 400 legacy records. Across seven warm reads, the median time to count blockers and return 12 tasks from the week-plus group fell from 965 ms to 298 ms after adding two partial indexes. A second run with concurrent tests measured 699 ms before indexing and 457 ms afterward. Both runs returned the same counts and rows. The report still reads each matching blocker. Concurrent tenant traffic and production latency remain to be measured.

## Expansion and acceptance criteria

| Phase | Acceptance criteria |
| --- | --- |
| Rehearse with a pilot repository | A harmless GitHub deployment job stops on a hold, proceeds on current independent approvals and stops again after a failed rerun. Compare the recorded workflow, QA and deployment identities with the GitHub run. |
| Support releases containing multiple changes | The manifest-aware gate is available behind `RELEASE_MANAGEMENT_ENABLED` for controlled rehearsal. Live GitHub approval and deployment observation remain pending. See [release management](../runbooks/multi-pr-release-management.md). |
| Expand requirement-aware engineering advice | Review the task's acceptance criteria, input sizes, constraints and alternatives alongside cited code and tests. Exercise a case where the best choice changes with the requirement. Expose measured performance separately from an AI estimate, and keep the recommendation subject to human review. |
| Validate organization-scale operation | Replay representative volumes of events and dashboard traffic across multiple organizations. Measure ingestion delay, backlog recovery and dashboard response times. Exercise role changes and prove that removing access takes effect during an active session. |
| Evaluate organization-level reporting | Agree with PMs and leadership on the definition and denominator for each project outcome. Expose missing evidence and sample size. Give developers and reviewers a way to inspect and correct attribution before a score informs an evaluation. |
