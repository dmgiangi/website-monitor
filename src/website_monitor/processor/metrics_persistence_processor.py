import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from asyncpg import Pool, exceptions

from website_monitor.contracts import ResultProcessor
from website_monitor.domain import FetchResult

# Module logger
logger = logging.getLogger(__name__)


class MetricsPersistenceProcessor(ResultProcessor):
    """
    Persists FetchResult metrics to the time-series 'metrics' table in batches.

    This processor efficiently buffers check results and writes them to a
    TimescaleDB hypertable. It transforms the raw FetchResult into the flattened,
    denormalized schema required by the metrics table, including deriving
    the 'is_success' flag for fast uptime/downtime queries.
    """

    def __init__(self, worker_id: str, pool: Pool, max_buffer_size: int = 50) -> None:
        """
        Initializes the processor.

        Args:
            worker_id: A unique identifier for the worker using this processor.
            pool: The asyncpg connection pool.
            max_buffer_size: The maximum number of results to buffer in memory
                before a flush is automatically triggered.
        """
        self._worker_id: str = worker_id
        self._pool: Pool = pool
        self._max_buffer_size: int = max_buffer_size

        # The buffer will store tuples ready for insertion.
        self._buffer: List[tuple] = []
        self._lock = asyncio.Lock()
        self._insert_sql = """
            INSERT INTO metrics (
                checked_at, target_id, target_url, status_code, regex_match,
                is_success, worker_id, response_time_ms
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8);
        """

    def _transform_result(self, result: FetchResult) -> tuple:
        """
        Transforms a FetchResult object into a tuple matching the 'metrics' table schema.
        """
        # Derive the is_success flag based on the check outcome.
        # A check is successful if there was no exception and the HTTP status is in the 2xx range.
        is_success = result.error is None

        # Calculate response time in milliseconds.
        response_time_ms = int((result.end_time - result.start_time) * 1000)

        # Convert the start time to a timezone-aware datetime object for the 'checked_at' column.
        checked_at = datetime.fromtimestamp(result.start_time, tz=timezone.utc)

        return (
            checked_at,
            result.target.id,
            result.target.url,
            result.status_code,
            result.regex_has_matches,
            is_success,
            self._worker_id,
            response_time_ms,
        )

    async def process(self, result: FetchResult) -> None:
        """
        Transforms and adds a result to the internal buffer. If the buffer
        exceeds the maximum size, it triggers a flush to the database.
        """
        record_to_insert = self._transform_result(result)

        async with self._lock:
            self._buffer.append(record_to_insert)
            should_flush = len(self._buffer) >= self._max_buffer_size

        if should_flush:
            logger.info(
                f"Metrics buffer limit of {self._max_buffer_size} reached. Flushing automatically."
            )
            await self.flush()

    async def flush(self) -> None:
        """
        Persists all currently buffered metrics to the database in a single batch.
        This method is safe to call even if the buffer is empty.
        """
        async with self._lock:
            if not self._buffer:
                return

            # Create a copy and clear the original buffer immediately to minimize lock time.
            records_to_insert = list(self._buffer)
            self._buffer.clear()

        logger.info(f"Flushing {len(records_to_insert)} metrics to the database.")

        try:
            async with self._pool.acquire(timeout=10.0) as conn:
                async with conn.transaction():
                    logger.debug("Acquired connection and started transaction.")
                    await conn.executemany(self._insert_sql, records_to_insert)
                    logger.debug("conn.executemany() completed successfully.")

            logger.debug(f"Successfully flushed {len(records_to_insert)} metrics.")
        except asyncio.TimeoutError:
            logger.error(f"Timeout during DB flush. {len(records_to_insert)} metrics may be lost.")
        except exceptions.PostgresError as e:
            logger.error(
                f"Database error during batch flush of metrics: {e}. "
                f"{len(records_to_insert)} metrics may be lost."
            )
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during metrics flush: {e}. "
                f"{len(records_to_insert)} metrics may be lost."
            )
