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
        """Prepares the scheduler to start yielding work."""
        pass

    @abc.abstractmethod
    async def close(self) -> None:
        """Gracefully stops the scheduler and releases any acquired resources."""
        pass

    def __aiter__(self) -> AsyncIterator[List[Target]]:
        """Allows the scheduler to be used in an 'async for' loop."""
        return self

    @abc.abstractmethod
    async def __anext__(self) -> List[Target]:
        """
        Waits for and returns the next batch of work.

        This method should block efficiently until work is available and should
        raise StopAsyncIteration when the scheduler is gracefully closed.
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

        Args:
            target: The Target object to check.

        Returns:
            A FetchResult object containing the outcome of the check.
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
        Processes a single FetchResult object.

        Args:
            result: The result of a target fetch operation to be processed.
        """
        pass
