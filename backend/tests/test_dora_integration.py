"""
Integration of the DORA pieces: incidents, deployment recording from GitHub
webhooks (commits, rollbacks, redeploys, deploy workflows), repository-to-
project matching, the Deployments page shape, and an end-to-end check that a
stream of webhook events produces the expected DORA report.

MongoDB and GitHub are replaced by small in-memory stand-ins.
"""

import asyncio
from datetime import date
from types import SimpleNamespace

import pytest

import core.database
from api.roles.devops import for_deployments_page
from domain.models.incident import IncidentCreate, IncidentUpdate
from domain.services.deployment_service import DeploymentService
from domain.services.incident_service import IncidentError, IncidentService
from domain.services.webhook_event_processor import WebhookEventProcessor, repository_key
from intelligence.metrics.delivery import dora_report


def run(coro):
    return asyncio.run(coro)


def _matches(doc, query):
    for key, cond in query.items():
        if isinstance(cond, dict) and "$in" in cond:
            if doc.get(key) not in cond["$in"]:
                return False
        elif doc.get(key) != cond:
            return False
    return True


class FakeRepo:
    def __init__(self, docs=()):
        self.docs = {d["id"]: dict(d) for d in docs}

    async def find_one(self, query, projection=None):
        return next((dict(d) for d in self.docs.values() if _matches(d, query)), None)

    async def find_by_id(self, doc_id):
        return dict(self.docs[doc_id]) if doc_id in self.docs else None

    async def find_all(self, query):
        return [dict(d) for d in self.docs.values() if _matches(d, query)]

    async def find_by_project(self, project_id):
        return await self.find_all({"project_id": project_id})

    async def find_for_projects(self, project_ids, status=None):
        query = {"project_id": {"$in": list(project_ids)}}
        if status:
            query["status"] = status
        return await self.find_all(query)

    async def insert(self, doc):
        self.docs[doc["id"]] = dict(doc)
        return True

    async def update(self, query, update):
        doc = self.docs.get(query["id"])
        if doc is None:
            return False
        doc.update(update)
        return True

    async def upsert(self, query, doc):
        self.docs.setdefault(query["id"], {}).update(doc)
        return True


class FakeGitHub:
    """compare: (base, head) -> response; commits: sha -> committer date."""

    def __init__(self, compare=None, commits=None, fail=False):
        self.compare = compare or {}
        self.commits = commits or {}
        self.fail = fail
        self.calls = []

    async def compare_commits(self, owner, repo, base, head):
        self.calls.append(("compare", f"{owner}/{repo}", base, head))
        if self.fail:
            raise RuntimeError("GitHub unavailable")
        return self.compare[(base, head)]

    async def get_commit(self, owner, repo, sha):
        self.calls.append(("commit", f"{owner}/{repo}", sha))
        if self.fail:
            raise RuntimeError("GitHub unavailable")
        return {"sha": sha, "commit": {"committer": {"date": self.commits[sha]}}}


CONFIG = {"project_id": "P", "repository_owner": "org", "repository_name": "app", "default_branch": "main",
          "production_environments": ["production"], "deploy_workflow": "Deploy"}


def service(github=None, docs=(), config=CONFIG):
    return DeploymentService(github_client=github or FakeGitHub(), repository=FakeRepo(docs),
                             configs=FakeRepo([{"id": "cfg", **config}]))


def deployment_event(gh_id, sha, env="production", ref="main", created="2026-11-02T09:00:00Z", project="P", **extra):
    return SimpleNamespace(project_id=project, repository="org/app", event_action="created", payload={
        "deployment": {"id": gh_id, "sha": sha, "ref": ref, "environment": env, "created_at": created,
                       "creator": {"login": "dev1"}, **extra}})


def status_event(gh_id, sha, state, at, env="production", ref="main"):
    return SimpleNamespace(project_id="P", repository="org/app", event_action="created", payload={
        "deployment": {"id": gh_id, "sha": sha, "ref": ref, "environment": env, "created_at": at},
        "deployment_status": {"state": state, "created_at": at, "updated_at": at}})


def commit(sha, date_):
    return {"sha": sha, "commit": {"committer": {"date": date_}}}


# ── incidents ─────────────────────────────────────────────────────

@pytest.fixture
def incidents():
    svc = IncidentService()
    svc.incidents = FakeRepo()
    svc.deployments = FakeRepo([{"id": "D1", "project_id": "P"}, {"id": "DX", "project_id": "OTHER"}])
    return svc


def test_create_incident_linked_to_deployment_is_caused_by_change(incidents):
    inc = run(incidents.create(IncidentCreate(project_id="P", title="Login down", caused_by_deployment_id="D1"), "E1"))
    assert inc["id"].startswith("INC-") and inc["status"] == "open" and inc["cause"] == "change"
    assert inc["started_at"] and inc["resolved_at"] is None and inc["created_by"] == "E1"
    plain = run(incidents.create(IncidentCreate(project_id="P", title="Slow"), None))
    assert plain["cause"] == "unknown"


def test_incident_deployment_must_exist_in_same_project(incidents):
    with pytest.raises(IncidentError, match="different project"):
        run(incidents.create(IncidentCreate(project_id="P", title="x", caused_by_deployment_id="DX"), None))
    with pytest.raises(IncidentError, match="not found"):
        run(incidents.create(IncidentCreate(project_id="P", title="x", caused_by_deployment_id="NOPE"), None))
    with pytest.raises(IncidentError, match="ISO-8601"):
        run(incidents.create(IncidentCreate(project_id="P", title="x", started_at="yesterday"), None))


def test_incident_status_flow(incidents):
    inc = run(incidents.create(IncidentCreate(project_id="P", title="Errors"), None))
    run(incidents.update(inc["id"], IncidentUpdate(status="investigating")))
    resolved = run(incidents.update(inc["id"], IncidentUpdate(status="resolved")))
    assert resolved["resolved_at"]
    reopened = run(incidents.update(inc["id"], IncidentUpdate(status="investigating")))
    assert reopened["resolved_at"] is None                         # recovery not over
    closed = run(incidents.update(inc["id"], IncidentUpdate(status="closed")))
    assert closed["closed_at"] and closed["resolved_at"]           # closing sets resolved_at too
    with pytest.raises(IncidentError, match="Cannot move"):
        run(incidents.update(inc["id"], IncidentUpdate(status="open")))
    with pytest.raises(LookupError):
        run(incidents.update("INC-NONE", IncidentUpdate(status="resolved")))


def test_linking_a_deployment_later_marks_cause(incidents):
    inc = run(incidents.create(IncidentCreate(project_id="P", title="x"), None))
    updated = run(incidents.update(inc["id"], IncidentUpdate(caused_by_deployment_id="D1", fixed_by_deployment_id="D1")))
    assert updated["cause"] == "change" and updated["fixed_by_deployment_id"] == "D1"


def test_list_incidents_newest_first(incidents):
    run(incidents.create(IncidentCreate(project_id="P", title="old", started_at="2026-11-01T00:00:00Z"), None))
    run(incidents.create(IncidentCreate(project_id="P", title="new", started_at="2026-11-05T00:00:00Z"), None))
    run(incidents.create(IncidentCreate(project_id="Q", title="other"), None))
    titles = [i["title"] for i in run(incidents.list_for_projects(["P"]))]
    assert titles == ["new", "old"] and run(incidents.list_for_projects([])) == []


# ── deployments from GitHub Deployments ───────────────────────────

def test_first_deployment_stores_head_commit():
    gh = FakeGitHub(commits={"s1": "2026-11-01T20:00:00Z"})
    svc = service(gh)
    run(svc.record_deployment(deployment_event(1, "s1")))
    doc = run(svc.record_deployment_status(status_event(1, "s1", "success", "2026-11-02T10:00:00Z")))
    assert doc["status"] == "success" and doc["production"] and doc["finished_at"] == "2026-11-02T10:00:00Z"
    assert doc["commits"] == [{"sha": "s1", "committed_at": "2026-11-01T20:00:00Z"}]
    assert doc["deployed_by"] == "dev1"          # the status event had no creator: not erased
    assert not doc["is_rollback"] and doc["previous_deployment_id"] is None


def test_next_deployment_takes_commits_from_compare():
    gh = FakeGitHub(compare={("s1", "s3"): {"status": "ahead", "commits": [commit("s2", "2026-11-03T08:00:00Z"),
                                                                             commit("s3", "2026-11-03T09:00:00Z")]}})
    svc = service(gh, docs=[{"id": "GH-org/app-1", "project_id": "P", "status": "success", "production": True,
                             "environment": "production", "sha": "s1", "finished_at": "2026-11-02T10:00:00Z"}])
    doc = run(svc.record_deployment_status(status_event(2, "s3", "success", "2026-11-03T12:00:00Z")))
    assert [c["sha"] for c in doc["commits"]] == ["s2", "s3"]
    assert doc["previous_deployment_id"] == "GH-org/app-1" and not doc["is_rollback"]
    assert gh.calls == [("compare", "org/app", "s1", "s3")]


def test_rollback_detected_when_deployed_commit_is_older():
    gh = FakeGitHub(compare={("s3", "s1"): {"status": "behind", "commits": []}})
    svc = service(gh, docs=[{"id": "GH-org/app-2", "project_id": "P", "status": "success", "production": True,
                             "environment": "production", "sha": "s3", "finished_at": "2026-11-03T12:00:00Z"}])
    doc = run(svc.record_deployment_status(status_event(3, "s1", "success", "2026-11-03T13:00:00Z")))
    assert doc["is_rollback"] and doc["rolled_back_deployment_id"] == "GH-org/app-2" and doc["commits"] == []


def test_redeploy_of_same_commit_has_no_new_commits():
    gh = FakeGitHub()
    svc = service(gh, docs=[{"id": "GH-org/app-2", "project_id": "P", "status": "success", "production": True,
                             "environment": "production", "sha": "s3", "finished_at": "2026-11-03T12:00:00Z"}])
    doc = run(svc.record_deployment_status(status_event(4, "s3", "success", "2026-11-04T09:00:00Z")))
    assert doc["commits"] == [] and not doc["is_rollback"] and gh.calls == []


def test_non_production_failures_and_out_of_order_statuses():
    gh = FakeGitHub()
    svc = service(gh)
    staging = run(svc.record_deployment_status(status_event(5, "s9", "success", "2026-11-04T09:00:00Z", env="staging")))
    assert staging["production"] is False and "commits" not in staging and gh.calls == []
    failed = run(svc.record_deployment_status(status_event(6, "s9", "failure", "2026-11-04T10:00:00Z")))
    assert failed["status"] == "failure" and failed["finished_at"] == "2026-11-04T10:00:00Z"
    late = run(svc.record_deployment_status(status_event(6, "s9", "in_progress", "2026-11-04T09:30:00Z")))
    assert late["status"] == "failure"                               # not reopened by a late event
    assert run(svc.record_deployment_status(status_event(6, "s9", "inactive", "2026-11-05T00:00:00Z"))) is None
    assert run(svc.record_deployment(deployment_event(7, "s9", project=None))) is None


def test_hotfix_branch_is_marked():
    doc = run(service().record_deployment(deployment_event(8, "s5", ref="hotfix/login")))
    assert doc["is_hotfix"] and doc["status"] == "in_progress"


def test_github_failure_keeps_the_deployment():
    svc = service(FakeGitHub(fail=True))
    doc = run(svc.record_deployment_status(status_event(9, "s1", "success", "2026-11-02T10:00:00Z")))
    assert doc["status"] == "success" and doc["commits"] == [] and "GitHub unavailable" in doc["commits_error"]


# ── deployments from a deploy workflow ────────────────────────────

def workflow_event(run_id, name="Deploy", branch="main", conclusion="success", sha="w1"):
    return SimpleNamespace(project_id="P", repository="org/app", event_action="completed", payload={
        "workflow_run": {"id": run_id, "name": name, "head_branch": branch, "head_sha": sha, "status": "completed",
                         "conclusion": conclusion, "run_started_at": "2026-11-05T09:00:00Z",
                         "updated_at": "2026-11-05T09:10:00Z", "actor": {"login": "ci-user"}}})


def test_deploy_workflow_runs_become_deployments():
    gh = FakeGitHub(commits={"w1": "2026-11-05T08:00:00Z"})
    svc = service(gh)
    doc = run(svc.record_workflow_run(workflow_event(1)))
    assert doc["source"] == "workflow_run" and doc["status"] == "success" and doc["production"]
    assert doc["deployed_by"] == "ci-user" and doc["commits"][0]["sha"] == "w1"
    assert run(svc.record_workflow_run(workflow_event(2, conclusion="failure")))["status"] == "failure"
    assert run(svc.record_workflow_run(workflow_event(3, conclusion="cancelled"))) is None
    assert run(svc.record_workflow_run(workflow_event(4, branch="feature/x"))) is None
    assert run(svc.record_workflow_run(workflow_event(5, name="Tests"))) is None
    unconfigured = service(config={**CONFIG, "deploy_workflow": None})
    assert run(unconfigured.record_workflow_run(workflow_event(6))) is None


# ── repository matching ───────────────────────────────────────────

@pytest.mark.parametrize("value, key", [
    ("Org/App", "org/app"), ("https://github.com/org/app.git", "org/app"), ("git@github.com:org/app.git", "org/app"),
    ("https://github.com/org/app/tree/main", "org/app"), ("https://github.com/org/app-v2", "org/app-v2"), ("org", ""),
])
def test_repository_key(value, key):
    assert repository_key(value) == key


def test_project_matching_is_exact(monkeypatch):
    class FakeCollection:
        def find(self, query, projection=None):
            return SimpleNamespace(to_list=lambda length=None: _async([
                {"project_id": "P-CFG", "repository_owner": "org", "repository_name": "service"}]))

    async def _async_value(value):
        return value

    def _async(value):
        return _async_value(value)

    monkeypatch.setattr(core.database, "col", lambda name: FakeCollection())
    processor = WebhookEventProcessor()
    processor.project_repo = FakeRepo([{"id": "P-URL", "code_repo_url": "https://github.com/org/app-v2"}])
    assert run(processor._match_repository_to_project("org/service")) == "P-CFG"
    assert run(processor._match_repository_to_project("org/app-v2")) == "P-URL"
    assert run(processor._match_repository_to_project("org/app")) is None      # old substring test matched P-URL


# ── Deployments page shape ────────────────────────────────────────

def test_deployments_page_shape():
    row = for_deployments_page({"id": "D", "repository": "org/app", "sha": "abcdef123", "status": "failure",
                                "finished_at": "2026-11-05T09:10:00Z", "production": True,
                                "previous_deployment_id": "C"})
    assert (row["service"], row["version"], row["status"], row["deployed_at"]) == ("org/app", "abcdef1", "failed",
                                                                                    "2026-11-05T09:10:00Z")
    assert row["rollback_available"] and for_deployments_page({"status": "in_progress"})["status"] == "pending"


# ── end to end ────────────────────────────────────────────────────

def test_webhook_stream_to_dora_report():
    """Five production deployments in a week, one rolled back, one causing an incident."""
    gh = FakeGitHub(
        commits={"c1": "2026-11-01T22:00:00Z"},
        compare={
            ("c1", "c3"): {"status": "ahead", "commits": [commit("c2", "2026-11-02T20:00:00Z"), commit("c3", "2026-11-03T06:00:00Z")]},
            ("c3", "c4"): {"status": "ahead", "commits": [commit("c4", "2026-11-04T08:00:00Z")]},
            ("c4", "c3"): {"status": "behind", "commits": []},
            ("c3", "c5"): {"status": "ahead", "commits": [commit("c5", "2026-11-05T09:00:00Z")]},
        },
    )
    svc = service(gh)
    steps = [(1, "c1", "2026-11-02T10:00:00Z"), (2, "c3", "2026-11-03T10:00:00Z"), (3, "c4", "2026-11-04T10:00:00Z"),
             (4, "c3", "2026-11-04T11:00:00Z"), (5, "c5", "2026-11-05T12:00:00Z")]
    for gh_id, sha, at in steps:
        run(svc.record_deployment(deployment_event(gh_id, sha, created=at)))
        run(svc.record_deployment_status(status_event(gh_id, sha, "in_progress", at)))
        run(svc.record_deployment_status(status_event(gh_id, sha, "success", at)))
    run(svc.record_deployment_status(status_event(6, "c6", "failure", "2026-11-06T10:00:00Z")))   # failed attempt
    incidents = [{"id": "I1", "caused_by_deployment_id": "GH-org/app-5", "started_at": "2026-11-05T13:00:00Z",
                  "resolved_at": "2026-11-05T15:00:00Z"}]
    report = dora_report(list(svc.deployments.docs.values()), incidents, date(2026, 11, 2), date(2026, 11, 8))

    assert report["deployment_frequency"]["deployments"] == 5 and report["deployment_frequency"]["per_week"] == 5.0
    # lead times: c1 12h, c2 14h, c3 4h, c4 2h, c5 3h -> median 4h
    assert report["change_lead_time_hours"]["n"] == 5 and report["change_lead_time_hours"]["median"] == 4.0
    # failed changes: deployment 3 (rolled back by 4) and 5 (incident) -> 2 of 5
    assert report["change_fail_rate"]["percent"] == 40.0
    assert report["change_fail_rate"]["failed_changes"] == ["GH-org/app-3", "GH-org/app-5"]
    assert report["failed_deployment_recovery_hours"]["median"] == 2.0
    assert report["deployment_rework_rate"] == 20.0                     # the rollback
    assert report["deployment_failure_rate"] == round(100 / 6, 2)       # 1 failed attempt of 6
    # recovery 2 hours: under one day -> "high" (2023 clusters)
    assert report["levels"] == {"deployment_frequency": "high", "change_lead_time": "elite",
                                "change_fail_rate": "low", "failed_deployment_recovery_time": "high"}
