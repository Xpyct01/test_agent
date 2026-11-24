"""Request and response bodies of the HTTP API."""

import pydantic

from trip_planner.app.core.schemas import indexing
from trip_planner.app.core.schemas import simulation


class SimulationRequest(pydantic.BaseModel):
    """Body of `POST /simulations`."""

    runs: int = pydantic.Field(default=1, ge=1, le=10)
    scenario: str | None = pydantic.Field(
        default=None,
        description='Scenario file stem under data/scenarios; default if '
        'omitted.',
    )


class SimulationResponse(pydantic.BaseModel):
    """Summary and trajectories of a batch."""

    summary: simulation.BatchSummary
    trajectories: list[simulation.Trajectory]


class IndexingRequest(pydantic.BaseModel):
    """Body of `POST /indexing`: CSV files of the source data bucket.

    At least one file must be named.
    """

    trails_file: str | None = pydantic.Field(
        default=None,
        min_length=1,
        description='Key of a CSV file with the columns of '
        'picos_trails/trails.csv, e.g. "trails.csv".',
        examples=['trails.csv'],
    )
    gear_items_file: str | None = pydantic.Field(
        default=None,
        min_length=1,
        description='Key of a CSV file with the columns of '
        'hiking_gear/gear_items.csv, e.g. "gear_items.csv".',
        examples=['gear_items.csv'],
    )

    @pydantic.model_validator(mode='after')
    def _names_a_file(self) -> 'IndexingRequest':
        if self.trails_file is None and self.gear_items_file is None:
            raise ValueError('Name trails_file, gear_items_file or both.')
        return self


class IndexingResponse(pydantic.BaseModel):
    """Result of `POST /indexing`."""

    report: indexing.IndexingReport
    duration_s: float
