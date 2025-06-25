"""
Unit tests for the AiohttpFetcher class.

This module contains comprehensive tests for the AiohttpFetcher class,
ensuring that it correctly performs HTTP requests and processes the results.

The tests follow the Arrange-Act-Assert (AAA) pattern and use proper mocking
of all external dependencies to ensure true unit testing.
"""

import asyncio
from datetime import timedelta
from typing import Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
import pytest_asyncio

from website_monitor.domain import HttpMethod, RequestTrace, Target
from website_monitor.fetcher.aiohttp_fetcher import AiohttpFetcher, _has_match


# Configure pytest-asyncio to use function scope for event loops
@pytest_asyncio.fixture(scope="function")
def event_loop() -> asyncio.AbstractEventLoop:
    """
    Creates an event loop for each test function.

    This is needed because the AiohttpFetcher creates tasks that need to be
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
async def mock_session() -> Tuple[AsyncMock, AsyncMock]:
    """
    Creates a mock aiohttp.ClientSession for testing.

    Returns:
        Tuple[AsyncMock, AsyncMock]: A tuple containing a mock ClientSession and a mock response.
    """
    session = AsyncMock(spec=aiohttp.ClientSession)

    # Configure the mock response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text.return_value = "Response body"
    mock_response.trace_request_ctx = None

    # Configure the session's request method to return the mock response
    session.request.return_value.__aenter__.return_value = mock_response

    return session, mock_response


@pytest_asyncio.fixture
async def sample_target() -> Target:
    """
    Creates a sample Target object for testing.

    Returns:
        Target: A Target object with test values.
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
async def fetcher(mock_session: Tuple[AsyncMock, AsyncMock]) -> AiohttpFetcher:
    """
    Creates an AiohttpFetcher instance with mock dependencies.

    Args:
        mock_session: A fixture providing a mock ClientSession.

    Returns:
        AiohttpFetcher: An AiohttpFetcher instance configured with mock dependencies.
    """
    session, _ = mock_session
    return AiohttpFetcher(
        worker_id="test-worker", session=session, max_timeout=60, raise_for_status=True
    )


@pytest.mark.asyncio
async def test_fetch_should_return_successful_result_for_200_response(
    fetcher: AiohttpFetcher, mock_session: Tuple[AsyncMock, AsyncMock], sample_target: Target
) -> None:
    """
    Tests that the fetch method returns a successful result for a 200 response.
    """
    # Arrange
    session, mock_response = mock_session
    mock_response.status = 200

    # Mock the event loop time method
    with patch("asyncio.get_event_loop") as mock_get_loop:
        mock_loop = MagicMock()
        mock_loop.time.side_effect = [0.0, 0.5]  # Start time, end time
        mock_get_loop.return_value = mock_loop

        # Act
        result = await fetcher.fetch(sample_target)

        # Assert
        session.request.assert_awaited_once_with(
            sample_target.method,
            sample_target.url,
            timeout=sample_target.check_interval.total_seconds(),
            headers=sample_target.default_headers,
        )
        assert result.target == sample_target
        assert result.error is None
        assert result.total_time == 0.5
        assert result.status_code == 200
        assert result.request_trace is None
        assert result.regex_has_matches is None


@pytest.mark.asyncio
async def test_fetch_should_return_error_result_for_exception(
    fetcher: AiohttpFetcher, mock_session: Tuple[AsyncMock, AsyncMock], sample_target: Target
) -> None:
    """
    Tests that the fetch method returns an error result when an exception occurs.
    """
    # Arrange
    session, _ = mock_session
    session.request.side_effect = aiohttp.ClientError("Test error")

    # Mock the event loop time method
    with patch("asyncio.get_event_loop") as mock_get_loop:
        mock_loop = MagicMock()
        mock_loop.time.side_effect = [0.0, 0.5]  # Start time, end time
        mock_get_loop.return_value = mock_loop

        # Act
        result = await fetcher.fetch(sample_target)

        # Assert
        session.request.assert_awaited_once()
        assert result.target == sample_target
        assert isinstance(result.error, aiohttp.ClientError)
        assert result.total_time == 0.5
        assert result.status_code is None
        assert result.request_trace is None
        assert result.regex_has_matches is None


@pytest.mark.asyncio
async def test_fetch_should_check_regex_pattern_for_200_response(
    fetcher: AiohttpFetcher, mock_session: Tuple[AsyncMock, AsyncMock], sample_target: Target
) -> None:
    """
    Tests that the fetch method checks the regex pattern for a 200 response.
    """
    # Arrange
    session, mock_response = mock_session
    mock_response.status = 200
    mock_response.text.return_value = "Response body with pattern"

    # Create a target with a regex pattern
    target_with_pattern = Target(
        id=sample_target.id,
        url=sample_target.url,
        method=sample_target.method,
        check_interval=sample_target.check_interval,
        regex_pattern="pattern",
        default_headers=sample_target.default_headers,
    )

    # Mock the _has_match function to return True
    with patch(
        "website_monitor.fetcher.aiohttp_fetcher._has_match", return_value=True
    ) as mock_has_match:
        # Mock the event loop time method
        with patch("asyncio.get_event_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_loop.time.side_effect = [0.0, 0.5]  # Start time, end time
            mock_get_loop.return_value = mock_loop

            # Act
            result = await fetcher.fetch(target_with_pattern)

            # Assert
            session.request.assert_awaited_once()
            mock_response.text.assert_awaited_once()
            mock_has_match.assert_called_once_with("pattern", "Response body with pattern")
            assert result.target == target_with_pattern
            assert result.error is None
            assert result.total_time == 0.5
            assert result.status_code == 200
            assert result.request_trace is None
            assert result.regex_has_matches is True


@pytest.mark.asyncio
async def test_fetch_should_not_check_regex_pattern_for_non_200_response(
    fetcher: AiohttpFetcher, mock_session: Tuple[AsyncMock, AsyncMock], sample_target: Target
) -> None:
    """
    Tests that the fetch method does not check the regex pattern for a non-200 response.
    """
    # Arrange
    session, mock_response = mock_session
    mock_response.status = 404

    # Create a target with a regex pattern
    target_with_pattern = Target(
        id=sample_target.id,
        url=sample_target.url,
        method=sample_target.method,
        check_interval=sample_target.check_interval,
        regex_pattern="pattern",
        default_headers=sample_target.default_headers,
    )

    # Mock the event loop time method
    with patch("asyncio.get_event_loop") as mock_get_loop:
        mock_loop = MagicMock()
        mock_loop.time.side_effect = [0.0, 0.5]  # Start time, end time
        mock_get_loop.return_value = mock_loop

        # Act
        result = await fetcher.fetch(target_with_pattern)

        # Assert
        session.request.assert_awaited_once()
        mock_response.text.assert_not_awaited()
        assert result.target == target_with_pattern
        assert result.error is None
        assert result.total_time == 0.5
        assert result.status_code == 404
        assert result.request_trace is None
        assert result.regex_has_matches is None


@pytest.mark.asyncio
async def test_fetch_should_extract_request_trace_if_available(
    fetcher: AiohttpFetcher, mock_session: Tuple[AsyncMock, AsyncMock], sample_target: Target
) -> None:
    """
    Tests that the fetch method extracts the request trace if available.
    """
    # Arrange
    session, mock_response = mock_session
    mock_response.status = 200

    # Create a request trace
    request_trace = RequestTrace()
    request_trace.request_start = 0.0
    request_trace.request_end = 0.5

    # Set the trace on the response
    mock_response.trace_request_ctx = request_trace

    # Mock the event loop time method
    with patch("asyncio.get_event_loop") as mock_get_loop:
        mock_loop = MagicMock()
        mock_loop.time.side_effect = [0.0, 0.5]  # Start time, end time
        mock_get_loop.return_value = mock_loop

        # Act
        result = await fetcher.fetch(sample_target)

        # Assert
        session.request.assert_awaited_once()
        assert result.target == sample_target
        assert result.error is None
        assert result.total_time == 0.5
        assert result.status_code == 200
        assert result.request_trace == request_trace
        assert result.regex_has_matches is None


@pytest.mark.asyncio
async def test_fetch_should_use_default_headers_if_provided(
    fetcher: AiohttpFetcher, mock_session: Tuple[AsyncMock, AsyncMock], sample_target: Target
) -> None:
    """
    Tests that the fetch method uses default headers if provided.
    """
    # Arrange
    session, _ = mock_session

    # Create a target with default headers
    target_with_headers = Target(
        id=sample_target.id,
        url=sample_target.url,
        method=sample_target.method,
        check_interval=sample_target.check_interval,
        regex_pattern=sample_target.regex_pattern,
        default_headers={"User-Agent": "Test Agent"},
    )

    # Mock the event loop time method
    with patch("asyncio.get_event_loop") as mock_get_loop:
        mock_loop = MagicMock()
        mock_loop.time.side_effect = [0.0, 0.5]  # Start time, end time
        mock_get_loop.return_value = mock_loop

        # Act
        result = await fetcher.fetch(target_with_headers)

        # Assert
        session.request.assert_awaited_once_with(
            target_with_headers.method,
            target_with_headers.url,
            timeout=target_with_headers.check_interval.total_seconds(),
            headers={"User-Agent": "Test Agent"},
        )
        assert result.target == target_with_headers


def test_has_match_should_return_true_for_matching_pattern() -> None:
    """
    Tests that the _has_match function returns True for a matching pattern.
    """
    # Arrange
    pattern = r"test\d+"
    text = "This is a test123 string"

    # Act
    result = _has_match(pattern, text)

    # Assert
    assert result is True


def test_has_match_should_return_false_for_non_matching_pattern() -> None:
    """
    Tests that the _has_match function returns False for a non-matching pattern.
    """
    # Arrange
    pattern = r"test\d+"
    text = "This is a test string"

    # Act
    result = _has_match(pattern, text)

    # Assert
    assert result is False
