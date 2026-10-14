# SPDX-License-Identifier: MIT
"""
Response-Time Middleware with Performance Metrics Collection
Implements SRS NFR-PERF-002 (WebSocket relay measurement point, sub-50 ms) and the
NFR-PERF-001 ingestion measurement point.

Origin: BioSync-Gateway middleware/api/middleware/response_time.py (adapted).

Adaptations:
  * Latency samples are kept in bounded windows (SAMPLE_WINDOW most recent values). The Gateway
    appended every sample to an unbounded list, which grows without limit at the NFR-PERF-001
    rate. Percentiles are computed over the window.
  * HTTP metrics are keyed by method and path. At most MAX_ENDPOINT_KEYS distinct keys are kept.
    Further paths are counted under an OTHER key for their method, so path cardinality cannot
    grow memory without bound.
  * The ASGI middleware records only HTTP scopes. WebSocket scopes pass through unchanged, so
    the relay connection is not wrapped.

Provides:
- ResponseTimeMiddleware: ASGI middleware that records per-endpoint latency.
- MetricsRegistry: thread-safe in-memory store for HTTP and WebSocket metrics.
- get_metrics(): the registry singleton.
- track_ws_relay(): context manager that records one WebSocket send latency sample.
- record_pulse_step() is used by engine/pulse.py.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from typing import Any, Deque, Dict, List, Optional

from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NFR thresholds (SRS Section 5.1 and the migrated NFR identifiers)
# ---------------------------------------------------------------------------

NFR_P3_HTTP_P95_MS = 200.0      # 95th percentile <= 200 ms for CRUD requests
NFR_P3_WS_P95_MS = 50.0         # 95th percentile <= 50 ms for WebSocket relay (NFR-PERF-002)
NFR_P1_INGESTION_RATE = 100_000  # >= 100,000 data points per second (NFR-PERF-001)
NFR_P2_FPS_TARGET = 60          # >= 60 fps sustained
NFR_P4_HASH_CHAIN_1M_SECONDS = 60.0  # <= 60 seconds for 1M rows
NFR_P5_PULSE_STEP_MS = 50.0     # <= 50 ms per time-step
NFR_P6_CONCURRENT_WS = 500      # >= 500 concurrent WebSocket connections

# Default slow-request thresholds (ms)
DEFAULT_HTTP_SLOW_THRESHOLD_MS = 100.0
DEFAULT_WS_SLOW_THRESHOLD_MS = 50.0

# Bounds on in-memory state
SAMPLE_WINDOW = 10_000
MAX_ENDPOINT_KEYS = 256
OVERFLOW_ENDPOINT_KEY = "OTHER"


def _percentile(sorted_values: List[float], pct: float) -> float:
    """Compute a percentile from a sorted list of values."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


class EndpointMetrics:
    """Accumulates latency samples for a single endpoint/method pair."""

    __slots__ = ("count", "total_ms", "_samples", "min_ms", "max_ms")

    def __init__(self) -> None:
        self.count: int = 0
        self.total_ms: float = 0.0
        self._samples: Deque[float] = deque(maxlen=SAMPLE_WINDOW)
        self.min_ms: float = float("inf")
        self.max_ms: float = 0.0

    def record(self, latency_ms: float) -> None:
        self.count += 1
        self.total_ms += latency_ms
        self._samples.append(latency_ms)
        if latency_ms < self.min_ms:
            self.min_ms = latency_ms
        if latency_ms > self.max_ms:
            self.max_ms = latency_ms

    def to_dict(self) -> Dict[str, Any]:
        avg = self.total_ms / self.count if self.count else 0.0
        sorted_samples = sorted(self._samples)
        return {
            "count": self.count,
            "avg_ms": round(avg, 3),
            "p50_ms": round(_percentile(sorted_samples, 50), 3),
            "p95_ms": round(_percentile(sorted_samples, 95), 3),
            "p99_ms": round(_percentile(sorted_samples, 99), 3),
            "min_ms": round(self.min_ms if self.count else 0.0, 3),
            "max_ms": round(self.max_ms, 3),
        }


class MetricsRegistry:
    """
    Thread-safe registry for HTTP and WebSocket performance metrics.

    Implements:
        SRS NFR-PERF-002: WebSocket relay latency tracking.
        SRS NFR-PERF-001: telemetry ingestion throughput tracking.
        SRS NFR-P5: Pulse Engine time-step tracking.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._http_metrics: Dict[str, EndpointMetrics] = {}
        self._ws_relay_samples: Deque[float] = deque(maxlen=SAMPLE_WINDOW)
        self._ws_connections: int = 0
        self._ws_connections_peak: int = 0
        self._ingestion_samples: Deque[float] = deque(maxlen=SAMPLE_WINDOW)  # points/sec
        self._pulse_step_samples: Deque[float] = deque(maxlen=SAMPLE_WINDOW)  # ms per step
        self._hash_chain_samples: Deque[float] = deque(maxlen=SAMPLE_WINDOW)  # seconds per run

    # -- HTTP metrics -------------------------------------------------------

    def record_http(self, endpoint: str, method: str, latency_ms: float) -> None:
        key = f"{method} {endpoint}"
        with self._lock:
            metrics = self._http_metrics.get(key)
            if metrics is None:
                if len(self._http_metrics) >= MAX_ENDPOINT_KEYS:
                    key = f"{method} {OVERFLOW_ENDPOINT_KEY}"
                    metrics = self._http_metrics.get(key)
                if metrics is None:
                    metrics = EndpointMetrics()
                    self._http_metrics[key] = metrics
            metrics.record(latency_ms)

    # -- WebSocket metrics --------------------------------------------------

    def record_ws_latency(self, latency_ms: float) -> None:
        with self._lock:
            self._ws_relay_samples.append(latency_ms)

    def record_ws_connection(self, delta: int) -> None:
        with self._lock:
            self._ws_connections += delta
            if self._ws_connections > self._ws_connections_peak:
                self._ws_connections_peak = self._ws_connections

    # -- Throughput metrics (NFR-PERF-001) ---------------------------------

    def record_ingestion_rate(self, points_per_second: float) -> None:
        with self._lock:
            self._ingestion_samples.append(points_per_second)

    # -- Pulse Engine metrics (NFR-P5) -------------------------------------

    def record_pulse_step(self, latency_ms: float) -> None:
        with self._lock:
            self._pulse_step_samples.append(latency_ms)

    # -- Hash chain metrics (NFR-P4) ---------------------------------------

    def record_hash_chain(self, rows: int, elapsed_seconds: float) -> None:
        with self._lock:
            self._hash_chain_samples.append(elapsed_seconds)

    # -- Snapshot -----------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            http_snapshot = {
                key: m.to_dict() for key, m in self._http_metrics.items()
            }
            ws_sorted = sorted(self._ws_relay_samples)
            ingestion_sorted = sorted(self._ingestion_samples)
            pulse_sorted = sorted(self._pulse_step_samples)
            hash_sorted = sorted(self._hash_chain_samples)

            return {
                "http": http_snapshot,
                "websocket": {
                    "relay_latency_ms": {
                        "count": len(ws_sorted),
                        "p50_ms": round(_percentile(ws_sorted, 50), 3),
                        "p95_ms": round(_percentile(ws_sorted, 95), 3),
                        "p99_ms": round(_percentile(ws_sorted, 99), 3),
                        "max_ms": round(ws_sorted[-1], 3) if ws_sorted else 0.0,
                        "target_p95_ms": NFR_P3_WS_P95_MS,
                        "passed": (
                            _percentile(ws_sorted, 95) <= NFR_P3_WS_P95_MS
                            if ws_sorted else True
                        ),
                    },
                    "active_connections": self._ws_connections,
                    "peak_connections": self._ws_connections_peak,
                    "target_concurrent": NFR_P6_CONCURRENT_WS,
                    "passed_connections": self._ws_connections_peak >= NFR_P6_CONCURRENT_WS,
                },
                "throughput": {
                    "ingestion_rate_pps": {
                        "count": len(ingestion_sorted),
                        "p50": round(_percentile(ingestion_sorted, 50), 0) if ingestion_sorted else 0,
                        "p95": round(_percentile(ingestion_sorted, 95), 0) if ingestion_sorted else 0,
                        "max": round(ingestion_sorted[-1], 0) if ingestion_sorted else 0,
                        "target_pps": NFR_P1_INGESTION_RATE,
                        "passed": (
                            _percentile(ingestion_sorted, 95) >= NFR_P1_INGESTION_RATE
                            if ingestion_sorted else True
                        ),
                    },
                },
                "pulse_engine": {
                    "step_latency_ms": {
                        "count": len(pulse_sorted),
                        "p50_ms": round(_percentile(pulse_sorted, 50), 3),
                        "p95_ms": round(_percentile(pulse_sorted, 95), 3),
                        "max_ms": round(pulse_sorted[-1], 3) if pulse_sorted else 0.0,
                        "target_p95_ms": NFR_P5_PULSE_STEP_MS,
                        "passed": (
                            _percentile(pulse_sorted, 95) <= NFR_P5_PULSE_STEP_MS
                            if pulse_sorted else True
                        ),
                    },
                },
                "hash_chain": {
                    "verification_seconds": {
                        "count": len(hash_sorted),
                        "p50_s": round(_percentile(hash_sorted, 50), 3),
                        "p95_s": round(_percentile(hash_sorted, 95), 3),
                        "max_s": round(hash_sorted[-1], 3) if hash_sorted else 0.0,
                        "target_1m_seconds": NFR_P4_HASH_CHAIN_1M_SECONDS,
                        "passed": (
                            _percentile(hash_sorted, 95) <= NFR_P4_HASH_CHAIN_1M_SECONDS
                            if hash_sorted else True
                        ),
                    },
                },
            }

    def reset(self) -> None:
        with self._lock:
            self._http_metrics.clear()
            self._ws_relay_samples.clear()
            self._ws_connections = 0
            self._ws_connections_peak = 0
            self._ingestion_samples.clear()
            self._pulse_step_samples.clear()
            self._hash_chain_samples.clear()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_registry = MetricsRegistry()


def get_metrics() -> MetricsRegistry:
    """Return the module-level MetricsRegistry singleton."""
    return _registry


def record_ws_latency(latency_ms: float) -> None:
    """Record a single WebSocket relay latency sample (NFR-PERF-002)."""
    _registry.record_ws_latency(latency_ms)


def record_ws_connection(delta: int) -> None:
    """Adjust the active WebSocket connection count by *delta*."""
    _registry.record_ws_connection(delta)


def record_ingestion_rate(points_per_second: float) -> None:
    """Record a telemetry ingestion throughput sample (NFR-PERF-001)."""
    _registry.record_ingestion_rate(points_per_second)


def record_pulse_step(latency_ms: float) -> None:
    """Record a Pulse Engine time-step latency sample (NFR-P5)."""
    _registry.record_pulse_step(latency_ms)


def record_hash_chain(rows: int, elapsed_seconds: float) -> None:
    """Record a hash-chain verification timing sample (NFR-P4)."""
    _registry.record_hash_chain(rows, elapsed_seconds)


def reset_metrics() -> None:
    """Clear all collected metrics. Intended for test isolation."""
    _registry.reset()


# ---------------------------------------------------------------------------
# ASGI middleware
# ---------------------------------------------------------------------------

class ResponseTimeMiddleware:
    """
    ASGI middleware that records per-endpoint response-time metrics for HTTP requests.

    Implements:
        SRS NFR-PERF-002 measurement point for request latency.

    Usage:
        app.add_middleware(ResponseTimeMiddleware)
    """

    def __init__(
        self,
        app: ASGIApp,
        slow_threshold_ms: float = DEFAULT_HTTP_SLOW_THRESHOLD_MS,
        registry: Optional[MetricsRegistry] = None,
    ) -> None:
        self.app = app
        self.slow_threshold_ms = slow_threshold_ms
        self.registry = registry or _registry

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")
        start = time.perf_counter()

        async def _send_wrapper(message):
            if message["type"] == "http.response.start":
                latency_ms = (time.perf_counter() - start) * 1000
                self.registry.record_http(path, method, latency_ms)
                if latency_ms > self.slow_threshold_ms:
                    logger.warning(
                        "Slow request: %s %s took %.2fms (threshold %.0fms)",
                        method, path, latency_ms, self.slow_threshold_ms,
                    )
            await send(message)

        await self.app(scope, receive, _send_wrapper)


@asynccontextmanager
async def track_ws_relay():
    """
    Context manager that records one WebSocket message relay latency sample.

    Usage:
        async with track_ws_relay():
            await websocket.send_json(message)
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        latency_ms = (time.perf_counter() - start) * 1000
        record_ws_latency(latency_ms)
        if latency_ms > DEFAULT_WS_SLOW_THRESHOLD_MS:
            logger.warning(
                "Slow WS relay: %.2fms (threshold %.0fms)",
                latency_ms, DEFAULT_WS_SLOW_THRESHOLD_MS,
            )
