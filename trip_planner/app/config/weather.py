"""Settings of the weather forecast."""

import pathlib
from typing import Literal

import pydantic_settings

from trip_planner.app.config import base

_DATA_DIR = pathlib.Path(__file__).resolve().parents[2] / 'data'


class WeatherConfiguration(base.ConfigurationSection):
    """Weather settings, read from the `TRIP_WEATHER_` variables.

    Attributes:
        variant: `open_meteo` for the live forecast, `fixture` for the
            recorded forecast in `fixture_path` (offline runs, tests).
        latitude: Latitude of the forecast point (Lagos de Covadonga).
        longitude: Longitude of the forecast point.
        forecast_url: Open-Meteo forecast endpoint.
        timeout_s: Timeout of one forecast request, in seconds.
        forecast_days: Days the forecast covers, starting on the trip
            planning date.
        fixture_path: Recorded forecast used by the `fixture` variant.
    """

    model_config = pydantic_settings.SettingsConfigDict(
        env_prefix='TRIP_WEATHER_'
    )

    variant: Literal['open_meteo', 'fixture'] = 'open_meteo'
    latitude: float = 43.27
    longitude: float = -4.98
    forecast_url: str = 'https://api.open-meteo.com/v1/forecast'
    timeout_s: float = 10.0
    forecast_days: int = 7
    fixture_path: pathlib.Path = _DATA_DIR / 'weather_fixture.json'
