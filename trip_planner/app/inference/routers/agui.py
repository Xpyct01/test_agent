"""AG-UI endpoint: live simulation runs streamed as server-sent events."""

import typing

from ag_ui import core as agui
from ag_ui import encoder as encoder_lib
import fastapi
from fastapi import responses

from trip_planner.app.inference.routers import state

if typing.TYPE_CHECKING:
    from trip_planner.app.inference.services import agui as agui_lib

router = fastapi.APIRouter(tags=['agui'])


@router.post('/agui')
async def run_agent(
    run_input: agui.RunAgentInput,
    request: fastapi.Request,
    service: 'agui_lib.AgUiService' = fastapi.Depends(state.agui_service),
) -> responses.StreamingResponse:
    """Runs the AG-UI agent and streams its events.

    Args:
        run_input: The AG-UI `RunAgentInput`; `forwardedProps` picks the
            mode (`watch` or `play`) and the scenario.
        request: The HTTP request; its `Accept` header picks the encoding.
        service: The AG-UI service; 503 while starting.

    Returns:
        The event stream.
    """
    encoder = encoder_lib.EventEncoder(accept=request.headers.get('accept'))

    async def stream() -> typing.AsyncIterator[str]:
        async for event in service.run(run_input):
            yield encoder.encode(event)

    return responses.StreamingResponse(
        stream(), media_type=encoder.get_content_type()
    )
