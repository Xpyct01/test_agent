"""Langfuse tracing of every LLM, tool and graph step."""

import logging
from typing import Any

import langfuse
from langfuse import langchain as langfuse_langchain

from trip_planner.app.config import observability as observability_lib

logger = logging.getLogger(__name__)


class ObservabilityCallbacks:
    """Builds the LangChain callbacks and trace metadata of each call.

    Traces are grouped in Langfuse by session (one run) and tagged with the
    batch and the participant. Without Langfuse keys tracing is off and the
    local trajectory metrics remain the source of truth.
    """

    def __init__(
        self, observability_config: observability_lib.ObservabilityConfiguration
    ):
        """Initializes the callbacks.

        Args:
            observability_config: Tracing settings.
        """
        self._client: langfuse.Langfuse | None = None
        self._handler: langfuse_langchain.CallbackHandler | None = None
        secret = observability_config.langfuse_secret_key
        public_key = observability_config.langfuse_public_key
        if observability_config.enabled and public_key and secret:
            self._client = langfuse.Langfuse(
                public_key=public_key,
                secret_key=secret.get_secret_value(),
                host=observability_config.langfuse_host,
            )
            self._handler = langfuse_langchain.CallbackHandler(
                public_key=public_key
            )
            logger.info(
                'Langfuse tracing on: %s', observability_config.langfuse_host
            )
        else:
            logger.info('Langfuse tracing off (no keys configured).')

    def run_config(
        self, run_id: str, batch_id: str, participant_id: str
    ) -> dict[str, Any]:
        """Returns the RunnableConfig entries of one participant's call.

        Args:
            run_id: Id of the run; the Langfuse session.
            batch_id: Id of the batch; a Langfuse tag.
            participant_id: Who is calling; a Langfuse tag and user.
        """
        return {
            'callbacks': [self._handler] if self._handler else [],
            'run_name': participant_id,
            'metadata': {
                'langfuse_session_id': run_id,
                'langfuse_user_id': participant_id,
                'langfuse_tags': [batch_id, participant_id],
            },
        }

    def flush(self) -> None:
        """Sends buffered traces."""
        if self._client is not None:
            self._client.flush()

    def close(self) -> None:
        """Sends buffered traces and stops the exporter."""
        if self._client is not None:
            self._client.shutdown()
