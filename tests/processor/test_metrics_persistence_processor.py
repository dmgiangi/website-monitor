"""
Unit tests for the MetricsPersistenceProcessor class.

This module contains comprehensive tests for the MetricsPersistenceProcessor class,
ensuring that it correctly buffers and persists metrics from monitoring checks
to a database in efficient batches.

The tests follow the Arrange-Act-Assert (AAA) pattern and use proper mocking
of all external dependencies to ensure true unit testing.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from asyncpg import Pool, exceptions

from website_monitor.domain import FetchResult, HttpMethod, Target
from website_monitor.processor.metrics_persistence_processor import MetricsPersistenceProcessor


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

    # Mock the transaction context manager
    transaction = AsyncMock()
    connection.transaction.return_value.__aenter__.return_value = transaction

    return pool


@pytest_asyncio.fixture
async def processor(mock_pool: AsyncMock) -> MetricsPersistenceProcessor:
    """
    Creates a MetricsPersistenceProcessor instance with mock dependencies.

    Args:
        mock_pool: A fixture providing a mock asyncpg.Pool.

    Returns:
        A MetricsPersistenceProcessor instance configured with mock dependencies.
    """
    return MetricsPersistenceProcessor(
        worker_id="test-worker",
        pool=mock_pool,
        max_buffer_size=3,
    )


@pytest.mark.asyncio
async def test_transform_result_should_correctly_transform_success_result(
    processor: MetricsPersistenceProcessor, sample_success_result: FetchResult
) -> None:
    """
    Tests that the _transform_result method correctly transforms a successful result.
    """
    # Arrange
    # Nothing to arrange

    # Act
    result = processor._transform_result(sample_success_result)

    # Assert
    assert isinstance(result, tuple)
    assert len(result) == 8
    assert isinstance(result[0], datetime)  # checked_at
    assert result[1] == sample_success_result.target.id  # target_id
    assert result[2] == sample_success_result.target.url  # target_url
    assert result[3] == sample_success_result.status_code  # status_code
    assert result[4] == sample_success_result.regex_has_matches  # regex_match
    assert result[5] is True  # is_success
    assert result[6] == "test-worker"  # worker_id
    assert result[7] == 1000  # response_time_ms (1001.0 - 1000.0) * 1000


@pytest.mark.asyncio
async def test_transform_result_should_correctly_transform_error_result(
    processor: MetricsPersistenceProcessor, sample_error_result: FetchResult
) -> None:
    """
    Tests that the _transform_result method correctly transforms a result with an error.
    """
    # Arrange
    # Nothing to arrange

    # Act
    result = processor._transform_result(sample_error_result)

    # Assert
    assert isinstance(result, tuple)
    assert len(result) == 8
    assert isinstance(result[0], datetime)  # checked_at
    assert result[1] == sample_error_result.target.id  # target_id
    assert result[2] == sample_error_result.target.url  # target_url
    assert result[3] is None  # status_code
    assert result[4] is None  # regex_match
    assert result[5] is False  # is_success
    assert result[6] == "test-worker"  # worker_id
    assert result[7] == 1000  # response_time_ms (1001.0 - 1000.0) * 1000


@pytest.mark.asyncio
async def test_process_should_buffer_result(
    processor: MetricsPersistenceProcessor, sample_success_result: FetchResult
) -> None:
    """
    Tests that the process method buffers the result.
    """
    # Arrange
    # The processor's buffer should be empty initially
    assert len(processor._buffer) == 0

    # Act
    await processor.process(sample_success_result)

    # Assert
    # The buffer should contain the transformed result
    assert len(processor._buffer) == 1
    assert isinstance(processor._buffer[0], tuple)
    assert len(processor._buffer[0]) == 8


@pytest.mark.asyncio
async def test_process_should_flush_when_buffer_reaches_max_size(
    processor: MetricsPersistenceProcessor, sample_success_result: FetchResult, mock_pool: AsyncMock
) -> None:
    """
    Tests that the process method triggers a flush when the buffer reaches its maximum size.
    """
    # Arrange
    # Mock the flush method to track calls
    processor.flush = AsyncMock()

    # Act
    # Process enough results to reach the max buffer size
    for _ in range(processor._max_buffer_size):
        await processor.process(sample_success_result)

    # Assert
    # The flush method should have been called once
    processor.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_flush_should_do_nothing_when_buffer_is_empty(
    processor: MetricsPersistenceProcessor, mock_pool: AsyncMock
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
    processor: MetricsPersistenceProcessor, sample_success_result: FetchResult, mock_pool: AsyncMock
) -> None:
    """
    Tests that the flush method clears the buffer after a successful database operation.
    """
    # Arrange
    # Add a result to the buffer
    await processor.process(sample_success_result)
    assert len(processor._buffer) == 1

    # Act
    await processor.flush()

    # Assert
    # The buffer should be empty after flushing
    assert len(processor._buffer) == 0


@pytest.mark.asyncio
async def test_flush_should_handle_timeout_error(
    processor: MetricsPersistenceProcessor, sample_success_result: FetchResult, mock_pool: AsyncMock
) -> None:
    """
    Tests that the flush method handles TimeoutError exceptions.
    """
    # Arrange
    # Add a result to the buffer
    await processor.process(sample_success_result)
    assert len(processor._buffer) == 1

    # Configure the pool to raise a TimeoutError
    mock_pool.acquire.side_effect = asyncio.TimeoutError("Test TimeoutError")

    # Act
    await processor.flush()

    # Assert
    # The buffer should be empty after flushing (even though there was an error)
    assert len(processor._buffer) == 0
    # The pool's acquire method should have been called
    assert mock_pool.acquire.called


@pytest.mark.asyncio
async def test_flush_should_handle_postgres_error(
    processor: MetricsPersistenceProcessor, sample_success_result: FetchResult, mock_pool: AsyncMock
) -> None:
    """
    Tests that the flush method handles PostgresError exceptions.
    """
    # Arrange
    # Add a result to the buffer
    await processor.process(sample_success_result)
    assert len(processor._buffer) == 1

    # Configure the pool to raise a PostgresError
    mock_pool.acquire.side_effect = exceptions.PostgresError("Test PostgresError")

    # Act
    await processor.flush()

    # Assert
    # The buffer should be empty after flushing (even though there was an error)
    assert len(processor._buffer) == 0


@pytest.mark.asyncio
async def test_flush_should_handle_generic_exception(
    processor: MetricsPersistenceProcessor, sample_success_result: FetchResult, mock_pool: AsyncMock
) -> None:
    """
    Tests that the flush method handles generic exceptions.
    """
    # Arrange
    # Add a result to the buffer
    await processor.process(sample_success_result)
    assert len(processor._buffer) == 1

    # Configure the pool to raise a generic Exception
    mock_pool.acquire.side_effect = Exception("Test generic exception")

    # Act
    await processor.flush()

    # Assert
    # The buffer should be empty after flushing (even though there was an error)
    assert len(processor._buffer) == 0


@pytest.mark.asyncio
async def test_flush_should_use_correct_sql_query(
    processor: MetricsPersistenceProcessor, sample_success_result: FetchResult
) -> None:
    """
    Tests that the flush method uses the correct SQL query.
    """
    # Arrange
    # Add a result to the buffer
    await processor.process(sample_success_result)
    assert len(processor._buffer) == 1

    # Verify that the processor has the correct SQL query
    assert "INSERT INTO metrics" in processor._insert_sql

    # Act
    await processor.flush()

    # Assert
    # The buffer should be empty after flushing
    assert len(processor._buffer) == 0
