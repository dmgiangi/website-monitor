"""
Database configuration module for the website monitoring system.

This module provides functionality to create and validate a connection pool
to the PostgreSQL database using the asyncpg library. It ensures that the
database is accessible before returning the connection pool.
"""

import logging

import asyncpg

from website_monitor.config import MonitoringContext

# Module logger
logger = logging.getLogger(__name__)


async def initiate_db_pool(context: MonitoringContext) -> asyncpg.pool.Pool:
    """
    Create and validate a connection pool to the PostgreSQL database.

    This function creates a connection pool using the provided configuration,
    then validates that the database is accessible by executing a simple query.
    If the connection fails, the pool is closed and an exception is raised.

    Args:
        context: Configuration context containing database connection parameters.

    Returns:
        asyncpg.pool.Pool: A connection pool that can be used to execute database queries.

    Raises:
        Exception: If the database connection cannot be established.
    """
    # Create the connection pool with the specified parameters
    pool: asyncpg.pool.Pool = await asyncpg.create_pool(
        dsn=context.dsn, max_size=context.db_pool_size
    )

    try:
        # Validate the connection by executing a simple query
        async with pool.acquire() as connection:
            await connection.fetchval("SELECT 1")
        logger.info("Database connection pool successfully created.")
        return pool
    except Exception as e:
        # If connection fails, log the error, close the pool, and re-raise the exception
        logger.error(f"Error: Could not connect to the database. {e}")
        await pool.close()
        raise
