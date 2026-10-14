# SPDX-License-Identifier: MIT
"""
SurgiTwin-RTA middleware application (SRS FR-DAT-001 three-tier gateway).

The relay (routes/telemetry.py) is the visualization tier. Its records are written by a writer
task (api/relay_writer.py) into the compliance tier through the sink (api/relay_sink.py).
create_app() takes an optional sink and queue size so tests can run the same wiring with a fake
sink. The module-level app is the production instance used by uvicorn.
"""

import asyncio
import contextlib
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI

from api.auth import User, get_current_user
from api.loop_policy import configure_uvloop
from api.middleware.response_time import ResponseTimeMiddleware
from api.relay_sink import SqlAlchemyRelaySink
from api.relay_writer import DEFAULT_QUEUE_MAXSIZE, RelaySink, RelayWriter
from api.routes import audit, auth, fhir, telemetry
from api.routes.telemetry import TelemetryRelay, run_telemetry_simulator

# R3 event-loop policy (Gateway open item, see docs/migration-map.md). Skipped under pytest.
configure_uvloop()

SIMULATOR_ENV = "TELEMETRY_SIMULATOR"


def health() -> dict[str, str]:
    return {"status": "ok"}


async def protected_endpoint(current_user: User = Depends(get_current_user)):
    """Example endpoint requiring a valid JWT (SRS NFR-SEC-001)."""
    return {
        "message": "Access granted",
        "user": current_user.username,
        "role": current_user.role,
        "scope": current_user.scopes,
        "scopes": current_user.scopes,
    }


def create_app(
    relay_sink: Optional[RelaySink] = None,
    relay_queue_maxsize: int = DEFAULT_QUEUE_MAXSIZE,
) -> FastAPI:
    """
    Build the application. The relay writer starts in the lifespan and stops on shutdown.

    Args:
        relay_sink: Persistence sink for relay records. Defaults to the PostgreSQL sink.
        relay_queue_maxsize: Bound of the relay queue (records).
    """
    writer = RelayWriter(
        relay_sink if relay_sink is not None else SqlAlchemyRelaySink(),
        maxsize=relay_queue_maxsize,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        writer.start()
        simulator = None
        if os.getenv(SIMULATOR_ENV, "").lower() in ("1", "true", "yes"):
            simulator = asyncio.create_task(
                run_telemetry_simulator(app.state.telemetry_relay), name="telemetry-simulator"
            )
        try:
            yield
        finally:
            if simulator is not None:
                simulator.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await simulator
            await writer.stop()

    app = FastAPI(title="SurgiTwin-RTA Middleware", lifespan=lifespan)
    app.state.telemetry_relay = TelemetryRelay(writer)

    app.add_middleware(ResponseTimeMiddleware)

    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(audit.router, prefix="/api/audit", tags=["audit"])
    app.include_router(fhir.router, prefix="/api/fhir", tags=["fhir"])
    app.include_router(telemetry.router, prefix="/api/telemetry", tags=["telemetry"])

    app.add_api_route("/health", health, methods=["GET"])
    app.add_api_route("/api/protected", protected_endpoint, methods=["GET"])
    return app


app = create_app()
