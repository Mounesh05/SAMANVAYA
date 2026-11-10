"""
Train a project's risk model from its git history, and score a new PR with it.

    train_from_repository(clone)   -> a JSON-safe bundle: model, the history
                                      state needed for new PRs, and its
                                      time-ordered evaluation
    predict(bundle, files, author, timestamp, messages)
                                   -> probability, top factors, features

Three candidates are compared on the held-out period: logistic regression on
the size features only (LA, LD, NF), logistic regression on all 14 and
boosted stumps on all 14. The simplest one wins unless a richer one has a
higher AUC; the winner is refitted on all labelled changes (the newest 10% are still left out:
their labels are not reliable yet). A bundle is only "usable" when its
held-out AUC is at least MIN_AUC and it was trained on at least
MIN_LABELLED changes with MIN_BUGGY bug-introducing ones; otherwise the risk
engine keeps using its rules.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .features import FEATURES, HistoryState, build_dataset
from .git_history import is_source_file, read_commits
from .model import BoostedStumps, LogisticModel, auc, classification, load_model, recall_at_effort
from .szz import is_fix_message, run_szz

MIN_AUC = 0.65
MIN_LABELLED = 200
MIN_BUGGY = 20
TRAIN, TEST = 0.6, 0.3
BUNDLE_VERSION = 1

_LABELS = {
    "LA": "lines added", "LD": "lines deleted", "LT": "size of the touched files", "NS": "subsystems touched",
    "ND": "directories touched", "NF": "files touched", "ENTROPY": "change spread across files",
    "FIX": "is a bug fix", "NDEV": "developers who changed these files", "AGE": "days since files last changed",
    "NUC": "earlier changes to these files", "EXP": "author's earlier changes",
    "REXP": "author's recent experience", "SEXP": "author's experience in these subsystems",
}


SIZE_FEATURES = ("LA", "LD", "NF")
# candidates, simplest first: a richer model is deployed only if it beats it on the held-out period
CANDIDATES = ("size_logistic", LogisticModel.kind, BoostedStumps.kind)


def _fit(kind: str, rows: Sequence[Mapping[str, float]], y: Sequence[int]):
    if kind == "size_logistic":
        return LogisticModel(features=SIZE_FEATURES).fit(rows, y)
    return (LogisticModel() if kind == LogisticModel.kind else BoostedStumps()).fit(rows, y)


def _scores(model, rows) -> List[float]:
    return [model.predict_proba(r) for r in rows]


def train_from_rows(rows: Sequence[Tuple[int, Dict[str, float], int]]) -> Dict[str, Any]:
    """rows: (timestamp, features, buggy 0/1). Returns model + evaluation (no history state)."""
    rows = sorted(rows, key=lambda r: r[0])
    a = int(len(rows) * TRAIN)
    b = a + int(len(rows) * TEST)
    train, test, labelled = rows[:a], rows[a:b], rows[:b]
    evaluation: Dict[str, Any] = {"split": {"train": len(train), "test": len(test), "dropped_newest": len(rows) - b},
                                  "buggy_rate": round(sum(r[2] for r in labelled) / max(len(labelled), 1), 4),
                                  "models": {}}
    best_kind, best_auc = CANDIDATES[0], None
    if train and test and 0 < sum(r[2] for r in train) < len(train):
        x_te, y_te = [r[1] for r in test], [r[2] for r in test]
        effort = [r[1]["LA"] + r[1]["LD"] for r in test]
        for kind in CANDIDATES:
            s = _scores(_fit(kind, [r[1] for r in train], [r[2] for r in train]), x_te)
            a_ = auc(s, y_te)
            evaluation["models"][kind] = {"auc": None if a_ is None else round(a_, 4),
                                          **classification(s, y_te, 0.5),
                                          "recall_at_20_effort": recall_at_effort(s, y_te, effort, 0.2)}
            if a_ is not None and (best_auc is None or a_ > best_auc):
                best_kind, best_auc = kind, a_
    buggy = sum(r[2] for r in labelled)
    usable = (best_auc is not None and best_auc >= MIN_AUC and len(labelled) >= MIN_LABELLED and buggy >= MIN_BUGGY)
    model = _fit(best_kind, [r[1] for r in labelled], [r[2] for r in labelled]) if 0 < buggy < len(labelled) else None
    evaluation.update({"selected": best_kind, "auc": None if best_auc is None else round(best_auc, 4),
                       "labelled": len(labelled), "buggy": buggy})
    return {"model": model.to_dict() if model else None, "evaluation": evaluation, "usable": bool(usable and model)}


def train_from_repository(repo: str, ref: str = "HEAD", suffixes: Sequence[str] = (".py",)) -> Dict[str, Any]:
    t0 = time.time()
    changes = read_commits(repo, ref)
    szz = run_szz(repo, changes, suffixes)
    rows, state = build_dataset(changes, szz.buggy, suffixes)
    bundle = train_from_rows([(r.timestamp, r.features, int(r.buggy)) for r in rows])
    bundle.update({
        "version": BUNDLE_VERSION,
        "features": list(FEATURES),
        "suffixes": list(suffixes),
        "head": changes[-1].sha if changes else None,
        "changes": len(changes),
        "szz": szz.to_dict(),
        "state": state.to_dict(),
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "seconds": round(time.time() - t0, 1),
        "thresholds": {"min_auc": MIN_AUC, "min_labelled": MIN_LABELLED, "min_buggy": MIN_BUGGY},
    })
    return bundle


def predict(bundle: Mapping[str, Any], files: Iterable[Tuple[str, int, int]], author: str,
            timestamp: Optional[int] = None, messages: Sequence[str] = (), top: int = 3) -> Optional[Dict[str, Any]]:
    """Score one change. `files`: (path, additions, deletions). None when the
    bundle is not usable or the change touches no product code."""
    if not bundle or not bundle.get("usable") or not bundle.get("model"):
        return None
    suffixes = tuple(bundle.get("suffixes") or (".py",))
    source = [(p, int(a or 0), int(d or 0)) for p, a, d in files if is_source_file(p, suffixes)]
    if not any(a or d for _, a, d in source):
        return None
    state = HistoryState.from_dict(bundle.get("state") or {})
    ts = int(timestamp if timestamp is not None else time.time())
    feats = state.features(source, (author or "").strip().lower(), ts, any(is_fix_message(m) for m in messages))
    model = load_model(bundle["model"])
    p = model.predict_proba(feats)
    factors = []
    for item in model.explain(feats, top=top + 3):
        if item["contribution"] > 0 and len(factors) < top:
            factors.append({**item, "label": _LABELS.get(item["feature"], item["feature"])})
    return {"probability": round(p, 4), "model": bundle["evaluation"].get("selected", bundle["model"]["kind"]),
            "auc": bundle["evaluation"].get("auc"),
            "factors": factors, "features": feats}
