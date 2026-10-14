# SPDX-License-Identifier: MIT
"""
Telemetry Relay Routes
Implements SRS NFR-PERF-002 (WebSocket relay), NFR-PERF-001 (ingestion), FR-DAT-001 (decoupled
relay), FR-RTA-005 (EMA filtering), FR-3.5.4 (alarms on the filtered value), and NFR-SEC-001
(scoped JWT on every route).

Origin: BioSync-Gateway middleware/api/routes/telemetry.py (adapted).

Adaptations:
  * The relay never writes to the database. Each accepted frame is placed in the RelayWriter queue
    (api/relay_writer.py). The writer task persists it through the sink (api/relay_sink.py).
    This module imports no database or model module (gate G1.5, FR-DAT-001).
  * The Gateway POST /ingest persisted synchronously and returned "persisted". This route
    returns 202 with "queued" when the frame is accepted. It returns 503 with Retry-After when
    the queue is full and does not relay the frame.
  * The WebSocket accepts telemetry frames from clients with the telemetry_write scope.
    The Gateway accepted only subscribe and ping frames.
  * The Gateway GET /history route is not migrated (synchronous reads on the event loop).
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from api.auth import require_scope, verify_token
from api.middleware.response_time import (
    get_metrics,
    record_ws_connection,
    track_ws_relay,
)
from api.relay_writer import (
    OFFER_ACCEPTED,
    RelayWriter,
    SampleRecord,
    SessionRecord,
)
from api.routes.telemetry_generator import TelemetryGenerator
from engine.signal import MultiChannelEMAFilter

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_OBSERVATIONS_PER_FRAME = 1000
MAX_RUN_KEY_LENGTH = 255
MAX_UNIT_LENGTH = 50
MESSAGE_BUFFER_SIZE = 1000
REPLAY_COUNT = 100

INGEST_ACCEPTED = "accepted"
INGEST_REJECTED = "rejected"
INGEST_INVALID = "invalid"

# Per-channel physiological alarm thresholds evaluated on the EMA-filtered value.
# Prevents false alarms from noisy raw samples (SRS FR-3.5.4).
# Thresholds reflect SRS Section 3.1.5 (e.g. 150 mmHg arthroscopic pump pressure limit).
ALARM_THRESHOLDS = {
    "pressure": {"high": 150.0},                  # mmHg
    "hr": {"high": 120.0, "low": 50.0},          # bpm
    "spo2": {"low": 90.0},                        # %
    "flow": {"high": 60.0, "low": -60.0},         # L/min
}

def evaluate_alarm(channel: str, filtered_value: Optional[float]) -> Optional[Dict]:
    """
    Evaluate alarm state for a channel using the EMA-filtered value.

    Args:
        channel: Resolved telemetry channel name
        filtered_value: EMA-filtered observation value

    Returns:
        Alarm dict with active flag and severity, or None if channel unknown.

    Implements:
        SRS FR-3.5.4 - Filtered alarms (false alarm prevention)
    """
    thresholds = ALARM_THRESHOLDS.get(channel)
    if not thresholds or filtered_value is None:
        return None

    if "high" in thresholds and filtered_value > thresholds["high"]:
        return {"active": True, "direction": "high", "threshold": thresholds["high"]}
    if "low" in thresholds and filtered_value < thresholds["low"]:
        return {"active": True, "direction": "low", "threshold": thresholds["low"]}
    return {"active": False, "direction": None, "threshold": None}


class FrameError(ValueError):
    """A telemetry frame failed validation. Raised before any filter state changes."""


def validate_frame(payload) -> tuple:
    """
    Validate a telemetry payload and return (observations, run_key or None).

    Each observation needs a finite numeric valueQuantity.value and a non-empty unit, because
    the sample record stores both. The run_key, when present, must be a string of at most 255
    characters.
    """
    if not isinstance(payload, dict):
        raise FrameError("payload must be an object")
    observations = payload.get("observations")
    if not isinstance(observations, list) or not observations:
        raise FrameError("observations must be a non-empty list")
    if len(observations) > MAX_OBSERVATIONS_PER_FRAME:
        raise FrameError(f"at most {MAX_OBSERVATIONS_PER_FRAME} observations per frame")
    for obs in observations:
        if not isinstance(obs, dict):
            raise FrameError("each observation must be an object")
        vq = obs.get("valueQuantity")
        if not isinstance(vq, dict):
            raise FrameError("each observation needs valueQuantity")
        value = vq.get("value")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise FrameError("valueQuantity.value must be a finite number")
        unit = vq.get("unit")
        if not isinstance(unit, str) or not unit.strip() or len(unit) > MAX_UNIT_LENGTH:
            raise FrameError(f"valueQuantity.unit must be a non-empty string of at most {MAX_UNIT_LENGTH} characters")
    run_key = payload.get("run_key")
    if run_key is not None:
        if not isinstance(run_key, str) or not run_key or len(run_key) > MAX_RUN_KEY_LENGTH:
            raise FrameError(f"run_key must be a non-empty string of at most {MAX_RUN_KEY_LENGTH} characters")
    return observations, run_key


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_iso() -> str:
    return _utc_now().isoformat()


def _parse_timestamp(value) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _error_frame(code: str, message: str) -> Dict:
    return {
        "type": "error",
        "payload": {"code": code, "message": message},
        "timestamp": _utc_iso(),
    }


class ConnectionManager:
    """Active WebSocket clients, fan-out broadcast, and a replay buffer for new clients."""

    def __init__(self) -> None:
        self.active_connections: List[WebSocket] = []
        self.message_buffer: Deque[Dict] = deque(maxlen=MESSAGE_BUFFER_SIZE)
        self.max_buffer_size = MESSAGE_BUFFER_SIZE

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        record_ws_connection(1)
        logger.info("WebSocket connected: %s", websocket.client)

        for msg in list(self.message_buffer)[-REPLAY_COUNT:]:
            try:
                async with track_ws_relay():
                    await websocket.send_json(msg)
            except Exception:
                break

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            record_ws_connection(-1)
            logger.info("WebSocket disconnected: %s", websocket.client)

    async def broadcast(self, message: Dict) -> None:
        """Send a message to every connected client."""
        self.message_buffer.append(message)

        disconnected = []
        for connection in list(self.active_connections):
            try:
                async with track_ws_relay():
                    await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)


@dataclass
class IngestResult:
    status: str
    points: int = 0
    alarms: List[Dict] = field(default_factory=list)
    message: Optional[Dict] = None
    reason: str = ""


class TelemetryRelay:
    """
    Per-application relay state: the writer handle, the EMA filter, and the client manager.

    ingest() is synchronous and never waits. It validates the frame, checks queue admission, runs
    the EMA filter, and enqueues raw and filtered sample records. It returns the message to relay.
    The caller relays only accepted frames, so a frame that was not queued for persistence is
    never shown to subscribers.
    """

    def __init__(self, writer: RelayWriter, ema_filter: Optional[MultiChannelEMAFilter] = None) -> None:
        self.writer = writer
        self.ema = ema_filter or MultiChannelEMAFilter()
        self.manager = ConnectionManager()

    async def broadcast(self, message: Dict) -> None:
        await self.manager.broadcast(message)

    def ingest(self, payload, default_run_key: str) -> IngestResult:
        try:
            observations, run_key = validate_frame(payload)
        except FrameError as exc:
            return IngestResult(status=INGEST_INVALID, reason=str(exc))

        admission = self.writer.admit_samples(len(observations))
        if admission != OFFER_ACCEPTED:
            return IngestResult(status=INGEST_REJECTED, reason=admission)

        run_key = run_key or default_run_key
        records: List[SampleRecord] = []
        filtered_observations: List[Dict] = []
        alarms: List[Dict] = []

        for obs in observations:
            channel = MultiChannelEMAFilter.resolve_channel(obs)
            vq = obs["valueQuantity"]
            raw_value = float(vq["value"])
            unit = vq["unit"]

            filtered_obs = self.ema.filter_observation(dict(obs))
            filtered_data = filtered_obs.get("filtered_data")
            filtered_value = filtered_data["value"] if filtered_data else None

            records.append(SampleRecord(
                run_key=run_key,
                channel=channel,
                unit=unit,
                raw_value=raw_value,
                filtered_value=filtered_value,
                filter_name=filtered_data["filter"] if filtered_data else None,
                filter_alpha=filtered_data["alpha"] if filtered_data else None,
                source_timestamp=_parse_timestamp(obs.get("effectiveDateTime")),
            ))

            filtered_obs["raw_data"] = {"value": raw_value, "unit": unit}
            alarm = evaluate_alarm(channel, filtered_value)
            if alarm:
                filtered_obs["alarm"] = alarm
                if alarm["active"]:
                    alarms.append({"channel": channel, **alarm})
            filtered_observations.append(filtered_obs)

        self.writer.enqueue_samples(records)

        message = {
            "type": "telemetry",
            "payload": {
                "patientId": payload.get("patientId"),
                "timestamp": payload.get("timestamp"),
                "observations": filtered_observations,
                "alarms": alarms,
            },
            "timestamp": _utc_iso(),
        }
        return IngestResult(
            status=INGEST_ACCEPTED,
            points=len(records),
            alarms=alarms,
            message=message,
        )


def _relay(connection) -> TelemetryRelay:
    """Return the relay of the application that owns a Request or WebSocket."""
    return connection.app.state.telemetry_relay


@router.websocket("/stream")
async def telemetry_stream(websocket: WebSocket, token: Optional[str] = None):
    """
    WebSocket endpoint for real-time telemetry streaming.
    Implements SRS NFR-PERF-002 (WSS relay) and NFR-SEC-001 (JWT).
    Requires a JWT via the ?token= query parameter or an Authorization header.
    Clients with telemetry_write may send {"type": "telemetry", "payload": {...}} frames.
    """
    auth_header = websocket.headers.get("Authorization")
    if not token and auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]

    if not token:
        await websocket.close(code=4401, reason="Missing authentication token")
        return

    try:
        payload = verify_token(token)
    except Exception:
        payload = None
    if not payload:
        await websocket.close(code=4401, reason="Invalid authentication token")
        return

    client_identity = payload.get("sub")
    if not isinstance(client_identity, str) or not client_identity:
        await websocket.close(code=4401, reason="Token has no subject")
        return

    scopes = payload.get("scope") or payload.get("scopes") or []
    if "telemetry_read" not in scopes and "admin" not in scopes:
        await websocket.close(code=4403, reason="Insufficient scope")
        return
    can_publish = "telemetry_write" in scopes or "admin" in scopes

    relay = _relay(websocket)
    if not relay.writer.running:
        await websocket.close(code=1013, reason="Relay writer unavailable")
        return

    await relay.manager.connect(websocket)

    session_uid = str(uuid4())
    connected_at = _utc_now()
    points = 0
    opened = False
    try:
        if not await relay.writer.put_lifecycle(SessionRecord(
            session_uid=session_uid,
            record_status="open",
            client_identity=client_identity,
            connected_at=connected_at,
            disconnected_at=None,
            points_relayed=0,
        )):
            await websocket.close(code=1013, reason="Relay writer unavailable")
            return
        opened = True

        while True:
            try:
                data = await websocket.receive_json()
            except json.JSONDecodeError:
                await websocket.send_json(_error_frame("invalid_json", "Frame is not valid JSON"))
                continue

            if not isinstance(data, dict):
                await websocket.send_json(_error_frame("invalid_frame", "Frame must be a JSON object"))
                continue

            frame_type = data.get("type")
            if frame_type == "subscribe":
                await websocket.send_json({
                    "type": "subscribed",
                    "payload": {"channels": data.get("channels", [])},
                    "timestamp": _utc_iso(),
                })
            elif frame_type == "ping":
                await websocket.send_json({"type": "pong", "timestamp": _utc_iso()})
            elif frame_type == "telemetry":
                if not can_publish:
                    await websocket.send_json(_error_frame("forbidden", "telemetry_write scope required"))
                    continue
                result = relay.ingest(data.get("payload"), default_run_key=f"relay:{session_uid}")
                if result.status == INGEST_INVALID:
                    await websocket.send_json(_error_frame("invalid_payload", result.reason))
                    continue
                if result.status == INGEST_REJECTED:
                    await websocket.send_json(_error_frame("backpressure", f"Relay queue unavailable ({result.reason})"))
                    continue
                points += result.points
                await relay.broadcast(result.message)
            else:
                await websocket.send_json(_error_frame("unsupported_type", "Unknown frame type"))
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
    finally:
        relay.manager.disconnect(websocket)
        if opened:
            await relay.writer.put_lifecycle(SessionRecord(
                session_uid=session_uid,
                record_status="finalized",
                client_identity=client_identity,
                connected_at=connected_at,
                disconnected_at=_utc_now(),
                points_relayed=points,
            ))


@router.post("/ingest", status_code=202)
async def ingest_telemetry(
    request: Request,
    telemetry_data: dict,
    current_user=Depends(require_scope("telemetry_write")),
):
    """
    Accept a telemetry frame over HTTP. Applies EMA filtering and queues raw and filtered samples
    for persistence. Relays the filtered frame to WebSocket subscribers after the queue admits it.
    Implements SRS FR-3.5.1, FR-3.5.3, FR-3.5.4, and NFR-PERF-001.
    """
    relay = _relay(request)
    result = relay.ingest(telemetry_data, default_run_key=f"relay:{uuid4()}")

    if result.status == INGEST_INVALID:
        raise HTTPException(status_code=422, detail=result.reason)
    if result.status == INGEST_REJECTED:
        return JSONResponse(
            status_code=503,
            content={"status": "rejected", "reason": result.reason},
            headers={"Retry-After": "1"},
        )

    await relay.broadcast(result.message)
    return {
        "status": "queued",
        "queued": result.points,
        "alarms": result.alarms,
        "timestamp": _utc_iso(),
    }


@router.get("/stream/info")
async def get_stream_info(
    request: Request,
    current_user=Depends(require_scope("telemetry_read")),
):
    """Get telemetry stream information."""
    relay = _relay(request)
    return {
        "stream_url": "/api/telemetry/stream",
        "active_connections": len(relay.manager.active_connections),
        "buffer_size": len(relay.manager.message_buffer),
        "supported_channels": ["pressure", "flow", "hr", "spo2"],
    }


@router.get("/ingestion/stats")
async def get_ingestion_stats(
    request: Request,
    current_user=Depends(require_scope("telemetry_read")),
):
    """
    Get telemetry ingestion statistics.
    Implements SRS NFR-PERF-001 (ingestion throughput) and NFR-PERF-002 (relay latency).
    """
    relay = _relay(request)
    snapshot = get_metrics().snapshot()
    return {
        "active_connections": len(relay.manager.active_connections),
        "buffer_size": len(relay.manager.message_buffer),
        "ingestion_rate_pps": snapshot["throughput"]["ingestion_rate_pps"],
        "ws_relay_latency_ms": snapshot["websocket"]["relay_latency_ms"],
        "writer": relay.writer.snapshot(),
    }


async def run_telemetry_simulator(relay: TelemetryRelay, interval_s: float = 0.1) -> None:
    """
    Broadcast synthetic telemetry to WebSocket clients. Opt-in (see api/main.py). Output is not
    persisted, because it is synthetic and not compliance data.
    """
    generator = TelemetryGenerator()
    logger.info("Telemetry simulator started")
    while True:
        try:
            data = generator.generate_timestep(dt=interval_s)
            await relay.broadcast({"type": "telemetry", "payload": data, "timestamp": _utc_iso()})
            await asyncio.sleep(interval_s)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Telemetry simulator error: %s", exc)
            await asyncio.sleep(1)
