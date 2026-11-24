"""Writes the scraped trails and gear list into the trip planner database."""

from collections.abc import Callable, Hashable, Iterable, Sequence
import logging
from typing import TypeVar

from trip_planner.app.core import errors
from trip_planner.app.core.repositories.postgres import (
    gear_category as gear_category_lib,
)
from trip_planner.app.core.repositories.postgres import (
    gear_product as gear_product_lib,
)
from trip_planner.app.core.repositories.postgres import trail as trail_lib
from trip_planner.app.core.schemas import indexing
from trip_planner.app.core.schemas import source_data
from trip_planner.app.ml.source_data_indexing import row_mapping

logger = logging.getLogger(__name__)

_Record = TypeVar('_Record')


class SourceDataIndexing:
    """Upserts trails into `trails` and the gear list into `gear_*` tables.

    Rows are matched on their natural key (trail code; category name;
    category, item type and product), so indexing a file again only
    refreshes its rows. Rows no longer in a file are kept, and so are the
    columns curated by hand (see the repositories).
    """

    def __init__(
        self,
        trail_repository: trail_lib.TrailRepository,
        gear_category_repository: gear_category_lib.GearCategoryRepository,
        gear_product_repository: gear_product_lib.GearProductRepository,
    ):
        """Initializes the component.

        Args:
            trail_repository: The `trails` table.
            gear_category_repository: The `gear_categories` table.
            gear_product_repository: The `gear_products` table.
        """
        self._trails = trail_repository
        self._gear_categories = gear_category_repository
        self._gear_products = gear_product_repository

    async def index(
        self, data: indexing.SourceData
    ) -> indexing.IndexingReport:
        """Writes the rows of the source data files into the database.

        Every trail is checked before anything is written, so an incomplete
        trails file leaves the database untouched. A row repeated in a file
        is written once, with its last values.

        Args:
            data: Rows read from the trails and gear files.

        Returns:
            The rows written to each table.

        Raises:
            errors.InvalidRequestError: A trail lacks its length, duration
                or difficulty.
        """
        incomplete = {
            record.trail_code: missing
            for record in data.trails
            if (missing := row_mapping.missing_trail_fields(record))
        }
        if incomplete:
            raise errors.InvalidRequestError(
                f'Trails without required values: {incomplete!r}'
            )
        report = indexing.IndexingReport()
        if data.trails:
            trails = _last_by_key(data.trails, lambda r: r.trail_code)
            report.trails = await self._trails.upsert(
                [row_mapping.to_trail_row(record) for record in trails]
            )
        if data.gear_items:
            report.gear_categories, report.gear_products = (
                await self._index_gear(data.gear_items)
            )
        logger.info('Indexed the source data: %s', report)
        return report

    async def _index_gear(
        self, items: Sequence[source_data.GearItemRecord]
    ) -> tuple[int, int]:
        """Writes the categories, then the products; returns both counts."""
        names = list(dict.fromkeys(item.category for item in items))
        category_ids = await self._gear_categories.upsert(
            [row_mapping.to_gear_category_row(name) for name in names]
        )
        products = _last_by_key(
            items, lambda i: (i.category, i.item_type, i.product)
        )
        written = await self._gear_products.upsert([
            row_mapping.to_gear_product_row(item, category_ids[item.category])
            for item in products
        ])
        return len(category_ids), written


def _last_by_key(
    records: Iterable[_Record], key: Callable[[_Record], Hashable]
) -> list[_Record]:
    """Drops repeated keys, keeping the last row of each in first order."""
    by_key: dict[Hashable, _Record] = {}
    for record in records:
        by_key[key(record)] = record
    return list(by_key.values())
