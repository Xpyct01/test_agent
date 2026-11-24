"""Settings of the OpenAI client."""

import pydantic
import pydantic_settings

from trip_planner.app.config import base


class OpenAIConfiguration(base.ConfigurationSection):
    """OpenAI settings, read from the `TRIP_OPENAI_` variables.

    Attributes:
        api_key: OpenAI API key; start-up fails without it.
        base_url: Optional OpenAI-compatible endpoint (proxy, self-hosted).
    """

    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix='TRIP_OPENAI_'
    )

    api_key: pydantic.SecretStr
    base_url: str | None = None
