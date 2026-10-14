# SPDX-License-Identifier: MIT
"""
Off-loop persistence queue for the telemetry relay (SRS FR-DAT-001, NFR-PERF-001, gate G1.5).

Origin: none. New module for Gateway open item R3 (synchronous database writes on the relay path).

The relay handlers never write to the database. They place records in a bounded asyncio queue.
One writer task drains the queue in batches and hands each batch to a sink. This module imports
no database code, so the relay path does not depend on the compliance tier. The sink
(api/relay_sink.py) is the only component that writes.

Backpressure:
  * Telemetry samples are offered all-or-nothing. A frame is accepted only when the queue has
    room for every record in it. Otherwise the frame is rejected and is not relayed.
  * Lifecycle records (session open and finalize) wait for queue space through put_lifecycle().
    The wait suspends only the calling coroutine.

Batches are written with one sink call each. A sink call is expected to commit its batch in one
transaction, so a retried batch cannot be partly applied.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol, Sequence, Union

from api.middleware.response_time import record_ingestion_rate

logger = logging.getLogger(__name__)

WRITER_TASK_NAME = "relay-writer"
DEFAULT_QUEUE_MAXSIZE = 10_000
DEFAULT_BATCH_SIZE = 500
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BASE_DELAY_S = 0.5
DEFAULT_DRAIN_TIMEOUT_S = 10.0

OFFER_ACCEPTED = "accepted"
OFFER_REJECTED_FULL = "rejected_full"
OFFER_REJECTED_STOPPED = "rejected_stopped"


@dataclass(frozen=True)
class SampleRecord:
    """One raw telemetry sample and its EMA-filtered value (FR-3.5.3 pattern)."""

    run_key: str
    channel: str
    unit: str
    raw_value: float
    filtered_value: Optional[float]
    filter_name: Optional[str]
    filter_alpha: Optional[float]
    source_timestamp: Optional[datetime]


@dataclass(frozen=True)
class SessionRecord:
    """One telemetry_sessions row. record_status is 'open' or 'finalized'."""

    session_uid: str
    record_status: str
    client_identity: str
    connected_at: datetime
    disconnected_at: Optional[datetime]
    points_relayed: int


RelayRecord = Union[SampleRecord, SessionRecord]


class RelaySink(Protocol):
    """Persists one batch. Runs inside the writer task and must not block the event loop."""

    async def write_batch(self, batch: Sequence[RelayRecord]) -> None:
        ...


class RelayWriter:
    """Bounded queue with a single writer task that drains batches into a sink."""

    def __init__(
        self,
        sink: RelaySink,
        maxsize: int = DEFAULT_QUEUE_MAXSIZE,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        retry_base_delay_s: float = DEFAULT_RETRY_BASE_DELAY_S,
        drain_timeout_s: float = DEFAULT_DRAIN_TIMEOUT_S,
    ) -> None:
        if maxsize < 1 or batch_size < 1 or max_attempts < 1:
            raise ValueError("maxsize, batch_size, and max_attempts must be at least 1")
        self._sink = sink
        self._maxsize = maxsize
        self._batch_size = batch_size
        self._max_attempts = max_attempts
        self._retry_base_delay_s = retry_base_delay_s
        self._drain_timeout_s = drain_timeout_s
        self._queue: Optional[asyncio.Queue] = None
        self._task: Optional[asyncio.Task] = None
        self._accepting = False
        self.accepted_samples = 0
        self.rejected_samples = 0
        self.persisted_records = 0
        self.failed_batches = 0
        self.failed_records = 0
        self.abandoned_records = 0

    @property
    def running(self) -> bool:
        return self._accepting

    @property
    def maxsize(self) -> int:
        return self._maxsize

    @property
    def queue_depth(self) -> int:
        return self._queue.qsize() if self._queue is not None else 0

    def free_slots(self) -> int:
        if not self._accepting:
            return 0
        return self._maxsize - self.queue_depth

    def start(self) -> None:
        """Create the queue and start the writer task on the running loop."""
        if self._task is not None:
            raise RuntimeError("relay writer already started")
        self._queue = asyncio.Queue(maxsize=self._maxsize)
        self._accepting = True
        self._task = asyncio.create_task(self._run(), name=WRITER_TASK_NAME)

    async def stop(self) -> None:
        """Stop intake, drain the queue for up to drain_timeout_s, then cancel the writer task."""
        if self._task is None:
            return
        self._accepting = False
        try:
            await asyncio.wait_for(self._queue.join(), timeout=self._drain_timeout_s)
        except TimeoutError:
            self.abandoned_records += self.queue_depth
            logger.error(
                "Relay drain timed out after %.1fs with %d records queued",
                self._drain_timeout_s, self.queue_depth,
            )
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    def admit_samples(self, count: int) -> str:
        """Check whether count sample records fit. A rejection is counted. Never blocks."""
        if not self._accepting:
            self.rejected_samples += count
            return OFFER_REJECTED_STOPPED
        if count > self.free_slots():
            self.rejected_samples += count
            return OFFER_REJECTED_FULL
        return OFFER_ACCEPTED

    def enqueue_samples(self, records: Sequence[SampleRecord]) -> None:
        """Enqueue records that admit_samples() accepted in the same loop turn."""
        if len(records) > self.free_slots():
            raise RuntimeError("enqueue_samples called without admission")
        for record in records:
            self._queue.put_nowait(record)
        self.accepted_samples += len(records)

    def offer_samples(self, records: Sequence[SampleRecord]) -> str:
        """Admit and enqueue sample records all-or-nothing without waiting."""
        status = self.admit_samples(len(records))
        if status == OFFER_ACCEPTED:
            self.enqueue_samples(records)
        return status

    async def put_lifecycle(self, record: SessionRecord) -> bool:
        """Enqueue a session record, waiting for space. Returns False when intake is stopped."""
        if not self._accepting:
            logger.error("Relay writer stopped; session record %s not queued", record.session_uid)
            return False
        await self._queue.put(record)
        return True

    def snapshot(self) -> dict:
        return {
            "running": self.running,
            "queue_depth": self.queue_depth,
            "queue_maxsize": self._maxsize,
            "accepted_samples": self.accepted_samples,
            "rejected_samples": self.rejected_samples,
            "persisted_records": self.persisted_records,
            "failed_batches": self.failed_batches,
            "failed_records": self.failed_records,
            "abandoned_records": self.abandoned_records,
        }

    async def _run(self) -> None:
        queue = self._queue
        while True:
            batch = [await queue.get()]
            while len(batch) < self._batch_size:
                try:
                    batch.append(queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
            try:
                await self._write_with_retry(batch)
            finally:
                for _ in batch:
                    queue.task_done()

    async def _write_with_retry(self, batch: Sequence[RelayRecord]) -> None:
        sample_count = sum(1 for record in batch if isinstance(record, SampleRecord))
        for attempt in range(1, self._max_attempts + 1):
            started = time.perf_counter()
            try:
                await self._sink.write_batch(batch)
            except Exception as exc:
                if attempt == self._max_attempts:
                    self.failed_batches += 1
                    self.failed_records += len(batch)
                    logger.error(
                        "Relay batch of %d records failed after %d attempts: %s",
                        len(batch), attempt, exc,
                    )
                    return
                delay = self._retry_base_delay_s * (2 ** (attempt - 1))
                logger.warning(
                    "Relay batch of %d records failed (attempt %d of %d), retrying in %.2fs: %s",
                    len(batch), attempt, self._max_attempts, delay, exc,
                )
                await asyncio.sleep(delay)
            else:
                self.persisted_records += len(batch)
                if sample_count:
                    elapsed = max(time.perf_counter() - started, 0.001)
                    record_ingestion_rate(sample_count / elapsed)
                return
