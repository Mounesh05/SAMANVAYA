# TaskFlow controlled development setup

## A — Environment

- Branch: `testing`; base commit: `d681387cbe59fa51454f90a87b4d25391fbaa3dc`. The fixes and setup scripts described below are uncommitted.
- Environment: `development`; MongoDB host is loopback; database: `samanvaya_test`.
- The database had no collections or records at preflight. The user explicitly approved this exact database after being told it is also used by automated tests. No pre-existing accounts or production records were modified.
- **Operational limitation:** automated MongoDB integration tests can delete demo data in this database. Do not run those suites concurrently with, or after preparing, a demo session unless loss of synthetic records is intended. This is an approved shared test database, not a dedicated persistent demo database.
- GitHub token present: **Yes**. Read-only access verified: **Yes**. Metadata, branches, pull requests and workflow runs returned HTTP 200 for the requested private lab repository.
- `PR_MULTI_AGENT_INTERNAL_ENABLED=false`, `PR_MULTI_AGENT_MANUAL_ENABLED=false`, and `VITE_PR_MULTI_AGENT_MANUAL_ENABLED=false` were verified. Existing environment files were not overwritten.
- Existing Python 3.12.10 backend virtual environment and existing bcrypt authentication helpers were used. No new dependencies, framework, database or queue was installed.

## B — Created records

All business records below were **CREATED** in the previously empty database, then **REUSED** on an idempotency rerun. Counts, identifiers and stored credential hashes were compared before/after that rerun and did not change.

| Resource | Name | Identifier | Count |
| --- | --- | --- | --- |
| Tenant association | TaskFlow Demo Organization | `TASKFLOW-DEMO` | One tenant ID |
| Dedicated platform administrator | Demo Platform Administrator | `DEMO_ADMIN` | 1 |
| Requested role accounts | See membership table | See membership table | 8 |
| Engineering team | TaskFlow Engineering | `TASKFLOW-ENGINEERING` | 1 |
| Project | TaskFlow | `PRJ-A7E48B66` | 1 |
| Sprint | TaskFlow Sprint 1 | `SPR-50B58318` | 1 |
| Stories / tasks | See workload table | See workload table | 7 / 7 |
| Validated local GitHub project configuration | Requested TaskFlow lab repository | `PRJ-A7E48B66` | 1 |

SAMANVAYA has no separate organization entity or organization login in the inspected implementation. Therefore a standalone organization record and organization password were **NOT CREATED**. Tenant scope is the existing `org_id` association on accounts/projects. The organization name and synthetic purpose are described in the team metadata; no second organization system was invented.

The bootstrap created the separate CEO and platform administrator through the existing `create_first_accounts` function. The remaining seven employees, team, memberships, project, sprint, stories and tasks were created through authenticated existing application routes. No authorization dependency was overridden. Setup used ASGI requests without starting the application lifespan, so no poller or workflow worker was launched.

### Workload

Sprint remains **planning**. Every story/task remains **todo**; no repository work, QA result or completion was asserted.

| Work | Assignee | Story | Task |
| --- | --- | --- | --- |
| Backend API foundation | `MOUNESH` | `STY-F19A89C0` | `TSK-99F9C2BE` |
| MongoDB persistence and data validation | `MOUNESH` | `STY-C4838040` | `TSK-94E5AE23` |
| React task dashboard | `MALLIKARJUN` | `STY-0BBDE546` | `TSK-4FD58E56` |
| TypeScript sorting and searching functions | `MALLIKARJUN` | `STY-B4E647AA` | `TSK-D7175F8F` |
| Backend integration tests | `SHREYAS` | `STY-BE3CDD9E` | `TSK-F6281544` |
| GitHub Actions CI configuration | `DEMO_DEVOPS` | `STY-85429AAA` | `TSK-F7DD06AA` |
| QA verification of task lifecycle | `SHREYAS` | `STY-AC5C437D` | `TSK-BA00456A` |

The CI story explicitly notes that DevOps owns the task and Shreyas will perform the actual repository work. The application has a single assignee per item; no unsupported second-assignee field was introduced. Project technology information is recorded in its description because the current project model has no structured technology-stack field.

## C — Credentials

All nine initial credential pairs are stored only in the local, Git-ignored file:

`M:/Samanvaya/credentials/taskflow-demo/accounts.json`

The directory has inheritance removed and full access granted only to the current Windows user. Its contents were not printed or placed in tracked files. Each entry identifies its username, employee ID, email, organization password and employee password. Both passwords are required by the existing login flow; this is not an organization-wide password login.

The requested administrator organization password was accepted by the existing policy and used only for the dedicated demo platform administrator. Requested `<username>@123` employee passwords were **NOT USED**: they fail the existing length/uppercase requirements. Generated policy-compliant passwords were used instead. The CEO/admin bootstrap additionally requires distinct credentials across the pair; that rule was preserved. Passwords in MongoDB are bcrypt hashes.

All synthetic emails use reserved `example.com`: the existing `EmailStr` validator rejected the preferred `example.test` domain. No email or invitation was sent.

Every existing credential pair was independently verified on the rerun. No reused account's password was reset.

## D — Membership and access

Usernames are accepted by the existing case-insensitive employee-ID lookup; stored IDs are uppercase. No separate username model was added.

| Username | Stored employee ID | Role | Team | Project relationship |
| --- | --- | --- | --- | --- |
| `demo_ceo` | `DEMO_CEO` | CEO, not admin | None | Existing organization-level executive visibility |
| `demo_admin` | `DEMO_ADMIN` | DEVOPS with platform-admin flag | None | Unassigned; no automatic engineering-project bypass |
| `demo_hr` | `DEMO_HR` | HR, not admin | None | People visibility; engineering project/QA data denied |
| `demo_pm` | `DEMO_PM` | PM | None | Project creator/assigned manager |
| `demo_lead` | `DEMO_LEAD` | LEAD | Team lead | Explicit project member |
| `mounesh` | `MOUNESH` | DEVELOPER | Member | Explicit project member; backend tasks |
| `mallikarjun` | `MALLIKARJUN` | DEVELOPER | Member | Explicit project member; frontend tasks |
| `shreyas` | `SHREYAS` | QA | Member | Explicit project member; QA tasks |
| `demo_devops` | `DEMO_DEVOPS` | DEVOPS, not admin | Member | Explicit project member; delivery task |

CEO, HR, PM and platform administrator were not added to the engineering team for convenience. Every account belongs to `TASKFLOW-DEMO`.

The project is linked to `Mounesh05/taskflow-samanvaya-lab`, default branch `main`, through the existing permission-checked configuration API. That API verified repository metadata, branch availability and URL consistency before persisting the local mapping. GitHub developer-identity/branch mappings remain **NOT CREATED** because no verified identity associations were supplied; the mapping list is empty.

## E — Verification and fixes

### Confirmed defects repaired

1. **HR credential/engineering-data exposure and missing tenant filtering.** Both role endpoints returned raw active user records. Tests first reproduced foreign-tenant inclusion; source tracing confirmed that password hashes and unknown nested fields also reached the response. Both now share tenant-scoped loading and the existing `EmployeeHRView` allowlist. An HR account without tenant provenance is limited to its own employee record.
2. **Lead dashboard credential exposure and cross-tenant team lookup.** Raw user documents were returned as team members. The dashboard now returns an explicit safe employee view with the permitted GitHub identity. Team loading shared by dashboard, workload and review-queue handlers now includes current organization scope.
3. **CEO dashboard aggregate scope.** Project and incident totals included other tenants. Projects are now scoped to the CEO's organization, and incidents to those projects. Missing CEO tenant provenance yields no project aggregate.
4. **PM dashboard/risk scope.** Active-project and risk aggregates included unmanaged and foreign projects. Both handlers now query the manager's assigned projects, with an organization filter when available.

The fixes change neither role grants nor scoring formulas. Legitimate project/team/people response fields remain available. No claim is made that this focused work is an exhaustive application-wide security audit.

### Executed checks

| Verification | Actual result |
| --- | --- |
| Preflight account/project/tenant tests | 49 passed |
| New HR boundary reproduction before repair | 4 failed, as expected |
| New CEO/PM/Lead reproduction before repair | 3 failed, as expected, after correcting one test's response-field name |
| Final combined backend checks: role boundaries, setup guards, dashboards, sprint status, HR access, HR filtering, authorization, PM membership, project authorization and first accounts | **161 passed**, 12 existing deprecation warnings; exit 0 |
| Existing frontend dashboard compatibility tests | **15 passed**; exit 0 |
| Pre-commit combined rerun including GitHub CI-evidence/client/poller/discovery/adapter regressions | **249 passed**, 39 existing deprecation warnings; exit 0 |
| Authenticated ASGI verification against real local MongoDB | **210 checks passed, 0 failed** |
| Setup rerun | Same 9 users, 1 team, 1 project, 1 sprint, 7 stories, 7 tasks and 1 repository configuration; IDs and password hashes unchanged |
| Scoped Ruff | Passed |
| Diff whitespace check | Passed |

The live-data checks authenticate all nine accounts with the existing password-authentication service, then exercise the real ASGI routes and normal current-account authorization dependencies. They cover all seven role dashboards, wrong-role denial, project visibility, explicit foreign-organization denial, project membership, sprint/story/task access, team reads, QA evidence, repository/code configuration, incident visibility, pipeline rights, forbidden project/team creation, HR engineering-analysis denial, normal logout, revoked-token refusal and wrong-password rejection. They do not bypass permissions or create authorized negative-test records.

The first verification run had one incorrect harness expectation: the unassigned platform administrator was expected to see project incidents. The application correctly returned 403. The expectation was corrected; no permission was granted and the rerun passed all 210 checks.

No full backend integration suite was run after populating the database, because cleanup could remove the requested setup. The focused regression modules use mocked storage. No browser walkthrough, live model inference, multi-agent analysis, CI execution, benchmark run or production deployment is claimed.

### GitHub read evidence

- Private repository metadata: HTTP 200; default branch `main`.
- Branch list: HTTP 200; 1 branch.
- Existing PR list: HTTP 200; 3 PRs.
- Actions run list: HTTP 200; 3 runs reported.
- Existing PRs/runs were inspected as available remote evidence; none were fabricated, linked to synthetic tasks, or imported as completed local QA results.
- No GitHub write endpoint, repository change, push, merge, workflow edit or webhook creation was requested. No Ollama inference was run.

### Changed files

- [HR role handlers](../../backend/api/roles/hr.py)
- [Lead role handlers](../../backend/api/roles/lead.py)
- [CEO role handlers](../../backend/api/roles/ceo.py)
- [PM role handlers](../../backend/api/roles/pm.py)
- [Explicit development setup command](../../backend/scripts/setup_taskflow_demo.py)
- [Demo verification command](../../backend/scripts/taskflow_demo_verification.py)
- [HR boundary regressions](../../backend/tests/test_hr_dashboard_data_boundary.py)
- [Dashboard boundary regressions](../../backend/tests/test_role_dashboard_boundaries.py)
- [Setup safety regressions](../../backend/tests/test_taskflow_setup_guards.py)
- This report.

No commits or pushes were made. Pre-existing unrelated untracked files were left untouched.

## F — Readiness and next action

TaskFlow is ready for the controlled local project-management and role-dashboard walkthrough, subject to the shared-test-database limitation above. Repository connectivity/link configuration is verified; synchronization behavior and a browser walkthrough remain separate checks. Multi-agent analysis remains disabled, and no Phase 2 algorithm work or live evaluation was started.

**Single next action:** start the local development application and sign in as `demo_ceo` using its two credentials from the restricted local file to begin the dashboard walkthrough.
