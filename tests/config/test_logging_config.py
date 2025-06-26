"""
Tests for the logging_config module in the website_monitor.config package.

This module contains tests for the configure_logging function and the _WorkerIdFilter class,
which are used to configure logging for the application.
"""

import json
import logging
import os
from typing import Any
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
    """Fixture that provides a mock MonitoringContext for testing."""
    return MonitoringContext(
        dsn="postgresql://user:password@localhost:5432/db",
        worker_id="worker-123",
        logging_type="dev",
        logging_config_file="logging.json",
        queue_size=100,
        batch_size=10,
        worker_number=5,
        db_pool_size=20,
        max_timeout=30,
        raise_for_status=True,
    )


@pytest.fixture
def mock_logging_config() -> dict[str, Any]:
    """Fixture that provides a mock logging configuration for testing."""
    return {
        "version": 1,
        "formatters": {
            "standard": {
                "format": "%(asctime)s [%(levelname)s] [%(worker_id)s] %(name)s: %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            }
        },
        "loggers": {"": {"level": "INFO", "handlers": ["console"], "propagate": True}},
    }


class TestConfigureLogging:
    """Tests for the configure_logging function."""

    def test_configure_logging_should_raise_error_for_empty_logging_type(self) -> None:
        """
        Test that configure_logging raises an error for empty logging type.

        This test verifies that the function raises a ValueError when the
        logging_type in the context is empty.
        """
        # Arrange
        context = MonitoringContext(
            dsn="postgresql://user:password@localhost:5432/db",
            worker_id="worker-123",
            logging_type="",  # Empty logging type
            logging_config_file="logging.json",
            queue_size=100,
            batch_size=10,
            worker_number=5,
            db_pool_size=20,
            max_timeout=30,
            raise_for_status=True,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Logging type must be provided."):
            configure_logging(context)

    def test_configure_logging_should_raise_error_for_invalid_logging_type(
        self, mock_context: MonitoringContext
    ) -> None:
        """
        Test that configure_logging raises an error for invalid logging type.

        This test verifies that the function raises a ValueError when the
        logging_type in the context is not one of the allowed values.
        """
        # Arrange
        context = MonitoringContext(
            dsn=mock_context.dsn,
            worker_id=mock_context.worker_id,
            logging_type="invalid",  # Invalid logging type
            logging_config_file=mock_context.logging_config_file,
            queue_size=mock_context.queue_size,
            batch_size=mock_context.batch_size,
            worker_number=mock_context.worker_number,
            db_pool_size=mock_context.db_pool_size,
            max_timeout=mock_context.max_timeout,
            raise_for_status=mock_context.raise_for_status,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid logging type: invalid"):
            configure_logging(context)

    def test_configure_logging_should_raise_error_for_custom_type_without_file(self) -> None:
        """
        Test that configure_logging raises an error for custom type without file.

        This test verifies that the function raises a ValueError when the
        logging_type is 'custom' but no logging_config_file is provided.
        """
        # Arrange
        context = MonitoringContext(
            dsn="postgresql://user:password@localhost:5432/db",
            worker_id="worker-123",
            logging_type="custom",
            logging_config_file="",  # Empty config file path
            queue_size=100,
            batch_size=10,
            worker_number=5,
            db_pool_size=20,
            max_timeout=30,
            raise_for_status=True,
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Custom logging configuration file must be provided."):
            configure_logging(context)

    @patch("website_monitor.config.logging_config._get_local_package_file_path")
    @patch("website_monitor.config.logging_config._load_logging_config")
    def test_configure_logging_should_load_dev_config_for_dev_type(
        self, mock_load_config: MagicMock, mock_get_path: MagicMock, mock_context: MonitoringContext
    ) -> None:
        """
        Test that configure_logging loads the dev config for dev logging type.

        This test verifies that the function calls _get_local_package_file_path
        with the correct filename and then calls _load_logging_config with the
        returned path when logging_type is 'dev'.
        """
        # Arrange
        context = MonitoringContext(
            dsn=mock_context.dsn,
            worker_id=mock_context.worker_id,
            logging_type="dev",
            logging_config_file=mock_context.logging_config_file,
            queue_size=mock_context.queue_size,
            batch_size=mock_context.batch_size,
            worker_number=mock_context.worker_number,
            db_pool_size=mock_context.db_pool_size,
            max_timeout=mock_context.max_timeout,
            raise_for_status=mock_context.raise_for_status,
        )
        mock_get_path.return_value = "/path/to/logging-config-dev.json"

        # Act
        with patch("logging.getLogger") as mock_get_logger:
            mock_get_logger.return_value = MagicMock()
            configure_logging(context)

        # Assert
        mock_get_path.assert_called_once_with("logging-config-dev.json")
        mock_load_config.assert_called_once_with("/path/to/logging-config-dev.json")

    @patch("website_monitor.config.logging_config._get_local_package_file_path")
    @patch("website_monitor.config.logging_config._load_logging_config")
    def test_configure_logging_should_load_prod_config_for_prod_type(
        self, mock_load_config: MagicMock, mock_get_path: MagicMock, mock_context: MonitoringContext
    ) -> None:
        """
        Test that configure_logging loads the prod config for prod logging type.

        This test verifies that the function calls _get_local_package_file_path
        with the correct filename and then calls _load_logging_config with the
        returned path when logging_type is 'prod'.
        """
        # Arrange
        context = MonitoringContext(
            dsn=mock_context.dsn,
            worker_id=mock_context.worker_id,
            logging_type="prod",
            logging_config_file=mock_context.logging_config_file,
            queue_size=mock_context.queue_size,
            batch_size=mock_context.batch_size,
            worker_number=mock_context.worker_number,
            db_pool_size=mock_context.db_pool_size,
            max_timeout=mock_context.max_timeout,
            raise_for_status=mock_context.raise_for_status,
        )
        mock_get_path.return_value = "/path/to/logging-config-prod.json"

        # Act
        with patch("logging.getLogger") as mock_get_logger:
            mock_get_logger.return_value = MagicMock()
            configure_logging(context)

        # Assert
        mock_get_path.assert_called_once_with("logging-config-prod.json")
        mock_load_config.assert_called_once_with("/path/to/logging-config-prod.json")

    @patch("website_monitor.config.logging_config._load_logging_config")
    def test_configure_logging_should_load_custom_config_for_custom_type(
        self, mock_load_config: MagicMock, mock_context: MonitoringContext
    ) -> None:
        """
        Test that configure_logging loads the custom config for custom logging type.

        This test verifies that the function calls _load_logging_config with the
        logging_config_file from the context when logging_type is 'custom'.
        """
        # Arrange
        context = MonitoringContext(
            dsn=mock_context.dsn,
            worker_id=mock_context.worker_id,
            logging_type="custom",
            logging_config_file="/path/to/custom-logging.json",
            queue_size=mock_context.queue_size,
            batch_size=mock_context.batch_size,
            worker_number=mock_context.worker_number,
            db_pool_size=mock_context.db_pool_size,
            max_timeout=mock_context.max_timeout,
            raise_for_status=mock_context.raise_for_status,
        )

        # Act
        with patch("logging.getLogger") as mock_get_logger:
            mock_get_logger.return_value = MagicMock()
            configure_logging(context)

        # Assert
        mock_load_config.assert_called_once_with("/path/to/custom-logging.json")

    @patch("website_monitor.config.logging_config._load_logging_config")
    def test_configure_logging_should_add_worker_id_filter(
        self, mock_get_path: MagicMock, mock_context: MonitoringContext
    ) -> None:
        """
        Test that configure_logging adds a worker ID filter to the root logger.

        This test verifies that the function adds a _WorkerIdFilter to the root
        logger with the worker_id from the context.
        """
        # Arrange
        mock_get_path.return_value = "/path/to/logging-config-dev.json"
        mock_root_logger = MagicMock()

        # Act
        with patch("logging.getLogger", return_value=mock_root_logger):
            configure_logging(mock_context)

        # Assert
        # Verify that addFilter was called on the root logger
        mock_root_logger.addFilter.assert_called_once()
        # Verify that the filter is a _WorkerIdFilter with the correct worker_id
        filter_arg = mock_root_logger.addFilter.call_args[0][0]
        assert isinstance(filter_arg, _WorkerIdFilter)
        assert filter_arg._worker_id == mock_context.worker_id


class TestLoadLoggingConfig:
    """Tests for the _load_logging_config function."""

    def test_load_logging_config_should_load_valid_config(
        self, mock_logging_config: dict[str, Any]
    ) -> None:
        """
        Test that _load_logging_config loads a valid logging configuration.

        This test verifies that the function opens the specified file, loads
        the JSON content, and configures logging with the loaded configuration.
        """
        # Arrange
        config_file = "/path/to/logging.json"
        mock_file = mock_open(read_data=json.dumps(mock_logging_config))

        # Act
        with (
            patch("builtins.open", mock_file),
            patch("logging.config.dictConfig") as mock_dict_config,
        ):
            _load_logging_config(config_file)

        # Assert
        mock_file.assert_called_once_with(config_file)
        mock_dict_config.assert_called_once_with(mock_logging_config)

    def test_load_logging_config_should_raise_error_for_missing_file(self) -> None:
        """
        Test that _load_logging_config raises an error for a missing file.

        This test verifies that the function raises a RuntimeError when the
        specified file does not exist.
        """
        # Arrange
        config_file = "/path/to/nonexistent.json"

        # Act & Assert
        with (
            patch("builtins.open", side_effect=FileNotFoundError()),
            pytest.raises(RuntimeError, match=f"Logging config file not found: {config_file}"),
        ):
            _load_logging_config(config_file)

    def test_load_logging_config_should_raise_error_for_invalid_json(self) -> None:
        """
        Test that _load_logging_config raises an error for invalid JSON.

        This test verifies that the function raises a RuntimeError when the
        specified file contains invalid JSON.
        """
        # Arrange
        config_file = "/path/to/invalid.json"
        mock_file = mock_open(read_data="invalid json")

        # Act & Assert
        with (
            patch("builtins.open", mock_file),
            patch("json.load", side_effect=json.JSONDecodeError("Invalid JSON", "", 0)),
            pytest.raises(
                RuntimeError, match=f"Invalid JSON format in logging config file: {config_file}"
            ),
        ):
            _load_logging_config(config_file)

    def test_load_logging_config_should_raise_error_for_other_exceptions(self) -> None:
        """
        Test that _load_logging_config raises an error for other exceptions.

        This test verifies that the function raises a RuntimeError when any
        other exception occurs during loading.
        """
        # Arrange
        config_file = "/path/to/logging.json"
        mock_file = mock_open(read_data="{}")

        # Act & Assert
        with (
            patch("builtins.open", mock_file),
            patch("logging.config.dictConfig", side_effect=Exception("Some error")),
            pytest.raises(RuntimeError, match="Error loading logging config: Some error"),
        ):
            _load_logging_config(config_file)


class TestGetLocalPackageFilePath:
    """Tests for the _get_local_package_file_path function."""

    def test_get_local_package_file_path_should_return_correct_path(self) -> None:
        """
        Test that _get_local_package_file_path returns the correct path.

        This test verifies that the function returns the absolute path to a file
        in the same directory as the logging_config module.
        """
        # Arrange
        config_file = "../../src/website_monitor/config/logging-config-dev.json"
        expected_path = os.path.join(os.path.dirname(__file__), config_file)

        # Act
        with patch("os.path.dirname", return_value="/path/to/config"):
            result = _get_local_package_file_path(config_file)

        # Assert
        assert result == os.path.join("/path/to/config", config_file)


class TestWorkerIdFilter:
    """Tests for the _WorkerIdFilter class."""

    def test_worker_id_filter_should_initialize_with_worker_id(self) -> None:
        """
        Test that _WorkerIdFilter initializes with the worker ID.

        This test verifies that the filter stores the worker_id provided
        during initialization.
        """
        # Arrange
        worker_id = "worker-123"

        # Act
        filter_instance = _WorkerIdFilter(worker_id)

        # Assert
        assert filter_instance._worker_id == worker_id

    def test_worker_id_filter_should_add_worker_id_to_record(self) -> None:
        """
        Test that _WorkerIdFilter adds the worker ID to the log record.

        This test verifies that the filter adds the worker_id as an attribute
        to the log record and returns True to allow the record to be processed.
        """
        # Arrange
        worker_id = "worker-123"
        filter_instance = _WorkerIdFilter(worker_id)
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Act
        result = filter_instance.filter(record)

        # Assert
        assert result is True  # Filter should always return True
        assert hasattr(record, "worker_id")
        assert record.worker_id == worker_id
