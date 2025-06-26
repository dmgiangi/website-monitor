"""
HTTP fetcher implementation using the aiohttp library.

This module provides an implementation of the TargetFetcher interface that uses
the aiohttp library to perform HTTP requests. It handles timing, error handling,
and optional regex validation of response bodies.
"""

import logging
import re
import time
from typing import Optional

import aiohttp

from website_monitor.contracts import TargetFetcher
from website_monitor.domain import FetchResult, Target

# Module logger
logger = logging.getLogger(__name__)


def has_match(pattern: str, text: str) -> bool:
    """
    Checks if a text matches a regular expression pattern.

    Args:
        pattern: The regular expression pattern to match against.
        text: The text to check for matches.

    Returns:
        bool: True if the pattern matches the text, False otherwise.
    """
    return bool(re.match(pattern, text))


class AiohttpFetcher(TargetFetcher):
    """
    A concrete implementation of TargetFetcher using the aiohttp library.

    This class handles the entire lifecycle of a single HTTP check, including
    timing, error handling, and optional regex validation of response bodies.
    It uses a shared aiohttp ClientSession for optimal performance.
    """

    def __init__(
        self,
        worker_id: str,
        session: aiohttp.ClientSession,
        max_timeout: int,
        raise_for_status: bool,
    ) -> None:
        """
        Initializes the fetcher with a shared aiohttp ClientSession.

        Args:
            worker_id: A unique identifier for this worker instance.
            session: An active aiohttp.ClientSession to be used for requests.
                     Using a single session is the best practice for performance.
        """
        self._worker_id: str = worker_id
        self._session: aiohttp.ClientSession = session
        self._max_timeout = max_timeout
        self._raise_for_status = raise_for_status

    async def fetch(self, target: Target) -> FetchResult:
        """
        Performs an HTTP request to the target's URL using the specified method.

        This method captures the response time, status code, and any errors.
        If a regex pattern is specified in the target and the response status is 200,
        it also validates the response body against the pattern.

        Args:
            target: The Target object to check, containing URL, method, and other configuration.

        Returns:
            FetchResult: An object containing the outcome of the check, including
                status code, timing information, and any errors encountered.
        """
        logger.debug(f"Starting fetch for target: {target.url}")
        error: Optional[Exception] = None
        status_code: Optional[int] = None
        regex_has_matches: Optional[bool] = None
        start_time: float = time.time()

        try:
            # Use the check_interval as the timeout to ensure we don't wait longer than needed
            timeout: float = min(target.check_interval.total_seconds() - 0.1, self._max_timeout)
            async with self._session.request(
                target.method,
                target.url,
                timeout=timeout,
                headers=target.default_headers,
            ) as response:
                if self._raise_for_status:
                    response.raise_for_status()
                status_code = response.status

                # Only check the regex pattern if response is successful
                if target.regex_pattern and status_code == 200:
                    response_body: str = await response.text()
                    regex_has_matches = has_match(target.regex_pattern, response_body)

        except Exception as e:
            error = e
            logger.exception(f"Error fetching {target.url}")

        end_time: float = time.time()
        if error is None:
            logger.debug(
                f"Successfully fetched {target.url} in {(start_time - end_time):.3f}s with status {status_code}"
            )

        return FetchResult(
            target=target,
            error=error,
            start_time=start_time,
            end_time=end_time,
            status_code=status_code,
            regex_has_matches=regex_has_matches,
        )
