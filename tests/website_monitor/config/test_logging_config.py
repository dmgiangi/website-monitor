"""
Unit tests for the logging configuration module.

This module contains comprehensive tests for the logging configuration module,
ensuring that it correctly configures logging based on the provided configuration
context and handles different logging types and error conditions.

The tests follow the Arrange-Act-Assert (AAA) pattern and use proper mocking
of all external dependencies to ensure true unit testing.
"""

import json
import logging
import os
from unittest.mock import MagicMock, mock_open, patch

import pytest

from website_monitor.config.logging_config import (
    _get_local_package_file_path,
    _load_logging_config,
    _WorkerIdFilter,
    configure_logging,
)
from website_monitor.config.monitoring_context import MonitoringContext


@pytest.fixture
def mock_context() -> MonitoringContext:
    """
    Creates a mock MonitoringContext for testing.

    Returns:
        MonitoringContext: A MonitoringContext with test values.
    """
    return MonitoringContext(
        dsn="postgresql://localhost/test",
        worker_id="test-worker",
        enable_tracing=False,
        logging_type="dev",
        logging_config_file="",
        queue_size=100,
        batch_size=10,
        worker_number=5,
        db_pool_size=10,
    )


@pytest.fixture
def mock_custom_context() -> MonitoringContext:
    """
    Creates a mock MonitoringContext with custom logging type for testing.

    Returns:
        MonitoringContext: A MonitoringContext with custom logging configuration.
    """
    return MonitoringContext(
        dsn="postgresql://localhost/test",
        worker_id="test-worker",
        enable_tracing=False,
        logging_type="custom",
        logging_config_file="/path/to/custom/config.json",
        queue_size=100,
        batch_size=10,
        worker_number=5,
        db_pool_size=10,
    )


@pytest.fixture
def mock_invalid_context() -> MonitoringContext:
    """
    Creates a mock MonitoringContext with invalid logging type for testing.

    Returns:
        MonitoringContext: A MonitoringContext with invalid logging configuration.
    """
    return MonitoringContext(
        dsn="postgresql://localhost/test",
        worker_id="test-worker",
        enable_tracing=False,
        logging_type="invalid",
        logging_config_file="",
        queue_size=100,
        batch_size=10,
        worker_number=5,
        db_pool_size=10,
    )


@pytest.fixture
def mock_empty_logging_type_context() -> MonitoringContext:
    """
    Creates a mock MonitoringContext with empty logging type for testing.

    Returns:
        MonitoringContext: A MonitoringContext with empty logging type.
    """
    return MonitoringContext(
        dsn="postgresql://localhost/test",
        worker_id="test-worker",
        enable_tracing=False,
        logging_type="",
        logging_config_file="",
        queue_size=100,
        batch_size=10,
        worker_number=5,
        db_pool_size=10,
    )


@pytest.fixture
def mock_custom_without_file_context() -> MonitoringContext:
    """
    Creates a mock MonitoringContext with custom logging type but no file path.

    Returns:
        MonitoringContext: A MonitoringContext with custom logging type but no config file.
    """
    return MonitoringContext(
        dsn="postgresql://localhost/test",
        worker_id="test-worker",
        enable_tracing=False,
        logging_type="custom",
        logging_config_file="",
        queue_size=100,
        batch_size=10,
        worker_number=5,
        db_pool_size=10,
    )


def test_get_local_package_file_path_should_return_absolute_path() -> None:
    """
    Tests that _get_local_package_file_path returns the absolute path to a file.
    """
    # Arrange
    config_file = "test-config.json"
    expected_path = "/path/to/config/test-config.json"

    # Mock os.path.dirname and os.path.join
    with patch("os.path.dirname", return_value="/path/to/config"):
        with patch("os.path.join", return_value=expected_path):
            # Act
            result = _get_local_package_file_path(config_file)

            # Assert
            assert result == expected_path
            os.path.dirname.assert_called_once_with(__file__)
            os.path.join.assert_called_once_with("/path/to/config", config_file)


def test_load_logging_config_should_load_and_apply_config() -> None:
    """
    Tests that _load_logging_config loads and applies the logging configuration.
    """
    # Arrange
    config_file = "test-config.json"
    mock_config = {"version": 1, "formatters": {}, "handlers": {}, "loggers": {}}

    # Mock open, json.load, and logging.config.dictConfig
    with patch("builtins.open", mock_open()) as mock_file:
        with patch("json.load", return_value=mock_config) as mock_json_load:
            with patch("logging.config.dictConfig") as mock_dict_config:
                # Act
                _load_logging_config(config_file)

                # Assert
                mock_file.assert_called_once_with(config_file)
                mock_json_load.assert_called_once()
                mock_dict_config.assert_called_once_with(mock_config)


def test_load_logging_config_should_raise_runtime_error_when_file_not_found() -> None:
    """
    Tests that _load_logging_config raises RuntimeError when the file is not found.
    """
    # Arrange
    config_file = "non-existent-config.json"

    # Mock open to raise FileNotFoundError
    with patch("builtins.open", side_effect=FileNotFoundError()):
        # Act & Assert
        with pytest.raises(RuntimeError, match=f"Logging config file not found: {config_file}"):
            _load_logging_config(config_file)


def test_load_logging_config_should_raise_runtime_error_when_invalid_json() -> None:
    """
    Tests that _load_logging_config raises RuntimeError when the JSON is invalid.
    """
    # Arrange
    config_file = "invalid-json-config.json"

    # Mock open and json.load to raise JSONDecodeError
    with patch("builtins.open", mock_open()):
        with patch("json.load", side_effect=json.JSONDecodeError("Invalid JSON", "", 0)):
            # Act & Assert
            with pytest.raises(
                RuntimeError, match=f"Invalid JSON format in logging config file: {config_file}"
            ):
                _load_logging_config(config_file)


def test_load_logging_config_should_raise_runtime_error_when_other_error() -> None:
    """
    Tests that _load_logging_config raises RuntimeError when any other error occurs.
    """
    # Arrange
    config_file = "error-config.json"

    # Mock open and json.load to raise a generic exception
    with patch("builtins.open", mock_open()):
        with patch("json.load", side_effect=Exception("Test error")):
            # Act & Assert
            with pytest.raises(RuntimeError, match="Error loading logging config: Test error"):
                _load_logging_config(config_file)


def test_worker_id_filter_should_add_worker_id_to_record() -> None:
    """
    Tests that _WorkerIdFilter adds the worker ID to the log record.
    """
    # Arrange
    worker_id = "test-worker"
    filter_instance = _WorkerIdFilter(worker_id=worker_id)
    record = MagicMock(spec=logging.LogRecord)

    # Act
    result = filter_instance.filter(record)

    # Assert
    assert result is True
    assert record.worker_id == worker_id


def test_configure_logging_should_use_dev_config() -> None:
    """
    Tests that configure_logging uses the dev configuration when logging_type is 'dev'.
    """
    # Arrange
    context = mock_context()  # Default is 'dev'
    expected_path = "/path/to/dev-config.json"

    # Mock _get_local_package_file_path, _load_logging_config, and logging
    with patch(
        "website_monitor.config.logging_config._get_local_package_file_path",
        return_value=expected_path,
    ) as mock_get_path:
        with patch(
            "website_monitor.config.logging_config._load_logging_config"
        ) as mock_load_config:
            with patch("logging.getLogger") as mock_get_logger:
                with patch("logging.debug") as mock_debug:
                    # Mock the root logger and filter
                    mock_root_logger = MagicMock()
                    mock_get_logger.return_value = mock_root_logger

                    # Act
                    configure_logging(context)

                    # Assert
                    mock_get_path.assert_called_once_with("logging-config-dev.json")
                    mock_load_config.assert_called_once_with(expected_path)
                    mock_get_logger.assert_called_once_with()
                    mock_root_logger.addFilter.assert_called_once()
                    mock_debug.assert_called_once_with(
                        "Logging configured and WorkerIdFilter added."
                    )


def test_configure_logging_should_use_prod_config() -> None:
    """
    Tests that configure_logging uses the prod configuration when logging_type is 'prod'.
    """
    # Arrange
    context = MonitoringContext(
        dsn="postgresql://localhost/test",
        worker_id="test-worker",
        enable_tracing=False,
        logging_type="prod",
        logging_config_file="",
        queue_size=100,
        batch_size=10,
        worker_number=5,
        db_pool_size=10,
    )
    expected_path = "/path/to/prod-config.json"

    # Mock _get_local_package_file_path, _load_logging_config, and logging
    with patch(
        "website_monitor.config.logging_config._get_local_package_file_path",
        return_value=expected_path,
    ) as mock_get_path:
        with patch(
            "website_monitor.config.logging_config._load_logging_config"
        ) as mock_load_config:
            with patch("logging.getLogger") as mock_get_logger:
                with patch("logging.debug") as mock_debug:
                    # Mock the root logger and filter
                    mock_root_logger = MagicMock()
                    mock_get_logger.return_value = mock_root_logger

                    # Act
                    configure_logging(context)

                    # Assert
                    mock_get_path.assert_called_once_with("logging-config-prod.json")
                    mock_load_config.assert_called_once_with(expected_path)
                    mock_get_logger.assert_called_once_with()
                    mock_root_logger.addFilter.assert_called_once()
                    mock_debug.assert_called_once_with(
                        "Logging configured and WorkerIdFilter added."
                    )


def test_configure_logging_should_use_custom_config(mock_custom_context: MonitoringContext) -> None:
    """
    Tests that configure_logging uses the custom configuration when logging_type is 'custom'.
    """
    # Arrange
    # Mock _load_logging_config and logging
    with patch("website_monitor.config.logging_config._load_logging_config") as mock_load_config:
        with patch("logging.getLogger") as mock_get_logger:
            with patch("logging.debug") as mock_debug:
                # Mock the root logger and filter
                mock_root_logger = MagicMock()
                mock_get_logger.return_value = mock_root_logger

                # Act
                configure_logging(mock_custom_context)

                # Assert
                mock_load_config.assert_called_once_with(mock_custom_context.logging_config_file)
                mock_get_logger.assert_called_once_with()
                mock_root_logger.addFilter.assert_called_once()
                mock_debug.assert_called_once_with("Logging configured and WorkerIdFilter added.")


def test_configure_logging_should_raise_value_error_when_empty_logging_type(
    mock_empty_logging_type_context: MonitoringContext,
) -> None:
    """
    Tests that configure_logging raises ValueError when logging_type is empty.
    """
    # Act & Assert
    with pytest.raises(ValueError, match="Logging type must be provided."):
        configure_logging(mock_empty_logging_type_context)


def test_configure_logging_should_raise_value_error_when_invalid_logging_type(
    mock_invalid_context: MonitoringContext,
) -> None:
    """
    Tests that configure_logging raises ValueError when logging_type is invalid.
    """
    # Act & Assert
    with pytest.raises(
        ValueError,
        match=f"Invalid logging type: {mock_invalid_context.logging_type}. Allowed values are: dev, prod, custom",
    ):
        configure_logging(mock_invalid_context)


def test_configure_logging_should_raise_value_error_when_custom_without_file(
    mock_custom_without_file_context: MonitoringContext,
) -> None:
    """
    Tests that configure_logging raises ValueError when logging_type is 'custom' but no config file is provided.
    """
    # Act & Assert
    with pytest.raises(ValueError, match="Custom logging configuration file must be provided."):
        configure_logging(mock_custom_without_file_context)
