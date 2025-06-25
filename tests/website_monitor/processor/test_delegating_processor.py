"""
Unit tests for the DelegatingResultProcessor class.

This module contains comprehensive tests for the DelegatingResultProcessor class,
ensuring that it correctly delegates processing to multiple child processors
concurrently and handles failures gracefully.

The tests follow the Arrange-Act-Assert (AAA) pattern and use proper mocking
of all external dependencies to ensure true unit testing.
"""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from website_monitor.contracts import ResultProcessor
from website_monitor.domain import FetchResult, HttpMethod, Target
from website_monitor.processor.delegating_processor import DelegatingResultProcessor


# Configure pytest-asyncio to use function scope for event loops
@pytest_asyncio.fixture(scope="function")
def event_loop():
    """
    Creates an event loop for each test function.

    This is needed because the DelegatingResultProcessor creates tasks that need to be
    properly cleaned up after each test.
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
async def mock_processor():
    """
    Creates a mock ResultProcessor for testing.

    Returns:
        A mock ResultProcessor with configured async methods.
    """
    return AsyncMock(spec=ResultProcessor)


@pytest_asyncio.fixture
async def sample_target():
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
        regex_pattern=None,
        default_headers=None,
    )


@pytest_asyncio.fixture
async def sample_fetch_result(sample_target):
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
        total_time=0.5,
        status_code=200,
        request_trace=None,
        regex_has_matches=None,
    )


@pytest_asyncio.fixture
async def delegating_processor(mock_processor):
    """
    Creates a DelegatingResultProcessor instance with mock dependencies.

    Args:
        mock_processor: A fixture providing a mock ResultProcessor.

    Returns:
        A DelegatingResultProcessor instance configured with mock dependencies.
    """
    return DelegatingResultProcessor(
        worker_id="test-worker", processors=[mock_processor, AsyncMock(spec=ResultProcessor)]
    )


@pytest.mark.asyncio
async def test_process_should_delegate_to_all_processors(
    delegating_processor, mock_processor, sample_fetch_result
):
    """
    Tests that the process method delegates to all child processors.
    """
    # Arrange
    # The delegating_processor fixture provides a processor with two mock child processors

    # Act
    await delegating_processor.process(sample_fetch_result)

    # Assert
    # Verify that each processor was called with the fetch result
    for processor in delegating_processor._processors:
        processor.process.assert_awaited_once_with(sample_fetch_result)


@pytest.mark.asyncio
async def test_process_should_do_nothing_with_empty_processor_list(sample_fetch_result):
    """
    Tests that the process method does nothing when the processor list is empty.
    """
    # Arrange
    processor = DelegatingResultProcessor(worker_id="test-worker", processors=[])

    # Act
    await processor.process(sample_fetch_result)

    # Assert
    # No assertions needed - the test passes if no exception is raised


@pytest.mark.asyncio
async def test_process_should_handle_processor_exception(sample_fetch_result):
    """
    Tests that the process method handles exceptions from child processors.
    """
    # Arrange
    failing_processor = AsyncMock(spec=ResultProcessor)
    failing_processor.process.side_effect = ValueError("Test error")

    successful_processor = AsyncMock(spec=ResultProcessor)

    processor = DelegatingResultProcessor(
        worker_id="test-worker", processors=[failing_processor, successful_processor]
    )

    # Act
    await processor.process(sample_fetch_result)

    # Assert
    # Verify that both processors were called, even though one failed
    failing_processor.process.assert_awaited_once_with(sample_fetch_result)
    successful_processor.process.assert_awaited_once_with(sample_fetch_result)


@pytest.mark.asyncio
async def test_process_should_execute_processors_concurrently(sample_fetch_result):
    """
    Tests that the process method executes child processors concurrently.
    """

    # Arrange
    # Create processors that take different amounts of time to complete
    async def slow_process(result):
        await asyncio.sleep(0.1)
        return None

    async def fast_process(result):
        return None

    slow_processor = AsyncMock(spec=ResultProcessor)
    slow_processor.process.side_effect = slow_process

    fast_processor = AsyncMock(spec=ResultProcessor)
    fast_processor.process.side_effect = fast_process

    processor = DelegatingResultProcessor(
        worker_id="test-worker", processors=[slow_processor, fast_processor]
    )

    # Act
    # Patch asyncio.gather to verify it's called with the expected tasks
    with patch("asyncio.gather") as mock_gather:
        mock_gather.return_value = None
        await processor.process(sample_fetch_result)

    # Assert
    # Verify that asyncio.gather was called, indicating concurrent execution
    mock_gather.assert_called_once()
    # Verify that both processors were called
    slow_processor.process.assert_awaited_once_with(sample_fetch_result)
    fast_processor.process.assert_awaited_once_with(sample_fetch_result)


@pytest.mark.asyncio
async def test_process_with_one_should_catch_and_log_exceptions(sample_fetch_result):
    """
    Tests that the _process_with_one method catches and logs exceptions.
    """
    # Arrange
    failing_processor = AsyncMock(spec=ResultProcessor)
    failing_processor.process.side_effect = ValueError("Test error")

    processor = DelegatingResultProcessor(worker_id="test-worker", processors=[failing_processor])

    # Act
    # Patch the logger to verify it's called
    with patch("logging.getLogger") as mock_get_logger:
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        # Call _process_with_one directly to test exception handling
        await processor._process_with_one(failing_processor, sample_fetch_result)

    # Assert
    # Verify that the exception was caught and logged
    failing_processor.process.assert_awaited_once_with(sample_fetch_result)
    mock_logger.exception.assert_called_once()
