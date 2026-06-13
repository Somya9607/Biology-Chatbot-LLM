"""In-memory metrics tracking (reset on process restart).

Tracks query volume, per-query total latency samples, error count and derived
statistics (average, p95, error rate). Exposed via the ``GET /metrics``
endpoint. Implemented as a thread-safe module-level singleton.
"""
from __future__ import annotations

import threading
from typing import Dict, List


class MetricsTracker:
    """Thread-safe singleton accumulating query latency and error metrics."""

    _instance: "MetricsTracker | None" = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "MetricsTracker":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_state()
        return cls._instance

    def _init_state(self) -> None:
        self._lock = threading.Lock()
        self.query_count = 0
        self.latency_samples: List[float] = []
        self.error_count = 0

    def record_query(self, total_ms: float, success: bool) -> None:
        """Record one query's total latency and success/failure."""
        with self._lock:
            self.query_count += 1
            self.latency_samples.append(float(total_ms))
            if not success:
                self.error_count += 1

    @staticmethod
    def _percentile(samples: List[float], pct: float) -> float:
        """Return the ``pct`` percentile (0-100) of a sample list."""
        if not samples:
            return 0.0
        ordered = sorted(samples)
        k = (len(ordered) - 1) * (pct / 100.0)
        lo = int(k)
        hi = min(lo + 1, len(ordered) - 1)
        if lo == hi:
            return ordered[lo]
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)

    def get_stats(self) -> Dict[str, float | int]:
        """Return aggregate stats: count, avg/p95 latency, errors, error rate."""
        with self._lock:
            count = self.query_count
            samples = list(self.latency_samples)
            errors = self.error_count

        avg = (sum(samples) / len(samples)) if samples else 0.0
        return {
            "query_count": count,
            "avg_latency_ms": round(avg, 2),
            "p95_latency_ms": round(self._percentile(samples, 95), 2),
            "error_count": errors,
            "error_rate": round(errors / count, 4) if count else 0.0,
        }


metrics_tracker = MetricsTracker()
"""Module-level singleton instance."""
