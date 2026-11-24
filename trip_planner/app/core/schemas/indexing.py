"""Schemas of loading the source data files into the database."""

import pydantic

from trip_planner.app.core.schemas import source_data


class SourceData(pydantic.BaseModel):
    """Rows read from the source data files of one indexing request.

    Attributes:
        trails: Rows of the trails file; empty when none was named.
        gear_items: Rows of the gear file; empty when none was named.
    """

    trails: list[source_data.TrailRecord] = pydantic.Field(
        default_factory=list
    )
    gear_items: list[source_data.GearItemRecord] = pydantic.Field(
        default_factory=list
    )


class IndexingReport(pydantic.BaseModel):
    """Rows written to each table by one indexing run.

    Attributes:
        trails: Rows written to `trails`.
        gear_categories: Rows written to `gear_categories`.
        gear_products: Rows written to `gear_products`.
    """

    trails: int = 0
    gear_categories: int = 0
    gear_products: int = 0
