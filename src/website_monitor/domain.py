"""
Domain models for the website monitoring system.

This module defines the core data structures used throughout the application,
including monitoring targets, HTTP methods, request traces, and fetch results.
These models serve as the foundation for the monitoring system's data flow.
"""

from datetime import timedelta
from enum import Enum
from typing import Any, Dict, NamedTuple, Optional


class HttpMethod(str, Enum):
    """
    Defines supported HTTP methods as a type-safe enumeration.

    Inheriting from 'str' allows enum members to behave like strings,
    making them compatible with libraries expecting string values.
    """

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class Target(NamedTuple):
    """
    Represents a single target to monitor with its complete configuration.

    This data structure directly corresponds to the columns in the
    'monitored_targets' database table. It contains all the information
    needed to perform a monitoring check.

    Attributes:
        id: The unique identifier of the target in the database.
        url: The URL to monitor.
        method: The HTTP method to use for the request.
        check_interval: How frequently the target should be checked.
        regex_pattern: Optional regex pattern to search for in the response.
        default_headers: Optional HTTP headers to include with each request.
    """

    id: int
    url: str
    method: HttpMethod
    check_interval: timedelta
    regex_pattern: Optional[str]
    default_headers: Optional[Dict[str, Any]]


class FetchResult(NamedTuple):
    """
    A data structure holding the result of a single monitoring check.

    This object is passed through the result processing pipeline and contains
    all information about the outcome of a monitoring check.

    Attributes:
        target: The original Target that was checked.
        error: Any exception that occurred during the check, or None if successful.
        start_time: The start time from time.time() in seconds.
        end_time: The end time from time.time() in seconds.
        status_code: The HTTP status code received, or None if an error occurred.
        request_trace: Detailed timing information about the request, or None.
        regex_has_matches: Whether the regex pattern matched the response, or None.
    """

    target: Target
    error: Optional[Exception]
    start_time: float
    end_time: float
    status_code: Optional[int]
    regex_has_matches: Optional[bool]
