"""
Unit tests for the PostgresScheduler class.

This module contains comprehensive tests for the PostgresScheduler class,
ensuring that it correctly fetches and distributes monitoring targets
from a PostgreSQL database.

The tests follow the Arrange-Act-Assert (AAA) pattern and use proper mocking
of all external dependencies to ensure true unit testing.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from asyncpg import Pool, Record

from website_monitor.domain import HttpMethod, Target
from website_monitor.scheduler.asyncpg_scheduler import (
    FETCH_AND_LEASE_QUERY,
    GET_NEXT_FIRE_AT_QUERY,
    PostgresScheduler,
    map_target,
)


# Configure pytest-asyncio to use function scope for event loops
@pytest_asyncio.fixture(scope="function")
def event_loop() -> asyncio.AbstractEventLoop:
    """
    Creates an event loop for each test function.

    This is needed because the PostgresScheduler creates tasks that need to be
    properly cleaned up after each test.

    Returns:
        asyncio.AbstractEventLoop: The event loop for the test.
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
async def mock_pool() -> AsyncMock:
    """
    Creates a mock asyncpg.Pool for testing.

    Returns:
        AsyncMock: A mock Pool with configured async methods.
    """
    pool = AsyncMock(spec=Pool)

    # Configure the mock connection and transaction
    mock_conn = AsyncMock()
    mock_transaction = AsyncMock()

    # Configure the connection's transaction method to return the mock transaction
    mock_conn.transaction.return_value = mock_transaction

    # Configure the pool's acquire method to return the mock connection
    pool.acquire.return_value.__aenter__.return_value = mock_conn

    return pool


@pytest_asyncio.fixture
async def mock_record() -> MagicMock:
    """
    Creates a mock database record for testing.

    Returns:
        MagicMock: A mock Record with test values.
    """
    record = MagicMock(spec=Record)
    record.get.return_value = "GET"
    record.__getitem__.side_effect = lambda key: {
        "id": 1,
        "url": "https://example.com",
        "method": "GET",
        "check_interval": timedelta(minutes=5),
        "regex_pattern": None,
        "default_headers": None,
    }.get(key)

    # Make the record behave like a dict for **record unpacking
    record.items.return_value = [
        ("id", 1),
        ("url", "https://example.com"),
        ("method", "GET"),
        ("check_interval", timedelta(minutes=5)),
        ("regex_pattern", None),
        ("default_headers", None),
    ]

    return record


@pytest_asyncio.fixture
async def scheduler(mock_pool: AsyncMock) -> PostgresScheduler:
    """
    Creates a PostgresScheduler instance with mock dependencies.

    Args:
        mock_pool: A fixture providing a mock Pool.

    Returns:
        PostgresScheduler: A PostgresScheduler instance configured with mock dependencies.
    """
    return PostgresScheduler(worker_id="test-worker", pool=mock_pool, batch_size=10, recover_time=5)


@pytest.mark.asyncio
async def test_init_should_validate_worker_id() -> None:
    """
    Tests that the constructor validates the worker_id parameter.
    """
    # Arrange
    mock_pool = AsyncMock(spec=Pool)

    # Act & Assert
    with pytest.raises(ValueError, match="worker_id must be provided and must be not blank."):
        PostgresScheduler(worker_id="", pool=mock_pool)

    with pytest.raises(ValueError, match="worker_id must be provided and must be not blank."):
        PostgresScheduler(worker_id=None, pool=mock_pool)


@pytest.mark.asyncio
async def test_init_should_validate_batch_size() -> None:
    """
    Tests that the constructor validates the batch_size parameter.
    """
    # Arrange
    mock_pool = AsyncMock(spec=Pool)

    # Act & Assert
    with pytest.raises(ValueError, match="batch_size must be a positive integer."):
        PostgresScheduler(worker_id="test", pool=mock_pool, batch_size=0)

    with pytest.raises(ValueError, match="batch_size must be a positive integer."):
        PostgresScheduler(worker_id="test", pool=mock_pool, batch_size=-1)

    with pytest.raises(ValueError, match="batch_size must be a positive integer."):
        PostgresScheduler(worker_id="test", pool=mock_pool, batch_size="not-an-int")


@pytest.mark.asyncio
async def test_init_should_validate_recover_time() -> None:
    """
    Tests that the constructor validates the recover_time parameter.
    """
    # Arrange
    mock_pool = AsyncMock(spec=Pool)

    # Act & Assert
    with pytest.raises(ValueError, match="recover_time must be a positive integer."):
        PostgresScheduler(worker_id="test", pool=mock_pool, recover_time=0)

    with pytest.raises(ValueError, match="recover_time must be a positive integer."):
        PostgresScheduler(worker_id="test", pool=mock_pool, recover_time=-1)

    with pytest.raises(ValueError, match="recover_time must be a positive integer."):
        PostgresScheduler(worker_id="test", pool=mock_pool, recover_time="not-an-int")


@pytest.mark.asyncio
async def test_start_should_set_is_running_to_true(scheduler: PostgresScheduler) -> None:
    """
    Tests that the start method sets _is_running to True.
    """
    # Arrange
    scheduler._is_running = False

    # Act
    await scheduler.start()

    # Assert
    assert scheduler._is_running is True


@pytest.mark.asyncio
async def test_stop_should_set_is_running_to_false(scheduler: PostgresScheduler) -> None:
    """
    Tests that the stop method sets _is_running to False.
    """
    # Arrange
    scheduler._is_running = True

    # Act
    await scheduler.stop()

    # Assert
    assert scheduler._is_running is False


@pytest.mark.asyncio
async def test_map_target_should_convert_record_to_target(mock_record: MagicMock) -> None:
    """
    Tests that the map_target function correctly converts a database record to a Target object.
    """
    # Arrange
    # The mock_record fixture provides a record with test values

    # Act
    target = await map_target(mock_record)

    # Assert
    assert isinstance(target, Target)
    assert target.id == 1
    assert target.url == "https://example.com"
    assert target.method == HttpMethod.GET
    assert target.check_interval == timedelta(minutes=5)
    assert target.regex_pattern is None
    assert target.default_headers is None


@pytest.mark.asyncio
async def test_map_target_should_convert_method_to_uppercase(mock_record: MagicMock) -> None:
    """
    Tests that the map_target function converts the HTTP method to uppercase.
    """
    # Arrange
    mock_record.get.return_value = "get"  # Lowercase method

    # Act
    target = await map_target(mock_record)

    # Assert
    assert target.method == HttpMethod.GET  # Should be uppercase


@pytest.mark.asyncio
async def test_anext_should_fetch_and_return_targets_when_due(
    scheduler: PostgresScheduler, mock_pool: AsyncMock, mock_record: MagicMock
) -> None:
    """
    Tests that the __anext__ method fetches and returns targets when there are due targets.
    """
    # Arrange
    conn = mock_pool.acquire.return_value.__aenter__.return_value
    conn.fetch.return_value = [mock_record]

    # Act
    result = await scheduler.__anext__()

    # Assert
    conn.fetch.assert_awaited_once_with(FETCH_AND_LEASE_QUERY, 10, "test-worker")
    assert len(result) == 1
    assert isinstance(result[0], Target)
    assert result[0].id == 1
    assert result[0].url == "https://example.com"


@pytest.mark.asyncio
async def test_anext_should_sleep_and_retry_when_no_due_targets(
    scheduler: PostgresScheduler, mock_pool: AsyncMock
) -> None:
    """
    Tests that the __anext__ method sleeps and retries when there are no due targets.
    """
    # Arrange
    conn = mock_pool.acquire.return_value.__aenter__.return_value
    # First call to fetch returns empty list, second call returns a record
    conn.fetch.side_effect = [[], [MagicMock(spec=Record)]]
    # Configure fetchval to return a future datetime
    future_time = datetime.now(timezone.utc) + timedelta(seconds=30)
    conn.fetchval.return_value = future_time

    # Mock asyncio.sleep to avoid actual waiting
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # Act
        result = await scheduler.__anext__()

        # Assert
        conn.fetch.assert_awaited()
        conn.fetchval.assert_awaited_once_with(GET_NEXT_FIRE_AT_QUERY)
        mock_sleep.assert_awaited_once()
        assert len(result) == 1


@pytest.mark.asyncio
async def test_anext_should_handle_database_exception(
    scheduler: PostgresScheduler, mock_pool: AsyncMock
) -> None:
    """
    Tests that the __anext__ method handles database exceptions.
    """
    # Arrange
    conn = mock_pool.acquire.return_value.__aenter__.return_value
    # First call raises exception, second call returns a record
    conn.fetch.side_effect = [Exception("Database error"), [MagicMock(spec=Record)]]

    # Mock asyncio.sleep to avoid actual waiting
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # Act
        result = await scheduler.__anext__()

        # Assert
        assert mock_sleep.await_count == 1
        assert mock_sleep.await_args[0][0] == scheduler._recover_time
        assert len(result) == 1


@pytest.mark.asyncio
async def test_anext_should_raise_stop_async_iteration_when_not_running(
    scheduler: PostgresScheduler,
) -> None:
    """
    Tests that the __anext__ method raises StopAsyncIteration when _is_running is False.
    """
    # Arrange
    scheduler._is_running = False

    # Act & Assert
    with pytest.raises(StopAsyncIteration):
        await scheduler.__anext__()


@pytest.mark.asyncio
async def test_anext_should_use_default_sleep_when_next_deadline_is_none(
    scheduler: PostgresScheduler, mock_pool: AsyncMock
) -> None:
    """
    Tests that the __anext__ method uses the default sleep duration when next_deadline is None.
    """
    # Arrange
    conn = mock_pool.acquire.return_value.__aenter__.return_value
    conn.fetch.return_value = []
    conn.fetchval.return_value = None  # No next deadline

    # Mock asyncio.sleep to avoid actual waiting
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # Set up to stop after first iteration
        scheduler._is_running = True

        def side_effect(*args: Any, **kwargs: Any) -> None:
            scheduler._is_running = False

        mock_sleep.side_effect = side_effect

        # Act & Assert
        with pytest.raises(StopAsyncIteration):
            await scheduler.__anext__()

        # Default sleep is 60 seconds, but capped at 60
        mock_sleep.assert_awaited_once_with(60)


@pytest.mark.asyncio
async def test_anext_should_cap_sleep_duration_at_60_seconds(
    scheduler: PostgresScheduler, mock_pool: AsyncMock
) -> None:
    """
    Tests that the __anext__ method caps the sleep duration at 60 seconds.
    """
    # Arrange
    conn = mock_pool.acquire.return_value.__aenter__.return_value
    conn.fetch.return_value = []
    # Set next deadline to be far in the future (more than 60 seconds)
    future_time = datetime.now(timezone.utc) + timedelta(seconds=120)
    conn.fetchval.return_value = future_time

    # Mock asyncio.sleep to avoid actual waiting
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # Set up to stop after first iteration
        scheduler._is_running = True

        def side_effect(*args: Any, **kwargs: Any) -> None:
            scheduler._is_running = False

        mock_sleep.side_effect = side_effect

        # Act & Assert
        with pytest.raises(StopAsyncIteration):
            await scheduler.__anext__()

        # Sleep duration should be capped at 60 seconds
        mock_sleep.assert_awaited_once_with(60)
