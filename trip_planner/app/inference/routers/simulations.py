"""Routes that run and read simulation batches."""

import typing

import fastapi

from trip_planner.app.core.schemas import api
from trip_planner.app.inference.routers import state

if typing.TYPE_CHECKING:
    from trip_planner.app.inference.services import simulation as simulation_lib

router = fastapi.APIRouter(prefix='/simulations', tags=['simulations'])


@router.post('', response_model=api.SimulationResponse)
async def run_simulations(
    simulation_request: api.SimulationRequest,
    service: 'simulation_lib.SimulationService' = fastapi.Depends(
        state.simulation_service
    ),
) -> api.SimulationResponse:
    """Plays a scenario several times and returns the evaluated batch.

    Args:
        simulation_request: Body of the request.
        service: The simulation service; 503 while starting.

    Returns:
        The batch summary and every trajectory.
    """
    return await service.run_batch(simulation_request)


@router.get('/{batch_id}', response_model=api.SimulationResponse)
async def get_simulations(
    batch_id: str,
    service: 'simulation_lib.SimulationService' = fastapi.Depends(
        state.simulation_service
    ),
) -> api.SimulationResponse:
    """Returns a batch run earlier.

    Args:
        batch_id: Id returned by `POST /simulations`.
        service: The simulation service; 503 while starting.

    Returns:
        The batch summary and every trajectory.
    """
    return await service.get_batch(batch_id)
