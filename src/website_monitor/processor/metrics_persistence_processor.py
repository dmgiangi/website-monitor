import logging

from asyncpg import Pool

from website_monitor.contracts import ResultProcessor
from website_monitor.domain import FetchResult

# Module logger
logger = logging.getLogger(__name__)


class MetricsPersistenceProcessor(ResultProcessor):
    def __init__(self, worker_id: str, pool: Pool) -> None:
        self._worker_id: str = worker_id
        self._pool: Pool = pool

    async def process(self, result: FetchResult) -> None:
        pass
