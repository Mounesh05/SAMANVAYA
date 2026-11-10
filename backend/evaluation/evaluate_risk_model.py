"""
Evaluate SAMANVAYA's PR risk prediction on real open-source history.

For each repository (a local clone):
    1. read the changes that landed on the main branch (git_history)
    2. label bug-introducing changes with SZZ (szz)
    3. compute Kamei's 14 change metrics in time order (features)
    4. time-ordered split: train on the oldest 60%, test on the next 30%,
       DROP the newest 10% (they have had too little time to be found buggy)
    5. score the test changes with every method and compare

Methods
    rules v0 (as deployed)   current RiskEngine PR rules with the two bugs:
                             lines always 0 and +15 for "no passing tests"
                             on every PR (test results are never passed in)
    rules v0 (bugs fixed)    the same rules with real line counts, no +15
    size (LA+LD)             bigger change = riskier
    smallest first           1 / (LA+LD) (Yang et al. 2016 "ManualDown"),
                             a strong effort-aware baseline
    logistic, size only      model.LogisticModel on LA, LD, NF
    logistic regression      model.LogisticModel on all 14
    boosted stumps           model.BoostedStumps
    LightGBM (reference)     only with --lightgbm (needs the package)

Metrics on the test period
    AUC          ranking quality, 0.5 = random
    precision / recall / F1 for the method's own yes/no call
                 (rules: level MEDIUM or above, score >= 30; models: p >= 0.5)
    recall@20%   share of buggy changes found when reviewing from the highest
                 score down until 20% of all changed lines are read
    recall@20% per line   the same, ordered by score / lines (risk density,
                 the effort-aware ranking of Kamei et al. 2013)

    python evaluation/evaluate_risk_model.py --repos <clone> [<clone> ...]
           [--out evaluation/results/risk_model_evaluation.md] [--cache DIR] [--lightgbm]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intelligence.risk_model.features import FEATURES, ChangeRow, build_dataset  # noqa: E402
from intelligence.risk_model.git_history import read_commits  # noqa: E402
from intelligence.risk_model.model import (  # noqa: E402
    BoostedStumps, LogisticModel, auc, classification, recall_at_effort,
)
from intelligence.risk_model.szz import run_szz  # noqa: E402
from intelligence.rules import risk_rules as R  # noqa: E402

TRAIN, TEST = 0.6, 0.3


def rule_score(row: Dict[str, float], deployed: bool) -> float:
    """RiskEngine._build_simple_pr_evidence for a PR with no test or coverage data."""
    files = row["NF"]
    lines = 0.0 if deployed else row["LA"] + row["LD"]
    score = 0.0
    if files > R.PR_SIZE_LARGE_THRESHOLD:
        score += R.PR_SIZE_LARGE_RISK
    elif files > R.PR_SIZE_MEDIUM_THRESHOLD:
        score += R.PR_SIZE_MEDIUM_RISK
    elif files > R.PR_SIZE_SMALL_THRESHOLD:
        score += R.PR_SIZE_SMALL_RISK
    if lines > R.CHURN_HIGH_THRESHOLD:
        score += R.CHURN_HIGH_RISK
    elif lines > R.CHURN_MEDIUM_THRESHOLD:
        score += R.CHURN_MEDIUM_RISK
    if deployed:
        score += R.TEST_NONE_PASSING_RISK
    return min(score, 100.0)


def load_dataset(repo: str, cache: Optional[Path]) -> Dict[str, object]:
    name = Path(repo).name
    cached = cache / f"{name}.json" if cache else None
    if cached and cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    t0 = time.time()
    changes = read_commits(repo)
    szz = run_szz(repo, changes)
    rows, _ = build_dataset(changes, szz.buggy)
    data = {
        "repo": name, "head": changes[-1].sha if changes else None, "changes": len(changes),
        "szz": szz.to_dict(), "seconds": round(time.time() - t0, 1),
        "first": changes[0].timestamp if changes else None, "last": changes[-1].timestamp if changes else None,
        "rows": [{"sha": r.sha, "t": r.timestamp, "y": int(r.buggy), "x": r.features} for r in rows],
    }
    if cached:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(data), encoding="utf-8")
    return data


def split(rows: List[dict]):
    rows = sorted(rows, key=lambda r: r["t"])
    a = int(len(rows) * TRAIN)
    b = a + int(len(rows) * TEST)
    return rows[:a], rows[a:b]


def evaluate(method: str, scores: List[float], y: List[int], effort: List[float], threshold: float) -> dict:
    a = auc(scores, y)
    res = {"method": method, "auc": round(a, 4) if a is not None else None}
    res.update(classification(scores, y, threshold))
    r20 = recall_at_effort(scores, y, effort, 0.2)
    res["recall_at_20_effort"] = round(r20, 4) if r20 is not None else None
    dens = recall_at_effort([s / (e + 1.0) for s, e in zip(scores, effort)], y, effort, 0.2)
    res["recall_at_20_effort_density"] = round(dens, 4) if dens is not None else None
    return res


def lightgbm_scores(train: List[dict], test: List[dict]) -> Optional[List[float]]:
    try:
        import lightgbm as lgb  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return None
    xtr = [[r["x"][f] for f in FEATURES] for r in train]
    ytr = [r["y"] for r in train]
    pos = sum(ytr)
    params = {"objective": "binary", "learning_rate": 0.05, "num_leaves": 15, "min_data_in_leaf": 10,
              "scale_pos_weight": (len(ytr) - pos) / max(pos, 1), "seed": 0, "deterministic": True,
              "num_threads": 1, "verbose": -1}
    booster = lgb.train(params, lgb.Dataset(np.array(xtr), label=np.array(ytr)), num_boost_round=200)
    return [float(v) for v in booster.predict(np.array([[r["x"][f] for f in FEATURES] for r in test]))]


def evaluate_repo(data: dict, use_lightgbm: bool) -> dict:
    train, test = split(data["rows"])
    y_tr = [r["y"] for r in train]
    y = [r["y"] for r in test]
    effort = [r["x"]["LA"] + r["x"]["LD"] for r in test]
    t0 = time.time()
    lr = LogisticModel().fit([r["x"] for r in train], y_tr)
    t_lr = time.time() - t0
    small = LogisticModel(features=("LA", "LD", "NF")).fit([r["x"] for r in train], y_tr)
    t0 = time.time()
    gb = BoostedStumps().fit([r["x"] for r in train], y_tr)
    t_gb = time.time() - t0
    methods: List[tuple] = [
        ("rules v0 (as deployed)", [rule_score(r["x"], True) for r in test], 30.0),
        ("rules v0 (bugs fixed)", [rule_score(r["x"], False) for r in test], 30.0),
        ("size (LA+LD)", effort, float("inf")),
        ("smallest first", [1.0 / (e + 1.0) for e in effort], float("inf")),
        ("logistic, size only (LA, LD, NF)", [small.predict_proba(r["x"]) for r in test], 0.5),
        ("logistic regression", [lr.predict_proba(r["x"]) for r in test], 0.5),
        ("boosted stumps", [gb.predict_proba(r["x"]) for r in test], 0.5),
    ]
    if use_lightgbm:
        s = lightgbm_scores(train, test)
        if s is not None:
            methods.append(("LightGBM (reference)", s, 0.5))
    results = [evaluate(name, s, y, effort, th) for name, s, th in methods]
    for res in results:
        if res["method"] in ("size (LA+LD)", "smallest first"):   # ranking only, no yes/no call
            res.update({"precision": None, "recall": None, "f1": None, "flagged": None})
    top = sorted(lr.weights.items(), key=lambda kv: -abs(kv[1]))
    return {
        "repo": data["repo"], "head": data["head"], "changes": data["changes"], "szz": data["szz"],
        "rows": len(data["rows"]), "train": len(train), "test": len(test),
        "buggy_train": round(sum(y_tr) / max(len(y_tr), 1), 4), "buggy_test": round(sum(y) / max(len(y), 1), 4),
        "train_seconds": {"logistic": round(t_lr, 2), "stumps": round(t_gb, 2)},
        "results": results, "logistic_weights": [(k, round(v, 3)) for k, v in top],
    }


def fmt(v) -> str:
    return "—" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))


def report(evals: List[dict]) -> str:
    lines = ["# PR risk prediction: evaluation on open-source history", "",
             "Generated by `evaluation/evaluate_risk_model.py`. Labels: SZZ on the main-branch history; "
             "features: Kamei et al. (2013) change metrics; time-ordered split (train oldest 60%, test next 30%, "
             "newest 10% dropped for label latency). Yes/no calls: rules at score >= 30 (MEDIUM), models at "
             "p >= 0.5. recall@20%: buggy changes found reviewing from the highest score down until 20% of all "
             "changed lines are read; \"per line\": the same, ordered by score / lines.", ""]
    methods = [r["method"] for r in evals[0]["results"]]
    for e in evals:
        lines += [f"## {e['repo']} (HEAD {e['head'][:10]})", "",
                  f"{e['changes']} main-line changes, {e['rows']} touch product code; SZZ: {e['szz']['fixes']} fixes, "
                  f"{e['szz']['fixes_traced']} traced, {e['szz']['buggy_changes']} bug-introducing changes. "
                  f"Train {e['train']} ({e['buggy_train']:.1%} buggy), test {e['test']} ({e['buggy_test']:.1%} buggy).", "",
                  "| method | AUC | precision | recall | F1 | flagged | recall@20% effort | recall@20% per line |",
                  "|---|---|---|---|---|---|---|---|"]
        for r in e["results"]:
            lines.append(f"| {r['method']} | {fmt(r['auc'])} | {fmt(r['precision'])} | {fmt(r['recall'])} | "
                         f"{fmt(r['f1'])} | {fmt(r['flagged'])} | {fmt(r['recall_at_20_effort'])} | "
                         f"{fmt(r['recall_at_20_effort_density'])} |")
        lines += ["", "Logistic weights (standardised, log1p): " +
                  ", ".join(f"{k} {v:+.2f}" for k, v in e["logistic_weights"]), ""]
    lines += ["## Mean over repositories", "",
              "| method | AUC | F1 | recall@20% effort | recall@20% per line |", "|---|---|---|---|---|"]
    for m in methods:
        rs = [next(r for r in e["results"] if r["method"] == m) for e in evals if any(r["method"] == m for r in e["results"])]
        def mean(key):
            vals = [r[key] for r in rs if r[key] is not None]
            return sum(vals) / len(vals) if vals else None
        lines.append(f"| {m} | {fmt(mean('auc'))} | {fmt(mean('f1'))} | {fmt(mean('recall_at_20_effort'))} | "
                     f"{fmt(mean('recall_at_20_effort_density'))} |")
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repos", nargs="+", required=True)
    ap.add_argument("--out", default=str(Path(__file__).parent / "results" / "risk_model_evaluation.md"))
    ap.add_argument("--cache", default=None, help="directory for labelled datasets (skip git on re-runs)")
    ap.add_argument("--lightgbm", action="store_true")
    args = ap.parse_args(argv)
    cache = Path(args.cache) if args.cache else None
    evals = []
    for repo in args.repos:
        data = load_dataset(repo, cache)
        print(f"{data['repo']}: {len(data['rows'])} rows, szz {data['szz']}", flush=True)
        evals.append(evaluate_repo(data, args.lightgbm))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report(evals), encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(evals, indent=2), encoding="utf-8")
    print(report(evals))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
