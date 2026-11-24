"""Loads source data CSV files from MinIO into the database."""

import logging

from trip_planner.app.core.providers import source_data as source_data_lib
from trip_planner.app.core.schemas import indexing
from trip_planner.app.ml.source_data_indexing import core as indexing_lib

logger = logging.getLogger(__name__)


class SourceDataIndexingPipeline:
    """Reads the named CSV files from the bucket, then indexes their rows."""

    def __init__(
        self,
        source_data_provider: source_data_lib.SourceDataProvider,
        source_data_indexing: indexing_lib.SourceDataIndexing,
    ):
        """Initializes the pipeline.

        Args:
            source_data_provider: The CSV files of the bucket.
            source_data_indexing: Writes their rows into the database.
        """
        self._source_data = source_data_provider
        self._indexing = source_data_indexing

    async def run(
        self,
        trails_file: str | None = None,
        gear_items_file: str | None = None,
    ) -> indexing.IndexingReport:
        """Indexes the given files; both are read before anything is written.

        Args:
            trails_file: Key of a trails CSV file (columns of
                `picos_trails/trails.csv`); None to skip trails.
            gear_items_file: Key of a gear CSV file (columns of
                `hiking_gear/gear_items.csv`); None to skip gear.

        Returns:
            The rows written to each table.

        Raises:
            errors.InvalidRequestError: A file is missing or malformed.
        """
        data = indexing.SourceData()
        if trails_file is not None:
            data.trails = await self._source_data.read_trails(trails_file)
        if gear_items_file is not None:
            data.gear_items = await self._source_data.read_gear_items(
                gear_items_file
            )
        logger.info(
            'Indexing %d trails from %s and %d gear items from %s',
            len(data.trails),
            trails_file,
            len(data.gear_items),
            gear_items_file,
        )
        return await self._indexing.index(data)
