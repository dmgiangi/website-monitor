import asyncio
import logging
from datetime import timedelta
from typing import Awaitable, Callable, Generator, List
from unittest.mock import AsyncMock, patch

import pytest

from website_monitor.contracts import (
    ResultProcessor,
    TargetFetcher,
    WorkScheduler,
)
from website_monitor.domain import FetchResult, HttpMethod, Target
from website_monitor.worker import MonitoringWorker

# A type alias for clarity in the factory fixture.
WorkerFactory = Callable[..., Awaitable[MonitoringWorker]]


@pytest.fixture
def target() -> Target:
    """Provides a sample Target object for tests."""
    return Target(
        id=1,
        url="https://example.com",
        method=HttpMethod.GET,
        check_interval=timedelta(seconds=60),
        regex_pattern=None,
        default_headers=None,
    )


@pytest.fixture
def fetch_result(target: Target) -> FetchResult:
    """Provides a sample successful FetchResult object."""
    return FetchResult(
        target=target,
        error=None,
        start_time=1000.0,
        end_time=1001.0,
        status_code=200,
        regex_has_matches=None,
    )


@pytest.fixture
def mock_scheduler() -> AsyncMock:
    """Provides a mock for the WorkScheduler."""
    return AsyncMock(spec=WorkScheduler)


@pytest.fixture
def mock_fetcher() -> AsyncMock:
    """Provides a mock for the TargetFetcher."""
    # This setup ensures mock.fetch is also an async mock, which is good practice.
    mock = AsyncMock(spec=TargetFetcher)
    mock.fetch = AsyncMock()
    return mock


@pytest.fixture
def mock_processor() -> AsyncMock:
    """Provides a mock for the ResultProcessor."""
    return AsyncMock(spec=ResultProcessor)


@pytest.fixture
def worker_factory(
    _function_event_loop: asyncio.AbstractEventLoop,
    mock_scheduler: AsyncMock,
    mock_fetcher: AsyncMock,
    mock_processor: AsyncMock,
) -> Generator[WorkerFactory, None, None]:
    """
    Provides a factory to create managed MonitoringWorker instances.
    This ensures each test gets a fresh worker that is properly shut down.
    """
    created_workers: List[MonitoringWorker] = []

    async def _factory(num_workers: int = 1) -> MonitoringWorker:
        """Creates, tracks, and returns a new worker instance."""
        worker_instance = MonitoringWorker(
            worker_id="test-worker",
            scheduler=mock_scheduler,
            fetcher=mock_fetcher,
            processor=mock_processor,
            num_workers=num_workers,
            queue_size=10,
            queue_size_monitoring_interval=2,
        )
        created_workers.append(worker_instance)
        return worker_instance

    yield _factory

    # TEARDOWN: This runs after each test to clean up resources.
    if created_workers:

        async def stop_all() -> None:
            """Stops all worker instances created by the factory."""
            await asyncio.gather(*(worker.stop() for worker in created_workers))

        _function_event_loop.run_until_complete(stop_all())


@pytest.mark.asyncio
async def test_executor_processes_target_from_queue(
    worker_factory: WorkerFactory,
    mock_fetcher: AsyncMock,
    mock_processor: AsyncMock,
    target: Target,
    fetch_result: FetchResult,
) -> None:
    """
    Tests that a running executor task correctly processes a target
    placed on the queue. This isolates the consumer logic.
    """
    # --- ARRANGE ---
    worker = await worker_factory(num_workers=1)
    mock_fetcher.fetch.return_value = fetch_result

    # Manually start the worker tasks without starting the producer loop.
    worker._worker_tasks = [
        asyncio.create_task(worker._executor(i + 1)) for i in range(worker._num_workers)
    ]

    # --- ACT ---
    # Manually put a target on the queue for the consumer to process.
    await worker._queue.put(target)

    # Wait for the consumer to finish processing the item.
    await worker._queue.join()

    # --- ASSERT ---
    # Verify the consumer (_executor task) processed the item as expected.
    mock_fetcher.fetch.assert_awaited_once_with(target)
    mock_processor.process.assert_awaited_once_with(fetch_result)


@pytest.mark.asyncio
async def test_executor_handles_fetch_failure_gracefully(
    worker_factory: WorkerFactory,
    mock_fetcher: AsyncMock,
    mock_processor: AsyncMock,
    target: Target,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Tests that if the fetcher raises an exception, the executor task
    catches it, logs the error, and does not call the processor.
    """
    # --- ARRANGE ---
    worker = await worker_factory(num_workers=1)
    fetch_error = ConnectionError("Failed to connect")
    mock_fetcher.fetch.side_effect = fetch_error

    # Manually start the consumer tasks.
    worker._worker_tasks = [
        asyncio.create_task(worker._executor(i + 1)) for i in range(worker._num_workers)
    ]

    # --- ACT ---
    with caplog.at_level(logging.ERROR):
        await worker._queue.put(target)
        await worker._queue.join()

    # --- ASSERT ---
    mock_fetcher.fetch.assert_awaited_once_with(target)
    mock_processor.process.assert_not_called()
    assert "Pipeline failed" in caplog.text
    assert f"target {target.id}" in caplog.text
    assert str(fetch_error) in caplog.text


@pytest.mark.asyncio
async def test_stop_performs_graceful_shutdown_sequence(
    worker_factory: WorkerFactory,
    mock_scheduler: AsyncMock,
    mock_processor: AsyncMock,
) -> None:
    """
    Tests that the stop() method executes the graceful shutdown
    sequence in the correct order.
    """
    # --- ARRANGE ---
    worker = await worker_factory()
    # Spy on the queue's join method to assert it was awaited.
    with patch.object(worker._queue, "join", new_callable=AsyncMock) as mock_queue_join:
        # --- ACT ---
        await worker.stop()

        # --- ASSERT ---
        mock_scheduler.stop.assert_awaited_once()
        mock_queue_join.assert_awaited_once()
        mock_processor.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_handles_empty_batches_from_scheduler(
    worker_factory: WorkerFactory, mock_scheduler: AsyncMock
) -> None:
    """
    Tests that the worker's producer loop correctly handles empty lists
    yielded by the scheduler without error and continues processing.
    """
    # --- ARRANGE ---
    worker = await worker_factory()
    # Configure the scheduler to yield an empty batch, then stop.
    mock_scheduler.__anext__.side_effect = [[], StopAsyncIteration]

    # --- ACT ---
    await worker.start()
    await worker._queue.join()

    # --- ASSERT ---
    # The queue should be empty because nothing was added.
    assert worker._queue.qsize() == 0
