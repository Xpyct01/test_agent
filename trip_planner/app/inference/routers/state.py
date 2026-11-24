"""Application state and the dependencies that hand out request services."""

import dataclasses
import typing

import fastapi

if typing.TYPE_CHECKING:
    from trip_planner.app.inference.services import core as services_lib
    from trip_planner.app.inference.services import simulation as simulation_lib


@dataclasses.dataclass
class ApplicationState:
    """What the routes need, stored on `app.state.application_state`.

    Attributes:
        ready: Whether start-up finished.
        service: The inference service, once built.
    """

    ready: bool = False
    service: 'services_lib.InferenceService | None' = None


def require_service(request: fastapi.Request) -> 'services_lib.InferenceService':
    """Returns the inference service, or answers 503 while starting."""
    state: ApplicationState = request.app.state.application_state
    if not state.ready or state.service is None:
        raise fastapi.HTTPException(
            status_code=503, detail='Service is starting.'
        )
    return state.service


def simulation_service(
    request: fastapi.Request,
) -> 'simulation_lib.SimulationService':
    """Returns the simulation request service."""
    return require_service(request).simulation
