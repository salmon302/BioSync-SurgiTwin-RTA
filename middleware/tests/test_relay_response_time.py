# SPDX-License-Identifier: MIT
"""
Response-time instrumentation for the relay (SRS NFR-PERF-002 measurement point, NFR-PERF-001).

Covers the HTTP middleware recording, the WebSocket relay sample, the bounded sample windows,
the endpoint-key cap, and the pass-through of WebSocket scopes.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from api.middleware.response_time import (
    DEFAULT_WS_SLOW_THRESHOLD_MS,
    MAX_ENDPOINT_KEYS,
    NFR_P3_WS_P95_MS,
    SAMPLE_WINDOW,
    MetricsRegistry,
    get_metrics,
    reset_metrics,
    track_ws_relay,
)
from api.main import create_app


@pytest.fixture(autouse=True)
def _fresh_metrics():
    reset_metrics()
    yield
    reset_metrics()


def test_http_requests_are_recorded_with_percentiles():
    app = create_app(relay_sink=_NullSink())
    client = TestClient(app)
    for _ in range(5):
        assert client.get("/health").status_code == 200

    snapshot = get_metrics().snapshot()
    stats = snapshot["http"]["GET /health"]
    assert stats["count"] == 5
    assert 0.0 <= stats["p50_ms"] <= stats["p95_ms"] <= stats["p99_ms"] <= stats["max_ms"]


def test_websocket_relay_sample_is_recorded_by_track_ws_relay():
    async def send_once():
        async with track_ws_relay():
            await asyncio.sleep(0.001)

    asyncio.run(send_once())
    relay = get_metrics().snapshot()["websocket"]["relay_latency_ms"]
    assert relay["count"] == 1
    assert relay["target_p95_ms"] == NFR_P3_WS_P95_MS == 50.0
    assert relay["passed"] is True


def test_slow_relay_sample_is_flagged_as_failing_the_p95_target():
    registry = MetricsRegistry()
    for _ in range(20):
        registry.record_ws_latency(DEFAULT_WS_SLOW_THRESHOLD_MS * 2)
    assert registry.snapshot()["websocket"]["relay_latency_ms"]["passed"] is False


def test_sample_windows_are_bounded():
    registry = MetricsRegistry()
    for i in range(SAMPLE_WINDOW + 2_500):
        registry.record_ws_latency(float(i % 7))
        registry.record_ingestion_rate(float(i))
    snapshot = registry.snapshot()
    assert snapshot["websocket"]["relay_latency_ms"]["count"] == SAMPLE_WINDOW
    assert snapshot["throughput"]["ingestion_rate_pps"]["count"] == SAMPLE_WINDOW


def test_endpoint_keys_are_capped_with_an_overflow_bucket():
    registry = MetricsRegistry()
    for i in range(MAX_ENDPOINT_KEYS + 50):
        registry.record_http(f"/api/item/{i}", "GET", 1.0)
    keys = set(registry.snapshot()["http"])
    assert len(keys) == MAX_ENDPOINT_KEYS + 1
    assert "GET OTHER" in keys
    assert sum(entry["count"] for entry in registry.snapshot()["http"].values()) == MAX_ENDPOINT_KEYS + 50


def test_websocket_scope_passes_through_the_response_time_middleware():
    """The middleware records HTTP only. A refused WebSocket still reaches the route and closes normally."""
    app = create_app(relay_sink=_NullSink())
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as refused:
        with client.websocket_connect("/api/telemetry/stream"):
            pass
    assert refused.value.code == 4401
    assert "GET /api/telemetry/stream" not in get_metrics().snapshot()["http"]


class _NullSink:
    async def write_batch(self, batch):
        return None
