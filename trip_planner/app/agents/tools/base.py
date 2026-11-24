"""Code shared by the tool concerns: fault tolerance and result format."""

import asyncio
from collections.abc import Awaitable, Callable
import logging
from typing import TypeVar

import pydantic

from trip_planner.app.core import errors
from trip_planner.app.core.schemas import tools
from trip_planner.app.ml.environment import run_context as run_context_lib

logger = logging.getLogger(__name__)

_T = TypeVar('_T')
_ENVIRONMENT = 'environment'


class BaseTools:
    """Base of every tool concern."""

    def __init__(
        self,
        run_context_provider: run_context_lib.RunContextProvider,
        max_attempts: int,
        retry_base_delay_s: float,
    ):
        """Initializes the concern.

        Args:
            run_context_provider: Gives access to the active run.
            max_attempts: Attempts of a faulty action before the failure is
                reported to the LLM.
            retry_base_delay_s: First back-off delay; doubles every retry.
        """
        self._run_context_provider = run_context_provider
        self._max_attempts = max_attempts
        self._retry_base_delay_s = retry_base_delay_s

    async def _call_with_faults(
        self, action: str, operation: Callable[[], Awaitable[_T]]
    ) -> _T | tools.ToolError:
        """Runs an environment action that may fail, retrying with back-off.

        Every failed attempt and retry is recorded in the trajectory. When
        all attempts fail, the LLM gets a retryable error it can act on
        instead of an exception that would end its turn.
        """
        context = self._run_context_provider.current()
        for attempt in range(1, self._max_attempts + 1):
            try:
                context.fault_injector.maybe_fail(action)
                return await operation()
            except errors.TransientActionError as error:
                final = attempt == self._max_attempts
                context.record(
                    'tool_failure', _ENVIRONMENT, action=action,
                    attempt=attempt, final=final, error=str(error),
                )
                if final:
                    logger.warning('%s failed %d times', action, attempt)
                    return tools.ToolError(
                        error=f'{error} Failed {attempt} attempts; you may '
                        'call the tool again.',
                        retryable=True,
                    )
                delay = self._retry_base_delay_s * 2 ** (attempt - 1)
                context.record(
                    'retry', _ENVIRONMENT, action=action,
                    next_attempt=attempt + 1, delay_s=delay,
                )
                await asyncio.sleep(delay)
        raise AssertionError('unreachable')


def to_result(model: pydantic.BaseModel) -> dict[str, object]:
    """Returns a tool result as a JSON-ready dict."""
    return model.model_dump(mode='json')
