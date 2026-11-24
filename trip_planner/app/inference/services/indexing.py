"""Loads source data files into the database on request."""

import asyncio
import time

from trip_planner.app.core.schemas import api
from trip_planner.app.pipelines.source_data_indexing import (
    core as source_data_pipeline_lib,
)


class IndexingService:
    """Runs the indexing pipelines.

    Runs are serialized: a request that arrives while another indexes waits
    for it, so concurrent upserts of the same rows never deadlock.
    """

    def __init__(
        self,
        source_data_pipeline: (
            source_data_pipeline_lib.SourceDataIndexingPipeline
        ),
    ):
        """Initializes the service.

        Args:
            source_data_pipeline: Loads CSV files from MinIO into the
                database.
        """
        self._source_data_pipeline = source_data_pipeline
        self._lock = asyncio.Lock()

    async def index_source_data(
        self, request: api.IndexingRequest
    ) -> api.IndexingResponse:
        """Loads the named trails and gear CSV files into the database.

        Args:
            request: Keys of the files in the source data bucket.

        Returns:
            The rows written to each table and how long it took.

        Raises:
            errors.InvalidRequestError: A file is missing or malformed.
        """
        async with self._lock:
            started = time.perf_counter()
            report = await self._source_data_pipeline.run(
                trails_file=request.trails_file,
                gear_items_file=request.gear_items_file,
            )
            duration_s = time.perf_counter() - started
        return api.IndexingResponse(
            report=report, duration_s=round(duration_s, 3)
        )
