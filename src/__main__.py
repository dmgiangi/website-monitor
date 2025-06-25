"""
Main entry point for the website monitoring application.

This module initializes and runs the website monitoring system. It sets up logging,
creates database and HTTP connections, initializes the worker components, and
handles graceful shutdown when the application is terminated.
"""

import asyncio
import logging

import aiohttp
import asyncpg

from website_monitor.config import MonitoringContext, get_context
from website_monitor.config.db_config import initiate_db_pool
from website_monitor.config.http_config import get_http_session
from website_monitor.config.logging_config import configure_logging
from website_monitor.fetcher.aiohttp_fetcher import AiohttpFetcher
from website_monitor.processor.delegating_processor import DelegatingResultProcessor
from website_monitor.processor.error_persistence_processor import ErrorPersistenceProcessor
from website_monitor.processor.metrics_persistence_processor import MetricsPersistenceProcessor
from website_monitor.processor.prometheus_processor import PrometheusProcessor
from website_monitor.scheduler.asyncpg_scheduler import PostgresScheduler
from website_monitor.worker import MonitoringWorker


async def main(context: MonitoringContext) -> None:
    """
    Set up and run the website monitoring application.

    This function initializes all components of the monitoring system:
    1. Creates an HTTP session for making requests
    2. Establishes database connection pool
    3. Creates a scheduler, fetcher, and processor
    4. Initializes and starts the monitoring worker
    5. Handles graceful shutdown when the application is terminated

    Args:
        context: Configuration context containing all application settings.

    Returns:
        None
    """
    logger: logging.Logger = logging.getLogger(__name__)
    logger.info("Starting application...")
    worker_id: str = context.worker_id

    # Initialize HTTP session for making requests
    http_session: aiohttp.ClientSession = get_http_session(context)
    logger.info("configured: http_session")

    # Initialize the database connection pool
    db_pool: asyncpg.pool.Pool = await initiate_db_pool(context)
    logger.info("initialized: db_pool")

    batch_size: int = context.batch_size

    # Initialize the monitoring worker with all its components
    worker: MonitoringWorker = MonitoringWorker(
        worker_id=worker_id,
        num_workers=context.worker_number,
        queue_size=context.queue_size,
        scheduler=PostgresScheduler(worker_id=worker_id, pool=db_pool, batch_size=batch_size),
        fetcher=AiohttpFetcher(
            worker_id=worker_id, 
            session=http_session, 
            max_timeout=context.max_timeout,
            raise_for_status=context.raise_for_status
        ),
        processor=DelegatingResultProcessor(
            worker_id,
            [
                ErrorPersistenceProcessor(worker_id=worker_id, pool=db_pool),
                PrometheusProcessor(worker_id=worker_id),
                MetricsPersistenceProcessor(worker_id=worker_id, pool=db_pool),
            ],
        ),
    )

    try:
        logger.info("Worker initialized. Starting monitoring loop...")
        await worker.start()

    except asyncio.CancelledError:
        logger.info("Application shutdown requested.")
    finally:
        # Ensure all resources are properly closed during shutdown
        logger.info("Shutting down resources...")
        if worker:
            await worker.stop()
        if http_session:
            await http_session.close()
        if db_pool:
            await db_pool.close()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    try:
        # Parse command-line arguments and environment variables
        website_monitor_context: MonitoringContext = get_context()

        # Configure logging based on the context
        configure_logging(website_monitor_context)

        # Run the main application
        asyncio.run(main(website_monitor_context))
    except KeyboardInterrupt:
        logging.info("Shutdown initiated by user (Ctrl+C).")
