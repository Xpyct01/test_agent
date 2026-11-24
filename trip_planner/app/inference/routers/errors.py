"""Maps exceptions to HTTP responses."""

import logging

import fastapi
from fastapi import responses

from trip_planner.app.core import errors

logger = logging.getLogger(__name__)


def register_exception_handlers(app: fastapi.FastAPI) -> None:
    """Answers 400 for invalid requests and 500 for anything else."""

    @app.exception_handler(errors.InvalidRequestError)
    async def invalid_request(
        request: fastapi.Request, error: errors.InvalidRequestError
    ) -> responses.JSONResponse:
        del request  # Unused.
        return responses.JSONResponse(
            status_code=400, content={'detail': str(error)}
        )

    @app.exception_handler(Exception)
    async def internal_error(
        request: fastapi.Request, error: Exception
    ) -> responses.JSONResponse:
        logger.exception(
            'Unhandled error on %s', request.url.path, exc_info=error
        )
        return responses.JSONResponse(
            status_code=500, content={'detail': 'Internal server error'}
        )
