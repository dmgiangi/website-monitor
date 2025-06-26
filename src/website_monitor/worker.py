"""
Core worker implementation for the website monitoring system.

This module provides the MonitoringWorker class, which orchestrates the entire
monitoring process by coordinating the scheduler, fetcher, and processor components.
It implements a producer-consumer pattern with a queue for backpressure control.
"""

import asyncio
import logging
from asyncio import Queue, Task
from typing import List

from .contracts import ResultProcessor, TargetFetcher, WorkScheduler
from .domain import Target


class MonitoringWorker:
    """
    Coordinates the monitoring workflow using a producer-consumer pattern.

    This class manages a pool of worker tasks that consume monitoring targets
    from a queue. The targets are produced by a scheduler and processed by
    a fetcher and result processor.
    """

    def __init__(
        self,
        worker_id: str,
        scheduler: WorkScheduler,
        fetcher: TargetFetcher,
        processor: ResultProcessor,
        num_workers: int,
        queue_size: int,
        queue_size_monitoring_interval: int = 20,
    ) -> None:
        """
        Initializes a new MonitoringWorker instance.

        Args:
            worker_id: A unique identifier for this worker instance.
            scheduler: Component that provides targets to monitor.
            fetcher: Component that performs HTTP checks on targets.
            processor: Component that processes the results of checks.
            num_workers: Number of concurrent worker tasks to create.
            queue_size: Maximum size of the work queue before backpressure is applied.
        """
        self._worker_id: str = worker_id
        self._scheduler: WorkScheduler = scheduler
        self._fetcher: TargetFetcher = fetcher
        self._processor: ResultProcessor = processor
        self._num_workers: int = num_workers
        self._logger: logging.Logger = logging.getLogger(__name__)
        self._queue_size = queue_size
        # The queue provides backpressure. The producer will pause if the queue is full.
        self._queue: Queue[Target] = Queue(maxsize=queue_size)
        self._queue_size_monitoring_interval: int = queue_size_monitoring_interval
        self._worker_tasks: List[Task] = []
        self._monitor_task: Task = asyncio.create_task(self._monitor_queue())

    async def _executor(self, worker_num: int) -> None:
        """
        Consumer task that processes targets from the queue.

        This method runs in a loop, taking targets from the queue and processing
        them using the fetcher and processor components.

        Args:
            worker_num: The identifier number of this worker task.

        Returns:
            None
        """
        worker_logger: logging.Logger = logging.getLogger(f"executor-{worker_num}")

        while True:
            try:
                # 1. Wait for an item from the queue
                target: Target = await self._queue.get()

                # 2. Process the item
                try:
                    result = await self._fetcher.fetch(target)
                    await self._processor.process(result)
                except Exception as e:
                    worker_logger.exception(
                        f"Pipeline failed for target {target.id} with error: {e}"
                    )

                # 3. Notify the queue that the item is done
                self._queue.task_done()

            except asyncio.CancelledError:
                worker_logger.info("Stopping.")
                break

    async def _monitor_queue(self) -> None:
        """
        A task that monitors the queue size and logs it periodically.

        This method runs in the background and logs the current queue size
        every x seconds to help with monitoring system performance.

        Returns:
            None
        """
        monitor_logger: logging.Logger = logging.getLogger(f"{self._worker_id}-QueueMonitor")

        while True:
            try:
                # Wait x seconds before logging again
                await asyncio.sleep(self._queue_size_monitoring_interval)
                qsize = self._queue.qsize()
                # Check if the queue has a defined maximum size
                if self._queue.maxsize > 0:
                    # Calculate the 90% threshold
                    ninety_percent_capacity = self._queue.maxsize * 0.9
                    if qsize > ninety_percent_capacity:
                        monitor_logger.warning(
                            f"Queue size ({qsize}) is above 90% of capacity ({self._queue.maxsize})"
                        )
                    else:
                        monitor_logger.info(f"Current queue size: {qsize}")
                else:
                    # For a queue with no maxsize limit, just log the size
                    monitor_logger.info(f"Current queue size: {qsize}")
            except asyncio.CancelledError:
                monitor_logger.info("Shutting down.")
                break

    async def start(self) -> None:
        """
        Starts the producer and all the worker (consumer) tasks.

        This method initializes the worker tasks and begins the main loop
        that retrieves targets from the scheduler and adds them to the queue.

        Returns:
            None

        Raises:
            Exception: If the producer loop fails for any reason.
        """
        self._logger.info(f"Starting monitoring worker with {self._num_workers} workers.")

        # 1. Start all the consumer workers in the background
        self._worker_tasks = [
            asyncio.create_task(self._executor(i + 1)) for i in range(self._num_workers)
        ]

        # 2. Start the producer loop
        try:
            await self._scheduler.start()

            async for batch in self._scheduler:
                if not batch:
                    continue

                self._logger.debug(f"Producer adding {len(batch)} targets to the queue.")
                # Targets are inserted into the queue
                for target in batch:
                    await self._queue.put(target)

        except Exception as e:
            self._logger.error(f"Producer loop failed: {e}")
            raise

    async def stop(self) -> None:
        """
        Gracefully stops all worker tasks.

        This method implements a clean shutdown sequence:
        1. Stop the scheduler to prevent new work from being added
        2. Wait for all queued tasks to complete
        3. Cancel all background worker tasks
        4. Wait for all tasks to acknowledge cancellation

        Returns:
            None
        """
        self._logger.info("Initiating graceful shutdown...")

        # 1. Scheduler is notified to not produce jobs anymore
        self._logger.info("Stopping scheduler...")
        await self._scheduler.stop()

        # 2. Waiting to complete all the pending tasks
        self._logger.info(f"Waiting for {self._queue.qsize()} pending tasks to complete...")
        await self._queue.join()
        self._logger.info("All pending tasks completed")

        # 3. Aggregate all pending tasks
        all_background_tasks = self._worker_tasks + [self._monitor_task]
        self._logger.info(f"Cancelling {len(all_background_tasks)} background tasks...")

        # 4. Now that the queue is empty, cancel all the worker tasks.
        for task in all_background_tasks:
            task.cancel()

        # 5. Wait for all worker tasks to acknowledge their cancellation and exit.
        await asyncio.gather(*all_background_tasks, return_exceptions=True)

        self._logger.info("Flushing results processor...")
        await self._processor.flush()

        self._logger.info("Worker shutdown complete")
