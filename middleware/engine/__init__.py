"""
Algorithmic Engines Module
Initializes the signal, hash chain, and Pulse engines for the SurgiTwin-RTA middleware.

Origin: BioSync-Gateway middleware/engine/__init__.py (adapted: barcode and dilution
engines are not migrated).
"""

import logging

logger = logging.getLogger(__name__)


def init_engines():
    """
    Initialize all algorithmic engines.
    Called during application startup.
    """
    logger.info("Initializing algorithmic engines...")

    try:
        from engine import signal, one_euro, lttb, pulse  # noqa: F401
        logger.info("Signal processing engines loaded (EMA, One Euro)")
        logger.info("Pulse engine module loaded")
    except ImportError as e:
        logger.warning(f"Some engines not yet implemented: {e}")

    logger.info("Algorithmic engines initialization complete")
