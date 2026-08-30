"""
Repository Baseline — historical statistics for Z-score deviation calculation.

Replaces static magic-number thresholds with data-driven risk scoring.

Example:
  Normal PR in this repo: 6 files, 120 lines
  Current PR: 18 files, 890 lines
  Z-score (files): (18-6)/σ = 3.0x normal  → HIGH anomaly

Collection: `repository_baselines`
"""

import math
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from core.database import col


class RepositoryBaseline:
    """
    Stores and retrieves historical PR statistics for a repository.
    Used by RiskEngine to compute Z-score deviations instead of
    hardcoded line-count thresholds.
    """

    COLLECTION = "repository_baselines"
    HISTORY_DAYS = 90       # Rolling window for baseline calculation
    MIN_SAMPLES = 5         # Minimum PRs before Z-score is used (fall back to defaults otherwise)

    # Fallback defaults when not enough history exists
    DEFAULTS: Dict[str, Dict[str, float]] = {
        "files_changed":  {"mean": 8.0,   "std": 6.0},
        "lines_added":    {"mean": 150.0,  "std": 120.0},
        "lines_deleted":  {"mean": 60.0,   "std": 80.0},
        "complexity_avg": {"mean": 5.0,    "std": 3.0},
        "test_coverage":  {"mean": 75.0,   "std": 15.0},
    }

    async def get_baseline(self, repository_id: str) -> Dict[str, Dict[str, float]]:
        """
        Retrieve the current baseline statistics for a repository.
        Returns defaults if insufficient history exists.
        """
        collection = col(self.COLLECTION)
        doc = await collection.find_one(
            {"repository_id": repository_id},
            sort=[("updated_at", -1)],
        )
        if doc and doc.get("sample_count", 0) >= self.MIN_SAMPLES:
            return doc.get("metrics", self.DEFAULTS)
        return self.DEFAULTS

    async def compute_zscore(
        self,
        repository_id: str,
        metric: str,
        value: float,
    ) -> float:
        """
        Compute the Z-score for a single metric value against historical data.

        Z = (value - μ) / σ

        Returns the Z-score (positive = above average, negative = below).
        Clamped to [-5.0, 5.0] to avoid extreme outlier inflation.
        """
        baseline = await self.get_baseline(repository_id)
        stats = baseline.get(metric, self.DEFAULTS.get(metric, {"mean": 0.0, "std": 1.0}))

        mean = stats.get("mean", 0.0)
        std = stats.get("std", 1.0)

        if std < 0.001:
            std = 0.001  # Avoid division by zero

        z = (value - mean) / std
        return max(-5.0, min(5.0, round(z, 3)))

    async def update_baseline(
        self,
        repository_id: str,
        pr_metrics: Dict[str, float],
    ) -> None:
        """
        Update the baseline with metrics from a new completed PR analysis.
        Uses Welford's online algorithm for streaming mean and variance.

        Called after each analysis run to keep the baseline current.
        """
        collection = col(self.COLLECTION)
        now = datetime.now(timezone.utc)

        existing = await collection.find_one({"repository_id": repository_id})

        if not existing:
            # Bootstrap: first PR for this repo
            metrics = {
                metric: {"mean": value, "std": 0.0, "m2": 0.0}
                for metric, value in pr_metrics.items()
            }
            await collection.insert_one({
                "repository_id": repository_id,
                "sample_count": 1,
                "metrics": metrics,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            })
            return

        # Welford's online update for streaming mean and variance
        n = existing.get("sample_count", 1) + 1
        metrics = existing.get("metrics", {})

        for metric, value in pr_metrics.items():
            stats = metrics.get(metric, {"mean": value, "std": 0.0, "m2": 0.0})
            old_mean = stats.get("mean", 0.0)
            m2 = stats.get("m2", 0.0)

            # Welford's algorithm
            delta = value - old_mean
            new_mean = old_mean + delta / n
            delta2 = value - new_mean
            m2 = m2 + delta * delta2

            std = math.sqrt(m2 / (n - 1)) if n > 1 else 0.0

            metrics[metric] = {
                "mean": round(new_mean, 3),
                "std": round(std, 3),
                "m2": round(m2, 3),
            }

        await collection.update_one(
            {"repository_id": repository_id},
            {
                "$set": {
                    "sample_count": n,
                    "metrics": metrics,
                    "updated_at": now.isoformat(),
                }
            },
        )

    async def get_history_summary(self, repository_id: str) -> Dict[str, Any]:
        """
        Return a human-readable summary of the repository's baseline stats.
        Used by the Code Agent prompt to give context about 'what's normal here'.
        """
        collection = col(self.COLLECTION)
        doc = await collection.find_one({"repository_id": repository_id})
        if not doc:
            return {
                "has_history": False,
                "message": "No baseline history yet — using default thresholds",
            }
        metrics = doc.get("metrics", {})
        return {
            "has_history": True,
            "sample_count": doc.get("sample_count", 0),
            "typical_pr_size": {
                "files": round(metrics.get("files_changed", {}).get("mean", 8), 1),
                "lines_added": round(metrics.get("lines_added", {}).get("mean", 150), 0),
                "lines_deleted": round(metrics.get("lines_deleted", {}).get("mean", 60), 0),
            },
            "typical_coverage": round(
                metrics.get("test_coverage", {}).get("mean", 75), 1
            ),
        }
