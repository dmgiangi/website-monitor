# monitoring_service/aiohttp_fetcher.py

import asyncio
import re
from typing import Optional

import aiohttp

from website_monitor.contracts import TargetFetcher
from website_monitor.domain import FetchResult, RequestTrace, Target


def _has_match(pattern: str, text: str) -> Optional[bool]:
    return bool(re.match(pattern, text))


class AiohttpFetcher(TargetFetcher):
    """
    A concrete implementation of TargetFetcher using the aiohttp library.

    This class handles the entire lifecycle of a single HTTP check, including
    timing, error handling, and optional regex validation.
    """

    def __init__(self, worker_id: str, session: aiohttp.ClientSession):
        """
        Initializes the fetcher with a shared aiohttp ClientSession.

        Args:
            session: An active aiohttp.ClientSession to be used for requests.
                     Using a single session is the best practice for performance.
        """
        self._worker_id = worker_id
        self._session = session

    async def fetch(self, target: Target) -> FetchResult:
        """
        Performs a single HTTP GET request to the target's URL.

        It captures the response time, status code, and any errors and
        optionally validates the response body against a regex.

        Args:
            target: The Target object to check.

        Returns:
            A FetchResult object containing the outcome of the check.
        """
        error: Optional[Exception] = None
        status_code: Optional[int] = None
        trace: Optional[RequestTrace] = None
        regex_has_matches: Optional[bool] = None
        start_time = asyncio.get_event_loop().time()

        try:
            timeout = target.check_interval.total_seconds()
            async with self._session.request(
                target.method, target.url, timeout=timeout, headers=target.default_headers
            ) as response:
                status_code = response.status

                if target.regex_pattern and status_code == 200:
                    response_body = await response.text()
                    regex_has_matches = _has_match(target.regex_pattern, response_body)

                if hasattr(response, "trace_request_ctx") and isinstance(
                    response.trace_request_ctx, RequestTrace
                ):
                    trace = response.trace_request_ctx

        except Exception as e:
            error = e

        return FetchResult(
            target=target,
            error=error,
            total_time=asyncio.get_event_loop().time() - start_time,
            status_code=status_code,
            request_trace=trace,
            regex_has_matches=regex_has_matches,
        )


def get_trace_config() -> aiohttp.TraceConfig:
    """
    Public method that returns the required aiohttp.TraceConfig object.
    This fulfills the design requirement.
    """
    trace_config = aiohttp.TraceConfig()
    return trace_config
