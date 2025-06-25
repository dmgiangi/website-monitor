"""
HTTP client configuration module for the website monitoring system.

This module provides functionality to create and configure HTTP client sessions
using the aiohttp library. It supports optional request tracing for detailed
performance monitoring.
"""

import logging

import aiohttp

from website_monitor.config import MonitoringContext

# Module logger
logger = logging.getLogger(__name__)


def get_http_session(context: MonitoringContext) -> aiohttp.ClientSession:
    """
    Create and configure an HTTP client session based on the provided configuration.

    Using a shared session is recommended for performance reasons.

    Args:
        context: Configuration context containing HTTP client settings.

    Returns:
        aiohttp.ClientSession: A configured HTTP client session that can be used to make HTTP requests.
    """
    return aiohttp.ClientSession()
