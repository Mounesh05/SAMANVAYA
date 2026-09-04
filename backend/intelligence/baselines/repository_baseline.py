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
    
    Thread-safe: Uses optimistic locking to prevent lost updates when
    multiple PRs analyzed concurrently.
    
    Rolling window: Only last HISTORY_DAYS of PRs affect baseline,
    allowing adaptation to changing repo characteristics.
    """

    COLLECTION = "repository_baselines"
    HISTORY_DAYS = 90       # Rolling window for baseline calculation
    MIN_SAMPLES = 5         # Minimum PRs before Z-score is used (fall back to defaults otherwise)
    MAX_UPDATE_RETRIES = 3  # Retry count for optimistic locking

    # Fallback defaults when not enough history exists
    DEFAULTS: Dict[str, Dict[str, float]] = {
        "files_changed":  {"mean": 8.0,   "std": 6.0},
        "lines_added":    {"mean": 150.0,  "std": 120.0},
        "lines_deleted":  {"mean": 60.0,   "std": 80.0},
        "lines_changed":  {"mean": 210.0,  "std": 180.0},  # lines_added + lines_deleted
        "complexity_avg": {"mean": 5.0,    "std": 3.0},
        "test_coverage":  {"mean": 75.0,   "std": 15.0},
    }

    async def ensure_index(self) -> None:
        """
        Create database index on repository_id for fast lookups.
        Call this once during application startup.
        """
        collection = col(self.COLLECTION)
        await collection.create_index("repository_id", unique=True)

    async def get_baseline(self, repository_id: str) -> Dict[str, Dict[str, float]]:
        """
        Retrieve the current baseline statistics for a repository.
        Returns defaults if insufficient history exists or data is too old.
        
        Enforces HISTORY_DAYS rolling window - ignores baselines
        last updated more than HISTORY_DAYS ago.
        """
        collection = col(self.COLLECTION)
        doc = await collection.find_one(
            {"repository_id": repository_id},
            sort=[("updated_at", -1)],
        )
        
        if not doc:
            return self.DEFAULTS
        
        # Enforce rolling window - discard stale baselines
        updated_at_str = doc.get("updated_at")
        if updated_at_str:
            try:
                updated_at = datetime.fromisoformat(updated_at_str)
                cutoff = datetime.now(timezone.utc) - timedelta(days=self.HISTORY_DAYS)
                if updated_at < cutoff:
                    # Baseline too old - reset to defaults
                    return self.DEFAULTS
            except (ValueError, TypeError):
                # Invalid date format - ignore and continue
                pass
        
        # Check minimum samples
        if doc.get("sample_count", 0) >= self.MIN_SAMPLES:
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
        
        Thread-safe: Uses optimistic locking with version field to prevent
        lost updates when multiple PRs analyzed simultaneously.
        
        Called after each analysis run to keep the baseline current.
        """
        collection = col(self.COLLECTION)
        now = datetime.now(timezone.utc)
        
        # Retry loop for optimistic locking
        for attempt in range(self.MAX_UPDATE_RETRIES):
            existing = await collection.find_one({"repository_id": repository_id})

            if not existing:
                # Bootstrap: first PR for this repo
                metrics = {
                    metric: {"mean": value, "std": 0.0, "m2": 0.0}
                    for metric, value in pr_metrics.items()
                }
                try:
                    await collection.insert_one({
                        "repository_id": repository_id,
                        "sample_count": 1,
                        "version": 1,  # Optimistic locking version
                        "metrics": metrics,
                        "created_at": now.isoformat(),
                        "updated_at": now.isoformat(),
                    })
                    return
                except Exception:
                    # Race condition - another thread inserted first, retry
                    if attempt < self.MAX_UPDATE_RETRIES - 1:
                        continue
                    raise

            # Welford's online update for streaming mean and variance
            old_version = existing.get("version", 0)
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

            # Optimistic locking update - only succeeds if version unchanged
            result = await collection.update_one(
                {"repository_id": repository_id, "version": old_version},
                {
                    "$set": {
                        "sample_count": n,
                        "version": old_version + 1,
                        "metrics": metrics,
                        "updated_at": now.isoformat(),
                    }
                },
            )

            if result.matched_count > 0:
                # Success - version matched, update applied
                return
            
            # Version mismatch - another thread updated first, retry
            if attempt < self.MAX_UPDATE_RETRIES - 1:
                continue
            
            # Max retries exceeded
            raise RuntimeError(
                f"Failed to update baseline for {repository_id} after "
                f"{self.MAX_UPDATE_RETRIES} attempts (concurrent update contention)"
            )
