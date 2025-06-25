"""
Configuration module for the website monitoring system.

This module provides functionality to parse command-line arguments and environment
variables to create a configuration context for the monitoring system. It defines
default values and help text for all configurable parameters.
"""

import argparse
import os
from typing import Any
from uuid import uuid4

from website_monitor.config.constants import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_DB_POOL_SIZE,
    DEFAULT_DSN,
    DEFAULT_LOGGING_CONFIG_FILE,
    DEFAULT_LOGGING_TYPE,
    DEFAULT_MAX_TIMEOUT,
    DEFAULT_QUEUE_SIZE,
    DEFAULT_RAISE_FOR_STATUS,
    DEFAULT_WORKER_ID_PREFIX,
    DEFAULT_WORKER_NUMBER,
)
from website_monitor.config.monitoring_context import MonitoringContext


def get_context() -> MonitoringContext:
    """
    Parse command-line arguments and environment variables to create a configuration context.

    This function creates an argument parser with options for all configurable aspects
    of the monitoring system. For each option, it first checks for a command-line argument,
    then falls back to an environment variable, and finally uses a default value.

    Returns:
        MonitoringContext: A configuration context object containing all parsed settings.
    """
    parser = argparse.ArgumentParser(
        description="A program that parses command-line arguments for website monitoring."
    )

    parser.add_argument(
        "-dsn",
        type=str,
        default=os.getenv(
            "WEBSITE_MONITOR_DSN",
            DEFAULT_DSN,
        ),
        help="Specifies the DSN (connection string) for the PostgreSQL database.\n"
        "If not provided, the value is read from the WEBSITE_MONITOR_DSN environment variable.\n"
        f"If that is also absent, a default value for a local database is used: {DEFAULT_WORKER_ID_PREFIX}",
    )

    parser.add_argument(
        "-wid",
        "--worker-id",
        type=str,
        default=os.getenv("WEBSITE_MONITOR_WORKER_ID", f"{DEFAULT_WORKER_ID_PREFIX}{uuid4()}"),
        help="Specifies the worker ID for the monitoring service.\n"
        "If not provided, the value is read from the WEBSITE_MONITOR_WORKER_ID environment variable.\n"
        f"If that is also absent, the default value will be {DEFAULT_WORKER_ID_PREFIX}-uuid4().",
    )

    parser.add_argument(
        "-bs",
        "--batch-size",
        type=int,
        default=int(os.getenv("WEBSITE_MONITOR_BATCH_SIZE", DEFAULT_BATCH_SIZE)),
        help="Specifies the batch size for processing website monitoring tasks.\n"
        "If not provided, the value is read from the WEBSITE_MONITOR_BATCH_SIZE environment variable.\n"
        f"If that is also absent, a default value of {DEFAULT_BATCH_SIZE} is used.",
    )

    parser.add_argument(
        "-ps",
        "--db-pool-size",
        type=int,
        default=int(os.getenv("WEBSITE_MONITOR_DB_POOL_SIZE", DEFAULT_DB_POOL_SIZE)),
        help="Specifies the maximum number of connections in the database connection pool.\n"
        "If not provided, the value is read from the WEBSITE_MONITOR_DB_POOL_SIZE environment variable.\n"
        f"If that is also absent, a default value of {DEFAULT_DB_POOL_SIZE} is used.",
    )

    parser.add_argument(
        "-wn",
        "--worker-number",
        type=int,
        default=int(os.getenv("WEBSITE_MONITOR_WORKER_NUMBER", DEFAULT_WORKER_NUMBER)),
        help="Specifies the maximum number of concurrent monitoring tasks.\n"
        "If not provided, the value is read from the WEBSITE_MONITOR_WORKER_NUMBER environment variable.\n"
        f"If that is also absent, a default value of {DEFAULT_WORKER_NUMBER} is used.",
    )

    parser.add_argument(
        "-qs",
        "--queue-size",
        type=int,
        default=int(os.getenv("WEBSITE_MONITOR_QUEUE_SIZE", DEFAULT_QUEUE_SIZE)),
        help="Specifies the maximum number of items in the processing queue.\n"
        "If not provided, the value is read from the WEBSITE_MONITOR_QUEUE_SIZE environment variable.\n"
        f"If that is also absent, a default value of {DEFAULT_QUEUE_SIZE} is used.",
    )

    parser.add_argument(
        "-lt",
        "--logging-type",
        type=str,
        default=os.getenv("WEBSITE_MONITOR_LOGGING_TYPE", DEFAULT_LOGGING_TYPE),
        help="Specifies the logging configuration type to use.\n"
        "Allowed values: dev, prod, custom (case insensitive).\n"
        "For 'dev' and 'prod', system will use built-in configurations.\n"
        "For 'custom', the --logging-config-file argument is required.",
    )

    parser.add_argument(
        "-lcf",
        "--logging-config-file",
        type=str,
        default=os.getenv("WEBSITE_MONITOR_LOGGING_CONFIG_FILE", DEFAULT_LOGGING_CONFIG_FILE),
        help="Path to custom logging configuration file.\n"
        "Required when --logging-type is set to 'custom'.",
    )

    parser.add_argument(
        "-mt",
        "--max-timeout",
        type=int,
        default=int(os.getenv("WEBSITE_MONITOR_MAX_TIMEOUT", DEFAULT_MAX_TIMEOUT)),
        help="Specifies the maximum timeout duration in seconds for HTTP requests.\n"
        "If not provided, the value is read from the WEBSITE_MONITOR_MAX_TIMEOUT environment variable.\n"
        f"If that is also absent, a default value of {DEFAULT_MAX_TIMEOUT} seconds is used.",
    )

    parser.add_argument(
        "-rfs",
        "--raise-for-status",
        type=str,
        default=os.getenv("WEBSITE_MONITOR_RAISE_FOR_STATUS", DEFAULT_RAISE_FOR_STATUS),
        help="Specifies whether to raise an exception for non-successful HTTP status codes.\n"
        "If not provided, the value is read from the WEBSITE_MONITOR_RAISE_FOR_STATUS environment variable.\n"
        f"If that is also absent, a default value of {DEFAULT_RAISE_FOR_STATUS} is used.",
    )

    # Parse the command-line arguments
    args: Any = parser.parse_args()

    # Parse the raise_for_status parameter
    raise_for_status = args.raise_for_status.lower() == "true"

    # Create and return a MonitoringContext with the parsed settings
    return MonitoringContext(
        dsn=args.dsn,
        worker_id=args.worker_id,
        logging_type=args.logging_type,
        logging_config_file=args.logging_config_file,
        batch_size=args.batch_size,
        db_pool_size=args.db_pool_size,
        worker_number=args.worker_number,
        queue_size=args.queue_size,
        max_timeout=args.max_timeout,
        raise_for_status=raise_for_status,
    )
