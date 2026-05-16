from __future__ import annotations

import logging
import random
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from threading import Lock
from typing import Iterator

logger = logging.getLogger(__name__)

Labels = tuple[tuple[str, str], ...]

_METRIC_HELP: dict[str, str] = {
    "http_requests_total": "Total HTTP requests",
    "http_errors_total": "Total HTTP error responses (4xx and 5xx)",
    "http_active_requests": "Currently in-flight HTTP requests",
    "http_request_latency_seconds": "HTTP request latency in seconds",
    "http_request_throughput_rps": "HTTP request throughput (requests per second, 60 s window)",
    "pipeline_stage_latency_seconds": "Pipeline stage latency in seconds",
    "extraction_success_total": "Total extractions with confidence_score > 0 (success) or = 0 (failure), labelled by result",
}

_COUNTER_METRICS = {"http_requests_total", "http_errors_total"}
_GAUGE_METRICS = {"http_active_requests", "http_request_throughput_rps"}
_SUMMARY_METRICS = {"http_request_latency_seconds", "pipeline_stage_latency_seconds"}


class _Reservoir:
    """Thread-unsafe reservoir sample (Algorithm R) for approximate percentiles.

    Caller must hold the registry lock before calling add() or quantile().
    """

    SIZE = 1024

    def __init__(self) -> None:
        self._samples: list[float] = []
        self._count = 0

    def add(self, value: float) -> None:
        self._count += 1
        if len(self._samples) < self.SIZE:
            self._samples.append(value)
        else:
            idx = random.randint(0, self._count - 1)  # nosec B311 — reservoir sampling, not crypto
            if idx < self.SIZE:
                self._samples[idx] = value

    def quantile(self, q: float) -> float | None:
        if not self._samples:
            return None
        ordered = sorted(self._samples)
        idx = min(int(q * len(ordered)), len(ordered) - 1)
        return ordered[idx]


class _SlidingRateCounter:
    """Counts events over a sliding time window to compute a rolling RPS.

    Thread-unsafe — caller must hold the registry lock.
    """

    def __init__(self, window: float = 60.0) -> None:
        self._window = window
        self._events: deque[float] = deque()

    def record(self) -> None:
        now = time.time()
        self._events.append(now)

    @property
    def rate(self) -> float:
        now = time.time()
        cutoff = now - self._window
        while self._events and self._events[0] < cutoff:
            self._events.popleft()
        return len(self._events) / self._window


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[tuple[str, Labels], float] = defaultdict(float)
        self._summaries: dict[tuple[str, Labels], dict[str, float]] = defaultdict(
            lambda: {"count": 0.0, "sum": 0.0, "max": 0.0}
        )
        self._gauges: dict[tuple[str, Labels], float] = {}
        self._reservoirs: dict[tuple[str, Labels], _Reservoir] = {}
        self._rate_counters: dict[tuple[str, Labels], _SlidingRateCounter] = {}

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        with self._lock:
            self._counters[(name, _normalize_labels(labels))] += value

    def increment_gauge(self, name: str, delta: float = 1.0, **labels: str) -> None:
        key = (name, _normalize_labels(labels))
        with self._lock:
            self._gauges[key] = self._gauges.get(key, 0.0) + delta

    def observe(self, name: str, value: float, **labels: str) -> None:
        key = (name, _normalize_labels(labels))
        with self._lock:
            summary = self._summaries[key]
            summary["count"] += 1
            summary["sum"] += value
            summary["max"] = max(summary["max"], value)
            if key not in self._reservoirs:
                self._reservoirs[key] = _Reservoir()
            self._reservoirs[key].add(value)

    def record_rate(self, name: str, **labels: str) -> float:
        """Record one event and update the named gauge with the current rolling RPS."""
        key = (name, _normalize_labels(labels))
        with self._lock:
            if key not in self._rate_counters:
                self._rate_counters[key] = _SlidingRateCounter()
            self._rate_counters[key].record()
            rate = self._rate_counters[key].rate
            self._gauges[key] = rate
        return rate

    def gauge(self, name: str, value: float, **labels: str) -> None:
        with self._lock:
            self._gauges[(name, _normalize_labels(labels))] = value

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            seen_names: set[str] = set()

            def _header(metric_name: str, metric_type: str) -> None:
                if metric_name not in seen_names:
                    seen_names.add(metric_name)
                    help_text = _METRIC_HELP.get(metric_name, metric_name.replace("_", " "))
                    lines.append(f"# HELP {metric_name} {help_text}")
                    lines.append(f"# TYPE {metric_name} {metric_type}")

            for (name, labels), value in sorted(self._counters.items()):
                _header(name, "counter")
                lines.append(f"{name}{_format_labels(labels)} {value}")

            for (name, labels), summary in sorted(self._summaries.items()):
                _header(name, "summary")
                rendered = _format_labels(labels)
                reservoir = self._reservoirs.get((name, labels))
                for q in (0.5, 0.95, 0.99):
                    v = reservoir.quantile(q) if reservoir else None
                    if v is not None:
                        q_labels = _format_labels(labels + (("quantile", str(q)),))
                        lines.append(f"{name}{q_labels} {v}")
                lines.append(f"{name}_count{rendered} {summary['count']}")
                lines.append(f"{name}_sum{rendered} {summary['sum']}")
                lines.append(f"{name}_max{rendered} {summary['max']}")

            for (name, labels), value in sorted(self._gauges.items()):
                _header(name, "gauge")
                lines.append(f"{name}{_format_labels(labels)} {value}")

        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._summaries.clear()
            self._gauges.clear()
            self._reservoirs.clear()
            self._rate_counters.clear()


metrics = MetricsRegistry()


@contextmanager
def timed_stage(stage: str, timings_ms: dict[str, float] | None = None) -> Iterator[None]:
    started_at = time.perf_counter()
    try:
        yield
    finally:
        elapsed_seconds = time.perf_counter() - started_at
        elapsed_ms = round(elapsed_seconds * 1000, 3)
        if timings_ms is not None:
            timings_ms[stage] = elapsed_ms
        metrics.observe("pipeline_stage_latency_seconds", elapsed_seconds, stage=stage)
        logger.info("Pipeline stage timing: stage=%s elapsed_ms=%s", stage, elapsed_ms)


def _normalize_labels(labels: dict[str, str]) -> Labels:
    return tuple(sorted((key, str(value)) for key, value in labels.items()))


def _format_labels(labels: Labels) -> str:
    if not labels:
        return ""
    formatted = ",".join(f'{key}="{_escape_label(value)}"' for key, value in labels)
    return "{" + formatted + "}"


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')

