"""
Configuration context for the website monitoring system.

This module defines a data structure that holds all configuration parameters
for the monitoring system. It serves as a central point for passing configuration
throughout the application.
"""

from typing import NamedTuple


class MonitoringContext(NamedTuple):
    """
    A data structure containing all configuration parameters for the monitoring system.

    This class is immutable and provides a type-safe way to pass configuration
    throughout the application. It is created by parsing command-line arguments
    and environment variables.

    Attributes:
        dsn: Database connection string for PostgreSQL.
        worker_id: Unique identifier for this worker instance.
        logging_type: Type of logging configuration to use (dev, prod, or custom).
        logging_config_file: Path to custom logging configuration file (if logging_type is 'custom').
        queue_size: Maximum size of the processing queue before backpressure is applied.
        batch_size: Number of targets to fetch in a single database query.
        worker_number: Number of concurrent worker tasks to create.
        db_pool_size: Maximum number of connections in the database connection pool.
        max_timeout: Maximum timeout duration in seconds for HTTP requests.
        raise_for_status: Whether to raise an exception for non-successful HTTP status codes.
    """

    dsn: str
    worker_id: str
    logging_type: str
    logging_config_file: str
    queue_size: int
    batch_size: int
    worker_number: int
    db_pool_size: int
    max_timeout: int
    raise_for_status: bool
