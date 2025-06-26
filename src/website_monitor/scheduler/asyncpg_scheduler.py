"""
PostgresSQL-based implementation of the WorkScheduler interface.

This module provides a scheduler that uses PostgresSQL to manage and distribute
monitoring tasks across multiple workers. It uses row-level locking to ensure
that each target is processed by only one worker at a time.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from asyncpg import Pool, Record

from website_monitor.contracts import WorkScheduler
from website_monitor.domain import Target

# Module logger
logger = logging.getLogger(__name__)

# SQL query to fetch due targets and update their lease information
FETCH_AND_LEASE_QUERY = """
                        WITH due_targets AS (SELECT monitored_target_id
                                             FROM target_leases
                                             WHERE next_fire_at <= NOW()
                                             ORDER BY next_fire_at
                                             LIMIT $1 FOR UPDATE SKIP LOCKED),
                             updated_leases AS (
                                 UPDATE target_leases tl
                                     SET
                                         next_fire_at = NOW() + mt.check_interval,
                                         worker_id = $2,
                                         lease_acquired_at = NOW()
                                     FROM due_targets dt
                                         JOIN monitored_targets mt ON mt.id = dt.monitored_target_id
                                     WHERE tl.monitored_target_id = dt.monitored_target_id
                                     RETURNING tl.monitored_target_id)
                        SELECT mt.id,
                               mt.url,
                               mt.method,
                               mt.check_interval,
                               mt.regex_pattern,
                               mt.default_headers
                        FROM monitored_targets mt
                                 JOIN updated_leases ul ON mt.id = ul.monitored_target_id; \
                        """

# SQL query to get the next scheduled target execution time
GET_NEXT_FIRE_AT_QUERY = "SELECT MIN(next_fire_at) FROM target_leases"


async def map_target(record: Record) -> Target:
    """
    Converts a database record to a Target domain object.

    This function transforms raw database records into domain objects,
    applying any necessary transformations to ensure data consistency.

    Args:
        record: A database record containing target information.

    Returns:
        Target: A domain object representing a monitoring target.
    """
    modified_record: Dict[str, Any] = {
        **record,
        "method": record.get("method", "GET").upper(),  # Ensure method is uppercase
    }
    return Target(**modified_record)


class PostgresScheduler(WorkScheduler):
    """
    A PostgreSQL-based implementation of the WorkScheduler interface.

    This scheduler uses PostgreSQL's row-level locking capabilities to
    distribute work across multiple workers while ensuring each target
    is processed by only one worker at a time.
    """

    def __init__(
        self,
        worker_id: str,
        pool: Pool,
        batch_size: int,
        recover_time: int = 10,
        max_sleep_duration: int = 60,
    ) -> None:
        """
        Initializes a new PostgresScheduler instance.

        Args:
            worker_id: A unique identifier for this worker instance.
            pool: A connection pool to the PostgreSQL database.
            batch_size: Maximum number of targets to fetch in a single batch.
            recover_time: Time in seconds to wait after an error before retrying.

        Raises:
            ValueError: If any of the parameters have invalid values.
        """
        if not isinstance(worker_id, str) or not worker_id:
            raise ValueError("worker_id must be provided and must be not blank.")

        if not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError("batch_size must be a positive integer.")

        if not isinstance(recover_time, int) or recover_time < 1:
            raise ValueError("recover_time must be a positive integer.")

        self._worker_id: str = worker_id
        self._pool: Pool = pool
        self._batch_size: int = batch_size
        self._recover_time: int = recover_time
        self._is_running: bool = False
        self._max_sleep_duration: int = max_sleep_duration

    async def start(self) -> None:
        """
        Prepares the scheduler to start yielding work.

        This method must be called before using the scheduler in an async for loop.

        Returns:
            None
        """
        logger.info(f"Starting scheduler (batch size: {self._batch_size})...")
        self._is_running = True

    async def stop(self) -> None:
        """
        Gracefully stops the scheduler and releases any acquired resources.

        This method should be called when the scheduler is no longer needed.

        Returns:
            None
        """
        logger.info("Closing scheduler...")
        self._is_running = False

    async def __anext__(self) -> List[Target]:
        """
        Waits for and returns the next batch of work.

        This method retrieves a batch of due targets from the database,
        updates their lease information, and returns them as Target objects.
        If no targets are due, it calculates the time until the next due target
        and sleeps accordingly.

        Returns:
            List[Target]: A list of Target objects to be processed.

        Raises:
            StopAsyncIteration: When the scheduler has been stopped.
        """
        while self._is_running:
            try:
                # Attempt to fetch and lease a batch of due targets
                async with self._pool.acquire() as conn:
                    async with conn.transaction():
                        records = await conn.fetch(
                            FETCH_AND_LEASE_QUERY, self._batch_size, self._worker_id
                        )

                if records:
                    # If we got targets, convert them to domain objects and return
                    batch = [await map_target(record) for record in records]
                    return batch

                # If no targets are due, find out when the next one is scheduled
                async with self._pool.acquire() as conn:
                    next_deadline = await conn.fetchval(GET_NEXT_FIRE_AT_QUERY)

                # Calculate how long to sleep until the next target is due
                if next_deadline:
                    now = datetime.now(timezone.utc)
                    sleep_duration_seconds = max(0, (next_deadline - now).total_seconds())

                # Cap the sleep duration to 60 seconds to ensure we check periodically
                sleep_duration_seconds = min(self._max_sleep_duration, 60)

                logger.info(f"No tasks due. Sleeping for {sleep_duration_seconds:.2f} seconds.")
                await asyncio.sleep(sleep_duration_seconds)

            except Exception as e:
                # Log any errors and wait before retrying
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(self._recover_time)

        # If we're no longer running, signal the end of iteration
        raise StopAsyncIteration
