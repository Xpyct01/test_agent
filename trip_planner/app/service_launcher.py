"""HTTP entry point: `uvicorn trip_planner.app.service_launcher:app`."""

import asyncio
import contextlib
import importlib
import logging

import fastapi

from trip_planner.app import config
from trip_planner.app.inference.routers import agui
from trip_planner.app.inference.routers import errors
from trip_planner.app.inference.routers import health
from trip_planner.app.inference.routers import indexing
from trip_planner.app.inference.routers import simulations
from trip_planner.app.inference.routers import state

logger = logging.getLogger(__name__)

_ROUTERS = (
    health.router, simulations.router, agui.router, indexing.router
)


async def _start(application_state: state.ApplicationState) -> None:
    try:
        # Deferred so /health/live answers before LangChain, LangGraph and
        # the OpenAI SDK finish importing.
        services_lib = await asyncio.to_thread(
            importlib.import_module, 'trip_planner.app.inference.services.core'
        )
        configuration = config.Configuration()
        application_state.service = (
            await services_lib.InferenceService.create(configuration)
        )
        application_state.ready = True
        logger.info('Trip planner service is ready.')
    except Exception:  # pylint: disable=broad-except
        logger.exception('Start-up failed.')


@contextlib.asynccontextmanager
async def _lifespan(app: fastapi.FastAPI):
    logging.basicConfig(level=logging.INFO)
    application_state = state.ApplicationState()
    app.state.application_state = application_state
    start_task = asyncio.create_task(_start(application_state))
    yield
    start_task.cancel()
    if application_state.service is not None:
        await application_state.service.close()


app = fastapi.FastAPI(title='Picos de Europa trip planner', lifespan=_lifespan)
for _router in _ROUTERS:
    app.include_router(_router)
errors.register_exception_handlers(app)
