"""
PR risk model: git history reading, SZZ labelling, Kamei features, the two
pure-Python models, evaluation metrics, training/prediction bundle, and the
RiskEngine integration (rule fixes + model with fallback).

The SZZ tests build a tiny real git repository in a temp folder.
"""

import asyncio
import math
import os
import random
import shutil
import subprocess

import pytest

from intelligence.risk_model.features import FEATURES, HistoryState, build_dataset, entropy
from intelligence.risk_model.git_history import Commit, FileChange, is_source_file, parse_log, read_commits, rename_target
from intelligence.risk_model.model import (
    BoostedStumps, LogisticModel, auc, classification, load_model, recall_at_effort, sigmoid,
)
from intelligence.risk_model.predictor import MIN_AUC, predict, train_from_rows
from intelligence.risk_model.szz import deleted_lines, is_fix_message, run_szz, to_ranges


def run(coro):
    return asyncio.run(coro)


# ── git history ────────────────────────────────────────────────────────
class TestGitHistory:
    def test_rename_target(self):
        assert rename_target("pkg/{old => new}/f.py") == "pkg/new/f.py"
        assert rename_target("pkg/{ => sub}/f.py") == "pkg/sub/f.py"
        assert rename_target("old.py => new.py") == "new.py"
        assert rename_target("plain.py") == "plain.py"

    def test_is_source_file(self):
        assert is_source_file("httpx/_client.py")
        assert not is_source_file("tests/test_client.py")
        assert not is_source_file("httpx/test_x.py")
        assert not is_source_file("docs/conf.py")
        assert not is_source_file("README.md")
        # vendored third-party code
        assert not is_source_file("requests/packages/urllib3/poolmanager.py")
        assert not is_source_file("pkg/_vendor/six.py")
        # top-level "packages/" is a monorepo root, kept
        assert is_source_file("packages/core/api.py")

    def test_parse_log(self):
        text = ("\x1eabc\x1fp1 p2\x1fA@X.org\x1f100\x1fMerge pull request #1\n\n"
                "3\t1\tpkg/a.py\n-\t-\timg.png\n2\t0\tpkg/{x => y}/b.py\n"
                "\x1edef\x1fabc\x1fb@x.org\x1f200\x1ffix: thing\n\n1\t1\tpkg/a.py\n")
        commits = parse_log(text)
        assert [c.sha for c in commits] == ["abc", "def"]
        assert commits[0].is_merge and commits[0].author == "a@x.org"
        assert commits[0].files == [FileChange("pkg/a.py", 3, 1), FileChange("pkg/y/b.py", 2, 0)]
        assert commits[1].parent == "abc" and not commits[1].is_merge


# ── SZZ ────────────────────────────────────────────────────────────────
class TestSZZParts:
    def test_fix_messages(self):
        assert is_fix_message("Fix crash when url is empty")
        assert is_fix_message("bugfix: handle None")
        assert is_fix_message("Fixes #123")
        assert not is_fix_message("Fix typo in docs")
        assert not is_fix_message("fix flake8 warnings")
        assert not is_fix_message("Add streaming support")
        assert not is_fix_message("prefix handling")   # word boundary

    def test_deleted_lines_skip_blank_and_comments(self):
        diff = ("diff --git a/pkg/a.py b/pkg/a.py\n--- a/pkg/a.py\n+++ b/pkg/a.py\n"
                "@@ -3,4 +3,1 @@\n-x = 1\n-\n-# note\n-y = 2\n+z = 3\n"
                "@@ -20 +17,0 @@\n-return x\n"
                "diff --git a/pkg/new.py b/pkg/new.py\n--- /dev/null\n+++ b/pkg/new.py\n@@ -0,0 +1 @@\n+a = 1\n")
        assert deleted_lines(diff) == {"pkg/a.py": [3, 6, 20]}

    def test_to_ranges(self):
        assert to_ranges([5, 3, 4, 9, 10, 1]) == [(1, 1), (3, 5), (9, 10)]


def _git(repo, *args, when=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_COMMITTER_NAME="t")
    if when:
        env.update(GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    subprocess.run(["git", "-C", str(repo), "-c", "commit.gpgsign=false", *args],
                   check=True, capture_output=True, env=env)


def _commit(repo, email, message, when, files):
    for path, content in files.items():
        full = repo / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", f"user.email={email}", "-c", "user.name=t", "commit", "-q", "-m", message, when=when)


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
class TestSZZOnRealRepository:
    @pytest.fixture
    def repo(self, tmp_path):
        r = tmp_path / "repo"
        r.mkdir()
        _git(r, "init", "-q", "-b", "main")
        _commit(r, "ann@x.org", "Initial version", "2024-01-01T10:00:00",
                {"pkg/calc.py": "def add(a, b):\n    return a + b\n\n\ndef div(a, b):\n    return a * b\n"})
        _commit(r, "bob@x.org", "Add helper", "2024-01-05T10:00:00",
                {"pkg/util.py": "def twice(x):\n    return 2 * x\n"})
        _commit(r, "bob@x.org", "Update docs", "2024-01-06T10:00:00", {"docs/index.md": "hello\n"})
        _commit(r, "cat@x.org", "Fix wrong division result", "2024-02-01T10:00:00",
                {"pkg/calc.py": "def add(a, b):\n    return a + b\n\n\ndef div(a, b):\n    return a / b\n"})
        return r

    def test_labels_the_introducing_change(self, repo):
        changes = read_commits(str(repo))
        assert [c.subject for c in changes] == ["Initial version", "Add helper", "Update docs",
                                                "Fix wrong division result"]
        result = run_szz(str(repo), changes)
        assert result.buggy == {changes[0].sha}
        assert result.to_dict() == {"buggy_changes": 1, "fixes": 1, "fixes_traced": 1, "errors": 0}

    def test_dataset_rows_and_features(self, repo):
        changes = read_commits(str(repo))
        rows, state = build_dataset(changes, run_szz(str(repo), changes).buggy)
        assert len(rows) == 3                         # the docs-only change is not product code
        first, _, fix = rows
        assert first.buggy and not fix.buggy
        assert fix.features["FIX"] == 1.0
        assert fix.features["LT"] == 6.0              # calc.py had 6 lines before the fix
        assert fix.features["NDEV"] == 1.0 and fix.features["NUC"] == 1.0
        assert fix.features["EXP"] == 0.0             # cat's first change
        assert fix.features["AGE"] == pytest.approx(31.0, abs=0.01)
        assert state.file_size["pkg/calc.py"] == 6


# ── features ───────────────────────────────────────────────────────────
class TestFeatures:
    def test_entropy(self):
        assert entropy([10]) == 0.0
        assert entropy([5, 5]) == 1.0
        assert 0 < entropy([9, 1]) < 1

    def test_history_state_and_round_trip(self):
        st = HistoryState()
        day = 86400
        st.apply("c1", [("pkg/a.py", 10, 0), ("lib/b.py", 4, 0)], "ann", 0)
        st.apply("c2", [("pkg/a.py", 2, 1)], "bob", 10 * day)
        f = st.features([("pkg/a.py", 3, 3), ("pkg/c.py", 5, 0)], "ann", 20 * day, fix=False)
        assert f["LA"] == 8 and f["LD"] == 3 and f["NF"] == 2
        assert f["LT"] == 11                    # a.py: 10 + 2 - 1
        assert f["NS"] == 1 and f["ND"] == 1    # both under pkg/
        assert f["NDEV"] == 2 and f["NUC"] == 2
        assert f["AGE"] == pytest.approx(10.0)  # only a.py has history
        assert f["EXP"] == 1 and f["SEXP"] == 1
        assert f["REXP"] == pytest.approx(1 / (1 + 20 / 365.25), abs=1e-4)
        assert set(f) == set(FEATURES)
        again = HistoryState.from_dict(st.to_dict()).features([("pkg/a.py", 3, 3), ("pkg/c.py", 5, 0)],
                                                              "ann", 20 * day, fix=False)
        assert again == f


# ── models and metrics ─────────────────────────────────────────────────
def _synthetic(n=400, seed=7):
    rng = random.Random(seed)
    rows, y = [], []
    for _ in range(n):
        la = rng.lognormvariate(3, 1.2)
        exp_ = rng.randint(0, 200)
        logit = -2.5 + 0.9 * math.log1p(la) - 0.6 * math.log1p(exp_) * 0.5 + rng.gauss(0, 0.3)
        row = {f: 0.0 for f in FEATURES}
        row.update(LA=round(la), LD=round(la / 3), NF=1 + rng.randint(0, 4), EXP=exp_)
        rows.append(row)
        y.append(1 if rng.random() < sigmoid(logit) else 0)
    return rows, y


class TestModels:
    def test_auc_and_classification(self):
        assert auc([0.1, 0.4, 0.35, 0.8], [0, 0, 1, 1]) == 0.75
        assert auc([1, 1, 1], [0, 1, 0]) == 0.5       # ties count as one half
        assert auc([0.2, 0.3], [1, 1]) is None
        c = classification([0.9, 0.6, 0.2, 0.7], [1, 0, 1, 1], 0.5)
        assert c == {"precision": round(2 / 3, 4), "recall": round(2 / 3, 4), "f1": round(2 / 3, 4), "flagged": 3}

    def test_recall_at_effort(self):
        # total effort 100, budget 20: take 'a' (10), skip 'b' (60, too big), take 'c' (10)
        scores, y, effort = [0.9, 0.8, 0.7, 0.1], [1, 1, 0, 1], [10, 60, 10, 20]
        assert recall_at_effort(scores, y, effort, 0.2) == pytest.approx(1 / 3)

    def test_logistic_learns_and_explains_exactly(self):
        rows, y = _synthetic()
        m = LogisticModel().fit(rows, y)
        assert auc([m.predict_proba(r) for r in rows], y) > 0.7
        assert m.weights["LA"] > 0
        r = rows[3]
        logit = math.log(m.predict_proba(r) / (1 - m.predict_proba(r)))
        assert m.bias + sum(m.log_odds_parts(r).values()) == pytest.approx(logit, abs=1e-9)
        clone = load_model(m.to_dict())
        assert clone.predict_proba(r) == pytest.approx(m.predict_proba(r))
        assert m.explain(r, top=2)[0]["feature"] in FEATURES

    def test_logistic_is_deterministic(self):
        rows, y = _synthetic()
        assert LogisticModel().fit(rows, y).to_dict() == LogisticModel().fit(rows, y).to_dict()

    def test_stumps_additive_explanations(self):
        rows, y = _synthetic()
        m = BoostedStumps(rounds=60).fit(rows, y)
        assert auc([m.predict_proba(r) for r in rows], y) > 0.7
        r = rows[5]
        logit = math.log(m.predict_proba(r) / (1 - m.predict_proba(r)))
        offsets = sum(m.offsets.values())
        assert m.base + offsets + sum(m.log_odds_parts(r).values()) == pytest.approx(logit, abs=1e-9)
        clone = load_model(m.to_dict())
        assert clone.predict_proba(r) == pytest.approx(m.predict_proba(r))

    def test_unknown_kind(self):
        with pytest.raises(ValueError):
            load_model({"kind": "nope"})


# ── training bundle and prediction ─────────────────────────────────────
class TestPredictor:
    def _bundle(self, n=500):
        rows, y = _synthetic(n)
        bundle = train_from_rows([(i, r, v) for i, (r, v) in enumerate(zip(rows, y))])
        bundle.update({"state": HistoryState().to_dict(), "suffixes": [".py"]})
        return bundle

    def test_train_selects_and_reports(self):
        b = self._bundle()
        ev = b["evaluation"]
        assert ev["split"] == {"train": 300, "test": 150, "dropped_newest": 50}
        assert set(ev["models"]) == {"size_logistic", "logistic_regression", "boosted_stumps"}
        assert ev["selected"] in ev["models"] and ev["auc"] == max(m["auc"] for m in ev["models"].values())
        assert b["usable"] == (ev["auc"] >= MIN_AUC)

    def test_predict_product_code_only(self):
        b = self._bundle()
        b["usable"] = True
        out = predict(b, [("pkg/a.py", 400, 50), ("tests/test_a.py", 900, 0)], "ann@x.org", 0, ["Add feature"])
        assert 0 < out["probability"] < 1
        assert out["features"]["LA"] == 400          # test file ignored
        assert all(f["contribution"] > 0 for f in out["factors"])
        assert predict(b, [("docs/x.md", 10, 0)], "ann@x.org") is None

    def test_unusable_bundle_gives_none(self):
        b = self._bundle()
        b["usable"] = False
        assert predict(b, [("pkg/a.py", 400, 50)], "ann@x.org") is None
        assert predict({}, [("pkg/a.py", 1, 0)], "x") is None

    def test_too_few_bugs_not_usable(self):
        rows = [(i, {f: float(i % 7) for f in FEATURES}, 1 if i % 50 == 0 else 0) for i in range(300)]
        assert train_from_rows(rows)["usable"] is False


# ── risk engine integration ────────────────────────────────────────────
class _FakePRRepo:
    def __init__(self, doc):
        self.doc = doc

    async def find_by_id(self, pr_id):
        return dict(self.doc) if self.doc else None


@pytest.fixture
def engine(monkeypatch):
    import intelligence.risk_engine as re_mod

    monkeypatch.setattr(re_mod, "PRRepository", lambda: _FakePRRepo(None))
    monkeypatch.setattr(re_mod, "SprintRepository", lambda: None)
    monkeypatch.setattr(re_mod, "StoryRepository", lambda: None)
    monkeypatch.setattr(re_mod, "get_risk_config_service", lambda: None)
    eng = re_mod.RiskEngine()

    async def classify(score, project_id=None):
        from intelligence.rules.risk_rules import RiskRules
        return RiskRules.classify_risk_level(score)

    eng._classify_risk_level = classify
    return eng


class TestRiskEngineFixes:
    def test_unknown_tests_add_no_risk(self, engine):
        ev = run(engine.analyze_pull_request("pr1", files_changed=3, lines_added=10, lines_deleted=2))
        assert ev["risk_score"] == 0 and "No passing tests" not in ev["risk_factors"]
        assert ev["metrics"]["test_results_known"] is False and ev["scoring_method"] == "rules"

    def test_reported_zero_passing_still_counts(self, engine):
        ev = run(engine.analyze_pull_request("pr1", files_changed=3, lines_added=10, lines_deleted=2,
                                             tests_passed=0, tests_failed=0))
        assert ev["risk_score"] == 15 and "No passing tests" in ev["risk_factors"]

    def test_lines_loaded_from_database(self, engine):
        engine.pr_repo = _FakePRRepo({"files_changed_count": 2, "commit_count": 1,
                                      "lines_added": 900, "lines_deleted": 200})
        ev = run(engine.analyze_pull_request("pr1"))
        assert ev["metrics"]["lines_added"] == 900
        assert ev["risk_score"] == 20 and "High code churn (>1000 lines)" in ev["risk_factors"]


class TestRiskEngineModel:
    def _patch(self, monkeypatch, prediction):
        import domain.services.risk_model_service as svc

        class FakeService:
            def __init__(self, *a, **k):
                pass

            async def score(self, project_id, files, author, timestamp=None, messages=()):
                return prediction

        monkeypatch.setattr(svc, "RiskModelService", FakeService)

    def test_model_replaces_rule_score(self, engine, monkeypatch):
        self._patch(monkeypatch, {"probability": 0.72, "model": "logistic_regression", "auc": 0.8,
                                  "factors": [{"feature": "LA", "label": "lines added", "value": 900.0,
                                               "contribution": 1.1}],
                                  "features": {"LA": 900.0}})
        ev = run(engine.analyze_pull_request("pr1", files_changed=3, lines_added=900, lines_deleted=0,
                                             project_id="p1", file_changes=[("pkg/a.py", 900, 0)],
                                             author_email="a@x.org"))
        assert ev["scoring_method"] == "ml" and ev["risk_score"] == 72 and ev["risk_level"] == "CRITICAL"
        assert ev["rule_score"] == 10
        assert ev["risk_factors"][0] == "Model: lines added (900)"
        assert ev["ml_prediction"]["probability"] == 0.72

    def test_falls_back_to_rules_without_model(self, engine, monkeypatch):
        self._patch(monkeypatch, None)
        ev = run(engine.analyze_pull_request("pr1", files_changed=3, lines_added=900, lines_deleted=0,
                                             project_id="p1", file_changes=[("pkg/a.py", 900, 0)]))
        assert ev["scoring_method"] == "rules" and ev["risk_score"] == 10 and "ml_prediction" not in ev


# ── service ────────────────────────────────────────────────────────────
class _FakeCollection:
    def __init__(self, docs=()):
        self.docs = [dict(d) for d in docs]

    async def find_one(self, query, projection=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                return dict(d)
        return None

    async def update_one(self, query, update, upsert=False):
        doc = next((d for d in self.docs if all(d.get(k) == v for k, v in query.items())), None)
        if doc is None and upsert:
            doc = dict(query)
            self.docs.append(doc)
        if doc is not None:
            doc.update(update.get("$set", {}))

    async def insert_one(self, doc):
        self.docs.append(dict(doc))


class TestRiskModelService:
    def _service(self, docs=()):
        from domain.services.risk_model_service import RiskModelService
        return RiskModelService(models=_FakeCollection(docs), history=_FakeCollection(), configs=_FakeCollection())

    def test_training_lock_and_stale_run(self):
        from datetime import datetime, timedelta, timezone
        svc = self._service()
        assert run(svc.mark_training("p1", "u1")) is True
        assert run(svc.mark_training("p1", "u1")) is False
        old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        svc.models.docs[0]["started_at"] = old
        assert run(svc.mark_training("p1", "u1")) is True

    def test_missing_config_fails_cleanly(self):
        svc = self._service()
        run(svc.train("p1"))
        assert svc.models.docs[0]["status"] == "failed"

    def test_score_uses_previous_model_while_retraining(self):
        rows, y = _synthetic(500)
        bundle = train_from_rows([(i, r, v) for i, (r, v) in enumerate(zip(rows, y))])
        bundle.update({"state": {}, "suffixes": [".py"], "usable": True})
        svc = self._service([{"project_id": "p1", "status": "training", "usable": True, "bundle": bundle}])
        out = run(svc.score("p1", [("pkg/a.py", 50, 5)], "a@x.org"))
        assert out and 0 < out["probability"] < 1
        assert run(svc.score(None, [("pkg/a.py", 50, 5)], "a")) is None

    def test_clone_rejects_unsafe_names(self):
        from domain.services.risk_model_service import clone_repository
        with pytest.raises(ValueError):
            clone_repository("owner", "../etc", "x")
        with pytest.raises(ValueError):
            clone_repository("-bad", "repo", "x")


def test_sync_inputs_for_model():
    from domain.services.github_sync_service import risk_model_inputs
    pr = {"created_at": "2024-03-01T12:00:00Z", "title": "Fix login"}
    files = [{"filename": "app/a.py", "additions": 5, "deletions": 1}]
    commits = [{"commit": {"author": {"email": "Dev@X.org"}, "message": "fix bug\n\nbody"}},
               {"commit": {"author": {"email": "dev@x.org"}, "message": "tidy"}}]
    out = risk_model_inputs("p1", pr, files, commits)
    assert out["author_email"] == "dev@x.org"
    assert out["file_changes"] == [("app/a.py", 5, 1)]
    assert out["commit_messages"] == ["fix bug", "tidy", "Fix login"]
    assert out["created_at"] == 1709294400
