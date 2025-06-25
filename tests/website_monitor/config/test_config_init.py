"""
Unit tests for the configuration module's initialization.

This module contains comprehensive tests for the configuration module's
initialization, ensuring that it correctly parses command-line arguments
and environment variables to create a configuration context.

The tests follow the Arrange-Act-Assert (AAA) pattern and use proper mocking
of all external dependencies to ensure true unit testing.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Get the absolute path to the project root directory
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
# Add the project root to the Python path
sys.path.insert(0, root_path)
# Import from the src directory
from src.website_monitor.config import get_context
from src.website_monitor.config.monitoring_context import MonitoringContext


@pytest.fixture
def mock_uuid() -> str:
    """
    Creates a mock UUID for testing.

    Returns:
        str: A string representing a mock UUID.
    """
    return "mock-uuid"


@pytest.fixture
def mock_args() -> MagicMock:
    """
    Creates a mock argparse.Namespace for testing.

    Returns:
        MagicMock: A mock argparse.Namespace with test values.
    """
    args = MagicMock()
    args.dsn = "postgresql://test@localhost/test"
    args.worker_id = "test-worker"
    args.enable_tracing = True
    args.logging_type = "dev"
    args.logging_config_file = "/path/to/config.json"
    args.batch_size = 20
    args.db_pool_size = 50
    args.worker_number = 30
    args.queue_size = 150
    args.max_timeout = 45
    args.raise_for_status = "true"
    return args


def test_get_context_should_return_context_with_default_values(mock_uuid: str) -> None:
    """
    Tests that get_context returns a context with default values when no arguments or environment variables are provided.
    """
    # Arrange
    # Mock sys.argv to simulate no command-line arguments
    with patch("sys.argv", ["program"]):
        # Mock uuid4 to return a predictable value
        with patch("uuid.uuid4", return_value=mock_uuid):
            # Mock os.getenv to return None for all environment variables
            with patch("os.getenv", return_value=None):
                # Act
                context = get_context()

                # Assert
                assert isinstance(context, MonitoringContext)
                assert (
                    context.dsn
                    == "postgresql://postgres:password@localhost/test?options=-c+search_path%3Dwebsite_monitor"
                )
                assert context.worker_id == f"website-monitor-{mock_uuid}"
                assert context.logging_type == "prod"
                assert context.logging_config_file == ""
                assert context.batch_size == 40
                assert context.db_pool_size == 100
                assert context.worker_number == 100
                assert context.queue_size == 300
                assert context.max_timeout == 60
                assert context.raise_for_status is True


def test_get_context_should_use_command_line_arguments(mock_args: MagicMock) -> None:
    """
    Tests that get_context uses command-line arguments when provided.
    """
    # Arrange
    # Mock argparse.ArgumentParser.parse_args to return mock_args
    with patch("argparse.ArgumentParser.parse_args", return_value=mock_args):
        # Act
        context = get_context()

        # Assert
        assert isinstance(context, MonitoringContext)
        assert context.dsn == mock_args.dsn
        assert context.worker_id == mock_args.worker_id
        assert context.logging_type == mock_args.logging_type
        assert context.logging_config_file == mock_args.logging_config_file
        assert context.batch_size == mock_args.batch_size
        assert context.db_pool_size == mock_args.db_pool_size
        assert context.worker_number == mock_args.worker_number
        assert context.queue_size == mock_args.queue_size
        assert context.max_timeout == mock_args.max_timeout
        # Check that the raise_for_status parameter is correctly parsed
        expected_raise_for_status = mock_args.raise_for_status.lower() == "true"
        assert context.raise_for_status == expected_raise_for_status


def test_get_context_should_use_environment_variables() -> None:
    """
    Tests that get_context uses environment variables when command-line arguments are not provided.
    """
    # Arrange
    # Mock sys.argv to simulate no command-line arguments
    with patch("sys.argv", ["program"]):
        # Mock os.getenv to return values for environment variables
        env_vars = {
            "WEBSITE_MONITOR_DSN": "postgresql://env@localhost/env",
            "WEBSITE_MONITOR_WORKER_ID": "env-worker",
            "WEBSITE_MONITOR_LOGGING_TYPE": "custom",
            "WEBSITE_MONITOR_LOGGING_CONFIG_FILE": "/env/config.json",
            "WEBSITE_MONITOR_BATCH_SIZE": "25",
            "WEBSITE_MONITOR_DB_POOL_SIZE": "75",
            "WEBSITE_MONITOR_WORKER_NUMBER": "35",
            "WEBSITE_MONITOR_QUEUE_SIZE": "175",
            "WEBSITE_MONITOR_MAX_TIMEOUT": "90",
            "WEBSITE_MONITOR_RAISE_FOR_STATUS": "false",
        }

        def mock_getenv(key, default=None):
            return env_vars.get(key, default)

        with patch("os.getenv", side_effect=mock_getenv):
            # Act
            context = get_context()

            # Assert
            assert isinstance(context, MonitoringContext)
            assert context.dsn == "postgresql://env@localhost/env"
            assert context.worker_id == "env-worker"
            assert context.logging_type == "custom"
            assert context.logging_config_file == "/env/config.json"
            assert context.batch_size == 25
            assert context.db_pool_size == 75
            assert context.worker_number == 35
            assert context.queue_size == 175
            assert context.max_timeout == 90
            assert context.raise_for_status is False


def test_get_context_should_prioritize_command_line_over_environment() -> None:
    """
    Tests that get_context prioritizes command-line arguments over environment variables.
    """
    # Arrange
    # Mock argparse.ArgumentParser.parse_args to return args with specific values
    args = MagicMock()
    args.dsn = "postgresql://cli@localhost/cli"
    args.worker_id = "cli-worker"
    args.logging_type = "dev"
    args.logging_config_file = "/cli/config.json"
    args.batch_size = 30
    args.db_pool_size = 60
    args.worker_number = 40
    args.queue_size = 200
    args.max_timeout = 120
    args.raise_for_status = "false"

    with patch("argparse.ArgumentParser.parse_args", return_value=args):
        # Mock os.getenv to return different values for environment variables
        env_vars = {
            "WEBSITE_MONITOR_DSN": "postgresql://env@localhost/env",
            "WEBSITE_MONITOR_WORKER_ID": "env-worker",
            "WEBSITE_MONITOR_LOGGING_TYPE": "custom",
            "WEBSITE_MONITOR_LOGGING_CONFIG_FILE": "/env/config.json",
            "WEBSITE_MONITOR_BATCH_SIZE": "25",
            "WEBSITE_MONITOR_DB_POOL_SIZE": "75",
            "WEBSITE_MONITOR_WORKER_NUMBER": "35",
            "WEBSITE_MONITOR_QUEUE_SIZE": "175",
            "WEBSITE_MONITOR_MAX_TIMEOUT": "90",
            "WEBSITE_MONITOR_RAISE_FOR_STATUS": "true",
        }

        def mock_getenv(key, default=None):
            return env_vars.get(key, default)

        with patch("os.getenv", side_effect=mock_getenv):
            # Act
            context = get_context()

            # Assert
            assert isinstance(context, MonitoringContext)
            assert context.dsn == "postgresql://cli@localhost/cli"
            assert context.worker_id == "cli-worker"
            assert context.logging_type == "dev"
            assert context.logging_config_file == "/cli/config.json"
            assert context.batch_size == 30
            assert context.db_pool_size == 60
            assert context.worker_number == 40
            assert context.queue_size == 200
            assert context.max_timeout == 120
            assert context.raise_for_status is False
