"""
Unit tests for the AiohttpFetcher class.

This module contains comprehensive tests for the AiohttpFetcher class,
ensuring that it correctly performs HTTP requests, handles errors,
and validates response bodies against regex patterns.

The tests follow the Arrange-Act-Assert (AAA) pattern and use proper mocking
of all external dependencies to ensure true unit testing.
"""

import re
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
import pytest_asyncio

from website_monitor.domain import HttpMethod, Target
from website_monitor.fetcher.aiohttp_fetcher import AiohttpFetcher, has_match


@pytest_asyncio.fixture
async def sample_target() -> Target:
    """
    Creates a sample Target object for testing.

    Returns:
        A Target object with test values.
    """
    return Target(
        id=1,
        url="https://example.com",
        method=HttpMethod.GET,
        check_interval=timedelta(minutes=5),
        regex_pattern="test pattern",
        default_headers={"User-Agent": "Test Agent"},
    )


@pytest_asyncio.fixture
async def sample_target_no_regex() -> Target:
    """
    Creates a sample Target object without regex pattern for testing.

    Returns:
        A Target object with no regex pattern.
    """
    return Target(
        id=2,
        url="https://example.com/no-regex",
        method=HttpMethod.GET,
        check_interval=timedelta(minutes=5),
        regex_pattern=None,
        default_headers={"User-Agent": "Test Agent"},
    )


@pytest_asyncio.fixture
async def mock_session() -> AsyncMock:
    """
    Creates a mock aiohttp.ClientSession for testing.

    Returns:
        A mock ClientSession with configured async methods.
    """
    session = AsyncMock(spec=aiohttp.ClientSession)

    # Mock the response context manager
    response = AsyncMock()
    session.request.return_value.__aenter__.return_value = response

    # Configure default response values
    response.status = 200
    response.text.return_value = "Response body"

    return session


@pytest_asyncio.fixture
async def fetcher(mock_session: AsyncMock) -> AiohttpFetcher:
    """
    Creates an AiohttpFetcher instance with mock dependencies.

    Args:
        mock_session: A fixture providing a mock aiohttp.ClientSession.

    Returns:
        An AiohttpFetcher instance configured with mock dependencies.
    """
    return AiohttpFetcher(
        worker_id="test-worker",
        session=mock_session,
        max_timeout=60,
        raise_for_status=False,
    )


@pytest_asyncio.fixture
async def fetcher_with_raise_for_status(mock_session: AsyncMock) -> AiohttpFetcher:
    """
    Creates an AiohttpFetcher instance with raise_for_status=True.

    Args:
        mock_session: A fixture providing a mock aiohttp.ClientSession.

    Returns:
        An AiohttpFetcher instance configured to raise for status.
    """
    return AiohttpFetcher(
        worker_id="test-worker",
        session=mock_session,
        max_timeout=60,
        raise_for_status=True,
    )


@pytest.mark.asyncio
async def test_fetch_should_return_successful_result_for_valid_request(
    fetcher: AiohttpFetcher, mock_session: AsyncMock, sample_target: Target
) -> None:
    """
    Tests that the fetch method returns a successful result for a valid request.
    """
    # Arrange
    response = mock_session.request.return_value.__aenter__.return_value
    response.status = 200
    response.text.return_value = "Response with test pattern match"

    # Mock the _has_match function to return True
    with patch("website_monitor.fetcher.aiohttp_fetcher._has_match", return_value=True):
        # Act
        with patch("time.time", side_effect=[1000.0, 1001.0]):
            result = await fetcher.fetch(sample_target)

    # Assert
    assert mock_session.request.called
    assert mock_session.request.call_count == 1
    call_args = mock_session.request.call_args[0]
    call_kwargs = mock_session.request.call_args[1]
    assert call_args[0] == sample_target.method
    assert call_args[1] == sample_target.url
    assert call_kwargs["timeout"] == min(sample_target.check_interval.total_seconds() - 0.1, 60)
    assert call_kwargs["headers"] == sample_target.default_headers
    assert result.target == sample_target
    assert result.error is None
    assert result.start_time == 1000.0
    assert result.end_time == 1001.0
    assert result.status_code == 200
    assert result.regex_has_matches is True


@pytest.mark.asyncio
async def test_fetch_should_not_check_regex_when_pattern_is_none(
    fetcher: AiohttpFetcher, mock_session: AsyncMock, sample_target_no_regex: Target
) -> None:
    """
    Tests that the fetch method doesn't check regex when the pattern is None.
    """
    # Arrange
    response = mock_session.request.return_value.__aenter__.return_value
    response.status = 200

    # Act
    result = await fetcher.fetch(sample_target_no_regex)

    # Assert
    response.text.assert_not_awaited()
    assert result.regex_has_matches is None


@pytest.mark.asyncio
async def test_fetch_should_not_check_regex_when_status_is_not_200(
    fetcher: AiohttpFetcher, mock_session: AsyncMock, sample_target: Target
) -> None:
    """
    Tests that the fetch method doesn't check regex when the status is not 200.
    """
    # Arrange
    response = mock_session.request.return_value.__aenter__.return_value
    response.status = 404

    # Act
    result = await fetcher.fetch(sample_target)

    # Assert
    response.text.assert_not_awaited()
    assert result.regex_has_matches is None


@pytest.mark.asyncio
async def test_fetch_should_return_false_for_regex_has_matches_when_no_match(
    fetcher: AiohttpFetcher, mock_session: AsyncMock, sample_target: Target
) -> None:
    """
    Tests that the fetch method returns False for regex_has_matches when there's no match.
    """
    # Arrange
    response = mock_session.request.return_value.__aenter__.return_value
    response.status = 200
    response.text.return_value = "Response with no match"

    # Act
    with patch("website_monitor.fetcher.aiohttp_fetcher._has_match", return_value=False):
        result = await fetcher.fetch(sample_target)

    # Assert
    assert result.regex_has_matches is False


@pytest.mark.asyncio
async def test_fetch_should_handle_request_exception(
    fetcher: AiohttpFetcher, mock_session: AsyncMock, sample_target: Target
) -> None:
    """
    Tests that the fetch method handles exceptions during the request.
    """
    # Arrange
    # Create a new exception instance
    error = Exception("Connection error")
    # Configure the mock to raise the exception
    mock_session.request.side_effect = error

    # Act
    result = await fetcher.fetch(sample_target)

    # Assert
    assert result.target == sample_target
    assert result.error is not None
    assert str(result.error) == "Connection error"
    assert result.start_time > 0
    assert result.end_time > 0
    assert result.end_time >= result.start_time
    assert result.status_code is None
    assert result.regex_has_matches is None


@pytest.mark.asyncio
async def test_fetch_should_handle_text_extraction_exception(
    fetcher: AiohttpFetcher, mock_session: AsyncMock, sample_target: Target
) -> None:
    """
    Tests that the fetch method handles exceptions during text extraction.
    """
    # Arrange
    response = mock_session.request.return_value.__aenter__.return_value
    response.status = 200
    response.text.side_effect = Exception("Text extraction error")

    # Act
    result = await fetcher.fetch(sample_target)

    # Assert
    assert isinstance(result.error, Exception)
    assert str(result.error) == "Text extraction error"
    assert result.regex_has_matches is None


@pytest.mark.asyncio
async def test_fetch_should_respect_raise_for_status_flag(
    fetcher_with_raise_for_status: AiohttpFetcher, mock_session: AsyncMock, sample_target: Target
) -> None:
    """
    Tests that the fetch method respects the raise_for_status flag.
    """
    # Arrange
    response = mock_session.request.return_value.__aenter__.return_value
    response.status = 404

    # Act
    await fetcher_with_raise_for_status.fetch(sample_target)

    # Assert
    response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_should_handle_raise_for_status_exception(
    fetcher_with_raise_for_status: AiohttpFetcher, mock_session: AsyncMock, sample_target: Target
) -> None:
    """
    Tests that the fetch method handles exceptions from raise_for_status.
    """
    # Arrange
    response = mock_session.request.return_value.__aenter__.return_value
    response.status = 404

    # Create a specific error instance
    error = Exception("404 Not Found")
    # Make sure raise_for_status raises the exception when called
    response.raise_for_status = MagicMock(side_effect=error)

    # Act
    result = await fetcher_with_raise_for_status.fetch(sample_target)

    # Assert
    # Verify that raise_for_status was called
    response.raise_for_status.assert_called_once()
    # Verify that the error was captured
    assert result.error is not None
    assert str(result.error) == "404 Not Found"
    # When an exception is raised by raise_for_status, the status_code is not set in the FetchResult
    assert result.status_code is None
    assert result.start_time > 0
    assert result.end_time > 0
    assert result.end_time >= result.start_time
    assert result.regex_has_matches is None


@pytest.mark.asyncio
async def test_fetch_should_use_correct_timeout_value(
    fetcher: AiohttpFetcher, mock_session: AsyncMock, sample_target: Target
) -> None:
    """
    Tests that the fetch method uses the correct timeout value.
    """
    # Arrange
    # The sample_target has a check_interval of 5 minutes (300 seconds)
    # The fetcher has a max_timeout of 60 seconds
    # So the timeout should be min(300 - 0.1, 60) = 60

    # Act
    await fetcher.fetch(sample_target)

    # Assert
    assert mock_session.request.called
    assert mock_session.request.call_count == 1
    call_args = mock_session.request.call_args[1]
    assert call_args["timeout"] == 60


@pytest.mark.asyncio
async def test_fetch_should_use_target_check_interval_for_timeout_when_smaller_than_max(
    mock_session: AsyncMock, sample_target: Target
) -> None:
    """
    Tests that the fetch method uses the target's check_interval for timeout when it's smaller than max_timeout.
    """
    # Arrange
    # Create a target with a small check_interval
    target = Target(
        id=3,
        url="https://example.com/small-interval",
        method=HttpMethod.GET,
        check_interval=timedelta(seconds=30),  # 30 seconds
        regex_pattern=None,
        default_headers=None,
    )

    # Create a fetcher with a large max_timeout
    fetcher = AiohttpFetcher(
        worker_id="test-worker",
        session=mock_session,
        max_timeout=60,  # 60 seconds
        raise_for_status=False,
    )

    # Act
    await fetcher.fetch(target)

    # Assert
    assert mock_session.request.called
    assert mock_session.request.call_count == 1
    call_args = mock_session.request.call_args[1]
    assert call_args["timeout"] == 29.9  # 30 - 0.1


def test_has_match_should_return_true_when_pattern_matches() -> None:
    """
    Tests that the _has_match function returns True when the pattern matches the text.
    """
    # Arrange
    pattern = r".*test pattern.*"  # Pattern that will match the text
    text = "This is a test pattern"

    # Act
    result = has_match(pattern, text)

    # Assert
    assert result is True


def test_has_match_should_return_false_when_pattern_does_not_match() -> None:
    """
    Tests that the _has_match function returns False when the pattern doesn't match the text.
    """
    # Arrange
    pattern = r"missing \w+"
    text = "This is a test pattern"

    # Act
    result = has_match(pattern, text)

    # Assert
    assert result is False


def test_has_match_should_handle_invalid_regex_pattern() -> None:
    """
    Tests that the _has_match function handles invalid regex patterns.
    """
    # Arrange
    pattern = r"invalid[regex"  # Invalid regex pattern
    text = "This is a test pattern"

    # Act & Assert
    with pytest.raises(re.error):
        has_match(pattern, text)
