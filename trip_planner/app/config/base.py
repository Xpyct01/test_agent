"""Base class of every settings section of the trip planner service."""

import pathlib

import pydantic_settings

_ENV_FILE = pathlib.Path(__file__).resolve().parents[3] / '.env'


class ConfigurationSection(pydantic_settings.BaseSettings):
    """Settings read from the environment, then from the root `.env` file."""

    model_config = pydantic_settings.SettingsConfigDict(
        env_file=_ENV_FILE, extra='ignore'
    )
