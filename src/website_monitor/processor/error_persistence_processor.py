"""
Database persistence module for monitoring check failures.

This module provides functionality to persist information about failed monitoring
checks to a database in efficient batches.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from asyncpg import Pool, exceptions

from website_monitor.contracts import ResultProcessor
from website_monitor.domain import FetchResult

# Module logger
logger = logging.getLogger(__name__)


class FailurePersistenceProcessor(ResultProcessor):
    """
    A result processor that persists failure information to a database in batches.

    This processor buffers results that contain an error and writes them to the
    database when the buffer is full or when the flush() method is called.
    Successful checks are ignored.
    """

    def __init__(self, worker_id: str, pool: Pool, max_buffer_size: int = 50) -> None:
        """
        Initialize a new FailurePersistenceProcessor.

        Args:
            worker_id: The identifier of the worker that performed the check.
            pool: The database connection pool for database operations.
            max_buffer_size: The max number of failures to buffer before flushing.
        """
        self._worker_id: str = worker_id
        self._pool: Pool = pool
        self._max_buffer_size: int = max_buffer_size
        self._buffer: List[FetchResult] = []
        self._lock = asyncio.Lock()
        self._insert_sql = """
            INSERT INTO failure_log (original_target_id, worker_id, check_start_time,
                                     check_end_time, failure_type, detail,
                                     http_status_code, target_snapshot)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8);
        """

    async def process(self, result: FetchResult) -> None:
        """
        Process a fetch result by buffering failure information.

        If the result contains an error, it's added to the buffer. If the buffer
        reaches its maximum size, a flush is triggered. Successful checks are ignored.

        Args:
            result: The result of a monitoring check to process.
        """
        if result.error is None:
            # The check was successful, do nothing.
            return

        async with self._lock:
            self._buffer.append(result)
            should_flush = len(self._buffer) >= self._max_buffer_size

        if should_flush:
            logger.info(f"Failure buffer limit of {self._max_buffer_size} reached. Flushing.")
            await self.flush()

    async def flush(self) -> None:
        """
        Persists all currently buffered failure logs to the database in a single batch.
        """
        async with self._lock:
            if not self._buffer:
                return
            data_to_flush = list(self._buffer)
            self._buffer.clear()

        logger.info(f"Flushing {len(data_to_flush)} failure logs to the database.")

        records_to_insert = []
        for result in data_to_flush:
            # This check is technically redundant if process() is the only way
            # to add to the buffer, but it adds robustness.
            if result.error is None:
                continue

            # Perform data transformations for each record
            check_start_time = datetime.fromtimestamp(result.start_time, tz=timezone.utc)
            check_end_time = datetime.fromtimestamp(result.end_time, tz=timezone.utc)
            failure_type = type(result.error).__name__
            detail = str(result.error)
            target_snapshot: Dict[str, Any] = {
                "url": result.target.url,
                "method": result.target.method.value,
                "check_interval_seconds": result.target.check_interval.total_seconds(),
                "regex_pattern": result.target.regex_pattern,
                "default_headers": result.target.default_headers,
            }
            records_to_insert.append(
                (
                    result.target.id,
                    self._worker_id,
                    check_start_time,
                    check_end_time,
                    failure_type,
                    detail,
                    result.status_code,
                    target_snapshot,
                )
            )

        if not records_to_insert:
            return

        try:
            async with self._pool.acquire() as connection:
                await connection.executemany(self._insert_sql, records_to_insert)
            logger.debug(f"Successfully flushed {len(records_to_insert)} failure logs.")
        except exceptions.PostgresError as e:
            logger.exception(
                f"Database error during batch flush of failure logs: {e}. "
                f"{len(records_to_insert)} logs may be lost."
            )
        except Exception:
            logger.exception(
                f"An unexpected error occurred during batch flush of failure logs. "
                f"{len(records_to_insert)} logs may be lost."
            )
