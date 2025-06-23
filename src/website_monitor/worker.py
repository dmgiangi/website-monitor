# monitoring_service/worker.py

import asyncio
from typing import AsyncGenerator, List

from .contracts import ResultProcessor, Target, TargetFetcher, WorkScheduler
from .domain import FetchResult


class MonitoringWorker:
    """
    Orchestrates the monitoring pipeline by consuming a stream of results
    produced by an asynchronous generator.
    """

    def __init__(
        self,
        worker_id: str,
        scheduler: WorkScheduler,
        fetcher: TargetFetcher,
        processor: ResultProcessor,
    ):
        self.worker_id = worker_id
        self.scheduler = scheduler
        self.fetcher = fetcher
        self.processor = processor

    async def _fetch_results_as_stream(
        self, batch: List[Target]
    ) -> AsyncGenerator[FetchResult, None]:
        """
        An async generator that fetches targets concurrently and yields
        results as they are completed, creating a real-time stream.
        """
        # Create a task for each fetch operation
        fetch_tasks = [asyncio.create_task(self.fetcher.fetch(t)) for t in batch]

        # asyncio.as_completed returns an iterator that yields futures as they finish
        for future in asyncio.as_completed(fetch_tasks):
            try:
                # Wait for the next completed future and yield its result
                yield await future
            except Exception:
                # This is a good place to handle exceptions from the fetcher
                # async_logger.exception(f"A fetch task failed unexpectedly: {e}")
                pass

    async def _process_single_result(self, result: FetchResult) -> None:
        """
        Helper method to safely process a single result.

        This method wraps the processor call in a try...except block,
        isolating potential failures.
        """
        try:
            # The core processing logic is now safely wrapped
            await self.processor.process(result)
        except Exception:
            # If one processor fails, we log the error but do not crash the worker.
            # The other results in the batch can still be processed.
            pass

    async def run(self) -> None:
        """
        Starts the main, long-running monitoring loop.
        """
        try:
            await self.scheduler.start()

            async for batch in self.scheduler:
                if not batch:
                    continue

                # We will collect all processing tasks to run them concurrently.
                processing_tasks = [
                    asyncio.create_task(self._process_single_result(result))
                    async for result in self._fetch_results_as_stream(batch)
                ]

                if processing_tasks:
                    await asyncio.gather(*processing_tasks)

        finally:
            await self.scheduler.close()
