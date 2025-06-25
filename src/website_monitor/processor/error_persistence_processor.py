"""
Database persistence module for monitoring check failures.

This module provides functionality to persist information about failed monitoring
checks to a database. It captures detailed information about the failure, including
the error type, timing information, and a snapshot of the target configuration.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from asyncpg import Pool

from website_monitor.contracts import ResultProcessor
from website_monitor.domain import FetchResult

# Module logger
logger = logging.getLogger(__name__)


class FailurePersistenceProcessor(ResultProcessor):
    """
    A result processor that persists failure information to a database.

    This processor is responsible for storing detailed information about failed
    monitoring checks in the database. It only processes results that contain
    an error and ignores successful checks.

    Attributes:
        _worker_id (str): The identifier of the worker that performed the check.
        _pool (Pool): The database connection pool for database operations.
    """

    def __init__(self, worker_id: str, pool: Pool) -> None:
        """
        Initialize a new FailurePersistenceProcessor.

        Args:
            worker_id (str): The identifier of the worker that performed the check.
            pool (Pool): The database connection pool for database operations.
        """
        self._worker_id: str = worker_id
        self._pool: Pool = pool

    async def process(self, result: FetchResult) -> None:
        """
        Process a fetch result by persisting failure information to the database.

        This method checks if the result contains an error. If it does, it extracts
        relevant information and stores it in the failure_log table. If the result
        does not contain an error (successful check), this method does nothing.

        Args:
            result (FetchResult): The result of a monitoring check to process.

        Returns:
            None

        Raises:
            No exceptions are raised from this method. Database errors are caught
            and logged internally.
        """
        if result.error is None:
            # The check was successful, do nothing.
            return

        # Convert Unix timestamps to datetime objects with UTC timezone
        check_start_time = datetime.fromtimestamp(result.start_time, tz=timezone.utc)
        check_end_time = datetime.fromtimestamp(result.end_time, tz=timezone.utc)

        # Extract error information
        failure_type = type(result.error).__name__
        detail = str(result.error)

        # Create a snapshot of the target configuration for historical reference
        target_snapshot: Dict[str, Any] = {
            "url": result.target.url,
            "method": result.target.method.value,
            "check_interval_seconds": result.target.check_interval.total_seconds(),
            "regex_pattern": result.target.regex_pattern,
            "default_headers": result.target.default_headers,
        }

        # SQL query to insert the failure record
        query = """
                INSERT INTO failure_log (original_target_id, worker_id, check_start_time,
                                         check_end_time, failure_type, detail,
                                         http_status_code, target_snapshot)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8) \
                """

        try:
            # Acquire a connection from the pool and execute the query
            async with self._pool.acquire() as connection:
                await connection.execute(
                    query,
                    result.target.id,
                    self._worker_id,
                    check_start_time,
                    check_end_time,
                    failure_type,
                    detail,
                    result.status_code,
                    target_snapshot,
                )
            logger.debug(
                "Successfully persisted failure for original_target_id=%s: %s",
                result.target.id,
                failure_type,
            )
        except Exception:
            # Log the exception but don't propagate it to avoid disrupting the processing pipeline
            logger.exception(
                "Failed to persist failure for original_target_id=%s to the database.",
                result.target.id,
            )
