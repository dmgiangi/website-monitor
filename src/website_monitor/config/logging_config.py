"""
Logging configuration module for the website monitoring system.

This module provides functionality to configure logging for the application
based on the provided configuration context. It supports different logging
configurations for development, production, and custom environments.
"""

import json
import logging.config
import os
from typing import Any, Dict

from website_monitor.config import MonitoringContext


def configure_logging(context: MonitoringContext) -> None:
    """
    Configure logging for the application based on the provided configuration.

    This function sets up logging based on the logging type specified in the
    configuration context. It supports three types of logging configurations:
    - dev: Development logging configuration
    - prod: Production logging configuration
    - custom: Custom logging configuration from a specified file

    It also adds a worker ID filter to all log records to identify which worker
    instance generated the log.

    Args:
        context: Configuration context containing logging settings.

    Raises:
        ValueError: If the logging type is invalid or if a custom logging
            configuration file is not provided when using the 'custom' type.
    """
    logging_type: str = context.logging_type.lower()
    if not logging_type:
        raise ValueError("Logging type must be provided.")
    elif logging_type == "dev":
        file_path = _get_local_package_file_path("logging-config-dev.json")
        _load_logging_config(file_path)
    elif logging_type == "prod":
        file_path = _get_local_package_file_path("logging-config-prod.json")
        _load_logging_config(file_path)
    elif logging_type == "custom":
        if not context.logging_config_file:
            raise ValueError("Custom logging configuration file must be provided.")
        else:
            _load_logging_config(context.logging_config_file)
    else:
        raise ValueError(
            f"Invalid logging type: {context.logging_type}. Allowed values are: dev, prod, custom"
        )

    # Add a worker ID filter to all log records
    root_logger = logging.getLogger()
    instance_filter = _WorkerIdFilter(worker_id=context.worker_id)
    root_logger.addFilter(instance_filter)

    logging.debug("Logging configured and WorkerIdFilter added.")


def _load_logging_config(config_file: str) -> None:
    """
    Load logging configuration from a JSON file.

    This function reads a JSON file containing logging configuration and
    applies it to the Python logging system using dictConfig.

    Args:
        config_file: Path to the JSON file containing logging configuration.

    Raises:
        RuntimeError: If the file is not found, contains invalid JSON, or
            if there is any other error loading the configuration.
    """
    try:
        with open(config_file) as f:
            config: Dict[str, Any] = json.load(f)
            logging.config.dictConfig(config)
    except FileNotFoundError as err:
        raise RuntimeError(f"Logging config file not found: {config_file}") from err
    except json.JSONDecodeError as err:
        raise RuntimeError(f"Invalid JSON format in logging config file: {config_file}") from err
    except Exception as err:
        raise RuntimeError(f"Error loading logging config: {str(err)}") from err


def _get_local_package_file_path(config_file: str) -> str:
    """
    Get the absolute path to a file in the same directory as this module.

    This function is used to locate built-in logging configuration files
    that are packaged with the application.

    Args:
        config_file: Name of the file to locate.

    Returns:
        str: Absolute path to the specified file.
    """
    return os.path.join(os.path.dirname(__file__), config_file)


class _WorkerIdFilter(logging.Filter):
    """
    A logging filter that injects the worker ID into every log record.

    This filter adds a 'worker_id' attribute to each log record, which can
    be used in log formatters to identify which worker instance generated the log.
    """

    def __init__(self, worker_id: str) -> None:
        """
        Initialize the filter with a worker ID.

        Args:
            worker_id: The unique identifier of the worker instance.
        """
        super().__init__()
        self._worker_id: str = worker_id

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add the worker ID to the log record.

        This method is called for each log record that passes through the filter.
        It adds the worker ID as an attribute to the record and always returns True
        to allow the record to be processed further.

        Args:
            record: The log record to be processed.

        Returns:
            bool: Always True to allow the record to be processed further.
        """
        record.worker_id = self._worker_id
        return True
