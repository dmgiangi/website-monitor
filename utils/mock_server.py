#!/usr/bin/env python3
"""
Mock server for testing website monitoring.

This server simulates a website with varying response times:
- 90% of requests: 5-500ms response time
- 10% of requests: 5-30s response time

All responses are 200 OK with a random sequence of 100 lowercase letters.
"""

import asyncio
import random
import string

from aiohttp import web

# Constants
PORT = 8080
HOST = "localhost"
RESPONSE_LENGTH = 100
FAST_RESPONSE_PROBABILITY = 0.9
FAST_RESPONSE_MIN_MS = 5
FAST_RESPONSE_MAX_MS = 500
SLOW_RESPONSE_MIN_S = 5
SLOW_RESPONSE_MAX_S = 30


async def handle_request(request: web.Request) -> web.Response:
    """
    Handle incoming HTTP requests.

    Args:
        request: The incoming HTTP request

    Returns:
        A response with a 200 status code and a random string of lowercase letters
    """
    # Generate random response content (100 lowercase letters)
    response_content = "".join(
        random.choice(string.ascii_lowercase) for _ in range(RESPONSE_LENGTH)
    )

    # Determine response time (90% fast, 10% slow)
    if random.random() < FAST_RESPONSE_PROBABILITY:
        # Fast response: 5-500ms
        delay_ms = random.uniform(FAST_RESPONSE_MIN_MS, FAST_RESPONSE_MAX_MS)
        delay_s = delay_ms / 1000
    else:
        # Slow response: 5-30s
        delay_s = random.uniform(SLOW_RESPONSE_MIN_S, SLOW_RESPONSE_MAX_S)

    # Simulate processing time
    await asyncio.sleep(delay_s)

    # Return response
    return web.Response(text=response_content)


async def init_app() -> web.Application:
    """
    Initialize the web application.

    Returns:
        Configured aiohttp web Application
    """
    app = web.Application()
    app.add_routes([web.get("/{tail:.*}", handle_request)])
    return app


def run_server() -> None:
    """Run the mock server.

    This function starts the aiohttp web server using the application
    initialized by init_app(). The server listens on the host and port
    defined by the HOST and PORT constants.

    Returns:
        None
    """
    web.run_app(init_app(), host=HOST, port=PORT)


if __name__ == "__main__":
    print(f"Starting mock server at http://{HOST}:{PORT}")
    print(
        f"- {FAST_RESPONSE_PROBABILITY * 100}% of responses: {FAST_RESPONSE_MIN_MS}-{FAST_RESPONSE_MAX_MS}ms"
    )
    print(
        f"- {(1 - FAST_RESPONSE_PROBABILITY) * 100}% of responses: {SLOW_RESPONSE_MIN_S}-{SLOW_RESPONSE_MAX_S}s"
    )
    run_server()
