"""
Tests for the __init__ module in the website_monitor.config package.

This module contains tests for the get_context function, which parses command-line
arguments and environment variables to create a configuration context.
"""

import os
import sys
from unittest.mock import patch

from website_monitor.config import get_context
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


class TestGetContext:
    """Tests for the get_context function."""

    def test_get_context_should_use_default_values_when_no_args_or_env_vars(self) -> None:
        """
        Test that get_context uses default values when no args or env vars are provided.

        This test verifies that the function uses the default values defined in
        constants.py when no command-line arguments or environment variables are provided.
        """
        # Arrange
        test_args: list[str] = []

        # Act
        with (
            patch.object(sys, "argv", ["program_name"] + test_args),
            patch.dict(os.environ, {}, clear=True),
        ):
            context = get_context()

        # Assert
        assert context.dsn == DEFAULT_DSN
        assert context.batch_size == DEFAULT_BATCH_SIZE
        assert context.db_pool_size == DEFAULT_DB_POOL_SIZE
        assert context.worker_number == DEFAULT_WORKER_NUMBER
        assert context.queue_size == DEFAULT_QUEUE_SIZE
        assert context.logging_type == DEFAULT_LOGGING_TYPE
        assert context.logging_config_file == DEFAULT_LOGGING_CONFIG_FILE
        assert context.max_timeout == DEFAULT_MAX_TIMEOUT
        assert context.raise_for_status == (DEFAULT_RAISE_FOR_STATUS.lower() == "true")
        # Worker ID is generated with a UUID, so we just check the prefix
        assert context.worker_id.startswith(DEFAULT_WORKER_ID_PREFIX)

    def test_get_context_should_use_command_line_args_when_provided(self) -> None:
        """
        Test that get_context uses command-line arguments when provided.

        This test verifies that the function uses the values provided as
        command-line arguments instead of the default values.
        """
        # Arrange
        test_args = [
            "-dsn",
            "postgresql://test:test@localhost:5432/testdb",
            "-wid",
            "test-worker-123",
            "-bs",
            "50",
            "-ps",
            "30",
            "-wn",
            "10",
            "-qs",
            "200",
            "-lt",
            "prod",
            "-lcf",
            "/path/to/custom-logging.json",
            "-mt",
            "60",
            "-rfs",
            "false",
        ]

        # Act
        with (
            patch.object(sys, "argv", ["program_name"] + test_args),
            patch.dict(os.environ, {}, clear=True),
        ):
            context = get_context()

        # Assert
        assert context.dsn == "postgresql://test:test@localhost:5432/testdb"
        assert context.worker_id == "test-worker-123"
        assert context.batch_size == 50
        assert context.db_pool_size == 30
        assert context.worker_number == 10
        assert context.queue_size == 200
        assert context.logging_type == "prod"
        assert context.logging_config_file == "/path/to/custom-logging.json"
        assert context.max_timeout == 60
        assert context.raise_for_status is False

    def test_get_context_should_use_environment_variables_when_provided(self) -> None:
        """
        Test that get_context uses environment variables when provided.

        This test verifies that the function uses the values provided as
        environment variables when command-line arguments are not provided.
        """
        # Arrange
        env_vars = {
            "WEBSITE_MONITOR_DSN": "postgresql://env:env@localhost:5432/envdb",
            "WEBSITE_MONITOR_WORKER_ID": "env-worker-456",
            "WEBSITE_MONITOR_BATCH_SIZE": "75",
            "WEBSITE_MONITOR_DB_POOL_SIZE": "40",
            "WEBSITE_MONITOR_WORKER_NUMBER": "15",
            "WEBSITE_MONITOR_QUEUE_SIZE": "300",
            "WEBSITE_MONITOR_LOGGING_TYPE": "custom",
            "WEBSITE_MONITOR_LOGGING_CONFIG_FILE": "/path/to/env-logging.json",
            "WEBSITE_MONITOR_MAX_TIMEOUT": "90",
            "WEBSITE_MONITOR_RAISE_FOR_STATUS": "true",
        }

        # Act
        with (
            patch.object(sys, "argv", ["program_name"]),
            patch.dict(os.environ, env_vars, clear=True),
        ):
            context = get_context()

        # Assert
        assert context.dsn == "postgresql://env:env@localhost:5432/envdb"
        assert context.worker_id == "env-worker-456"
        assert context.batch_size == 75
        assert context.db_pool_size == 40
        assert context.worker_number == 15
        assert context.queue_size == 300
        assert context.logging_type == "custom"
        assert context.logging_config_file == "/path/to/env-logging.json"
        assert context.max_timeout == 90
        assert context.raise_for_status is True

    def test_get_context_should_prioritize_command_line_args_over_env_vars(self) -> None:
        """
        Test that get_context prioritizes command-line args over env vars.

        This test verifies that the function uses the values provided as
        command-line arguments even when environment variables are also provided.
        """
        # Arrange
        test_args = [
            "-dsn",
            "postgresql://arg:arg@localhost:5432/argdb",
            "-bs",
            "100",
        ]

        env_vars = {
            "WEBSITE_MONITOR_DSN": "postgresql://env:env@localhost:5432/envdb",
            "WEBSITE_MONITOR_BATCH_SIZE": "75",
            "WEBSITE_MONITOR_WORKER_ID": "env-worker-456",
        }

        # Act
        with (
            patch.object(sys, "argv", ["program_name"] + test_args),
            patch.dict(os.environ, env_vars, clear=True),
        ):
            context = get_context()

        # Assert
        # These should come from command-line args
        assert context.dsn == "postgresql://arg:arg@localhost:5432/argdb"
        assert context.batch_size == 100
        # This should come from env vars
        assert context.worker_id == "env-worker-456"

    def test_get_context_should_parse_raise_for_status_correctly(self) -> None:
        """
        Test that get_context parses the raise_for_status parameter correctly.

        This test verifies that the function correctly converts the string value
        of raise_for_status to a boolean.
        """
        # Arrange
        test_cases = [
            {"value": "true", "expected": True},
            {"value": "True", "expected": True},
            {"value": "TRUE", "expected": True},
            {"value": "false", "expected": False},
            {"value": "False", "expected": False},
            {"value": "FALSE", "expected": False},
            {"value": "anything_else", "expected": False},
        ]

        for case in test_cases:
            # Act
            with (
                patch.object(sys, "argv", ["program_name", "-rfs", case["value"]]),
                patch.dict(os.environ, {}, clear=True),
            ):
                context = get_context()

            # Assert
            assert context.raise_for_status is case["expected"], (
                f"Failed for value '{case['value']}', "
                f"expected {case['expected']}, got {context.raise_for_status}"
            )
