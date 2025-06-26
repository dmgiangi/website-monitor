"""
Unit tests for the DelegatingResultProcessor class.

This module contains comprehensive tests for the DelegatingResultProcessor class,
ensuring that it correctly delegates processing to multiple child processors
concurrently and handles failures in individual processors gracefully.

The tests follow the Arrange-Act-Assert (AAA) pattern and use proper mocking
of all external dependencies to ensure true unit testing.
"""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from website_monitor.contracts import ResultProcessor
from website_monitor.domain import FetchResult, HttpMethod, Target
from website_monitor.processor.delegating_processor import DelegatingResultProcessor


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
async def sample_result(sample_target: Target) -> FetchResult:
    """
    Creates a sample FetchResult object for testing.

    Args:
        sample_target: A fixture providing a sample Target.

    Returns:
        A FetchResult object with test values.
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
async def mock_processor() -> AsyncMock:
    """
    Creates a mock ResultProcessor for testing.

    Returns:
        A mock ResultProcessor with async methods.
    """
    processor = AsyncMock(spec=ResultProcessor)
    return processor


@pytest_asyncio.fixture
async def delegating_processor(mock_processor) -> DelegatingResultProcessor:
    """
    Creates a DelegatingResultProcessor with a single mock processor.

    Args:
        mock_processor: A fixture providing a mock ResultProcessor.

    Returns:
        A DelegatingResultProcessor configured with a mock processor.
    """
    return DelegatingResultProcessor(
        worker_id="test-worker",
        processors=[mock_processor],
    )


@pytest_asyncio.fixture
async def delegating_processor_with_multiple_processors() -> DelegatingResultProcessor:
    """
    Creates a DelegatingResultProcessor with multiple mock processors.

    Returns:
        A DelegatingResultProcessor configured with multiple mock processors.
    """
    processors = [AsyncMock(spec=ResultProcessor) for _ in range(3)]
    return DelegatingResultProcessor(
        worker_id="test-worker",
        processors=processors,
    )


@pytest_asyncio.fixture
async def delegating_processor_with_no_processors() -> DelegatingResultProcessor:
    """
    Creates a DelegatingResultProcessor with no processors.

    Returns:
        A DelegatingResultProcessor configured with an empty list of processors.
    """
    return DelegatingResultProcessor(
        worker_id="test-worker",
        processors=[],
    )


@pytest.mark.asyncio
async def test_process_should_delegate_to_single_processor(
    delegating_processor: DelegatingResultProcessor,
    mock_processor: AsyncMock,
    sample_result: FetchResult,
) -> None:
    """
    Tests that the process method delegates to a single processor.

    This test verifies that when the DelegatingResultProcessor has a single
    child processor, it correctly delegates the process call to that processor.
    """
    # Arrange
    # The mock_processor is already set up in the fixture

    # Act
    await delegating_processor.process(sample_result)

    # Assert
    mock_processor.process.assert_awaited_once_with(sample_result)


@pytest.mark.asyncio
async def test_process_should_delegate_to_multiple_processors(
    delegating_processor_with_multiple_processors: DelegatingResultProcessor,
    mock_processor: AsyncMock,
    sample_result: FetchResult,
) -> None:
    """
    Tests that the process method delegates to multiple processors concurrently.

    This test verifies that when the DelegatingResultProcessor has multiple
    child processors, it correctly delegates the process call to all of them.
    """
    # Arrange
    processors = delegating_processor_with_multiple_processors._processors

    # Act
    await delegating_processor_with_multiple_processors.process(sample_result)

    # Assert
    for processor in processors:
        processor.process.assert_awaited_once_with(sample_result)


@pytest.mark.asyncio
async def test_process_should_handle_empty_processor_list(
    delegating_processor_with_no_processors: DelegatingResultProcessor,
    sample_result: FetchResult,
) -> None:
    """
    Tests that the process method handles an empty processor list gracefully.

    This test verifies that when the DelegatingResultProcessor has no child
    processors, the process method returns without error.
    """
    # Arrange
    # The delegating_processor_with_no_processors is already set up in the fixture

    # Act & Assert
    # This should not raise an exception
    await delegating_processor_with_no_processors.process(sample_result)


@pytest.mark.asyncio
async def test_process_should_handle_processor_exception(
    delegating_processor: DelegatingResultProcessor,
    mock_processor: AsyncMock,
    sample_result: FetchResult,
) -> None:
    """
    Tests that the process method handles exceptions from processors gracefully.

    This test verifies that when a child processor raises an exception during
    processing, the DelegatingResultProcessor catches the exception and continues.
    """
    # Arrange
    mock_processor.process.side_effect = Exception("Processor error")

    # Patch the logger to verify it's called
    with patch("website_monitor.processor.delegating_processor.logger") as mock_logger:
        # Act
        await delegating_processor.process(sample_result)

        # Assert
        mock_processor.process.assert_awaited_once_with(sample_result)
        mock_logger.exception.assert_called_once()


@pytest.mark.asyncio
async def test_flush_should_delegate_to_single_processor(
    delegating_processor: DelegatingResultProcessor,
    mock_processor: AsyncMock,
) -> None:
    """
    Tests that the flush method delegates to a single processor.

    This test verifies that when the DelegatingResultProcessor has a single
    child processor, it correctly delegates the flush call to that processor.
    """
    # Arrange
    # The mock_processor is already set up in the fixture

    # Act
    await delegating_processor.flush()

    # Assert
    mock_processor.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_flush_should_delegate_to_multiple_processors(
    delegating_processor_with_multiple_processors: DelegatingResultProcessor,
) -> None:
    """
    Tests that the flush method delegates to multiple processors concurrently.

    This test verifies that when the DelegatingResultProcessor has multiple
    child processors, it correctly delegates the flush call to all of them.
    """
    # Arrange
    processors = delegating_processor_with_multiple_processors._processors

    # Act
    await delegating_processor_with_multiple_processors.flush()

    # Assert
    for processor in processors:
        processor.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_flush_should_handle_empty_processor_list(
    delegating_processor_with_no_processors: DelegatingResultProcessor,
) -> None:
    """
    Tests that the flush method handles an empty processor list gracefully.

    This test verifies that when the DelegatingResultProcessor has no child
    processors, the flush method returns without error.
    """
    # Arrange
    # The delegating_processor_with_no_processors is already set up in the fixture

    # Act & Assert
    # This should not raise an exception
    await delegating_processor_with_no_processors.flush()


@pytest.mark.asyncio
async def test_flush_should_handle_processor_exception(
    delegating_processor: DelegatingResultProcessor, mock_processor: AsyncMock
) -> None:
    """
    Tests that the flush method handles exceptions from processors gracefully.

    This test verifies that when a child processor raises an exception during
    flushing, the DelegatingResultProcessor catches the exception and continues.
    """
    # Arrange
    mock_processor.flush.side_effect = Exception("Processor error")

    # Patch the logger to verify it's called
    with patch("website_monitor.processor.delegating_processor.logger") as mock_logger:
        # Act
        await delegating_processor.flush()

        # Assert
        mock_processor.flush.assert_awaited_once()
        mock_logger.exception.assert_called_once()


@pytest.mark.asyncio
async def test_process_should_use_gather_for_concurrency(
    delegating_processor_with_multiple_processors: DelegatingResultProcessor,
    sample_result: FetchResult,
) -> None:
    """
    Tests that the process method uses asyncio.gather for concurrency.

    This test verifies that the DelegatingResultProcessor uses asyncio.gather
    to run all child processors concurrently.
    """
    # Arrange
    # Patch asyncio.gather to verify it's called with the correct tasks
    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
        # Act
        await delegating_processor_with_multiple_processors.process(sample_result)

        # Assert
        mock_gather.assert_called_once()
        # Verify that gather was called with the correct number of tasks
        assert len(mock_gather.call_args[0]) == len(
            delegating_processor_with_multiple_processors._processors
        )


@pytest.mark.asyncio
async def test_flush_should_use_gather_for_concurrency(
    delegating_processor_with_multiple_processors: DelegatingResultProcessor,
) -> None:
    """
    Tests that the flush method uses asyncio.gather for concurrency.

    This test verifies that the DelegatingResultProcessor uses asyncio.gather
    to flush all child processors concurrently.
    """
    # Arrange
    # Patch asyncio.gather to verify it's called with the correct tasks
    with patch("asyncio.gather", new_callable=AsyncMock) as mock_gather:
        # Act
        await delegating_processor_with_multiple_processors.flush()

        # Assert
        mock_gather.assert_called_once()
        # Verify that gather was called with the correct number of tasks
        assert len(mock_gather.call_args[0]) == len(
            delegating_processor_with_multiple_processors._processors
        )
