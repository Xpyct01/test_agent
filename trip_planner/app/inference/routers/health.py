"""Liveness and readiness probes."""

import fastapi

router = fastapi.APIRouter(prefix='/health', tags=['health'])


@router.get('/live')
async def live() -> dict[str, str]:
    """Answers 200 as long as the process serves HTTP."""
    return {'status': 'alive'}


@router.get('/ready')
async def ready(request: fastapi.Request) -> dict[str, str]:
    """Answers 200 once the runtime is built, 503 before."""
    state = request.app.state.application_state
    if not state.ready:
        raise fastapi.HTTPException(status_code=503, detail='Starting.')
    return {'status': 'ready'}
