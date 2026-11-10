# DORA delivery metrics, deployments and incidents

Branch: `feature/dora-metrics` (based on `feature/flow-metrics`). This document is for reviewers.

## What this branch adds

| Piece | What it does |
|---|---|
| `intelligence/metrics/delivery.py` | Deployment frequency, change lead time, change fail rate, failed deployment recovery time, deployment rework rate, DORA levels, weekly trend |
| `domain/services/deployment_service.py` | Records production deployments from GitHub webhooks (`deployment`, `deployment_status`, or a configured deploy workflow), with the commits in each deployment and rollback detection |
| Incidents (`domain/models/incident.py`, `domain/services/incident_service.py`, `api/routes/incidents.py`) | The backend the Incidents page never had: create, list, update, status flow, link to the deployment that caused or fixed it |
| `GET /api/delivery/projects/{id}/dora?days=90` | The DORA report for a project |
| Frontend `IncidentsPage.jsx` + `api/incidents.api.js` | The page now loads, reports and updates real incidents |

## Definitions

From DORA's own guide ([dora.dev/guides/dora-metrics-four-keys](https://dora.dev/guides/dora-metrics-four-keys/)) and metric history
([dora.dev/insights/dora-metrics-history](https://dora.dev/insights/dora-metrics-history/)):

| Metric | How SAMANVAYA measures it |
|---|---|
| Deployment frequency | Successful **production** deployments per week; also the share of days with a deployment |
| Change lead time | Per commit: committer date → the first successful production deployment containing it |
| Change fail rate | Deployments that required immediate intervention: an incident names them as its cause, or they were rolled back |
| Failed deployment recovery time | Incident started → resolved, **only incidents caused by a change**. That's DORA's definition since 2023; external causes such as a cloud outage are excluded. Recovery over all incidents is reported separately |
| Deployment rework rate (2024) | Rollbacks, hotfixes, and deployments an incident names as its fix ÷ deployments |
| Deployment failure rate | Failed deployment *attempts* (never reached success). Not a DORA metric; DORA counts failures in production |

**Levels** use the **2023 Accelerate State of DevOps report** clusters, as upper bounds:

| Level | Deployment frequency | Lead time | Fail rate | Recovery |
|---|---|---|---|---|
| Elite | daily or more | < 1 day | ≤ 5% | < 1 hour |
| High | ≥ weekly | < 1 week | ≤ 10% | < 1 day |
| Medium | ≥ monthly (12/52 per week) | < 1 month | ≤ 15% | < 1 week |
| Low | slower | slower | > 15% | slower |

Sources: [2023 clusters table](https://octopus.com/blog/software-delivery-performance-clusters-2023) and the
[Google 2023 report PDF](https://services.google.com/fh/files/misc/2023_final_report_sodr.pdf).

- The clusters are statistical groups, not official cut-offs.
- The 2024 report published different values, and secondary sources disagree, especially on change fail rate.
- In the published 2023 table, Low has the same deployment frequency and lead time as Medium. Here, anything slower than
  Medium counts as Low.
- DORA defines no overall level, so the report gives `lowest_level`.

## How deployments are recorded

- **Project mapping:** the repository is matched to a project through `github_project_configs` (exact owner/name), then
  through `projects.code_repo_url`. Events from unmatched repositories are not recorded.
- **Production:** environments listed in `github_project_configs.production_environments` (default production / prod /
  live) are production. Others are stored with `production: false`.
- **Deploy workflow:** teams that deploy with GitHub Actions instead of GitHub Deployments set
  `github_project_configs.deploy_workflow` to the workflow's name. Its completed runs on the default branch count:
  success → success; failure or timed out → failure; cancelled or skipped → ignored.
- **On a successful production deployment:** one GitHub compare call, previous successful production deployment →
  this one.
  - **ahead / diverged:** the new commits are stored for lead time.
  - **behind:** a **rollback**; the previous deployment is marked as rolled back, which counts as a failed change.
  - **identical:** a redeploy; no new commits.
  - The first deployment of a project stores only its head commit.
- **Hotfix:** a ref starting with `hotfix/`, or "hotfix" in the description.
- **Out-of-order webhooks** never reopen a finished deployment, and a later event with less detail never erases known
  fields.
- **GitHub unavailable:** the deployment is kept with `commits_error`.

## Bugs fixed

1. **Repository → project matching used a substring test** (`webhook_event_processor._match_repository_to_project`).
   `org/app` also matched a project at `.../org/app-v2`, so PRs, notifications and now deployments could be attributed
   to the wrong project. It now compares exact owner/name and uses `github_project_configs` first.
2. **DevOps dashboard** (`api/roles/devops.py`):
   - It showed **every project's** pipelines and deployments to any DevOps user. Now it shows only the user's
     accessible projects.
   - `deployments_today` counted deployment events among the latest 100 of **any date**. Now it counts production
     deployments finished today.
   - `active_incidents` counted **failed builds**. Now it counts open or investigating incidents (failed builds are
     `failed_runs`).
   - The Deployments page expects `service`, `version`, `status` (success / failed / pending) and `deployed_at`, which
     raw webhook events never had. The API now returns recorded deployments in that shape.
3. **CEO dashboard** counted incidents with status `open` / `active` in a collection nothing wrote. Incidents now exist,
   and the count uses their real statuses (`open`, `investigating`).
4. **Incidents page** returned a hard-coded empty list, and its "Report Incident" button only closed the dialog. It now
   uses the API, has a project picker, and has status buttons (Investigate / Resolve / Close / Reopen). "Resolved
   Today" counts incidents resolved today, not every resolved one.

## Behaviour changes reviewers should check

- **New collections:** `deployments` and `incidents`.
- **New optional `github_project_configs` fields:** `production_environments`, `deploy_workflow`.
- **One extra GitHub API call** per successful production deployment (`/compare`), or per first deployment
  (`/commits/{sha}`).
- **New routes:** `POST/GET /api/incidents/`, `GET/PATCH /api/incidents/{id}` (create and update need
  `CREATE_INCIDENT`, i.e. DevOps and CEO by default, plus project write access), and
  `GET /api/delivery/projects/{id}/dora`.
- **Correction to the plan:** the `project_id=f"webhook-{repo}"` code in `WebhookService._handle_pull_request` is not
  called by the live webhook route, which uses `WebhookEventProcessor` and passes the matched project. It was left as
  is; it could be removed as unused code.

## Tests

- `test_metrics_delivery.py`: 39 tests, hand-calculated values for each metric, level boundaries and the full report.
- `test_dora_integration.py`: 22 tests. Covers:
  - incidents: cause, same-project check, status flow, reopen
  - deployments: first, ahead, rollback, redeploy, staging, failures, out-of-order events, hotfix, GitHub down
  - deploy workflow
  - exact repository matching
  - the Deployments page shape
  - **end to end**: a stream of webhook events produces the expected DORA report (5 deployments, lead-time median
    4 h, change fail rate 40%, rework 20%)

```bash
SECRET_KEY=test python -m pytest tests/test_metrics_delivery.py tests/test_dora_integration.py --noconftest
```

The existing tests that can run here pass too (321 in total on this branch).

**Not tested:** the frontend Incidents page change. The frontend dependencies (`node_modules`) are not installed in
this environment, so vitest could not run. Please run `npm test` in `frontend/` before merging.
