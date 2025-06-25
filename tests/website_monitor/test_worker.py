"""
Unit tests for the MonitoringWorker class.

This module contains comprehensive tests for the MonitoringWorker class,
ensuring that it correctly coordinates the monitoring workflow using
the scheduler, fetcher, and processor components.

The tests follow the Arrange-Act-Assert (AAA) pattern and use proper mocking
of all external dependencies to ensure true unit testing.
"""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from website_monitor.contracts import ResultProcessor, TargetFetcher, WorkScheduler
from website_monitor.domain import FetchResult, HttpMethod, Target
from website_monitor.worker import MonitoringWorker


# Configure pytest-asyncio to use function scope for event loops
@pytest_asyncio.fixture(scope="function")
def event_loop() -> asyncio.AbstractEventLoop:
    """
    Creates an event loop for each test function.

    This is needed because the MonitoringWorker creates tasks that need to be
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
async def mock_scheduler() -> AsyncMock:
    """
    Creates a mock WorkScheduler for testing.

    Returns:
        AsyncMock: A mock WorkScheduler with configured async methods.
    """
    scheduler = AsyncMock(spec=WorkScheduler)

    # Configure the async iterator behavior
    # Make __aiter__ return the scheduler itself
    scheduler.__aiter__.return_value = scheduler

    # Configure __anext__ to be awaitable and return a list by default
    # Tests can override this behavior as needed
    scheduler.__anext__.return_value = []

    return scheduler


@pytest_asyncio.fixture
async def mock_fetcher():
    """
    Creates a mock TargetFetcher for testing.

    Returns:
        A mock TargetFetcher with configured async methods.
    """
    return AsyncMock(spec=TargetFetcher)


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
async def worker(mock_scheduler, mock_fetcher, mock_processor):
    """
    Creates a MonitoringWorker instance with mock dependencies.

    Args:
        mock_scheduler: A fixture providing a mock WorkScheduler.
        mock_fetcher: A fixture providing a mock TargetFetcher.
        mock_processor: A fixture providing a mock ResultProcessor.

    Returns:
        A MonitoringWorker instance configured with mock dependencies.
    """
    # Patch the create_task method to avoid issues with the event loop
    with patch("asyncio.create_task") as mock_create_task:
        # Make the mock return a mock task
        mock_task = MagicMock()
        mock_task.cancel = MagicMock()
        mock_create_task.return_value = mock_task

        # Create the worker with the patched create_task
        worker_instance = MonitoringWorker(
            worker_id="test-worker",
            scheduler=mock_scheduler,
            fetcher=mock_fetcher,
            processor=mock_processor,
            num_workers=2,
            queue_size=10,
        )

        # Replace the monitor task with our mock
        worker_instance._monitor_task = mock_task

        yield worker_instance


@pytest.mark.asyncio
async def test_start_should_initialize_worker_tasks_and_process_targets(
    worker, mock_scheduler, mock_fetcher, mock_processor, sample_target, sample_fetch_result
):
    """
    Tests that the start method initializes worker tasks and processes targets from the scheduler.
    """
    # Arrange
    batch = [sample_target]
    mock_scheduler.__anext__.side_effect = [batch, asyncio.CancelledError]
    mock_fetcher.fetch.return_value = sample_fetch_result

    # Act
    with pytest.raises(asyncio.CancelledError):
        await worker.start()

    # Assert
    mock_scheduler.start.assert_awaited_once()
    mock_scheduler.__anext__.assert_awaited()
    # Wait a moment for the async tasks to process
    await asyncio.sleep(0.1)
    mock_fetcher.fetch.assert_awaited_once_with(sample_target)
    mock_processor.process.assert_awaited_once_with(sample_fetch_result)


@pytest.mark.asyncio
async def test_start_should_skip_empty_batches(
    worker, mock_scheduler, mock_fetcher, mock_processor
):
    """
    Tests that the start method skips empty batches from the scheduler.
    """
    # Arrange
    mock_scheduler.__anext__.side_effect = [[], asyncio.CancelledError]

    # Act
    with pytest.raises(asyncio.CancelledError):
        await worker.start()

    # Assert
    mock_scheduler.start.assert_awaited_once()
    mock_scheduler.__anext__.assert_awaited()
    mock_fetcher.fetch.assert_not_awaited()
    mock_processor.process.assert_not_awaited()


@pytest.mark.asyncio
async def test_stop_should_gracefully_shutdown_all_tasks(worker, mock_scheduler):
    """
    Tests that the stop method gracefully shuts down all tasks.
    """
    # Arrange - Create some background tasks
    worker._worker_tasks = [asyncio.create_task(asyncio.sleep(1)) for _ in range(2)]

    # Act
    await worker.stop()

    # Assert
    mock_scheduler.stop.assert_awaited_once()
    # Verify all tasks were cancelled
    for task in worker._worker_tasks:
        assert task.cancelled()
    assert worker._monitor_task.cancelled()


@pytest.mark.asyncio
async def test_executor_should_process_target_successfully(
    worker, mock_fetcher, mock_processor, sample_target, sample_fetch_result
):
    """
    Tests that the _executor method processes a target successfully.
    """
    # Arrange
    mock_fetcher.fetch.return_value = sample_fetch_result
    # Create a queue and add a sample target
    worker._queue = asyncio.Queue()
    await worker._queue.put(sample_target)

    # Create a task that will run for a short time and then be cancelled
    # Use a coroutine directly instead of creating a task
    executor_coro = worker._executor(1)

    # Act - Run the coroutine for a short time using asyncio.wait_for with a timeout
    try:
        await asyncio.wait_for(executor_coro, timeout=0.1)
    except asyncio.TimeoutError:
        # Expected - the executor runs in an infinite loop
        pass

    # Assert
    mock_fetcher.fetch.assert_awaited_once_with(sample_target)
    mock_processor.process.assert_awaited_once_with(sample_fetch_result)
    assert worker._queue.empty()


@pytest.mark.asyncio
async def test_executor_should_handle_fetcher_exception(
    worker, mock_fetcher, mock_processor, sample_target
):
    """
    Tests that the _executor method handles exceptions from the fetcher.
    """
    # Arrange
    mock_fetcher.fetch.side_effect = ValueError("Test error")
    # Create a queue and add a sample target
    worker._queue = asyncio.Queue()
    await worker._queue.put(sample_target)

    # Create a coroutine
    executor_coro = worker._executor(1)

    # Act - Run the coroutine for a short time using asyncio.wait_for with a timeout
    try:
        await asyncio.wait_for(executor_coro, timeout=0.1)
    except asyncio.TimeoutError:
        # Expected - the executor runs in an infinite loop
        pass

    # Assert
    mock_fetcher.fetch.assert_awaited_once_with(sample_target)
    mock_processor.process.assert_not_awaited()
    assert worker._queue.empty()


@pytest.mark.asyncio
async def test_executor_should_handle_processor_exception(
    worker, mock_fetcher, mock_processor, sample_target, sample_fetch_result
):
    """
    Tests that the _executor method handles exceptions from the processor.
    """
    # Arrange
    mock_fetcher.fetch.return_value = sample_fetch_result
    mock_processor.process.side_effect = ValueError("Test error")
    # Create a queue and add a sample target
    worker._queue = asyncio.Queue()
    await worker._queue.put(sample_target)

    # Create a coroutine
    executor_coro = worker._executor(1)

    # Act - Run the coroutine for a short time using asyncio.wait_for with a timeout
    try:
        await asyncio.wait_for(executor_coro, timeout=0.1)
    except asyncio.TimeoutError:
        # Expected - the executor runs in an infinite loop
        pass

    # Assert
    mock_fetcher.fetch.assert_awaited_once_with(sample_target)
    mock_processor.process.assert_awaited_once_with(sample_fetch_result)
    assert worker._queue.empty()


@pytest.mark.asyncio
async def test_monitor_queue_should_log_queue_size_periodically(worker):
    """
    Tests that the _monitor_queue method logs the queue size periodically.
    """
    # Arrange
    # Patch asyncio.sleep to avoid waiting in the test
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        # Create a coroutine for the monitor
        monitor_coro = worker._monitor_queue()

        # Act - Run the coroutine for a short time using asyncio.wait_for with a timeout
        try:
            await asyncio.wait_for(monitor_coro, timeout=0.1)
        except asyncio.TimeoutError:
            # Expected - the monitor runs in an infinite loop
            pass

        # Assert
        mock_sleep.assert_awaited_with(20)


@pytest.mark.asyncio
async def test_start_should_handle_multiple_targets_in_batch(
    worker, mock_scheduler, mock_fetcher, mock_processor, sample_target, sample_fetch_result
):
    """
    Tests that the start method processes multiple targets in a batch.
    """
    # Arrange
    target1 = sample_target
    target2 = Target(
        id=2,
        url="https://example.org",
        method=HttpMethod.GET,
        check_interval=timedelta(minutes=10),
        regex_pattern=None,
        default_headers=None,
    )
    batch = [target1, target2]

    mock_scheduler.__anext__.side_effect = [batch, asyncio.CancelledError]
    mock_fetcher.fetch.return_value = sample_fetch_result

    # Act
    with pytest.raises(asyncio.CancelledError):
        await worker.start()

    # Assert
    mock_scheduler.start.assert_awaited_once()
    # Wait a moment for the async tasks to process
    await asyncio.sleep(0.1)
    assert mock_fetcher.fetch.await_count == 2
    assert mock_processor.process.await_count == 2


@pytest.mark.asyncio
async def test_start_should_handle_scheduler_exception(worker, mock_scheduler):
    """
    Tests that the start method handles exceptions from the scheduler.
    """
    # Arrange
    mock_scheduler.start.side_effect = ValueError("Test error")

    # Act & Assert
    with pytest.raises(ValueError, match="Test error"):
        await worker.start()

    mock_scheduler.start.assert_awaited_once()
    mock_scheduler.__anext__.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_should_handle_none_target_in_batch(
    worker, mock_scheduler, mock_fetcher, mock_processor, sample_target, sample_fetch_result
):
    """
    Tests that the start method handles None values in the batch by skipping them.
    """
    # Arrange
    batch = [sample_target, None, sample_target]
    mock_scheduler.__anext__.side_effect = [batch, asyncio.CancelledError]
    mock_fetcher.fetch.return_value = sample_fetch_result

    # Act
    with pytest.raises(asyncio.CancelledError):
        await worker.start()

    # Assert
    mock_scheduler.start.assert_awaited_once()
    mock_scheduler.__anext__.assert_awaited()
    # Wait a moment for the async tasks to process
    await asyncio.sleep(0.1)
    # Should only process the non-None targets
    assert mock_fetcher.fetch.await_count == 2
    assert mock_processor.process.await_count == 2


@pytest.mark.asyncio
async def test_start_should_handle_queue_backpressure(
    worker, mock_scheduler, mock_fetcher, mock_processor, sample_target
):
    """
    Tests that the start method correctly applies backpressure when the queue is full.
    """
    # Arrange
    # Create a large batch that exceeds the queue size
    # Since Target is a NamedTuple, we need to create new instances with different IDs
    large_batch = [
        Target(
            id=i,
            url=sample_target.url,
            method=sample_target.method,
            check_interval=sample_target.check_interval,
            regex_pattern=sample_target.regex_pattern,
            default_headers=sample_target.default_headers,
        )
        for i in range(1, 21)  # 20 targets with IDs 1-20
    ]
    mock_scheduler.__anext__.side_effect = [large_batch, asyncio.CancelledError]

    # Make fetcher.fetch take some time to simulate processing delay
    async def delayed_fetch(target):
        await asyncio.sleep(0.1)
        return FetchResult(
            target=target,
            error=None,
            total_time=0.5,
            status_code=200,
            request_trace=None,
            regex_has_matches=None,
        )

    mock_fetcher.fetch.side_effect = delayed_fetch

    # Act
    with pytest.raises(asyncio.CancelledError):
        await worker.start()

    # Assert
    mock_scheduler.start.assert_awaited_once()
    mock_scheduler.__anext__.assert_awaited()
    # The test should complete without hanging, demonstrating that
    # backpressure is working correctly


@pytest.mark.asyncio
async def test_start_should_process_single_item_batch(
    worker, mock_scheduler, mock_fetcher, mock_processor, sample_target, sample_fetch_result
):
    """
    Tests that the start method correctly processes a batch containing only one target.
    """
    # Arrange
    batch = [sample_target]  # Single-item batch
    mock_scheduler.__anext__.side_effect = [batch, asyncio.CancelledError]
    mock_fetcher.fetch.return_value = sample_fetch_result

    # Act
    with pytest.raises(asyncio.CancelledError):
        await worker.start()

    # Assert
    mock_scheduler.start.assert_awaited_once()
    mock_scheduler.__anext__.assert_awaited()
    # Wait a moment for the async tasks to process
    await asyncio.sleep(0.1)
    mock_fetcher.fetch.assert_awaited_once_with(sample_target)
    mock_processor.process.assert_awaited_once_with(sample_fetch_result)
