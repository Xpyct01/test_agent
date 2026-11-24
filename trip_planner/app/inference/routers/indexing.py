"""Routes that load source data files into the database."""

import typing

import fastapi

from trip_planner.app.core.schemas import api
from trip_planner.app.inference.routers import state

if typing.TYPE_CHECKING:
    from trip_planner.app.inference.services import indexing as indexing_lib

router = fastapi.APIRouter(prefix='/indexing', tags=['indexing'])


@router.post('', response_model=api.IndexingResponse)
async def index_source_data(
    indexing_request: api.IndexingRequest,
    service: 'indexing_lib.IndexingService' = fastapi.Depends(
        state.indexing_service
    ),
) -> api.IndexingResponse:
    """Loads trails and gear CSV files from MinIO into the database.

    Args:
        indexing_request: Keys of the CSV files in the bucket.
        service: The indexing service; 503 while starting.

    Returns:
        The rows written to each table.
    """
    return await service.index_source_data(indexing_request)
