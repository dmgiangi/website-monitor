# monitoring_service/scheduler.py

import asyncio
from datetime import datetime, timezone
from typing import List

from asyncpg import Pool

from website_monitor.contracts import WorkScheduler
from website_monitor.domain import HttpMethod, Target

FETCH_AND_LEASE_QUERY = """
                        WITH due_targets AS (SELECT monitored_target_id
                                             FROM target_leases
                                             WHERE next_fire_at <= NOW()
                                             ORDER BY next_fire_at
                                             LIMIT $1 FOR UPDATE SKIP LOCKED),
                             updated_leases AS (
                                 UPDATE target_leases tl
                                     SET
                                         next_fire_at = NOW() + mt.check_interval,
                                         worker_id = $2,
                                         lease_acquired_at = NOW()
                                     FROM due_targets dt
                                         JOIN monitored_targets mt ON mt.id = dt.monitored_target_id
                                     WHERE tl.monitored_target_id = dt.monitored_target_id
                                     RETURNING tl.monitored_target_id)
                        SELECT mt.id,
                               mt.url,
                               mt.method,
                               mt.check_interval,
                               mt.regex_pattern,
                               mt.default_headers
                        FROM monitored_targets mt
                                 JOIN updated_leases ul ON mt.id = ul.monitored_target_id; \
                        """

GET_NEXT_FIRE_AT_QUERY = "SELECT MIN(next_fire_at) FROM target_leases"


class PostgresScheduler(WorkScheduler):
    def __init__(self, worker_id: str, pool: Pool, batch_size: int = 10, recover_time: int = 10):
        if not isinstance(worker_id, str) or not worker_id:
            raise ValueError("worker_id must be provided and must be not blank.")

        if not isinstance(batch_size, int) or batch_size < 1:
            raise ValueError("batch_size must be a positive integer.")

        if not isinstance(recover_time, int) or batch_size < 1:
            raise ValueError("recover_time must be a positive integer.")

        self._worker_id = worker_id
        self._pool = pool
        self._batch_size = batch_size
        self._recover_time = recover_time
        self._is_running = False

    async def start(self) -> None:
        print(f"[{self._worker_id}] Starting scheduler (batch size: {self._batch_size})...")
        self._is_running = True

    async def close(self) -> None:
        print(f"[{self._worker_id}] Closing scheduler...")
        self._is_running = False

    async def __anext__(self) -> List[Target]:
        """
        Recupera un batch di lavoro. Se non c'è lavoro, calcola il tempo
        di attesa fino alla prossima scadenza e si mette in pausa.
        """
        while self._is_running:
            try:
                async with self._pool.acquire() as conn:
                    async with conn.transaction():
                        records = await conn.fetch(
                            FETCH_AND_LEASE_QUERY, self._batch_size, self._worker_id
                        )

                if records:
                    batch = [Target(**dict(r), method=HttpMethod(r["method"])) for r in records]
                    return batch

                async with self._pool.acquire() as conn:
                    next_deadline = await conn.fetchval(GET_NEXT_FIRE_AT_QUERY)

                sleep_duration_seconds = 60
                if next_deadline:
                    now = datetime.now(timezone.utc)
                    sleep_duration_seconds = max(0, (next_deadline - now).total_seconds())

                sleep_duration_seconds = min(sleep_duration_seconds, 60)

                print(f"No tasks due. Sleeping for {sleep_duration_seconds:.2f} seconds.")
                await asyncio.sleep(sleep_duration_seconds)

            except Exception as e:
                print(f"[{self._worker_id}] Error in scheduler loop: {e}")
                await asyncio.sleep(self._recover_time)

        raise StopAsyncIteration
