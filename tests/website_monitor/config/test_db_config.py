"""
Unit tests for the database configuration module.

This module contains comprehensive tests for the database configuration module,
ensuring that it correctly creates and validates a connection pool to the
PostgreSQL database.

The tests follow the Arrange-Act-Assert (AAA) pattern and use proper mocking
of all external dependencies to ensure true unit testing.
"""

import asyncio
from asyncio import AbstractEventLoop
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest
import pytest_asyncio

from website_monitor.config.db_config import initiate_db_pool
from website_monitor.config.monitoring_context import MonitoringContext


# Configure pytest-asyncio to use function scope for event loops
@pytest_asyncio.fixture(scope="function")
def event_loop() -> AsyncGenerator[AbstractEventLoop, None]:
    """
    Creates an event loop for each test function.

    This is needed because the database configuration functions are asynchronous.

    Returns:
        AsyncGenerator[AbstractEventLoop, None]: An event loop for the test function.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    # Clean up any pending tasks
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    loop.close()


@pytest_asyncio.fixture
async def mock_context() -> MonitoringContext:
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


@pytest_asyncio.fixture
async def mock_pool() -> asyncpg.pool.Pool:
    """
    Creates a mock asyncpg.pool.Pool for testing.

    Returns:
        asyncpg.pool.Pool: A mock Pool with configured async methods.
    """
    pool = AsyncMock(spec=asyncpg.pool.Pool)

    # Configure the mock connection
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)

    # Configure the pool's acquire method to return the mock connection
    pool.acquire.return_value.__aenter__.return_value = mock_conn

    return pool


@pytest.mark.asyncio
async def test_initiate_db_pool_should_create_and_validate_pool(
    mock_context: MonitoringContext, mock_pool: asyncpg.pool.Pool
) -> None:
    """
    Tests that initiate_db_pool creates and validates a connection pool successfully.
    """
    # Arrange
    # Mock asyncpg.create_pool and logging
    with patch("asyncpg.create_pool", return_value=mock_pool) as mock_create_pool:
        with patch("logging.getLogger") as mock_get_logger:
            # Mock the logger
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            # Act
            result = await initiate_db_pool(mock_context)

            # Assert
            mock_create_pool.assert_awaited_once_with(
                dsn=mock_context.dsn, max_size=mock_context.db_pool_size
            )
            mock_pool.acquire.assert_awaited_once()
            mock_conn = mock_pool.acquire.return_value.__aenter__.return_value
            mock_conn.fetchval.assert_awaited_once_with("SELECT 1")
            mock_logger.info.assert_called_once_with(
                "Database connection pool successfully created."
            )
            assert result == mock_pool


@pytest.mark.asyncio
async def test_initiate_db_pool_should_close_pool_and_raise_exception_on_error(
    mock_context, mock_pool
):
    """
    Tests that initiate_db_pool closes the pool and raises an exception when connection validation fails.
    """
    # Arrange
    # Configure the mock connection to raise an exception
    mock_conn = mock_pool.acquire.return_value.__aenter__.return_value
    mock_conn.fetchval.side_effect = Exception("Connection error")

    # Mock asyncpg.create_pool and logging
    with patch("asyncpg.create_pool", return_value=mock_pool) as mock_create_pool:
        with patch("logging.getLogger") as mock_get_logger:
            # Mock the logger
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            # Act & Assert
            with pytest.raises(Exception, match="Connection error"):
                await initiate_db_pool(mock_context)

            # Verify that the pool was closed
            mock_pool.close.assert_awaited_once()
            mock_logger.error.assert_called_once()
