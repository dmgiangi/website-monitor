"""
Core interfaces for the website monitoring system.

This module defines the abstract base classes that form the foundation of the
monitoring system's architecture. These interfaces establish a clear contract
for implementations and enable a modular, pluggable design.
"""

import abc
from typing import AsyncIterator, List

from .domain import FetchResult, Target


class WorkScheduler(abc.ABC):
    """
    Abstract interface for a work scheduler.

    Its responsibility is to provide an asynchronous stream of 'Target' objects
    that need to be processed. The implementation can be based on a database,
    a message queue, or any other source.
    """

    @abc.abstractmethod
    async def start(self) -> None:
        """
        Prepares the scheduler to start yielding work.

        This method should be called before using the scheduler in an async for loop.
        It may establish connections, initialize resources, or perform other setup tasks.

        Returns:
            None
        """
        pass

    @abc.abstractmethod
    async def stop(self) -> None:
        """
        Gracefully stops the scheduler and releases any acquired resources.

        This method should be called when the scheduler is no longer needed.
        It should clean up any resources and ensure a graceful shutdown.

        Returns:
            None
        """
        pass

    def __aiter__(self) -> AsyncIterator[List[Target]]:
        """
        Allows the scheduler to be used in an 'async for' loop.

        This method implements the AsyncIterator protocol, making the scheduler
        directly usable in async for loops.

        Returns:
            AsyncIterator[List[Target]]: The scheduler instance itself.
        """
        return self

    @abc.abstractmethod
    async def __anext__(self) -> List[Target]:
        """
        Waits for and returns the next batch of work.

        This method should block efficiently until work is available and should
        raise StopAsyncIteration when the scheduler is gracefully closed.

        Returns:
            List[Target]: A list of Target objects to be processed.

        Raises:
            StopAsyncIteration: When the scheduler has been stopped.
        """
        raise StopAsyncIteration


class TargetFetcher(abc.ABC):
    """
    Abstract interface for a component that performs the check for a single target.

    Its responsibility is to encapsulate the network I/O for a given Target
    and return a structured result.
    """

    @abc.abstractmethod
    async def fetch(self, target: Target) -> FetchResult:
        """
        Performs an HTTP check on the given target.

        This method is responsible for making the actual HTTP request to the target,
        measuring performance metrics, and packaging the results into a structured format.

        Args:
            target: The Target object to check, containing URL, method, and other configuration.

        Returns:
            FetchResult: An object containing the outcome of the check, including status code,
                timing information, and any errors encountered.

        Raises:
            Exception: Implementations should handle network errors internally and include
                them in the FetchResult rather than raising them.
        """
        pass


class ResultProcessor(abc.ABC):
    """
    Abstract interface for a component that processes a fetch result.

    This enables a pipeline pattern where multiple processors can act on the
    outcome of a check to perform tasks like persisting data, updating metrics,
    or sending notifications.
    """

    @abc.abstractmethod
    async def process(self, result: FetchResult) -> None:
        """
        Processes or buffers a single FetchResult object.

        This method is called for each result produced by a TargetFetcher.
        Implementations might store the result in a database, update metrics,
        trigger alerts, or perform other actions based on the result.

        Args:
            result: The result of a target fetch operation to be processed,
                containing all information about the check outcome.

        Returns:
            None
        """
        pass

    @abc.abstractmethod
    async def flush(self) -> None:
        """
        Forces the persistence of any buffered results.

        This method is intended to be called periodically or during a graceful
        shutdown to ensure that all processed data is saved. For processors
        that do not buffer data, this method can be a no-op.

        Returns:
            None
        """
        pass
