# monitoring_service/processors.py

import asyncio
from typing import List

# Assuming contracts and domain are in the same package
from website_monitor.contracts import ResultProcessor
from website_monitor.domain import FetchResult


class DelegatingResultProcessor(ResultProcessor):
    """
    A concrete implementation of ResultProcessor that follows the Composite pattern.

    It holds a list of other ResultProcessor instances and delegates the 'process'
    call to each of them concurrently. This simplifies the worker logic by
    exposing a single entry point for a complex processing pipeline.
    """

    def __init__(self, processors: List[ResultProcessor]):
        """
        Initializes the delegator with a list of processors to delegate to.

        Args:
            processors: A list of objects that adhere to the ResultProcessor interface.
        """
        self._processors = processors

    async def _process_with_one(self, processor: ResultProcessor, result: FetchResult) -> None:
        """
        NEW: A helper method to safely run a single processor.

        It wraps the individual process call in a try...except block, ensuring
        that one processor's failure does not affect any others.
        """
        try:
            await processor.process(result)
        except Exception:
            print(f"Processor '{type(processor).__name__}' failed for target ")

    async def process(self, result: FetchResult) -> None:
        """
        Processes a single FetchResult by delegating to all child processors.

        All processors are executed concurrently using asyncio.gather.
        This implementation is robust: if one processor fails, the others
        are still executed.
        """
        if not self._processors:
            return

        tasks = [self._process_with_one(processor, result) for processor in self._processors]

        await asyncio.gather(*tasks)
