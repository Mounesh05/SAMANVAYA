"""
Two classifiers for "will this change introduce a bug?", pure Python and
deterministic (same data -> same model), with exact per-feature explanations.

LogisticModel
    log1p on count features, then standardisation (mean / std of the
    training set). Fitted by Newton's method (IRLS) with L2 regularisation,
    so it converges to the exact optimum in a few iterations. Classes are
    weighted "balanced" (n / (2 * n_class)) because bug-introducing changes
    are rare (5-30%). The log-odds is  b + sum_j w_j * z_j, so the
    contribution of each feature is exactly w_j * z_j.

BoostedStumps
    Gradient boosting (Friedman 2001) with logistic loss; every tree is a
    single split ("stump") on one feature, chosen from up to 32 quantile
    thresholds by the Newton gain, with shrinkage. Because each stump uses one
    feature, the model is additive: log-odds = base + sum_j f_j(x_j), so the
    contribution of feature j is f_j(x_j) minus its average on the training
    data (exact, no SHAP approximation needed).

Both models save to and load from plain JSON-safe dicts.
"""

from __future__ import annotations

import math
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .features import FEATURES

# Features that are not counts (already on a 0-1 scale): no log transform.
_NO_LOG = {"FIX", "ENTROPY"}


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def balanced_weights(y: Sequence[int]) -> List[float]:
    n, pos = len(y), sum(y)
    neg = n - pos
    if not pos or not neg:
        return [1.0] * n
    wp, wn = n / (2.0 * pos), n / (2.0 * neg)
    return [wp if v else wn for v in y]


def _transform(name: str, value: float) -> float:
    return value if name in _NO_LOG else math.log1p(max(0.0, value))


def _solve(a: List[List[float]], b: List[float]) -> List[float]:
    """Gaussian elimination with partial pivoting (a is small: features + 1)."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[piv] = m[piv], m[col]
        if abs(m[col][col]) < 1e-12:
            continue
        for r in range(n):
            if r != col and m[r][col]:
                f = m[r][col] / m[col][col]
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    return [m[i][n] / m[i][i] if abs(m[i][i]) > 1e-12 else 0.0 for i in range(n)]


def _contributions(parts: Dict[str, float], raw: Mapping[str, float], top: int) -> List[Dict[str, float]]:
    ranked = sorted(parts.items(), key=lambda kv: -abs(kv[1]))[:top]
    return [{"feature": k, "value": raw.get(k, 0.0), "contribution": round(v, 4)} for k, v in ranked]


class LogisticModel:
    kind = "logistic_regression"

    def __init__(self, features: Sequence[str] = FEATURES, l2: float = 1.0):
        self.features = tuple(features)
        self.l2 = l2
        self.mean: Dict[str, float] = {}
        self.std: Dict[str, float] = {}
        self.weights: Dict[str, float] = {}
        self.bias = 0.0

    def _z(self, row: Mapping[str, float]) -> List[float]:
        return [(_transform(f, float(row.get(f, 0.0))) - self.mean[f]) / self.std[f] for f in self.features]

    def fit(self, rows: Sequence[Mapping[str, float]], y: Sequence[int], iterations: int = 25) -> "LogisticModel":
        for f in self.features:
            col = [_transform(f, float(r.get(f, 0.0))) for r in rows]
            mu = sum(col) / len(col)
            sd = math.sqrt(sum((v - mu) ** 2 for v in col) / len(col))
            self.mean[f], self.std[f] = mu, (sd if sd > 1e-9 else 1.0)
        x = [[1.0] + self._z(r) for r in rows]
        sw = balanced_weights(y)
        k = len(self.features) + 1
        beta = [0.0] * k
        for _ in range(iterations):
            grad = [0.0] * k
            hess = [[0.0] * k for _ in range(k)]
            for xi, yi, wi in zip(x, y, sw):
                p = sigmoid(sum(b * v for b, v in zip(beta, xi)))
                g, h = wi * (p - yi), wi * p * (1 - p)
                for a in range(k):
                    grad[a] += g * xi[a]
                    ha = h * xi[a]
                    row = hess[a]
                    for c in range(a, k):
                        row[c] += ha * xi[c]
            for a in range(k):
                for c in range(a):
                    hess[a][c] = hess[c][a]
                if a:  # no penalty on the intercept
                    grad[a] += self.l2 * beta[a]
                    hess[a][a] += self.l2
            step = _solve(hess, grad)
            beta = [b - s for b, s in zip(beta, step)]
            if max(abs(s) for s in step) < 1e-8:
                break
        self.bias = beta[0]
        self.weights = dict(zip(self.features, beta[1:]))
        return self

    def log_odds_parts(self, row: Mapping[str, float]) -> Dict[str, float]:
        return {f: self.weights[f] * z for f, z in zip(self.features, self._z(row))}

    def predict_proba(self, row: Mapping[str, float]) -> float:
        return sigmoid(self.bias + sum(self.log_odds_parts(row).values()))

    def explain(self, row: Mapping[str, float], top: int = 5) -> List[Dict[str, float]]:
        """Top features by |contribution| to the log-odds (positive = raises risk)."""
        return _contributions(self.log_odds_parts(row), row, top)

    def to_dict(self) -> Dict[str, object]:
        return {"kind": self.kind, "features": list(self.features), "l2": self.l2, "mean": self.mean,
                "std": self.std, "weights": self.weights, "bias": self.bias}

    @classmethod
    def from_dict(cls, d: Mapping[str, object]) -> "LogisticModel":
        m = cls(d["features"], float(d.get("l2", 1.0)))
        m.mean, m.std, m.weights = dict(d["mean"]), dict(d["std"]), dict(d["weights"])
        m.bias = float(d["bias"])
        return m


class BoostedStumps:
    kind = "boosted_stumps"

    def __init__(self, features: Sequence[str] = FEATURES, rounds: int = 200, learning_rate: float = 0.1,
                 bins: int = 32, l2: float = 1.0, min_hessian: float = 2.0):
        self.features = tuple(features)
        self.rounds, self.learning_rate, self.bins = rounds, learning_rate, bins
        self.l2, self.min_hessian = l2, min_hessian   # min_hessian: smallest leaf (about 8 rows)
        self.base = 0.0
        self.stumps: List[Tuple[str, float, float, float]] = []   # (feature, threshold, left, right)
        self.offsets: Dict[str, float] = {}                        # mean f_j on training data

    def _thresholds(self, values: List[float]) -> List[float]:
        uniq = sorted(set(values))
        if len(uniq) <= self.bins:
            return [(a + b) / 2 for a, b in zip(uniq, uniq[1:])]
        s = sorted(values)
        cuts = {s[int(len(s) * q / self.bins)] for q in range(1, self.bins)}
        return sorted(cuts)

    def fit(self, rows: Sequence[Mapping[str, float]], y: Sequence[int]) -> "BoostedStumps":
        n = len(rows)
        sw = balanced_weights(y)
        cols = {f: [float(r.get(f, 0.0)) for r in rows] for f in self.features}
        # bin index per row per feature: number of thresholds below the value
        cuts = {f: self._thresholds(cols[f]) for f in self.features}
        binned = {}
        for f in self.features:
            c = cuts[f]
            binned[f] = [_bisect(c, v) for v in cols[f]]
        wpos = sum(w for w, v in zip(sw, y) if v)
        self.base = math.log(wpos / (sum(sw) - wpos)) if 0 < wpos < sum(sw) else 0.0
        score = [self.base] * n
        self.stumps = []
        for _ in range(self.rounds):
            g = [0.0] * n
            h = [0.0] * n
            for i in range(n):
                p = sigmoid(score[i])
                g[i], h[i] = sw[i] * (p - y[i]), sw[i] * p * (1 - p)
            gt, ht = sum(g), sum(h)
            best = None
            for f in self.features:
                nb = len(cuts[f]) + 1
                gs, hs = [0.0] * nb, [0.0] * nb
                for i, b in enumerate(binned[f]):
                    gs[b] += g[i]
                    hs[b] += h[i]
                gl = hl = 0.0
                for b in range(nb - 1):   # split after bin b -> threshold cuts[f][b]
                    gl += gs[b]
                    hl += hs[b]
                    gr, hr = gt - gl, ht - hl
                    if hl < self.min_hessian or hr < self.min_hessian:
                        continue
                    gain = gl * gl / (hl + self.l2) + gr * gr / (hr + self.l2) - gt * gt / (ht + self.l2)
                    if best is None or gain > best[0]:
                        best = (gain, f, b, -gl / (hl + self.l2), -gr / (hr + self.l2))
            if best is None or best[0] <= 1e-9:
                break
            _, f, b, left, right = best
            left, right = left * self.learning_rate, right * self.learning_rate
            self.stumps.append((f, cuts[f][b], left, right))
            for i, bi in enumerate(binned[f]):
                score[i] += left if bi <= b else right
        # offsets so explanations are relative to an average change
        self.offsets = {f: 0.0 for f in self.features}
        for r in rows:
            for f, part in self._parts_raw(r).items():
                self.offsets[f] += part / n
        return self

    def _parts_raw(self, row: Mapping[str, float]) -> Dict[str, float]:
        parts = {f: 0.0 for f in self.features}
        for f, t, left, right in self.stumps:
            parts[f] += left if float(row.get(f, 0.0)) <= t else right
        return parts

    def log_odds_parts(self, row: Mapping[str, float]) -> Dict[str, float]:
        return {f: v - self.offsets.get(f, 0.0) for f, v in self._parts_raw(row).items()}

    def predict_proba(self, row: Mapping[str, float]) -> float:
        return sigmoid(self.base + sum(self._parts_raw(row).values()))

    def explain(self, row: Mapping[str, float], top: int = 5) -> List[Dict[str, float]]:
        return _contributions(self.log_odds_parts(row), row, top)

    def to_dict(self) -> Dict[str, object]:
        return {"kind": self.kind, "features": list(self.features), "base": self.base,
                "stumps": [list(s) for s in self.stumps], "offsets": self.offsets,
                "params": {"rounds": self.rounds, "learning_rate": self.learning_rate, "bins": self.bins,
                           "l2": self.l2, "min_hessian": self.min_hessian}}

    @classmethod
    def from_dict(cls, d: Mapping[str, object]) -> "BoostedStumps":
        m = cls(d["features"], **d.get("params", {}))
        m.base = float(d["base"])
        m.stumps = [(s[0], float(s[1]), float(s[2]), float(s[3])) for s in d["stumps"]]
        m.offsets = dict(d.get("offsets", {}))
        return m


def _bisect(cuts: List[float], value: float) -> int:
    """Index of the first threshold >= value (rows with value <= cuts[b] fall in bins 0..b)."""
    lo, hi = 0, len(cuts)
    while lo < hi:
        mid = (lo + hi) // 2
        if cuts[mid] < value:
            lo = mid + 1
        else:
            hi = mid
    return lo


def load_model(d: Mapping[str, object]):
    kinds = {LogisticModel.kind: LogisticModel, BoostedStumps.kind: BoostedStumps}
    if d.get("kind") not in kinds:
        raise ValueError(f"unknown model kind: {d.get('kind')!r}")
    return kinds[d["kind"]].from_dict(d)


# ── evaluation metrics ────────────────────────────────────────────────
def auc(scores: Sequence[float], y: Sequence[int]) -> Optional[float]:
    """ROC AUC by the rank-sum (Mann-Whitney) formula, ties counted as 1/2."""
    pos = sum(y)
    neg = len(y) - pos
    if not pos or not neg:
        return None
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    rank_pos = sum(r for r, v in zip(ranks, y) if v)
    return (rank_pos - pos * (pos + 1) / 2) / (pos * neg)


def classification(scores: Sequence[float], y: Sequence[int], threshold: float) -> Dict[str, float]:
    tp = sum(1 for s, v in zip(scores, y) if s >= threshold and v)
    fp = sum(1 for s, v in zip(scores, y) if s >= threshold and not v)
    fn = sum(1 for s, v in zip(scores, y) if s < threshold and v)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "flagged": tp + fp}


def recall_at_effort(scores: Sequence[float], y: Sequence[int], effort: Sequence[float],
                     budget: float = 0.2) -> Optional[float]:
    """Share of buggy changes found when reviewing changes from the highest
    score down until `budget` (20%) of all changed lines have been read
    (effort-aware evaluation, Kamei et al. 2013; effort = lines added + deleted).
    A change that would exceed the budget is skipped and smaller ones after it
    are still taken. Ties: smaller change first."""
    total_bugs = sum(y)
    total_effort = sum(effort)
    if not total_bugs or total_effort <= 0:
        return None
    order = sorted(range(len(y)), key=lambda i: (-scores[i], effort[i]))
    spent = found = 0.0
    for i in order:
        if spent + effort[i] > budget * total_effort:
            continue
        spent += effort[i]
        found += y[i]
    return found / total_bugs
