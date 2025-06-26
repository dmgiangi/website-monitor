"""
Unit tests for the FailurePersistenceProcessor class.

This module contains comprehensive tests for the FailurePersistenceProcessor class,
ensuring that it correctly buffers and persists information about failed monitoring
checks to a database in efficient batches.

The tests follow the Arrange-Act-Assert (AAA) pattern and use proper mocking
of all external dependencies to ensure true unit testing.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from asyncpg import Pool, exceptions

from website_monitor.domain import FetchResult, HttpMethod, Target
from website_monitor.processor.error_persistence_processor import FailurePersistenceProcessor


@pytest_asyncio.fixture
async def sample_target() -> Target:
    """
    Creates a sample Target object for testing.

    Returns:
        A Target object with test values.
    """
    return Target(
        id=1,
        url="https://example.com",
        method=HttpMethod.GET,
        check_interval=timedelta(minutes=5),
        regex_pattern="test pattern",
        default_headers={"User-Agent": "Test Agent"},
    )


@pytest_asyncio.fixture
async def sample_success_result(sample_target: Target) -> FetchResult:
    """
    Creates a sample successful FetchResult object for testing.

    Args:
        sample_target: A fixture providing a sample Target.

    Returns:
        A FetchResult object representing a successful check.
    """
    return FetchResult(
        target=sample_target,
        error=None,
        start_time=1000.0,
        end_time=1001.0,
        status_code=200,
        regex_has_matches=True,
    )


@pytest_asyncio.fixture
async def sample_error_result(sample_target: Target) -> FetchResult:
    """
    Creates a sample FetchResult object with an error for testing.

    Args:
        sample_target: A fixture providing a sample Target.

    Returns:
        A FetchResult object representing a failed check.
    """
    return FetchResult(
        target=sample_target,
        error=Exception("Test error"),
        start_time=1000.0,
        end_time=1001.0,
        status_code=None,
        regex_has_matches=None,
    )


@pytest_asyncio.fixture
async def mock_pool() -> AsyncMock:
    """
    Creates a mock asyncpg.Pool for testing.

    Returns:
        A mock Pool with configured async methods.
    """
    pool = AsyncMock(spec=Pool)

    # Mock the connection context manager
    connection = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = connection

    return pool


@pytest_asyncio.fixture
async def processor(mock_pool: AsyncMock) -> FailurePersistenceProcessor:
    """
    Creates a FailurePersistenceProcessor instance with mock dependencies.

    Args:
        mock_pool: A fixture providing a mock asyncpg.Pool.

    Returns:
        A FailurePersistenceProcessor instance configured with mock dependencies.
    """
    return FailurePersistenceProcessor(
        worker_id="test-worker",
        pool=mock_pool,
        max_buffer_size=3,
    )


@pytest.mark.asyncio
async def test_process_should_ignore_successful_results(
    processor: FailurePersistenceProcessor, sample_success_result: FetchResult
) -> None:
    """
    Tests that the process method ignores successful results.
    """
    # Arrange
    # The processor's buffer should be empty initially
    assert len(processor._buffer) == 0

    # Act
    await processor.process(sample_success_result)

    # Assert
    # The buffer should still be empty after processing a successful result
    assert len(processor._buffer) == 0


@pytest.mark.asyncio
async def test_process_should_buffer_error_results(
    processor: FailurePersistenceProcessor, sample_error_result: FetchResult
) -> None:
    """
    Tests that the process method buffers results with errors.
    """
    # Arrange
    # The processor's buffer should be empty initially
    assert len(processor._buffer) == 0

    # Act
    await processor.process(sample_error_result)

    # Assert
    # The buffer should contain the error result
    assert len(processor._buffer) == 1
    assert processor._buffer[0] == sample_error_result


@pytest.mark.asyncio
async def test_process_should_flush_when_buffer_reaches_max_size(
    processor: FailurePersistenceProcessor, sample_error_result: FetchResult
) -> None:
    """
    Tests that the process method triggers a flush when the buffer reaches its maximum size.
    """
    # Arrange
    # Mock the flush method to track calls
    processor.flush = AsyncMock()

    # Act
    # Process enough error results to reach the max buffer size
    for _ in range(processor._max_buffer_size):
        await processor.process(sample_error_result)

    # Assert
    # The flush method should have been called once
    processor.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_flush_should_do_nothing_when_buffer_is_empty(
    processor: FailurePersistenceProcessor, mock_pool: AsyncMock
) -> None:
    """
    Tests that the flush method does nothing when the buffer is empty.
    """
    # Arrange
    # The processor's buffer should be empty initially
    assert len(processor._buffer) == 0

    # Act
    await processor.flush()

    # Assert
    # The pool's acquire method should not have been called
    mock_pool.acquire.assert_not_called()


@pytest.mark.asyncio
async def test_flush_should_clear_buffer_after_successful_db_operation(
    processor: FailurePersistenceProcessor, sample_error_result: FetchResult, mock_pool: AsyncMock
) -> None:
    """
    Tests that the flush method clears the buffer after a successful database operation.
    """
    # Arrange
    # Add an error result to the buffer
    await processor.process(sample_error_result)
    assert len(processor._buffer) == 1

    # Act
    await processor.flush()

    # Assert
    # The buffer should be empty after flushing
    assert len(processor._buffer) == 0
    # The connection's executemany method should have been called
    connection = mock_pool.acquire.return_value.__aenter__.return_value
    assert connection.executemany.called


@pytest.mark.asyncio
async def test_flush_should_handle_postgres_error(
    processor: FailurePersistenceProcessor, sample_error_result: FetchResult, mock_pool: AsyncMock
) -> None:
    """
    Tests that the flush method handles PostgresError exceptions.
    """
    # Arrange
    # Add an error result to the buffer
    await processor.process(sample_error_result)
    assert len(processor._buffer) == 1

    # Configure the connection to raise a PostgresError
    connection = mock_pool.acquire.return_value.__aenter__.return_value
    connection.executemany.side_effect = exceptions.PostgresError("Test PostgresError")

    # Act
    await processor.flush()

    # Assert
    # The buffer should be empty after flushing (even though there was an error)
    assert len(processor._buffer) == 0
    # The connection's executemany method should have been called
    assert connection.executemany.called


@pytest.mark.asyncio
async def test_flush_should_handle_generic_exception(
    processor: FailurePersistenceProcessor, sample_error_result: FetchResult, mock_pool: AsyncMock
) -> None:
    """
    Tests that the flush method handles generic exceptions.
    """
    # Arrange
    # Add an error result to the buffer
    await processor.process(sample_error_result)
    assert len(processor._buffer) == 1

    # Configure the connection to raise a generic Exception
    connection = mock_pool.acquire.return_value.__aenter__.return_value
    connection.executemany.side_effect = Exception("Test generic exception")

    # Act
    await processor.flush()

    # Assert
    # The buffer should be empty after flushing (even though there was an error)
    assert len(processor._buffer) == 0
    # The connection's executemany method should have been called
    assert connection.executemany.called


@pytest.mark.asyncio
async def test_flush_should_transform_data_correctly(
    processor: FailurePersistenceProcessor, sample_error_result: FetchResult, mock_pool: AsyncMock
) -> None:
    """
    Tests that the flush method transforms the data correctly before inserting it into the database.
    """
    # Arrange
    # Add an error result to the buffer
    await processor.process(sample_error_result)
    assert len(processor._buffer) == 1

    # Act
    await processor.flush()

    # Assert
    # The connection's executemany method should have been called with the correct parameters
    connection = mock_pool.acquire.return_value.__aenter__.return_value
    assert connection.executemany.called

    # Get the arguments passed to executemany
    call_args = connection.executemany.call_args
    assert call_args is not None

    # Check that the SQL query is correct
    sql = call_args[0][0]
    assert "INSERT INTO failure_log " in sql

    # Check that the records are correctly transformed
    records = call_args[0][1]
    assert len(records) == 1
    record = records[0]

    # Check each field in the record
    assert record[0] == sample_error_result.target.id  # original_target_id
    assert record[1] == "test-worker"  # worker_id
    assert isinstance(record[2], datetime)  # check_start_time
    assert isinstance(record[3], datetime)  # check_end_time
    assert record[4] == "Exception"  # failure_type
    assert record[5] == "Test error"  # detail
    assert record[6] is None  # http_status_code

    # Check the target_snapshot
    target_snapshot = record[7]
    assert target_snapshot["url"] == sample_error_result.target.url
    assert target_snapshot["method"] == sample_error_result.target.method.value
    assert (
        target_snapshot["check_interval_seconds"]
        == sample_error_result.target.check_interval.total_seconds()
    )
    assert target_snapshot["regex_pattern"] == sample_error_result.target.regex_pattern
    assert target_snapshot["default_headers"] == sample_error_result.target.default_headers
