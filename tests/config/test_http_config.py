"""
Tests for the http_config module in the website_monitor.config package.

This module contains tests for the get_http_session function, which creates
and configures an HTTP client session using the aiohttp library.
"""

from unittest.mock import MagicMock, patch

import pytest

from website_monitor.config.http_config import get_http_session
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


class TestGetHttpSession:
    """Tests for the get_http_session function."""

    def test_get_http_session_should_create_client_session(
        self, mock_context: MonitoringContext
    ) -> None:
        """
        Test that get_http_session creates an aiohttp.ClientSession.

        This test verifies that the function creates and returns a new
        aiohttp.ClientSession instance.
        """
        # Arrange
        mock_client_session = MagicMock()
        with patch("aiohttp.ClientSession", return_value=mock_client_session) as mock_session_class:
            # Act
            result = get_http_session(mock_context)

            # Assert
            mock_session_class.assert_called_once()
            assert result == mock_client_session

    def test_get_http_session_should_handle_client_session_creation_error(
        self, mock_context: MonitoringContext
    ) -> None:
        """
        Test that get_http_session handles errors when creating the client session.

        This test verifies that if an error occurs during client session creation,
        the function raises the exception.
        """
        # Arrange
        with patch(
            "aiohttp.ClientSession", side_effect=Exception("Session creation error")
        ) as mock_session_class:
            # Act & Assert
            with pytest.raises(Exception, match="Session creation error"):
                get_http_session(mock_context)

    def test_get_http_session_should_use_context_parameters_when_implemented(
        self, mock_context: MonitoringContext
    ) -> None:
        """
        Test that get_http_session uses context parameters when implemented.

        This test is a placeholder for future implementation where the function
        might use parameters from the context to configure the client session.
        Currently, the function doesn't use any context parameters, but this test
        ensures that when that functionality is added, it will be tested.

        Note: This test will pass with the current implementation but should be
        updated when the function is enhanced to use context parameters.
        """
        # Arrange
        mock_client_session = MagicMock()
        with patch("aiohttp.ClientSession", return_value=mock_client_session) as mock_session_class:
            # Act
            result = get_http_session(mock_context)

            # Assert
            # Currently, no context parameters are used, but this assertion
            # should be updated when the function is enhanced
            mock_session_class.assert_called_once_with()
            assert result == mock_client_session
