"""
Constants for the website monitoring system.

This module defines default values for all configurable parameters
of the monitoring system. These constants are used as fallback values
when neither command-line arguments nor environment variables are provided.
"""

# Database configuration defaults
DEFAULT_DSN = (
    "postgresql://postgres:password@localhost/test?options=-c+search_path%3Dwebsite_monitor"
)

DEFAULT_WORKER_NUMBER = 50
DEFAULT_DB_POOL_SIZE = 25
DEFAULT_BATCH_SIZE = 15
DEFAULT_QUEUE_SIZE = 150
DEFAULT_MAX_TIMEOUT = 3

# Worker configuration defaults
DEFAULT_WORKER_ID_PREFIX = "website-monitor-"

# HTTP configuration defaults
DEFAULT_ENABLE_TRACING = "false"
DEFAULT_RAISE_FOR_STATUS = "true"

# Logging configuration defaults
DEFAULT_LOGGING_TYPE = "prod"
DEFAULT_LOGGING_CONFIG_FILE = ""
