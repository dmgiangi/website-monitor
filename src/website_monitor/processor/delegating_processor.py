"""
Delegating result processor implementation.

This module provides a composite implementation of the ResultProcessor interface
that delegates processing to multiple child processors concurrently. It ensures
that failures in one processor don't affect the others.
"""

import asyncio
import logging
from typing import List

from website_monitor.contracts import ResultProcessor
from website_monitor.domain import FetchResult

# Module logger
logger = logging.getLogger(__name__)


class DelegatingResultProcessor(ResultProcessor):
    """
    A concrete implementation of ResultProcessor that follows the Composite pattern.

    This class holds a list of other ResultProcessor instances and delegates the 'process'
    and 'flush' calls to each of them concurrently. This simplifies the worker logic by
    exposing a single entry point for a complex processing pipeline.

    The implementation is fault-tolerant: if one processor fails, the others
    will still be executed, ensuring maximum resilience in the processing pipeline.
    """

    def __init__(self, worker_id: str, processors: List[ResultProcessor]) -> None:
        """
        Initializes the delegator with a list of processors to delegate to.

        Args:
            worker_id: A unique identifier for this worker instance.
            processors: A list of objects that adhere to the ResultProcessor interface.
                These will be called concurrently when processing a result.
        """
        self._worker_id: str = worker_id
        self._processors: List[ResultProcessor] = processors

    async def _process_with_one(self, processor: ResultProcessor, result: FetchResult) -> None:
        """
        A helper method to safely run a single processor's 'process' method.

        It wraps the individual process call in a try-except block, ensuring
        that one processor's failure does not affect any others. All exceptions
        are caught and logged, but not propagated.

        Args:
            processor: The individual processor to run.
            result: The fetch result to be processed.
        """
        try:
            await processor.process(result)
        except Exception:
            logger.exception(
                f"Processor '{type(processor).__name__}' failed during process() for target {result.target.url}",
            )

    async def _flush_one(self, processor: ResultProcessor) -> None:
        """
        A helper method to safely run a single processor's 'flush' method.

        It wraps the individual flush call in a try-except block, ensuring
        that one processor's failure does not affect any others.

        Args:
            processor: The individual processor to flush.
        """
        try:
            await processor.flush()
        except Exception:
            logger.exception(
                f"Processor '{type(processor).__name__}' failed during flush()",
            )

    async def process(self, result: FetchResult) -> None:
        """
        Processes a single FetchResult by delegating to all child processors.

        This method creates a task for each child processor and executes them
        concurrently using asyncio.gather. If there are no processors configured,
        it returns immediately without doing anything.

        Args:
            result: The fetch result to be processed by all child processors.
        """
        if not self._processors:
            return

        # Create a task for each processor to run concurrently
        tasks = [self._process_with_one(processor, result) for processor in self._processors]

        # Wait for all processors to complete
        await asyncio.gather(*tasks)

    async def flush(self) -> None:
        """
        Flushes all child processors concurrently.

        This method creates a task to flush each child processor and executes them
        concurrently using asyncio.gather. This is intended to be called during
        a graceful shutdown to ensure all buffered data is persisted.
        """
        if not self._processors:
            return

        logger.info(f"Flushing all {len(self._processors)} result processors...")
        tasks = [self._flush_one(p) for p in self._processors]
        await asyncio.gather(*tasks)
        logger.info("All result processors flushed.")
