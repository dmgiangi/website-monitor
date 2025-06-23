# monitoring_service/__main__.py

import asyncio
import os
from uuid import uuid4

import aiohttp
import asyncpg

from website_monitor.fetcher.aiohttp_fetcher import AiohttpFetcher, get_trace_config
from website_monitor.processor.delegating_processor import DelegatingResultProcessor
from website_monitor.scheduler.asyncpg_scheduler import PostgresScheduler
from website_monitor.worker import MonitoringWorker


async def initiate_db_pool() -> asyncpg.pool.Pool:
    dsn = os.getenv(
        "WEBSITE_MONITOR_DSN",
        "postgresql://postgres:password@localhost/test?options=-c+search_path%3Dwebsite_monitor",
    )
    pool = await asyncpg.create_pool(dsn=dsn)

    try:
        async with pool.acquire() as connection:
            await connection.fetchval("SELECT 1")
        print("Database connection pool successfully created.")
        return pool
    except Exception as e:
        print(f"Error: Could not connect to the database. {e}")
        await pool.close()
        raise


async def main() -> None:
    """
    The main function to set up and run the application.
    """
    worker_id = os.getenv("WEBSITE_MONITOR_WORKER_ID", f"website-monitor-{uuid4()}")
    logging_config = os.getenv("WEBSITE_MONITOR_LOGGING_CONFIG", None)

    batch_size = int(os.getenv("WEBSITE_MONITOR_BATCH_SIZE", 10))

    tracing_config = get_trace_config()
    http_session = aiohttp.ClientSession(trace_configs=[tracing_config])

    db_pool = await initiate_db_pool()

    try:
        worker = MonitoringWorker(
            worker_id=worker_id,
            scheduler=PostgresScheduler(worker_id=worker_id, pool=db_pool, batch_size=batch_size),
            fetcher=AiohttpFetcher(worker_id=worker_id, session=http_session),
            processor=DelegatingResultProcessor([]),
        )

        await worker.run()

    except asyncio.CancelledError:
        print("Application shutdown requested.")
    finally:
        print("Shutting down resources...")
        if http_session:
            await http_session.close()
        if db_pool:
            await db_pool.close()
        print("Shutdown complete.")


if __name__ == "__main__":
    try:
        print("Starting Monitoring Service...")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutdown initiated by user (Ctrl+C).")
