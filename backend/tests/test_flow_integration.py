"""
Integration of the PR and flow metrics: SprintFlowService (start, complete,
scope changes, flow report), the fixed RiskEngine.analyze_sprint and the
GitHub sync fields. Uses small in-memory stand-ins for MongoDB.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import domain.services.sprint_flow_service as flow_module
from domain.services.github_sync_service import pr_flow_fields
from domain.services.sprint_flow_service import SprintFlowService, SprintTransitionError
from intelligence.risk_engine import RiskEngine

UTC = timezone.utc
NOW = datetime.now(UTC)


def iso(dt):
    return dt.isoformat()


# ── in-memory stand-ins ───────────────────────────────────────────

def _matches(doc, query):
    for key, cond in query.items():
        if isinstance(cond, dict) and "$in" in cond:
            if doc.get(key) not in cond["$in"]:
                return False
        elif doc.get(key) != cond:
            return False
    return True


class FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    async def to_list(self, length=None):
        return [dict(d) for d in self.docs]


class FakeCollection:
    def __init__(self):
        self.docs = []

    def find(self, query, projection=None):
        return FakeCursor([d for d in self.docs if _matches(d, query)])

    async def insert_many(self, docs):
        self.docs.extend(dict(d) for d in docs)


class FakeRepo:
    def __init__(self, docs):
        self.docs = {d["id"]: dict(d) for d in docs}

    async def find_by_id(self, doc_id):
        doc = self.docs.get(doc_id)
        return dict(doc) if doc else None

    async def find_by_sprint(self, sprint_id):
        return [dict(d) for d in self.docs.values() if d.get("sprint_id") == sprint_id]

    async def find_by_project(self, project_id):
        return [dict(d) for d in self.docs.values() if d.get("project_id") == project_id]

    async def update(self, query, update):
        doc = self.docs.get(query["id"])
        if doc is None:
            return False
        doc.update(update)
        return True


@pytest.fixture
def world(monkeypatch):
    """A project with one finished sprint (S0) and one planned sprint (S1)."""
    started = NOW - timedelta(days=4)
    sprints = FakeRepo([
        {"id": "S0", "project_id": "P", "status": "completed", "start_date": iso(NOW - timedelta(days=20)),
         "end_date": iso(NOW - timedelta(days=6)), "committed_points": 12, "completed_points": 10},
        {"id": "S1", "project_id": "P", "status": "planning", "start_date": iso(started),
         "end_date": iso(NOW + timedelta(days=6))},
    ])
    stories = FakeRepo([
        {"id": "ST1", "sprint_id": "S1", "status": "done", "points": 5, "created_at": iso(NOW - timedelta(days=9))},
        {"id": "ST2", "sprint_id": "S1", "status": "in_progress", "points": 3, "created_at": iso(NOW - timedelta(days=9))},
        {"id": "ST0", "sprint_id": "S0", "status": "done", "points": 4, "created_at": iso(NOW - timedelta(days=19))},
    ])
    tasks = FakeRepo([
        {"id": "T1", "sprint_id": "S1", "status": "todo"},                     # standalone: 1 point
        {"id": "T2", "sprint_id": "S1", "status": "done", "story_id": "ST1"},  # inside a story: not counted
    ])
    transitions = FakeCollection()
    transitions.docs = [
        {"item_id": "ST1", "from_status": "todo", "to_status": "in_progress", "created_at": iso(NOW - timedelta(days=3))},
        {"item_id": "ST1", "from_status": "in_progress", "to_status": "done", "created_at": iso(NOW - timedelta(days=1))},
        {"item_id": "ST2", "from_status": "todo", "to_status": "in_progress", "created_at": iso(NOW - timedelta(days=2))},
        {"item_id": "ST0", "from_status": "todo", "to_status": "in_progress", "created_at": iso(NOW - timedelta(days=12))},
        {"item_id": "ST0", "from_status": "in_progress", "to_status": "done", "created_at": iso(NOW - timedelta(days=10))},
    ]
    scope = FakeCollection()
    collections = {"transitions": transitions, "sprint_scope_changes": scope}
    monkeypatch.setattr(flow_module, "col", lambda name: collections[name])

    service = SprintFlowService()
    service.sprint_repo, service.story_repo, service.task_repo = sprints, stories, tasks
    return service, sprints, scope


def run(coro):
    return asyncio.run(coro)


# ── start / complete ──────────────────────────────────────────────

def test_start_sprint_snapshots_committed_scope(world):
    service, sprints, _ = world
    started = run(service.start_sprint("S1"))
    assert started["status"] == "active" and started["started_at"]
    assert started["committed_points"] == 5 + 3 + 1             # stories + standalone task
    assert sorted(started["committed_item_ids"]) == ["ST1", "ST2", "T1"]
    assert sprints.docs["S1"]["committed_points"] == 9
    with pytest.raises(SprintTransitionError):
        run(service.start_sprint("S1"))                          # already active


def test_only_one_active_sprint_per_project(world):
    service, sprints, _ = world
    sprints.docs["S2"] = {"id": "S2", "project_id": "P", "status": "planning"}
    run(service.start_sprint("S1"))
    with pytest.raises(SprintTransitionError, match="already active"):
        run(service.start_sprint("S2"))


def test_complete_sprint_stores_velocity(world):
    service, sprints, _ = world
    with pytest.raises(SprintTransitionError):
        run(service.complete_sprint("S1"))                       # not started yet
    run(service.start_sprint("S1"))
    done = run(service.complete_sprint("S1"))
    assert (done["status"], done["completed_points"], done["velocity"]) == ("completed", 5, 5)
    assert done["completion_pct"] == round(100 * 5 / 9, 2)
    with pytest.raises(LookupError):
        run(service.complete_sprint("nope"))


# ── scope changes and flow report ─────────────────────────────────

def test_record_scope_change(world):
    service, _, scope = world
    run(service.record_scope_change({"id": "T9", "points": 2}, "task", None, "S1", changed_by="E1"))
    run(service.record_scope_change({"id": "T9", "points": 2}, "task", "S1", "S0"))
    run(service.record_scope_change({"id": "T9"}, "task", "S0", "S0"))           # unchanged: no-op
    actions = [(d["sprint_id"], d["action"], d["points"]) for d in scope.docs]
    assert actions == [("S1", "added", 2), ("S1", "removed", 2), ("S0", "added", 2)]


def test_flow_report_measures_scope_creep_velocity_and_forecast(world):
    service, sprints, scope = world
    run(service.start_sprint("S1"))
    sprints.docs["S1"]["started_at"] = iso(NOW - timedelta(days=4))   # started 4 days ago
    scope.docs.append({"sprint_id": "S1", "item_id": "ST3", "action": "added", "points": 3,
                       "at": iso(NOW - timedelta(days=2))})
    report = run(service.flow_report("S1", now=NOW))
    assert report["scope_creep"]["added_points"] == 3 and report["scope_creep"]["creep_percent"] == round(300 / 9, 2)
    assert report["velocity"]["completed_points"] == [10]            # from the finished sprint S0
    assert report["completion"]["done_points"] == 5
    assert report["cycle_hours"]["n"] == 1 and report["cycle_hours"]["median"] == 48.0
    assert report["forecast"]["remaining_items"] == 2 and report["forecast"]["method"] == "monte_carlo"
    assert run(service.flow_report("missing")) is None


# ── the fixed RiskEngine.analyze_sprint ───────────────────────────

def test_analyze_sprint_counts_done_and_points(world, monkeypatch):
    service, sprints, _ = world
    run(service.start_sprint("S1"))
    monkeypatch.setattr(flow_module.SprintFlowService, "__init__",
                        lambda self: setattr(self, "sprint_repo", sprints) or setattr(self, "story_repo", service.story_repo)
                        or setattr(self, "task_repo", service.task_repo))

    async def level(self, score):
        return "LOW"

    monkeypatch.setattr(RiskEngine, "_classify_risk_level", level)
    engine = RiskEngine()
    engine.sprint_repo = sprints
    evidence = run(engine.analyze_sprint("S1"))
    m = evidence["metrics"]
    # before the fix: completed_stories 0, total_points 0 (wrong status and field names)
    assert (m["total_stories"], m["completed_stories"], m["total_points"], m["completed_points"]) == (3, 1, 9, 5)
    assert evidence["flow"]["completion"]["by_points"] == round(500 / 9, 2)


def test_analyze_sprint_with_posted_numbers_has_no_flow(world, monkeypatch):
    _, sprints, _ = world

    async def level(self, score):
        return "LOW"

    monkeypatch.setattr(RiskEngine, "_classify_risk_level", level)
    engine = RiskEngine()
    engine.sprint_repo = sprints
    evidence = run(engine.analyze_sprint("S1", stories_data={"total_stories": 4, "completed_stories": 1,
                                                              "total_points": 10, "completed_points": 2}))
    assert "flow" not in evidence and evidence["metrics"]["total_points"] == 10


# ── GitHub sync fields ────────────────────────────────────────────

def test_pr_flow_fields_from_github_data():
    pr = {"user": {"login": "alice"}, "closed_at": "2026-11-04T10:00:00Z"}
    files = [{"filename": "src/a.py", "additions": 80, "deletions": 20},
             {"filename": "package-lock.json", "additions": 500, "deletions": 300}]
    reviews = [{"user": {"login": "alice", "type": "User"}, "state": "APPROVED", "submitted_at": "2026-11-02T09:00:00Z"},
               {"user": {"login": "bob", "type": "User"}, "state": "CHANGES_REQUESTED", "submitted_at": "2026-11-02T12:00:00Z"}]
    fields = pr_flow_fields(pr, files, reviews)
    assert (fields["lines_added"], fields["lines_deleted"], fields["generated_lines_excluded"]) == (80, 20, 800)
    assert fields["size_bucket"] == "M" and fields["closed_at"] == "2026-11-04T10:00:00Z"
    assert fields["first_review_at"] == "2026-11-02T12:00:00Z"     # the author's self-approval is ignored
    assert fields["review_status"] == "changes_requested" and fields["review_rounds"] == 1
    assert "review_status" not in pr_flow_fields(pr, files, None)    # reviews unavailable: keep old values
