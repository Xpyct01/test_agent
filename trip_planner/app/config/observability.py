"""Settings of the Langfuse tracing."""

import pydantic
import pydantic_settings

from trip_planner.app.config import base


class ObservabilityConfiguration(base.ConfigurationSection):
    """Tracing settings, read from the `TRIP_OBSERVABILITY_` variables.

    Attributes:
        enabled: Sends traces to Langfuse when both keys are set.
        langfuse_public_key: Langfuse project public key.
        langfuse_secret_key: Langfuse project secret key.
        langfuse_host: Langfuse server URL.
    """

    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix='TRIP_OBSERVABILITY_'
    )

    enabled: bool = True
    langfuse_public_key: str | None = None
    langfuse_secret_key: pydantic.SecretStr | None = None
    langfuse_host: str = 'http://localhost:3000'
