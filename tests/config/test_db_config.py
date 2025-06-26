"""
Tests for the db_config module in the website_monitor.config package.

This module contains tests for the initiate_db_pool function, which creates
and validates a connection pool to the PostgreSQL database.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from website_monitor.config.db_config import initiate_db_pool
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


# Helper function to create awaitable mocks
def async_return(value) -> asyncio.Future:
    """Create an awaitable that returns the given value."""
    future = asyncio.Future()
    future.set_result(value)
    return future


class TestInitiateDbPool:
    """Tests for the initiate_db_pool function."""

    @pytest.mark.asyncio
    async def test_initiate_db_pool_should_create_pool_with_correct_parameters(
        self, mock_context: MonitoringContext
    ) -> None:
        """
        Test that initiate_db_pool creates a pool with the correct parameters.

        This test verifies that the function calls asyncpg.create_pool with the
        correct DSN and max_size parameters from the context.
        """
        # Arrange
        mock_pool = MagicMock()
        mock_connection = MagicMock()
        mock_connection.fetchval = MagicMock(return_value=async_return(1))

        # Mock the context manager for acquire
        mock_pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=MagicMock(return_value=async_return(mock_connection)),
                __aexit__=MagicMock(return_value=async_return(None)),
            )
        )

        # Mock the close method
        mock_pool.close = MagicMock(return_value=async_return(None))

        with patch("asyncpg.create_pool", return_value=async_return(mock_pool)) as mock_create_pool:
            # Act
            result = await initiate_db_pool(mock_context)

            # Assert
            mock_create_pool.assert_called_once_with(
                dsn=mock_context.dsn, max_size=mock_context.db_pool_size
            )
            assert result == mock_pool

    @pytest.mark.asyncio
    async def test_initiate_db_pool_should_validate_connection(
        self, mock_context: MonitoringContext
    ) -> None:
        """
        Test that initiate_db_pool validates the connection by executing a query.

        This test verifies that the function acquires a connection from the pool
        and executes a simple query to validate the connection.
        """
        # Arrange
        mock_pool = MagicMock()
        mock_connection = MagicMock()
        mock_connection.fetchval = MagicMock(return_value=async_return(1))

        # Mock the context manager for acquire
        mock_pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=MagicMock(return_value=async_return(mock_connection)),
                __aexit__=MagicMock(return_value=async_return(None)),
            )
        )

        with patch("asyncpg.create_pool", return_value=async_return(mock_pool)):
            # Act
            await initiate_db_pool(mock_context)

            # Assert
            mock_pool.acquire.assert_called_once()
            mock_connection.fetchval.assert_called_once_with("SELECT 1")

    @pytest.mark.asyncio
    async def test_initiate_db_pool_should_close_pool_and_raise_exception_on_error(
        self, mock_context: MonitoringContext
    ) -> None:
        """
        Test that initiate_db_pool closes the pool and raises an exception on error.

        This test verifies that if an error occurs during connection validation,
        the function closes the pool and re-raises the exception.
        """
        # Arrange
        error_msg = "Connection error"
        exception = Exception(error_msg)

        mock_pool = MagicMock()
        mock_connection = MagicMock()
        mock_connection.fetchval = MagicMock(side_effect=exception)

        # Mock the context manager for acquire
        mock_pool.acquire = MagicMock(
            return_value=MagicMock(
                __aenter__=MagicMock(return_value=async_return(mock_connection)),
                __aexit__=MagicMock(return_value=async_return(None)),
            )
        )

        # Mock the close method
        mock_pool.close = MagicMock(return_value=async_return(None))

        with patch("asyncpg.create_pool", return_value=async_return(mock_pool)):
            # Act & Assert
            with pytest.raises(Exception) as excinfo:
                await initiate_db_pool(mock_context)

            # Verify the exception message
            assert str(excinfo.value) == error_msg

            # Verify that the pool was closed
            mock_pool.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_initiate_db_pool_should_handle_create_pool_error(
        self, mock_context: MonitoringContext
    ) -> None:
        """
        Test that initiate_db_pool handles errors when creating the pool.

        This test verifies that if an error occurs during pool creation,
        the function raises the exception without attempting to close the pool.
        """
        # Arrange
        error_msg = "Pool creation error"
        exception = Exception(error_msg)

        with patch("asyncpg.create_pool", side_effect=exception):
            # Act & Assert
            with pytest.raises(Exception) as excinfo:
                await initiate_db_pool(mock_context)

            # Verify the exception message
            assert str(excinfo.value) == error_msg
