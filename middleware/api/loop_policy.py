# SPDX-License-Identifier: MIT
"""uvloop event-loop policy selection (R3 performance path).

Selecting uvloop as the asyncio event-loop policy is what delivers the
throughput required by NFR-P1 (>=100k pts/s) and keeps the WebSocket relay
under the NFR-P3 latency budget under load (PQ-1 / PQ-8). uvicorn also picks
uvloop automatically when installed, but setting the policy explicitly here
makes the choice deterministic and unit-testable.
"""
import sys
import asyncio
import logging

logger = logging.getLogger(__name__)


def configure_uvloop(force: bool = False) -> bool:
    """
    Use uvloop as the asyncio event-loop policy when available.

    Skipped automatically under pytest (so the test loop is left untouched)
    and on platforms without uvloop (e.g. Windows local dev). `force=True`
    bypasses the pytest guard (used by tests and the explicit server start).

    Returns True if uvloop was selected.
    """
    if not force and "pytest" in sys.modules:
        return False
    try:
        import uvloop
    except ImportError:
        logger.info("uvloop not installed; using default asyncio event loop")
        return False
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logger.info("uvloop event-loop policy enabled (R3 performance path)")
    return True
