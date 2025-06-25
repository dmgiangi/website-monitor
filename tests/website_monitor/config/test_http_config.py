"""
Unit tests for the HTTP client configuration module.

This module contains comprehensive tests for the HTTP client configuration module,
ensuring that it correctly creates and configures HTTP client sessions based on
the provided configuration context.

The tests follow the Arrange-Act-Assert (AAA) pattern and use proper mocking
of all external dependencies to ensure true unit testing.
"""

from unittest.mock import MagicMock, patch

import aiohttp
import pytest
from aiohttp import TraceConfig

from website_monitor.config.http_config import get_http_session, get_trace_config
from website_monitor.config.monitoring_context import MonitoringContext


@pytest.fixture
def mock_context_tracing_enabled() -> MonitoringContext:
    """
    Creates a mock MonitoringContext with tracing enabled for testing.

    Returns:
        MonitoringContext: A MonitoringContext with tracing enabled.
    """
    return MonitoringContext(
        dsn="postgresql://localhost/test",
        worker_id="test-worker",
        enable_tracing=True,
        logging_type="dev",
        logging_config_file="",
        queue_size=100,
        batch_size=10,
        worker_number=5,
        db_pool_size=10,
    )


@pytest.fixture
def mock_context_tracing_disabled() -> MonitoringContext:
    """
    Creates a mock MonitoringContext with tracing disabled for testing.

    Returns:
        MonitoringContext: A MonitoringContext with tracing disabled.
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


def test_get_http_session_should_create_session_with_tracing_when_enabled(
    mock_context_tracing_enabled: MonitoringContext,
) -> None:
    """
    Tests that get_http_session creates a session with tracing when tracing is enabled.
    """
    # Arrange
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    mock_trace_config = [MagicMock(spec=TraceConfig)]

    # Mock aiohttp.ClientSession and get_trace_config
    with patch("aiohttp.ClientSession", return_value=mock_session) as mock_client_session:
        with patch(
            "website_monitor.config.http_config.get_trace_config", return_value=mock_trace_config
        ) as mock_get_trace_config:
            with patch("logging.getLogger") as mock_get_logger:
                # Mock the logger
                mock_logger = MagicMock()
                mock_get_logger.return_value = mock_logger

                # Act
                result = get_http_session(mock_context_tracing_enabled)

                # Assert
                mock_get_logger.assert_called_once_with(__name__)
                mock_logger.info.assert_called_once_with(
                    "Creating HTTP session with tracing enabled"
                )
                mock_get_trace_config.assert_called_once_with()
                mock_client_session.assert_called_once_with(trace_configs=mock_trace_config)
                assert result == mock_session


def test_get_http_session_should_create_session_without_tracing_when_disabled(
    mock_context_tracing_disabled: MonitoringContext,
) -> None:
    """
    Tests that get_http_session creates a session without tracing when tracing is disabled.
    """
    # Arrange
    mock_session = MagicMock(spec=aiohttp.ClientSession)

    # Mock aiohttp.ClientSession
    with patch("aiohttp.ClientSession", return_value=mock_session) as mock_client_session:
        with patch("logging.getLogger") as mock_get_logger:
            # Mock the logger
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            # Act
            result = get_http_session(mock_context_tracing_disabled)

            # Assert
            mock_get_logger.assert_called_once_with(__name__)
            mock_logger.info.assert_called_once_with("Creating HTTP session without tracing")
            mock_client_session.assert_called_once_with()
            assert result == mock_session


def test_get_trace_config_should_return_empty_list() -> None:
    """
    Tests that get_trace_config returns an empty list.
    """
    # Arrange
    # Mock logging
    with patch("logging.getLogger") as mock_get_logger:
        # Mock the logger
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Act
        result = get_trace_config()

        # Assert
        mock_get_logger.assert_called_once_with(__name__)
        mock_logger.debug.assert_called_once_with("Configuring HTTP tracing")
        assert isinstance(result, list)
        assert len(result) == 0
