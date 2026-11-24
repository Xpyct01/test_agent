"""Request and response bodies of the HTTP API."""

import pydantic

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
